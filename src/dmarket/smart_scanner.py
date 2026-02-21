"""Smart Scanner Module with AI Price Prediction and Trade Lock Analysis.

This module implements an optimized market scanner that:
1. Uses cursor-based pagination for efficient API traversal
2. Filters items by trade lock duration (lockStatus)
3. Applies local delta filtering to skip already-seen items
4. Uses AI price prediction to validate arbitrage opportunities
5. Supports both DMarket and Waxpeer cross-platform arbitrage

Key Features:
- Smart filtering: Skip items with trade lock > configurable days
- AI validation: Use ML model to predict fair price
- Duplicate detection: Hash-based deduplication
- Silent mode: Configurable logging verbosity
- Cross-platform: Compare DMarket prices with Waxpeer

Usage:
    ```python
    from src.dmarket.smart_scanner import SmartScanner
    from src.dmarket.dmarket_api import DMarketAPI
    from src.ai import PricePredictor

    api = DMarketAPI(public_key, secret_key)
    predictor = PricePredictor()

    scanner = SmartScanner(api, predictor)
    await scanner.scan()  # Start continuous scanning
    ```

Configuration via environment variables:
- SMART_SCANNER_MAX_LOCK_DAYS: Maximum trade lock days (default: 0 for instant)
- SMART_SCANNER_MIN_PROFIT_PERCENT: Minimum profit % to trigger buy (default: 5.0)
- SMART_SCANNER_PRICE_MAX_CENTS: Maximum item price in cents (default: 4550)
- SMART_SCANNER_SILENT_MODE: Reduce logging noise (default: true)
- SMART_SCANNER_ENABLE_AI: Enable AI price validation (default: true)
- SMART_SCANNER_ALLOW_TRADE_BAN: Allow items with trade ban (default: false)
"""

import asyncio
import hashlib
import logging
import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.ai.price_predictor import PricePredictor
    from src.dmarket.dmarket_api import DMarketAPI
    from src.waxpeer.waxpeer_api import WaxpeerAPI

logger = logging.getLogger(__name__)

# Default configuration
DEFAULT_MAX_LOCK_DAYS = 0  # By default, only instant tradeable items
DEFAULT_MIN_PROFIT_PERCENT = 5.0  # Minimum 5% profit
DEFAULT_PRICE_MAX_CENTS = 4550  # $45.50 max price
DEFAULT_SCAN_LIMIT = 100  # Items per API request
DEFAULT_SCAN_DELAY = 0.5  # Seconds between scans
DEFAULT_SILENT_MODE = True  # Reduce logging


@dataclass
class SmartScannerConfig:
    """Configuration for Smart Scanner.

    Attributes:
        max_lock_days: Maximum trade lock days to consider (0 = instant only)
        min_profit_percent: Minimum profit percentage to trigger action
        price_max_cents: Maximum item price in cents
        scan_limit: Number of items per API request
        scan_delay: Delay between scan iterations in seconds
        silent_mode: If True, suppress non-essential logging
        enable_ai: If True, use AI price prediction
        allow_trade_ban: If True, allow items with trade ban (requires AI analysis)
        dry_run: If True, don't execute actual purchases
    """

    max_lock_days: int = DEFAULT_MAX_LOCK_DAYS
    min_profit_percent: float = DEFAULT_MIN_PROFIT_PERCENT
    price_max_cents: int = DEFAULT_PRICE_MAX_CENTS
    scan_limit: int = DEFAULT_SCAN_LIMIT
    scan_delay: float = DEFAULT_SCAN_DELAY
    silent_mode: bool = DEFAULT_SILENT_MODE
    enable_ai: bool = True
    allow_trade_ban: bool = False
    dry_run: bool = True
    game_id: str = "a8db"  # CS:GO/CS2 by default

    @classmethod
    def from_env(cls) -> "SmartScannerConfig":
        """Create configuration from environment variables."""
        return cls(
            max_lock_days=int(
                os.getenv("SMART_SCANNER_MAX_LOCK_DAYS", str(DEFAULT_MAX_LOCK_DAYS))
            ),
            min_profit_percent=float(
                os.getenv(
                    "SMART_SCANNER_MIN_PROFIT_PERCENT", str(DEFAULT_MIN_PROFIT_PERCENT)
                )
            ),
            price_max_cents=int(
                os.getenv("SMART_SCANNER_PRICE_MAX_CENTS", str(DEFAULT_PRICE_MAX_CENTS))
            ),
            silent_mode=os.getenv("SMART_SCANNER_SILENT_MODE", "true").lower()
            == "true",
            enable_ai=os.getenv("SMART_SCANNER_ENABLE_AI", "true").lower() == "true",
            allow_trade_ban=os.getenv("SMART_SCANNER_ALLOW_TRADE_BAN", "false").lower()
            == "true",
            dry_run=os.getenv("DRY_RUN", "true").lower() == "true",
            game_id=os.getenv("SMART_SCANNER_GAME_ID", "a8db"),
        )


