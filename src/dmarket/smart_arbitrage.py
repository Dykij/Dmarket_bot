"""Smart Arbitrage Module - Balance-adaptive trading.

This module provides intelligent trading limits based on current balance,
implementing diversification and risk management automatically.

Key Features:
- Dynamic max item price based on balance (percentage-based, not fixed!)
- Adaptive profit requirements by balance tier
- Automatic inventory limits that scale with balance
- Integration with whitelist/blacklist
- Universal money management (works for $10 to $10,000+)

Usage:
    from src.dmarket.smart_arbitrage import SmartArbitrageEngine

    engine = SmartArbitrageEngine(api_client)
    limits = await engine.calculate_adaptive_limits()
    opportunities = await engine.find_smart_opportunities(game="csgo")
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog

from src.dmarket.money_manager import (
    DynamicLimits,
    MoneyManager,
    MoneyManagerConfig,
    calculate_universal_limits,
)

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI

logger = structlog.get_logger(__name__)


@dataclass
class SmartLimits:
    """Adaptive trading limits based on current balance.

    Note: This class is kept for backwards compatibility.
    New code should use DynamicLimits from money_manager.
    """

    max_buy_price: float  # Maximum price for single item
    min_roi: float  # Minimum profit percentage
    inventory_limit: int  # Max items in inventory
    max_same_items: int  # Max duplicates of same item
    usable_balance: float  # Balance minus reserve
    reserve: float  # Safety reserve
    diversification_factor: float  # How much of balance per item (e.g., 0.3 = 30%)
    tier: str = "small"  # Balance tier for strategy selection
    min_item_price: float = 0.10  # Minimum item price

    @classmethod
    def from_dynamic_limits(cls, limits: DynamicLimits) -> SmartLimits:
        """Convert DynamicLimits to SmartLimits for compatibility."""
        return cls(
            max_buy_price=limits.max_item_price,
            min_roi=limits.min_roi,
            inventory_limit=limits.max_inventory_items,
            max_same_items=limits.max_same_items,
            usable_balance=limits.usable_balance,
            reserve=limits.reserve,
            diversification_factor=limits.diversification_factor,
            tier=limits.tier.value,
            min_item_price=limits.min_item_price,
        )


@dataclass
class SmartOpportunity:
    """An arbitrage opportunity with smart scoring."""

    item_id: str
    title: str
    buy_price: float
    sell_price: float
    profit: float
    profit_percent: float
    game: str
    liquidity_score: float = 0.0
    smart_score: float = 0.0  # Combined score for prioritization
    created_at: datetime = field(default_factory=datetime.now)


class SmartArbitrageEngine:
    """Balance-adaptive arbitrage engine.

    Automatically adjusts trading parameters based on:
    - Current DMarket balance (percentage-based scaling)
    - Balance tier (micro/small/medium/large/whale)
    - Inventory size
    - Market conditions

    Works equally well for $45.50 or $4,550.00 balances!
    """

    def __init__(
        self,
        api_client: IDMarketAPI,
        diversification_factor: float = 0.3,
        reserve_percent: float = 0.05,
        small_balance_threshold: float = 100.0,
        money_manager_config: MoneyManagerConfig | None = None,
    ) -> None:
        """Initialize Smart Arbitrage Engine.

        Args:
            api_client: DMarket API client
            diversification_factor: Max percentage of balance per item (default 30%)
            reserve_percent: Percentage to keep as safety reserve (default 5%)
            small_balance_threshold: Below this balance, use stricter profit requirements
            money_manager_config: Optional config for money manager
        """
        self.api_client = api_client
        self.diversification_factor = diversification_factor
        self.reserve_percent = reserve_percent
        self.small_balance_threshold = small_balance_threshold

        # Initialize the universal money manager
        config = money_manager_config or MoneyManagerConfig(
            max_buy_percent=diversification_factor,
            reserve_percent=reserve_percent,
            micro_threshold=small_balance_threshold,
        )
        self.money_manager = MoneyManager(api_client, config)

        # State
        self._current_balance: float = 0.0
        self._last_balance_check: datetime | None = None
        self._is_running = False

        logger.info(
            "smart_arbitrage_initialized",
            diversification=diversification_factor,
            reserve_percent=reserve_percent,
            threshold=small_balance_threshold,
        )

    async def get_current_balance(self, force_refresh: bool = False) -> float:
        """Get current DMarket balance with caching.

        Uses MoneyManager for consistent balance parsing (DRY principle).

        Args:
            force_refresh: Force API call even if cached

        Returns:
            Current balance in USD
        """
        try:
            # Delegate to MoneyManager for consistent parsing
            balance = await self.money_manager.get_balance(force_refresh=force_refresh)
            self._current_balance = balance
            self._last_balance_check = datetime.now()
            logger.info("smart_balance_fetched", balance=self._current_balance)
            return self._current_balance
        except Exception as e:
            logger.exception("smart_balance_proxy_error", error=str(e))
            return self._current_balance  # Return last known balance

    async def calculate_adaptive_limits(self) -> SmartLimits:
        """Calculate trading limits based on current balance.

        Uses the universal MoneyManager for percentage-based calculations.
        This makes the bot work equally well for any balance size!

        Returns:
            SmartLimits with calculated parameters
        """
        # Use the money manager for universal calculations
        dynamic_limits = await self.money_manager.calculate_dynamic_limits()

        # Update internal balance tracking
        self._current_balance = dynamic_limits.total_balance
        self._last_balance_check = datetime.now()

        # Convert to SmartLimits for backwards compatibility
        limits = SmartLimits.from_dynamic_limits(dynamic_limits)

        logger.info(
            "smart_limits_calculated",
            tier=limits.tier,
            balance=dynamic_limits.total_balance,
            max_price=limits.max_buy_price,
            min_roi=limits.min_roi,
            inventory_limit=limits.inventory_limit,
        )

        return limits

    async def get_strategy_description(self) -> str:
        """Get human-readable description of current trading strategy.

        Returns:
            Strategy description based on current balance tier
        """
        limits = await self.money_manager.calculate_dynamic_limits()
        return self.money_manager.get_strategy_description(limits)

    def check_balance_safety(self) -> tuple[bool, str]:
        """Check if balance changed significantly (safety feature).

        Returns:
            Tuple of (is_safe, warning_message)
        """
        is_paused, reason = self.money_manager.is_paused()
        if is_paused:
            return False, f"⚠️ {reason}\nConfirm to continue trading."
        return True, ""

    def confirm_balance_change(self) -> None:
        """Confirm balance change and resume trading."""
        self.money_manager.resume()

    async def find_smart_opportunities(
        self,
        game: str = "csgo",
        whitelist: list[str] | None = None,
        blacklist: list[str] | None = None,
    ) -> list[SmartOpportunity]:
        """Find arbitrage opportunities within smart limits.

        Uses pagination to scan up to 500 items (5 pages x 100).
        DMarket API limit is 100 per request.

        Args:
            game: Game to scan
            whitelist: Only consider these items (optional)
            blacklist: Exclude these items (optional)

        Returns:
            List of opportunities sorted by smart score
        """
        limits = await self.calculate_adaptive_limits()

        # AUTO-CORRECTION: For micro balances (<$100), use lower ROI for faster turnover
        if self._current_balance < 100.0 and limits.min_roi > 5.0:
            original_roi = limits.min_roi
            limits.min_roi = 5.0  # Allow 5% profit for quick trades
            logger.info(
                "micro_balance_roi_adjustment",
                old_roi=original_roi,
                new_roi=limits.min_roi,
                balance=self._current_balance,
            )

        if limits.usable_balance <= 0:
            logger.warning("smart_no_balance", usable=limits.usable_balance)
            return []

        try:
            # PAGINATION: Scan multiple pages (DMarket limit = 100 per request)
            all_objects: list[dict[str, Any]] = []
            cursor = ""
            pages_to_scan = 5  # 5 pages x 100 = 500 items total

            # Note: price_from/price_to are in DOLLARS (API converts to cents)
            min_price_dollars = limits.min_item_price
            max_price_dollars = limits.max_buy_price

            for page in range(pages_to_scan):
                try:
                    # DEBUG: Log the exact API call parameters
                    logger.debug(
                        "smart_api_call",
                        game=game,
                        page=page,
                        price_from=min_price_dollars,
                        price_to=max_price_dollars,
                        cursor=cursor[:20] if cursor else "empty",
                    )

                    items = await self.api_client.get_market_items(
                        game=game,
                        limit=100,  # DMarket max limit is 100!
                        price_from=0.01,  # Start from $0.01 to see all cheap items
                        price_to=max_price_dollars,
                        cursor=cursor,  # Empty string for first page, cursor for next
                        sort="price",  # Sort by price ascending to get cheapest first
                    )

                    current_objects = items.get("objects", []) if isinstance(items, dict) else []

                    # DEBUG: Log what we received from API
                    logger.info(
                        "smart_page_received",
                        page=page,
                        items_count=len(current_objects),
                        has_cursor=bool(items.get("cursor", "")),
                        total_in_response=items.get("total", {}).get("items", 0) if isinstance(items.get("total"), dict) else items.get("total", 0),
                    )

                    if not current_objects:
                        break

                    all_objects.extend(current_objects)

                    # Get cursor for next page
                    cursor = items.get("cursor", "")
                    if not cursor:
                        break

                    # Small delay to avoid rate limiting
                    await asyncio.sleep(0.3)

                except Exception as page_err:
                    logger.warning("pagination_page_error", page=page, error=str(page_err))
                    break

            # Log total scanned items
            logger.info(
                "smart_scan_complete",
                game=game,
                total_scanned=len(all_objects),
                pages=min(page + 1, pages_to_scan),
                price_range=f"${min_price_dollars:.2f}-${max_price_dollars:.2f}",
            )

            opportunities = []
            for item in all_objects:
                opp = self._analyze_item(item, limits, whitelist, blacklist)
                if opp:
                    opportunities.append(opp)

            # Sort by smart score (highest first)
            opportunities.sort(key=lambda x: x.smart_score, reverse=True)

            logger.info(
                "smart_opportunities_found",
                game=game,
                count=len(opportunities),
                max_price=limits.max_buy_price,
            )

            return opportunities[:20]  # Return top 20

        except Exception as e:
            logger.exception("smart_scan_error", game=game, error=str(e))
            return []

    def _analyze_item(
        self,
        item: dict[str, Any],
        limits: SmartLimits,
        whitelist: list[str] | None,
        blacklist: list[str] | None,
    ) -> SmartOpportunity | None:
        """Analyze single item for smart opportunity.

        Includes Trade Lock handling with hybrid ROI requirements:
        - No lock: use min_roi (e.g., 5%)
        - Lock 1-3 days: require 12% ROI
        - Lock >3 days: require 20% ROI (only super deals)

        Args:
            item: Raw item data from API
            limits: Current smart limits
            whitelist: Allowed items
            blacklist: Blocked items

        Returns:
            SmartOpportunity if valid, None otherwise
        """
        try:
            title = item.get("title", "")

            # Check whitelist (if provided) - only in priority mode
            if whitelist:
                if not any(w.lower() in title.lower() for w in whitelist):
                    return None

            # Check blacklist
            if blacklist:
                if any(b.lower() in title.lower() for b in blacklist):
                    return None

            # Get prices (in cents) - bulletproof parsing
            price_data = item.get("price", {})
            try:
                buy_price_cents = int(float(str(price_data.get("USD", 0))))
            except (ValueError, TypeError):
                buy_price_cents = 0
            buy_price = buy_price_cents / 100.0

            # Get suggested price for profit calculation
            suggested_data = item.get("suggestedPrice", {})
            try:
                sell_price_cents = int(float(str(suggested_data.get("USD", buy_price_cents))))
            except (ValueError, TypeError):
                sell_price_cents = buy_price_cents
            sell_price = sell_price_cents / 100.0

            # Skip if price too high or too low (dynamic limits!)
            if buy_price > limits.max_buy_price:
                return None
            if buy_price < limits.min_item_price:
                return None  # Skip items below minimum (avoid dust)

            # Calculate profit (DMarket commission ~7%)
            commission = sell_price * 0.07
            profit = sell_price - buy_price - commission
            profit_percent = (profit / buy_price) * 100 if buy_price > 0 else 0

            # TRADE LOCK HANDLING (Hybrid Filter)
            # Get trade lock duration in seconds
            extra = item.get("extra", {}) or item.get("extraAttributes", {}) or {}
            trade_lock_seconds = int(extra.get("tradeLockDuration", 0) or 0)
            trade_lock_days = trade_lock_seconds / 86400

            # Dynamic ROI requirement based on trade lock
            required_roi = limits.min_roi  # Default (e.g., 5% for micro balance)

            if trade_lock_days > 0.1 and trade_lock_days <= 3:
                required_roi = max(limits.min_roi, 12.0)  # Lock 1-3 days: 12%+
            elif trade_lock_days > 3:
                required_roi = max(limits.min_roi, 20.0)  # Lock >3 days: only super deals (20%+)

            # Skip if profit too low for this trade lock duration
            if profit_percent < required_roi:
                logger.debug(
                    "item_skipped",
                    reason="low_roi_for_lock",
                    title=title[:35],
                    roi=f"{profit_percent:.1f}%",
                    required=f"{required_roi:.1f}%",
                    lock_days=f"{trade_lock_days:.1f}",
                )
                return None

            # Log found opportunity
            logger.info(
                "smart_match_found",
                title=title[:35],
                buy_price=f"${buy_price:.2f}",
                sell_price=f"${sell_price:.2f}",
                roi=f"{profit_percent:.1f}%",
                lock=f"{trade_lock_days:.0f}d" if trade_lock_days > 0 else "none",
            )

            # Calculate smart score
            # Higher profit + lower price + no lock = better score
            price_factor = 1 - (buy_price / limits.max_buy_price)  # 0-1, higher for cheaper
            profit_factor = profit_percent / 100  # Normalized profit
            lock_penalty = 0.1 if trade_lock_days > 3 else (0.05 if trade_lock_days > 0 else 0)
            smart_score = (profit_factor * 0.6) + (price_factor * 0.3) - lock_penalty

            return SmartOpportunity(
                item_id=item.get("itemId", ""),
                title=title,
                buy_price=buy_price,
                sell_price=sell_price,
                profit=round(profit, 2),
                profit_percent=round(profit_percent, 1),
                game=item.get("gameId", "csgo"),
                smart_score=round(smart_score * 100, 1),
            )

        except Exception as e:
            logger.debug("smart_item_analysis_error", error=str(e))
            return None

    async def _execute_auto_buy_real(
        self,
        opportunities: list[SmartOpportunity],
    ) -> None:
        """Execute auto-buy for opportunities (real mode)."""
        for opp in opportunities[:3]:
            # Skip expensive items (>30% of balance)
            if opp.buy_price > self._current_balance * 0.3:
                logger.info(
                    "auto_buy_skipped_expensive",
                    item=opp.title[:30],
                    price=opp.buy_price,
                )
                continue

            logger.info(
                "auto_buy_executing",
                item=opp.title[:30],
                price=f"${opp.buy_price:.2f}",
                profit=f"{opp.profit_percent:.1f}%",
            )

            try:
                await self.api_client.buy_item(opp.item_id, int(opp.buy_price * 100))
                logger.info("auto_buy_success", item=opp.title[:30])
                self._current_balance -= opp.buy_price
                await asyncio.sleep(2)  # Rate limit between purchases
            except Exception as buy_err:
                logger.exception(
                    "auto_buy_failed",
                    item=opp.title[:30],
                    error=str(buy_err),
                )

    async def _execute_auto_buy_dry_run(
        self,
        opportunities: list[SmartOpportunity],
    ) -> None:
        """Log auto-buy opportunities (dry-run mode)."""
        for opp in opportunities[:3]:
            logger.info(
                "auto_buy_dry_run",
                item=opp.title[:30],
                price=f"${opp.buy_price:.2f}",
                profit=f"{opp.profit_percent:.1f}%",
            )

    async def _process_auto_buy(
        self,
        opportunities: list[SmartOpportunity],
        auto_buy: bool,
    ) -> None:
        """Process auto-buy for opportunities."""
        if not auto_buy or not opportunities:
            return

        dry_run = getattr(self.api_client, "dry_run", True)
        if dry_run:
            await self._execute_auto_buy_dry_run(opportunities)
        else:
            await self._execute_auto_buy_real(opportunities)

    async def start_smart_mode(
        self,
        games: list[str] | None = None,
        callback: Any = None,
        auto_buy: bool = True,
    ) -> None:
        """Start Smart Arbitrage scanning mode with auto-buy.

        Args:
            games: Games to scan (default: all supported)
            callback: Function to call with opportunities
            auto_buy: Enable automatic purchasing (default: True)
        """
        if self._is_running:
            logger.warning("smart_already_running")
            return

        self._is_running = True
        games = games or ["csgo", "dota2", "rust", "tf2"]

        logger.info("smart_mode_started", games=games, auto_buy=auto_buy)

        try:
            while self._is_running:
                for game in games:
                    if not self._is_running:
                        break

                    opportunities = await self.find_smart_opportunities(game=game)

                    # Notify via callback if provided
                    if opportunities and callback:
                        await callback(opportunities)

                    # Process auto-buy (refactored to reduce nesting)
                    await self._process_auto_buy(opportunities, auto_buy)

                    # Small delay between games
                    await asyncio.sleep(3)

                # Wait before next full scan
                # Adaptive: faster when balance is low (more urgent for turnover)
                balance = await self.get_current_balance()
                scan_interval = 30 if balance < 50 else 60
                logger.info(
                    "smart_scan_cycle_complete",
                    balance=f"${balance:.2f}",
                    next_scan_in=f"{scan_interval}s",
                )
                await asyncio.sleep(scan_interval)

        except asyncio.CancelledError:
            logger.info("smart_mode_cancelled")
        except Exception as e:
            logger.exception("smart_mode_error", error=str(e))
        finally:
            self._is_running = False
            logger.info("smart_mode_stopped")

    def stop_smart_mode(self) -> None:
        """Stop Smart Arbitrage scanning mode."""
        self._is_running = False
        logger.info("smart_mode_stop_requested")

    @property
    def is_running(self) -> bool:
        """Check if smart mode is running."""
        return self._is_running


# Standalone helper function for use without full engine
def get_smart_limits(balance: float) -> dict[str, Any]:
    """Calculate smart limits from balance (standalone function).

    This uses the universal money management system, so it works
    equally well for $10, $100, $1000, or $10000 balances.

    Args:
        balance: Current balance in USD

    Returns:
        Dict with max_buy_price, min_roi, inventory_limit, etc.
    """
    return calculate_universal_limits(balance)
