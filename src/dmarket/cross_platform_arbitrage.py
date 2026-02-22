"""Cross-platform arbitrage module for DMarket + Waxpeer.

This module implements advanced arbitrage strategies:
1. Full market scanning (not just "best deals")
2. Balance-aware purchasing (only items within budget)
3. Trade Lock analysis for investment opportunities
4. Liquidity checks to avoid illiquid items
5. Cross-platform price comparison (DMarket → Waxpeer)

Based on analysis from January 2026.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI
    from src.waxpeer.waxpeer_api import WaxpeerAPI

logger = structlog.get_logger(__name__)


# ============================================================================
# Constants and Configuration
# ============================================================================

# Waxpeer commission (6%)
WAXPEER_COMMISSION = Decimal("0.06")
WAXPEER_MULTIPLIER = Decimal("0.94")  # 1 - 0.06

# DMarket commission (5% default)
DMARKET_COMMISSION = Decimal("0.05")
DMARKET_MULTIPLIER = Decimal("0.95")

# CS2 Game ID on DMarket
CS2_GAME_ID = "a8db99ca-dc45-4c0e-9989-11ba71ed97a2"

# Default thresholds
DEFAULT_MIN_PROFIT_USD = Decimal("0.30")  # Minimum $0.30 profit
DEFAULT_MIN_ROI_PERCENT = Decimal("5.0")  # Minimum 5% ROI for instant arb
DEFAULT_LOCK_ROI_PERCENT = Decimal("15.0")  # Minimum 15% ROI for locked items
DEFAULT_MAX_LOCK_DAYS = 8  # Maximum trade lock days to consider
DEFAULT_MIN_LIQUIDITY = 5  # Minimum daily sales on Waxpeer


class ArbitrageDecision(StrEnum):
    """Decision types for arbitrage opportunities."""

    BUY_INSTANT = "buy_instant"  # No lock, good profit - buy immediately
    BUY_AND_HOLD = "buy_and_hold"  # Has lock, high profit - buy and wait
    SKIP = "skip"  # Not profitable or too risky
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"  # Item sells too slowly


class ItemCategory(StrEnum):
    """Item categories for whitelist/blacklist filtering."""

    CASE = "Case"
    KEY = "Key"
    WEAPON = "Weapon"
    KNIFE = "Knife"
    GLOVES = "Gloves"
    AGENT = "Agent"
    MUSIC_KIT = "Music Kit"
    PATCH = "Patch"
    STICKER = "Sticker"
    GRAFFITI = "Graffiti"
    SOUVENIR = "Souvenir Package"
    CONTAlgoNER = "ContAlgoner"


# Allowed categories for auto-buy (high liquidity)
ALLOWED_CATEGORIES = {
    ItemCategory.CASE,
    ItemCategory.KEY,
    ItemCategory.WEAPON,
    ItemCategory.KNIFE,
    ItemCategory.GLOVES,
    ItemCategory.AGENT,
    ItemCategory.MUSIC_KIT,
    ItemCategory.PATCH,
}

# Blacklisted categories (low liquidity or unstable prices)
BLACKLISTED_CATEGORIES = {
    ItemCategory.GRAFFITI,
    ItemCategory.SOUVENIR,
}

# Blacklisted keywords in item names
BLACKLISTED_KEYWORDS = frozenset(
    {
        "graffiti",
        "souvenir",
        "sealed graffiti",
    }
)


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class ArbitrageOpportunity:
    """Represents an arbitrage opportunity between DMarket and Waxpeer."""

    item_id: str
    title: str
    dmarket_price: Decimal
    waxpeer_price: Decimal
    net_profit: Decimal
    roi_percent: Decimal
    decision: ArbitrageDecision
    lock_days: int = 0
    liquidity_score: int = 0
    category: str = ""
    offer_id: str = ""

    @property
    def is_profitable(self) -> bool:
        """Check if opportunity is profitable."""
        return self.decision in {
            ArbitrageDecision.BUY_INSTANT,
            ArbitrageDecision.BUY_AND_HOLD,
        }

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "item_id": self.item_id,
            "title": self.title,
            "dmarket_price": float(self.dmarket_price),
            "waxpeer_price": float(self.waxpeer_price),
            "net_profit": float(self.net_profit),
            "roi_percent": float(self.roi_percent),
            "decision": self.decision.value,
            "lock_days": self.lock_days,
            "liquidity_score": self.liquidity_score,
            "category": self.category,
        }


@dataclass
class ScanConfig:
    """Configuration for cross-platform scanning."""

    min_profit_usd: Decimal = DEFAULT_MIN_PROFIT_USD
    min_roi_instant: Decimal = DEFAULT_MIN_ROI_PERCENT
    min_roi_locked: Decimal = DEFAULT_LOCK_ROI_PERCENT
    max_lock_days: int = DEFAULT_MAX_LOCK_DAYS
    min_liquidity: int = DEFAULT_MIN_LIQUIDITY
    use_balance_limit: bool = True
    include_locked: bool = True
    allowed_categories: set[ItemCategory] = field(
        default_factory=ALLOWED_CATEGORIES.copy
    )
    dry_run: bool = True


# ============================================================================
# MAlgon Scanner Class
# ============================================================================


class CrossPlatformArbitrageScanner:
    """Scanner for cross-platform arbitrage between DMarket and Waxpeer.

    This scanner implements the full market analysis strategy:
    1. Gets user balance from DMarket
    2. Scans ALL market items (not just "best deals")
    3. Compares prices with Waxpeer in real-time
    4. Calculates net profit with commission handling
    5. Makes buy/skip decisions based on ROI and liquidity

    Example:
        ```python
        scanner = CrossPlatformArbitrageScanner(dmarket_api, waxpeer_api)
        opportunities = await scanner.scan_full_market()
        for opp in opportunities:
            if opp.is_profitable:
                print(f"Found: {opp.title} - Profit: ${opp.net_profit}")
        ```
    """

    def __init__(
        self,
        dmarket_api: "DMarketAPI",
        waxpeer_api: "WaxpeerAPI",
        config: ScanConfig | None = None,
    ) -> None:
        """Initialize the cross-platform scanner.

        Args:
            dmarket_api: DMarket API client instance
            waxpeer_api: Waxpeer API client instance
            config: Scanner configuration (uses defaults if not provided)
        """
        self.dmarket = dmarket_api
        self.waxpeer = waxpeer_api
        self.config = config or ScanConfig()

        # Cache for Waxpeer prices to reduce API calls
        self._waxpeer_cache: dict[str, tuple[Decimal, int]] = {}
        self._cache_ttl = 60  # 1 minute cache

        logger.info(
            "cross_platform_scanner_initialized",
            dry_run=self.config.dry_run,
            use_balance_limit=self.config.use_balance_limit,
            include_locked=self.config.include_locked,
        )

    async def get_avAlgolable_balance(self) -> Decimal:
        """Get avAlgolable balance from DMarket.

        Returns:
            Balance in USD as Decimal
        """
        try:
            balance_data = await self.dmarket.get_balance()
            # DMarket API returns 'balance' field in dollars directly
            balance_usd = balance_data.get("balance", 0)
            return Decimal(str(balance_usd))
        except Exception as e:
            logger.exception("failed_to_get_balance", error=str(e))
            return Decimal(0)

    async def scan_full_market(
        self,
        game_id: str = CS2_GAME_ID,
        limit: int = 100,
        offset: int = 0,
    ) -> list[ArbitrageOpportunity]:
        """Scan the full DMarket for arbitrage opportunities.

        This method:
        1. Gets current balance (if use_balance_limit is True)
        2. Fetches items sorted by price (cheapest first)
        3. Compares each item with Waxpeer prices
        4. Returns list of profitable opportunities

        Args:
            game_id: Game ID to scan (default: CS2)
            limit: Maximum items per request (max 100)
            offset: Pagination offset

        Returns:
            List of ArbitrageOpportunity objects
        """
        opportunities: list[ArbitrageOpportunity] = []

        # Step 1: Get balance if needed
        balance = Decimal(999999)  # No limit by default
        if self.config.use_balance_limit:
            balance = await self.get_avAlgolable_balance()
            if balance <= 0:
                logger.warning("no_balance_avAlgolable")
                return []

        logger.info(
            "starting_full_market_scan",
            balance=float(balance),
            limit=limit,
            include_locked=self.config.include_locked,
        )

        # Step 2: Fetch items from DMarket (sorted by price, cheapest first)
        items = await self._fetch_market_items(game_id, balance, limit, offset)

        if not items:
            logger.info("no_items_found")
            return []

        # Step 3: Analyze each item
        for item in items:
            opportunity = await self._analyze_item(item)
            if opportunity and opportunity.is_profitable:
                opportunities.append(opportunity)

        # Sort by ROI (best first)
        opportunities.sort(key=lambda x: x.roi_percent, reverse=True)

        logger.info(
            "scan_completed",
            total_items=len(items),
            profitable=len(opportunities),
        )

        return opportunities

    async def _fetch_market_items(
        self,
        game_id: str,
        max_price: Decimal,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        """Fetch market items from DMarket.

        Key changes from default behavior:
        - Uses orderBy=price, orderDir=asc (cheapest first)
        - Uses priceTo=balance (only affordable items)
        - Does NOT use best_deals filter

        Args:
            game_id: Game ID
            max_price: Maximum price (usually user balance)
            limit: Items per page
            offset: Pagination offset

        Returns:
            List of item dictionaries
        """
        try:
            # Convert USD to cents for DMarket API
            price_to_cents = int(max_price * 100)

            result = await self.dmarket.get_market_items(
                game=game_id,
                limit=limit,
                offset=offset,
                price_from=1,  # At least 1 cent
                price_to=price_to_cents,
                sort="price",  # Sort by price
                sort_dir="asc",  # Cheapest first
            )

            return result.get("objects", []) or result.get("items", [])

        except Exception as e:
            logger.exception("failed_to_fetch_market_items", error=str(e))
            return []

    async def _analyze_item(self, item: dict[str, Any]) -> ArbitrageOpportunity | None:
        """Analyze a single item for arbitrage potential.

        Args:
            item: Item data from DMarket API

        Returns:
            ArbitrageOpportunity if viable, None otherwise
        """
        try:
            title = item.get("title", "")
            item_id = item.get("itemId", "") or item.get("extra", {}).get("itemId", "")

            # Check blacklist
            if self._is_blacklisted(title):
                return None

            # Get DMarket price (in cents, convert to USD)
            price_data = item.get("price", {})
            if isinstance(price_data, dict):
                dm_price_cents = int(
                    price_data.get("USD", 0) or price_data.get("amount", 0)
                )
            else:
                dm_price_cents = int(price_data)

            dm_price = Decimal(str(dm_price_cents)) / Decimal(100)

            if dm_price <= 0:
                return None

            # Get trade lock duration
            extra = item.get("extra", {}) or item.get("extraAttributes", {})
            lock_seconds = extra.get("tradeLockDuration", 0) or extra.get(
                "lockDuration", 0
            )
            lock_days = lock_seconds // 86400

            # Skip if lock is too long
            if lock_days > self.config.max_lock_days:
                return None

            # Skip locked items if not included
            if lock_days > 0 and not self.config.include_locked:
                return None

            # Get Waxpeer price
            wax_price, liquidity = await self._get_waxpeer_price(title)

            if wax_price <= 0:
                return None

            # Check liquidity
            if liquidity < self.config.min_liquidity:
                return ArbitrageOpportunity(
                    item_id=item_id,
                    title=title,
                    dmarket_price=dm_price,
                    waxpeer_price=wax_price,
                    net_profit=Decimal(0),
                    roi_percent=Decimal(0),
                    decision=ArbitrageDecision.INSUFFICIENT_LIQUIDITY,
                    lock_days=lock_days,
                    liquidity_score=liquidity,
                    offer_id=extra.get("offerId", ""),
                )

            # Calculate net profit
            # Formula: (Waxpeer_Price * 0.94) - DMarket_Price
            net_profit = (wax_price * WAXPEER_MULTIPLIER) - dm_price
            roi_percent = (net_profit / dm_price * 100) if dm_price > 0 else Decimal(0)

            # Make decision
            decision = self._make_decision(net_profit, roi_percent, lock_days)

            return ArbitrageOpportunity(
                item_id=item_id,
                title=title,
                dmarket_price=dm_price,
                waxpeer_price=wax_price,
                net_profit=net_profit,
                roi_percent=roi_percent,
                decision=decision,
                lock_days=lock_days,
                liquidity_score=liquidity,
                category=self._get_category(title),
                offer_id=extra.get("offerId", ""),
            )

        except Exception as e:
            logger.exception(
                "item_analysis_failed", error=str(e), item=item.get("title", "")
            )
            return None

    async def _get_waxpeer_price(self, item_name: str) -> tuple[Decimal, int]:
        """Get item price and liquidity from Waxpeer.

        Uses WaxpeerPriceInfo for structured data if avAlgolable.

        Args:
            item_name: Item title to search

        Returns:
            Tuple of (price_usd, liquidity_count)
        """
        try:
            # Check cache first
            if item_name in self._waxpeer_cache:
                return self._waxpeer_cache[item_name]

            # Try to use get_item_price_info if avAlgolable
            if hasattr(self.waxpeer, "get_item_price_info"):
                price_info = await self.waxpeer.get_item_price_info(item_name)
                if price_info:
                    result = (price_info.price_usd, price_info.count)
                    self._waxpeer_cache[item_name] = result
                    return result
                return Decimal(0), 0

            # Fallback to get_items_list
            result = await self.waxpeer.get_items_list(names=[item_name])

            items = result.get("items", [])
            if not items:
                return Decimal(0), 0

            # Get minimum price (in mils, convert to USD)
            min_price_mils = items[0].get("price", 0)
            price_usd = Decimal(str(min_price_mils)) / Decimal(1000)

            # Get avAlgolability count from Waxpeer API
            # Note: "count" represents items avAlgolable for sale, used as a proxy for liquidity
            # Higher count generally indicates better liquidity (easier to sell)
            # Use 0 as default - do NOT use len(items) as fallback since it's misleading
            liquidity = items[0].get("count", 0)

            # Cache result
            self._waxpeer_cache[item_name] = (price_usd, liquidity)

            return price_usd, liquidity

        except Exception as e:
            logger.exception("waxpeer_price_fetch_failed", error=str(e), item=item_name)
            return Decimal(0), 0

    def _make_decision(
        self,
        net_profit: Decimal,
        roi_percent: Decimal,
        lock_days: int,
    ) -> ArbitrageDecision:
        """Make arbitrage decision based on profit and lock.

        Args:
            net_profit: Net profit in USD
            roi_percent: ROI percentage
            lock_days: Trade lock duration in days

        Returns:
            ArbitrageDecision enum value
        """
        # Check minimum profit
        if net_profit < self.config.min_profit_usd:
            return ArbitrageDecision.SKIP

        # Instant arbitrage (no lock)
        if lock_days == 0 and roi_percent >= self.config.min_roi_instant:
            return ArbitrageDecision.BUY_INSTANT

        # Investment arbitrage (with lock)
        if lock_days > 0 and roi_percent >= self.config.min_roi_locked:
            return ArbitrageDecision.BUY_AND_HOLD

        return ArbitrageDecision.SKIP

    def _is_blacklisted(self, title: str) -> bool:
        """Check if item is blacklisted.

        Args:
            title: Item title

        Returns:
            True if blacklisted
        """
        title_lower = title.lower()
        return any(keyword in title_lower for keyword in BLACKLISTED_KEYWORDS)

    def _get_category(self, title: str) -> str:
        """Determine item category from title.

        Args:
            title: Item title

        Returns:
            Category string
        """
        title_lower = title.lower()

        if "case" in title_lower:
            return ItemCategory.CASE.value
        if "key" in title_lower:
            return ItemCategory.KEY.value
        if (
            "knife" in title_lower
            or "karambit" in title_lower
            or "bayonet" in title_lower
        ):
            return ItemCategory.KNIFE.value
        if "gloves" in title_lower:
            return ItemCategory.GLOVES.value
        if "agent" in title_lower:
            return ItemCategory.AGENT.value
        if "music kit" in title_lower:
            return ItemCategory.MUSIC_KIT.value
        if "patch" in title_lower:
            return ItemCategory.PATCH.value
        if "sticker" in title_lower:
            return ItemCategory.STICKER.value
        if "graffiti" in title_lower:
            return ItemCategory.GRAFFITI.value

        return ItemCategory.WEAPON.value

    async def execute_buy(self, opportunity: ArbitrageOpportunity) -> bool:
        """Execute a buy order for an opportunity.

        Args:
            opportunity: The arbitrage opportunity to execute

        Returns:
            True if purchase was successful
        """
        if self.config.dry_run:
            logger.info(
                "dry_run_buy",
                title=opportunity.title,
                price=float(opportunity.dmarket_price),
                profit=float(opportunity.net_profit),
                roi=float(opportunity.roi_percent),
                lock_days=opportunity.lock_days,
                decision=opportunity.decision.value,
            )
            return True

        if not opportunity.offer_id:
            logger.error("no_offer_id", title=opportunity.title)
            return False

        try:
            # Execute the purchase
            result = await self.dmarket.buy_offers(
                [
                    {
                        "offerId": opportunity.offer_id,
                        "price": {
                            "amount": str(int(opportunity.dmarket_price * 100)),
                            "currency": "USD",
                        },
                    }
                ]
            )

            success = result.get("success", False) or result.get("status") == "success"

            if success:
                logger.info(
                    "purchase_successful",
                    title=opportunity.title,
                    price=float(opportunity.dmarket_price),
                    expected_profit=float(opportunity.net_profit),
                    roi=float(opportunity.roi_percent),
                    lock_days=opportunity.lock_days,
                )

            return success

        except Exception as e:
            logger.exception("purchase_failed", error=str(e), title=opportunity.title)
            return False

    def format_opportunity_message(self, opp: ArbitrageOpportunity) -> str:
        """Format opportunity for Telegram notification.

        Args:
            opp: ArbitrageOpportunity to format

        Returns:
            Formatted message string
        """
        decision_emoji = {
            ArbitrageDecision.BUY_INSTANT: "⚡",
            ArbitrageDecision.BUY_AND_HOLD: "📦",
            ArbitrageDecision.SKIP: "⏭️",
            ArbitrageDecision.INSUFFICIENT_LIQUIDITY: "💧",
        }

        lock_info = (
            f"⏳ Лок: {opp.lock_days} дн." if opp.lock_days > 0 else "✅ Без лока"
        )

        mode = "АВТО-ПОКУПКА" if not self.config.dry_run else "ТЕСТ (DRY_RUN)"

        return (
            f"{decision_emoji.get(opp.decision, '🎯')} <b>Найдена сделка!</b>\n\n"
            f"📦 <b>Предмет:</b> <code>{opp.title}</code>\n"
            f"💰 <b>Покупка (DMarket):</b> <code>${float(opp.dmarket_price):.2f}</code>\n"
            f"📈 <b>Продажа (Waxpeer):</b> <code>${float(opp.waxpeer_price):.2f}</code>\n"
            f"💵 <b>Чистый профит:</b> <code>+${float(opp.net_profit):.2f}</code>\n"
            f"📊 <b>ROI:</b> <code>{float(opp.roi_percent):.1f}%</code>\n"
            f"{lock_info}\n"
            f"🏷 <b>Категория:</b> {opp.category}\n"
            f"💧 <b>Ликвидность:</b> {opp.liquidity_score}/день\n"
            f"---\n"
            f"🚀 <b>Режим:</b> {mode}"
        )


# ============================================================================
# Utility Functions
# ============================================================================


def calculate_net_profit(
    buy_price: Decimal,
    sell_price: Decimal,
    sell_commission: Decimal = WAXPEER_COMMISSION,
) -> Decimal:
    """Calculate net profit with commission.

    Formula: (sell_price * (1 - commission)) - buy_price

    Args:
        buy_price: Purchase price
        sell_price: Selling price
        sell_commission: Commission rate (default: 6% for Waxpeer)

    Returns:
        Net profit in same currency as inputs
    """
    multiplier = Decimal(1) - sell_commission
    return (sell_price * multiplier) - buy_price


def calculate_roi(profit: Decimal, investment: Decimal) -> Decimal:
    """Calculate ROI percentage.

    Args:
        profit: Net profit
        investment: Initial investment

    Returns:
        ROI as percentage (e.g., 15.0 for 15%)
    """
    if investment <= 0:
        return Decimal(0)
    return (profit / investment) * Decimal(100)


async def quick_arbitrage_check(
    dmarket_api: "DMarketAPI",
    waxpeer_api: "WaxpeerAPI",
    max_items: int = 50,
) -> list[ArbitrageOpportunity]:
    """Quick check for arbitrage opportunities.

    Convenience function for fast scanning.

    Args:
        dmarket_api: DMarket API client
        waxpeer_api: Waxpeer API client
        max_items: Maximum items to scan

    Returns:
        List of profitable opportunities
    """
    config = ScanConfig(
        min_profit_usd=Decimal("0.50"),
        min_roi_instant=Decimal("10.0"),
        include_locked=False,  # Only instant arbitrage
        dry_run=True,
    )

    scanner = CrossPlatformArbitrageScanner(dmarket_api, waxpeer_api, config)
    return await scanner.scan_full_market(limit=max_items)