@dataclass
class ScanResult:
    """Result of analyzing a single item.

    Attributes:
        item_id: DMarket item ID
        title: Item name
        market_price: Current market price in USD
        ai_fair_price: AI-predicted fair price (if available)
        waxpeer_price: Waxpeer price (if cross-platform enabled)
        profit_usd: Expected profit in USD
        profit_percent: Expected profit percentage
        lock_days: Trade lock duration in days
        should_buy: Whether scanner recommends purchase
        reason: Explanation for the decision
    """

    item_id: str
    title: str
    market_price: Decimal
    ai_fair_price: Decimal | None = None
    waxpeer_price: Decimal | None = None
    profit_usd: Decimal = Decimal(0)
    profit_percent: float = 0.0
    lock_days: int = 0
    should_buy: bool = False
    reason: str = ""
    offer_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "item_id": self.item_id,
            "title": self.title,
            "market_price": float(self.market_price),
            "ai_fair_price": float(self.ai_fair_price) if self.ai_fair_price else None,
            "waxpeer_price": float(self.waxpeer_price) if self.waxpeer_price else None,
            "profit_usd": float(self.profit_usd),
            "profit_percent": self.profit_percent,
            "lock_days": self.lock_days,
            "should_buy": self.should_buy,
            "reason": self.reason,
        }


@dataclass
class LocalDeltaFilter:
    """Filter to track and skip already-seen items.

    Uses MD5 hashing of item_id + price to detect changes.
    Items are only re-analyzed if their price changes.

    Attributes:
        seen_hashes: Set of already processed item hashes
        max_size: Maximum number of hashes to keep (prevents memory leak)
    """

    seen_hashes: set[str] = field(default_factory=set)
    max_size: int = 100000  # Max items to track

    def is_new(self, item: dict[str, Any]) -> bool:
        """Check if item is new or has changed since last seen.

        Args:
            item: Item data from DMarket API

        Returns:
            True if item is new or price changed, False otherwise
        """
        item_id = item.get("itemId", "")
        price = item.get("price", {})

        # Handle both price formats
        if isinstance(price, dict):
            price_val = price.get("USD", 0) or price.get("amount", 0)
        else:
            price_val = price

        # Create unique hash for item + price
        # Using sha256 for security best practices (non-cryptographic use but safer default)
        hash_input = f"{item_id}_{price_val}".encode()
        item_hash = hashlib.sha256(hash_input).hexdigest()[
            :16
        ]  # Truncate for efficiency

        # Check if already seen
        if item_hash in self.seen_hashes:
            return False

        # Prevent memory leak - remove old hashes if too many
        if len(self.seen_hashes) >= self.max_size:
            # Remove ~20% of oldest entries (simple approach: just clear some)
            to_remove = list(self.seen_hashes)[: int(self.max_size * 0.2)]
            for h in to_remove:
                self.seen_hashes.discard(h)

        # Add new hash
        self.seen_hashes.add(item_hash)
        return True

    def clear(self) -> None:
        """Clear all seen hashes."""
        self.seen_hashes.clear()


class SmartScanner:
    """Smart Scanner with AI Price Prediction and Trade Lock Analysis.

    This scanner implements an optimized market scanning strategy:
    1. Fetches items using cursor-based pagination
    2. Filters by trade lock duration
    3. Skips already-processed items using delta filter
    4. Validates prices with AI prediction (optional, requires trained model)
    5. Optionally compares with Waxpeer for cross-platform arbitrage
       (requires waxpeer_api parameter to be provided)

    Note:
        - AI prediction requires a trained PricePredictor model
        - Waxpeer integration is optional and only active when waxpeer_api is provided
        - Trade lock analysis is enabled via allow_trade_ban config option

    Example:
        ```python
        scanner = SmartScanner(api, predictor, config)

        # Single scan
        results = await scanner.scan_once()
        for result in results:
            if result.should_buy:
                print(f"Buy: {result.title} for ${result.market_price}")

        # Continuous scanning (with auto-buy)
        await scanner.run_continuous()
        ```
    """

    def __init__(
        self,
        api: "DMarketAPI",
        predictor: "PricePredictor | None" = None,
        waxpeer_api: "WaxpeerAPI | None" = None,
        config: SmartScannerConfig | None = None,
    ) -> None:
        """Initialize the Smart Scanner.

        Args:
            api: DMarket API client
            predictor: AI Price Predictor (optional, enables AI validation)
            waxpeer_api: Waxpeer API client (optional, enables cross-platform)
            config: Scanner configuration (uses defaults if not provided)
        """
        self.api = api
        self.predictor = predictor
        self.waxpeer_api = waxpeer_api
        self.config = config or SmartScannerConfig.from_env()

        # Local delta filter for duplicate detection
        self.delta_filter = LocalDeltaFilter()

        # Statistics
        self.stats = {
            "scans_completed": 0,
            "items_analyzed": 0,
            "items_skipped_lock": 0,
            "items_skipped_duplicate": 0,
            "items_skipped_ai": 0,
            "opportunities_found": 0,
            "purchases_made": 0,
        }

        # Running flag for continuous mode
        self._running = False
        self._current_cursor = ""

        logger.info(
            "smart_scanner_initialized",
            config={
                "max_lock_days": self.config.max_lock_days,
                "min_profit_percent": self.config.min_profit_percent,
                "price_max_cents": self.config.price_max_cents,
                "enable_ai": self.config.enable_ai,
                "allow_trade_ban": self.config.allow_trade_ban,
                "dry_run": self.config.dry_run,
            },
        )

    async def scan_once(self, cursor: str = "") -> list[ScanResult]:
        """Perform a single scan iteration.

        Args:
            cursor: Pagination cursor (empty for first page)

        Returns:
            List of ScanResult objects for analyzed items
        """
        results: list[ScanResult] = []

        try:
            # Build API request parameters
            params = {
                "gameId": self.config.game_id,
                "limit": self.config.scan_limit,
                "currency": "USD",
                "sort": "price",  # Sort by price (cheapest first)
            }

            # Use cursor for pagination if provided
            if cursor:
                params["cursor"] = cursor

            # Add price filter based on balance
            if self.config.price_max_cents > 0:
                params["priceTo"] = str(self.config.price_max_cents)

            # Fetch items from DMarket
            response = await self.api.get_market_items(**params)
            items = response.get("objects", [])

            # Update cursor for next iteration
            self._current_cursor = response.get("cursor", "")

            if not items:
                if not self.config.silent_mode:
                    logger.info("no_items_found")
                return results

            # Process each item
            for item in items:
                result = await self._analyze_item(item)
                if result:
                    results.append(result)

                    # Execute buy if recommended
                    if result.should_buy and not self.config.dry_run:
                        await self._execute_buy(result)

            self.stats["scans_completed"] += 1
            self.stats["items_analyzed"] += len(items)

            if results and not self.config.silent_mode:
                opportunities = [r for r in results if r.should_buy]
                if opportunities:
                    logger.info(
                        "opportunities_found",
                        count=len(opportunities),
                        best_profit=max(r.profit_percent for r in opportunities),
                    )

            return results

        except Exception as e:
            logger.exception("scan_failed", error=str(e))
            return results

    async def _analyze_item(self, item: dict[str, Any]) -> ScanResult | None:
        """Analyze a single item for arbitrage potential.

        Args:
            item: Item data from DMarket API

        Returns:
            ScanResult or None if item should be skipped
        """
        try:
            item_id = item.get("itemId", "")
            title = item.get("title", "")
            extra = item.get("extra", {}) or {}

            # Get price (convert from cents to USD)
            price_data = item.get("price", {})
            if isinstance(price_data, dict):
                price_cents = int(
                    price_data.get("USD", 0) or price_data.get("amount", 0)
                )
            else:
                price_cents = int(price_data)

            market_price = Decimal(str(price_cents)) / Decimal(100)

            if market_price <= 0:
                return None

            # Get trade lock duration
            lock_seconds = extra.get("tradeLockDuration", 0) or extra.get(
                "lockStatus", 0
            )
            lock_days = lock_seconds // 86400 if lock_seconds > 0 else 0

            # FILTER 1: Check trade lock
            if not self.config.allow_trade_ban:
                # Only allow instant-tradeable items
                if lock_days > self.config.max_lock_days:
                    self.stats["items_skipped_lock"] += 1
                    if not self.config.silent_mode:
                        logger.debug(
                            "item_skipped_lock",
                            title=title,
                            lock_days=lock_days,
                        )
                    return None
            # Trade ban allowed, but must pass AI check
            elif lock_days > 0 and not self.config.enable_ai:
                # Can't analyze locked items without AI
                self.stats["items_skipped_lock"] += 1
                return None

            # FILTER 2: Check local delta (skip duplicates)
            if not self.delta_filter.is_new(item):
                self.stats["items_skipped_duplicate"] += 1
                return None

            # Create initial result
            result = ScanResult(
                item_id=item_id,
                title=title,
                market_price=market_price,
                lock_days=lock_days,
                offer_id=extra.get("offerId", ""),
            )

            # FILTER 3: AI Price Prediction (if enabled)
            if self.config.enable_ai and self.predictor:
                float_value = extra.get("floatValue") or extra.get("float", 0.5)

                # For locked items, AI must confirm profitability
                ai_price = self.predictor.predict_with_guard(
                    item_name=title,
                    market_price=float(market_price),
                    current_float=float_value,
                )

                if ai_price:
                    result.ai_fair_price = Decimal(str(ai_price))

                    # Calculate profit from AI prediction
                    ai_profit = result.ai_fair_price - market_price
                    ai_profit_percent = float(ai_profit / market_price * 100)

                    if ai_profit_percent >= self.config.min_profit_percent:
                        result.profit_usd = ai_profit
                        result.profit_percent = ai_profit_percent
                        result.should_buy = True
                        result.reason = f"AI: +{ai_profit_percent:.1f}%"

                        self.stats["opportunities_found"] += 1
                    else:
                        result.reason = f"AI profit too low: {ai_profit_percent:.1f}%"
                else:
                    # AI couldn't validate or rejected the item
                    self.stats["items_skipped_ai"] += 1

                    # For locked items, we MUST have AI approval
                    if lock_days > 0:
                        result.reason = "AI rejected (locked item requires validation)"
                        return result
                    result.reason = "AI: no prediction available"

            # FILTER 4: Waxpeer Cross-Platform (if enabled)
            if self.waxpeer_api:
                wax_price = await self._get_waxpeer_price(title)
                if wax_price:
                    result.waxpeer_price = wax_price

                    # Calculate cross-platform profit (with 6% Waxpeer fee)
                    net_wax_price = wax_price * Decimal("0.94")
                    cross_profit = net_wax_price - market_price
                    cross_profit_percent = float(cross_profit / market_price * 100)

                    # Update result if Waxpeer profit is better than AI
                    if cross_profit_percent >= self.config.min_profit_percent:
                        if cross_profit > result.profit_usd:
                            result.profit_usd = cross_profit
                            result.profit_percent = cross_profit_percent
                            result.should_buy = True
                            result.reason = f"Waxpeer: +{cross_profit_percent:.1f}%"

            return result

        except Exception as e:
            logger.exception(
                "item_analysis_failed",
                item_id=item.get("itemId", ""),
                error=str(e),
            )
            return None

    async def _get_waxpeer_price(self, item_name: str) -> Decimal | None:
        """Get item price from Waxpeer.

        Args:
            item_name: Item title

        Returns:
            Price in USD or None if not found
        """
        if not self.waxpeer_api:
            return None

        try:
            price_info = await self.waxpeer_api.get_item_price_info(item_name)
            if price_info:
                return price_info.price_usd
            return None
        except Exception as e:
            logger.debug("waxpeer_price_failed", item=item_name, error=str(e))
            return None

    async def _execute_buy(self, result: ScanResult) -> bool:
        """Execute a buy order for the analyzed item.

        Args:
            result: ScanResult with buy recommendation

        Returns:
            True if purchase was successful
        """
        if self.config.dry_run:
            logger.info(
                "dry_run_buy",
                title=result.title,
                price=float(result.market_price),
                profit_percent=result.profit_percent,
                reason=result.reason,
            )
            return True

        try:
            # Build buy request
            buy_data = await self.api.buy_offers(
                [
                    {
                        "offerId": result.offer_id or result.item_id,
                        "price": {
                            "amount": str(int(result.market_price * 100)),
                            "currency": "USD",
                        },
                        "type": "dmarket",
                    }
                ]
            )

            success = (
                buy_data.get("success", False)
                or buy_data.get("status") == "success"
                or "orderId" in buy_data
            )

            if success:
                self.stats["purchases_made"] += 1
                logger.info(
                    "purchase_executed",
                    title=result.title,
                    price=float(result.market_price),
                    profit_percent=result.profit_percent,
                )

            return success

        except Exception as e:
            logger.exception("purchase_failed", title=result.title, error=str(e))
            return False

    async def run_continuous(self, max_iterations: int | None = None) -> None:
        """Run continuous scanning loop.

        Args:
            max_iterations: Maximum number of scan iterations (None = infinite)
        """
        self._running = True
        iterations = 0

        logger.info(
            "continuous_scanning_started",
            max_iterations=max_iterations,
        )

        try:
            while self._running:
                if max_iterations and iterations >= max_iterations:
                    break

                # Perform scan
                cursor = self._current_cursor
                await self.scan_once(cursor=cursor)

                # Wait before next iteration
                await asyncio.sleep(self.config.scan_delay)

                iterations += 1

                # Reset cursor if empty (start over)
                if not self._current_cursor:
                    if not self.config.silent_mode:
                        logger.info(
                            "cursor_reset",
                            items_analyzed=self.stats["items_analyzed"],
                            opportunities=self.stats["opportunities_found"],
                        )

        except asyncio.CancelledError:
            logger.info("scanning_cancelled")
        except Exception as e:
            logger.exception("scanning_error", error=str(e))
        finally:
            self._running = False
            logger.info(
                "continuous_scanning_stopped",
                iterations=iterations,
                stats=self.stats,
            )

    def stop(self) -> None:
        """Stop continuous scanning."""
        self._running = False

    def get_stats(self) -> dict[str, Any]:
        """Get scanner statistics.

        Returns:
            Dictionary with current statistics
        """
        return {
            **self.stats,
            "delta_filter_size": len(self.delta_filter.seen_hashes),
            "current_cursor": bool(self._current_cursor),
            "is_running": self._running,
        }

    def reset_stats(self) -> None:
        """Reset all statistics."""
        for key in self.stats:
            self.stats[key] = 0
        self.delta_filter.clear()
        self._current_cursor = ""


async def analyze_trade_ban_item(
    api: "DMarketAPI",
    predictor: "PricePredictor",
    waxpeer_api: "WaxpeerAPI | None",
    item: dict[str, Any],
    min_profit_percent: float = 15.0,
) -> dict[str, Any]:
    """Analyze an item with trade ban to determine if it's worth buying.

    This function provides detailed analysis for items with trade lock:
    1. AI price prediction for DMarket resale
    2. Waxpeer price comparison for cross-platform arbitrage
    3. Combined recommendation based on multiple factors

    Args:
        api: DMarket API client
        predictor: AI Price Predictor
        waxpeer_api: Waxpeer API client (optional)
        item: Item data from DMarket
        min_profit_percent: Minimum profit % to recommend (higher for locked items)

    Returns:
        Analysis result with recommendation:
        {
            "can_resell_profit": bool,
            "dmarket_analysis": {...},
            "waxpeer_analysis": {...},
            "recommendation": "buy" | "skip",
            "reason": str
        }
    """
    title = item.get("title", "")
    extra = item.get("extra", {}) or {}

    # Get market price
    price_data = item.get("price", {})
    if isinstance(price_data, dict):
        price_cents = int(price_data.get("USD", 0) or price_data.get("amount", 0))
    else:
        price_cents = int(price_data)

    market_price = float(price_cents) / 100
    float_value = extra.get("floatValue") or extra.get("float", 0.5)
    lock_days = (
        extra.get("tradeLockDuration", 0) or extra.get("lockStatus", 0)
    ) // 86400

    result: dict[str, Any] = {
        "item_title": title,
        "market_price": market_price,
        "lock_days": lock_days,
        "can_resell_profit": False,
        "dmarket_analysis": None,
        "waxpeer_analysis": None,
        "recommendation": "skip",
        "reason": "",
    }

    # 1. AI Analysis for DMarket
    ai_price = predictor.predict_with_guard(
        item_name=title,
        market_price=market_price,
        current_float=float_value,
    )

    if ai_price:
        ai_profit = ai_price - market_price
        ai_profit_percent = (ai_profit / market_price) * 100

        result["dmarket_analysis"] = {
            "ai_fair_price": ai_price,
            "profit_usd": ai_profit,
            "profit_percent": ai_profit_percent,
            "is_profitable": ai_profit_percent >= min_profit_percent,
        }

        if ai_profit_percent >= min_profit_percent:
            result["can_resell_profit"] = True
            result["recommendation"] = "buy"
            result["reason"] = (
                f"AI предсказывает профит +{ai_profit_percent:.1f}% на DMarket"
            )

    # 2. Waxpeer Analysis (if available)
    if waxpeer_api:
        try:
            wax_info = await waxpeer_api.get_item_price_info(title)
            if wax_info:
                wax_price = float(wax_info.price_usd)
                # Account for 6% Waxpeer commission
                net_wax_price = wax_price * 0.94
                wax_profit = net_wax_price - market_price
                wax_profit_percent = (wax_profit / market_price) * 100

                result["waxpeer_analysis"] = {
                    "waxpeer_price": wax_price,
                    "net_after_fee": net_wax_price,
                    "profit_usd": wax_profit,
                    "profit_percent": wax_profit_percent,
                    "liquidity": wax_info.count,
                    "is_profitable": wax_profit_percent >= min_profit_percent,
                }

                # Update recommendation if Waxpeer is more profitable
                if wax_profit_percent >= min_profit_percent:
                    result["can_resell_profit"] = True

                    if (
                        not result["dmarket_analysis"]
                        or wax_profit_percent
                        > result["dmarket_analysis"]["profit_percent"]
                    ):
                        result["recommendation"] = "buy"
                        result["reason"] = (
                            f"Можно продать на Waxpeer с профитом +{wax_profit_percent:.1f}%"
                        )

        except Exception as e:
            logger.debug("waxpeer_analysis_failed", error=str(e))

    # 3. Final recommendation
    if not result["can_resell_profit"]:
        result["recommendation"] = "skip"
        result["reason"] = (
            f"Недостаточный профит. "
            f"Требуется минимум {min_profit_percent:.0f}% для предметов с локом {lock_days} дн."
        )

    return result
