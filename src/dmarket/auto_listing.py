"""Auto-Listing System for automatic item listing on marketplaces.

This module provides automatic listing of expensive items from DMarket inventory
to other marketplaces (Waxpeer) at optimal prices.

Features:
- Automatic detection of expensive items in DMarket inventory
- Price optimization based on market analysis
- WebSocket-based real-time monitoring for Waxpeer
- Automatic repricing to stay competitive
- Profit margin protection

Usage:
    ```python
    from src.dmarket.auto_listing import AutoListingEngine

    engine = AutoListingEngine(
        dmarket_api=dmarket_api,
        waxpeer_api=waxpeer_api,
        min_price_usd=50.0,  # Only list items worth $50+
        target_profit_margin=0.1,  # 10% profit margin
    )

    await engine.start()
    ```

Created: January 10, 2026
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI
    from src.waxpeer.waxpeer_api import WaxpeerAPI


logger = structlog.get_logger(__name__)


# DMarket commission: 7%
DMARKET_COMMISSION = Decimal("0.07")
# Waxpeer commission: 6%
WAXPEER_COMMISSION = Decimal("0.06")


class ListingStrategy(StrEnum):
    """Listing price strategies."""

    UNDERCUT = "undercut"  # Slightly below competition
    MATCH = "match"  # Match lowest price
    PREMIUM = "premium"  # Above market for profit
    INSTANT_SELL = "instant_sell"  # Lowest for quick sale


class ListingStatus(StrEnum):
    """Listing status."""

    PENDING = "pending"
    LISTED = "listed"
    SOLD = "sold"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass
class ListingConfig:
    """Configuration for auto-listing."""

    # Price thresholds
    min_price_usd: Decimal = Decimal("50.0")  # Minimum item price to list
    max_price_usd: Decimal = Decimal("10000.0")  # Maximum item price

    # Profit settings
    target_profit_margin: Decimal = Decimal("0.10")  # 10% target profit
    min_profit_margin: Decimal = Decimal("0.03")  # 3% minimum acceptable
    include_commission: bool = True  # Factor in marketplace commissions

    # Listing strategy
    default_strategy: ListingStrategy = ListingStrategy.UNDERCUT
    undercut_percent: Decimal = Decimal("0.02")  # 2% below competition

    # Repricing settings
    auto_reprice: bool = True
    reprice_interval_minutes: int = 15
    reprice_threshold_percent: Decimal = Decimal(
        "0.05"
    )  # 5% price change triggers reprice

    # Safety settings
    max_listings_per_hour: int = 10
    cooldown_after_sale_minutes: int = 5
    blacklist_items: set[str] = field(default_factory=set)

    # Monitoring
    check_interval_seconds: float = 60.0


@dataclass
class ListingCandidate:
    """A candidate item for listing."""

    item_id: str
    item_name: str
    dmarket_price: Decimal  # Price on DMarket
    waxpeer_price: Decimal | None = None  # Current price on Waxpeer
    recommended_price: Decimal | None = None
    estimated_profit: Decimal | None = None
    profit_margin: Decimal | None = None
    liquidity_score: float = 0.0
    status: ListingStatus = ListingStatus.PENDING
    listed_at: datetime | None = None
    error_message: str | None = None


@dataclass
class ListingResult:
    """Result of a listing operation."""

    success: bool
    item_id: str
    item_name: str
    listed_price: Decimal | None = None
    marketplace: str = "waxpeer"
    error: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


class AutoListingEngine:
    """Automatic listing engine for cross-marketplace arbitrage.

    Monitors DMarket inventory and automatically lists expensive items
    on Waxpeer at optimal prices for profit.
    """

    def __init__(
        self,
        dmarket_api: DMarketAPI,
        waxpeer_api: WaxpeerAPI,
        config: ListingConfig | None = None,
        on_listing: Any | None = None,
        on_sale: Any | None = None,
    ) -> None:
        """Initialize auto-listing engine.

        Args:
            dmarket_api: DMarket API client
            waxpeer_api: Waxpeer API client
            config: Listing configuration
            on_listing: Callback when item is listed
            on_sale: Callback when item is sold
        """
        self.dmarket = dmarket_api
        self.waxpeer = waxpeer_api
        self.config = config or ListingConfig()
        self.on_listing = on_listing
        self.on_sale = on_sale

        # State
        self._running = False
        self._listings: dict[str, ListingCandidate] = {}
        self._listing_history: list[ListingResult] = []
        self._last_check_time: datetime | None = None
        self._listings_this_hour: int = 0
        self._hour_start: datetime = datetime.now(UTC)

        # Tasks
        self._monitor_task: asyncio.Task | None = None
        self._reprice_task: asyncio.Task | None = None

    @property
    def is_running(self) -> bool:
        """Check if engine is running."""
        return self._running

    @property
    def active_listings(self) -> list[ListingCandidate]:
        """Get active listings."""
        return [
            listing
            for listing in self._listings.values()
            if listing.status == ListingStatus.LISTED
        ]

    async def start(self) -> None:
        """Start auto-listing engine."""
        if self._running:
            logger.warning("auto_listing_already_running")
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._monitoring_loop())

        if self.config.auto_reprice:
            self._reprice_task = asyncio.create_task(self._repricing_loop())

        logger.info(
            "auto_listing_started",
            min_price=str(self.config.min_price_usd),
            target_margin=str(self.config.target_profit_margin),
        )

    async def stop(self) -> None:
        """Stop auto-listing engine."""
        self._running = False

        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        if self._reprice_task:
            self._reprice_task.cancel()
            try:
                await self._reprice_task
            except asyncio.CancelledError:
                pass

        logger.info("auto_listing_stopped", total_listings=len(self._listing_history))

    async def _monitoring_loop(self) -> None:
        """Main monitoring loop."""
        while self._running:
            try:
                # Reset hourly counter if needed
                now = datetime.now(UTC)
                if now - self._hour_start > timedelta(hours=1):
                    self._listings_this_hour = 0
                    self._hour_start = now

                # Check for expensive items
                candidates = await self._find_listing_candidates()

                for candidate in candidates:
                    if not self._running:
                        break

                    # Check rate limit
                    if self._listings_this_hour >= self.config.max_listings_per_hour:
                        logger.info("auto_listing_rate_limit_reached")
                        break

                    # List the item
                    result = await self._list_item(candidate)

                    if result.success:
                        self._listings_this_hour += 1
                        self._listing_history.append(result)

                        if self.on_listing:
                            await self.on_listing(result)

                self._last_check_time = now
                await asyncio.sleep(self.config.check_interval_seconds)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("auto_listing_monitor_error", error=str(e))
                await asyncio.sleep(30)

    async def _repricing_loop(self) -> None:
        """Automatic repricing loop."""
        while self._running:
            try:
                await asyncio.sleep(self.config.reprice_interval_minutes * 60)

                for listing in self.active_listings:
                    if not self._running:
                        break

                    # Get current market price
                    new_price = await self._calculate_optimal_price(listing.item_name)

                    if new_price and listing.recommended_price:
                        price_diff = abs(new_price - listing.recommended_price)
                        diff_percent = price_diff / listing.recommended_price

                        if diff_percent >= self.config.reprice_threshold_percent:
                            await self._reprice_item(listing.item_id, new_price)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("auto_listing_reprice_error", error=str(e))

    async def _find_listing_candidates(self) -> list[ListingCandidate]:
        """Find items suitable for listing.

        Returns:
            List of listing candidates
        """
        candidates = []

        try:
            # Get DMarket inventory
            inventory = await self.dmarket.get_user_inventory()
            items = inventory.get("items", [])

            for item in items:
                item_name = item.get("title", "")

                # Skip blacklisted items
                if item_name.lower() in {
                    b.lower() for b in self.config.blacklist_items
                }:
                    continue

                # Get price
                price_data = item.get("price", {})
                price_cents = int(price_data.get("USD", "0"))
                price_usd = Decimal(str(price_cents)) / 100

                # Check price thresholds
                if price_usd < self.config.min_price_usd:
                    continue
                if price_usd > self.config.max_price_usd:
                    continue

                # Check if already listed
                item_id = item.get("itemId", "")
                if item_id in self._listings:
                    continue

                # Create candidate
                candidate = ListingCandidate(
                    item_id=item_id,
                    item_name=item_name,
                    dmarket_price=price_usd,
                )

                # Calculate optimal price
                optimal_price = await self._calculate_optimal_price(item_name)
                if optimal_price:
                    candidate.recommended_price = optimal_price
                    candidate.estimated_profit = self._calculate_profit(
                        buy_price=price_usd,
                        sell_price=optimal_price,
                    )
                    if price_usd > 0:
                        candidate.profit_margin = candidate.estimated_profit / price_usd

                    # Check minimum profit
                    if (
                        candidate.profit_margin
                        and candidate.profit_margin >= self.config.min_profit_margin
                    ):
                        candidates.append(candidate)

            logger.info("auto_listing_candidates_found", count=len(candidates))

        except Exception as e:
            logger.exception("auto_listing_find_candidates_error", error=str(e))

        return candidates

    async def _calculate_optimal_price(self, item_name: str) -> Decimal | None:
        """Calculate optimal listing price.

        Args:
            item_name: Item name

        Returns:
            Optimal price in USD or None
        """
        try:
            # Get Waxpeer market price
            price_data = await self.waxpeer.get_market_prices([item_name])
            items = price_data.get("items", [])

            if not items:
                return None

            item = items[0]
            market_price_mils = item.get("price", 0)
            market_price = Decimal(str(market_price_mils)) / 1000

            # Apply strategy
            if self.config.default_strategy == ListingStrategy.UNDERCUT:
                # Undercut by configured percentage
                optimal = market_price * (1 - self.config.undercut_percent)
            elif self.config.default_strategy == ListingStrategy.MATCH:
                optimal = market_price
            elif self.config.default_strategy == ListingStrategy.PREMIUM:
                # Add premium
                optimal = market_price * (1 + self.config.target_profit_margin)
            else:  # INSTANT_SELL
                optimal = market_price * Decimal("0.95")

            return optimal.quantize(Decimal("0.01"))

        except Exception as e:
            logger.exception(
                "auto_listing_price_calc_error", item=item_name, error=str(e)
            )
            return None

    def _calculate_profit(
        self,
        buy_price: Decimal,
        sell_price: Decimal,
    ) -> Decimal:
        """Calculate profit after commissions.

        Args:
            buy_price: Purchase price
            sell_price: Listing price

        Returns:
            Net profit
        """
        if not self.config.include_commission:
            return sell_price - buy_price

        # DMarket purchase (no commission when buying from own inventory)
        # Waxpeer sale commission
        net_after_commission = sell_price * (1 - WAXPEER_COMMISSION)

        return net_after_commission - buy_price

    async def _list_item(self, candidate: ListingCandidate) -> ListingResult:
        """List an item on Waxpeer.

        Args:
            candidate: Item to list

        Returns:
            Listing result
        """
        try:
            if not candidate.recommended_price:
                return ListingResult(
                    success=False,
                    item_id=candidate.item_id,
                    item_name=candidate.item_name,
                    error="No recommended price",
                )

            # List on Waxpeer
            result = await self.waxpeer.list_single_item(
                item_id=candidate.item_id,
                price_usd=candidate.recommended_price,
            )

            if result.get("success"):
                candidate.status = ListingStatus.LISTED
                candidate.listed_at = datetime.now(UTC)
                self._listings[candidate.item_id] = candidate

                logger.info(
                    "auto_listing_success",
                    item=candidate.item_name,
                    price=str(candidate.recommended_price),
                    profit_margin=str(candidate.profit_margin),
                )

                return ListingResult(
                    success=True,
                    item_id=candidate.item_id,
                    item_name=candidate.item_name,
                    listed_price=candidate.recommended_price,
                )
            error_msg = result.get("msg", "Unknown error")
            candidate.status = ListingStatus.ERROR
            candidate.error_message = error_msg

            return ListingResult(
                success=False,
                item_id=candidate.item_id,
                item_name=candidate.item_name,
                error=error_msg,
            )

        except Exception as e:
            logger.exception(
                "auto_listing_error", item=candidate.item_name, error=str(e)
            )
            return ListingResult(
                success=False,
                item_id=candidate.item_id,
                item_name=candidate.item_name,
                error=str(e),
            )

    async def _reprice_item(self, item_id: str, new_price: Decimal) -> bool:
        """Reprice a listed item.

        Args:
            item_id: Item ID
            new_price: New price

        Returns:
            Success status
        """
        try:
            result = await self.waxpeer.edit_item_price(item_id, new_price)

            if result.get("success"):
                if item_id in self._listings:
                    self._listings[item_id].recommended_price = new_price

                logger.info(
                    "auto_listing_repriced",
                    item_id=item_id,
                    new_price=str(new_price),
                )
                return True

        except Exception as e:
            logger.exception(
                "auto_listing_reprice_error", item_id=item_id, error=str(e)
            )

        return False

    async def cancel_listing(self, item_id: str) -> bool:
        """Cancel a listing.

        Args:
            item_id: Item ID to cancel

        Returns:
            Success status
        """
        try:
            result = await self.waxpeer.remove_items([item_id])

            if result.get("success"):
                if item_id in self._listings:
                    self._listings[item_id].status = ListingStatus.CANCELLED
                    del self._listings[item_id]

                logger.info("auto_listing_cancelled", item_id=item_id)
                return True

        except Exception as e:
            logger.exception("auto_listing_cancel_error", item_id=item_id, error=str(e))

        return False

    async def cancel_all_listings(self) -> int:
        """Cancel all active listings.

        Returns:
            Number of cancelled listings
        """
        cancelled = 0
        for listing in self.active_listings:
            if await self.cancel_listing(listing.item_id):
                cancelled += 1
        return cancelled

    def get_stats(self) -> dict[str, Any]:
        """Get engine statistics.

        Returns:
            Statistics dictionary
        """
        total_profit = sum(
            r.listed_price
            - self._listings.get(
                r.item_id, ListingCandidate("", "", Decimal(0))
            ).dmarket_price
            for r in self._listing_history
            if r.success and r.listed_price
        )

        return {
            "is_running": self._running,
            "active_listings": len(self.active_listings),
            "total_listings": len(self._listing_history),
            "successful_listings": sum(1 for r in self._listing_history if r.success),
            "listings_this_hour": self._listings_this_hour,
            "estimated_total_profit": str(total_profit),
            "last_check": (
                self._last_check_time.isoformat() if self._last_check_time else None
            ),
        }


# Factory function
def create_auto_listing_engine(
    dmarket_api: DMarketAPI,
    waxpeer_api: WaxpeerAPI,
    min_price: float = 50.0,
    target_profit: float = 0.10,
) -> AutoListingEngine:
    """Create auto-listing engine with preset configuration.

    Args:
        dmarket_api: DMarket API client
        waxpeer_api: Waxpeer API client
        min_price: Minimum price threshold
        target_profit: Target profit margin

    Returns:
        Configured AutoListingEngine
    """
    config = ListingConfig(
        min_price_usd=Decimal(str(min_price)),
        target_profit_margin=Decimal(str(target_profit)),
    )

    return AutoListingEngine(
        dmarket_api=dmarket_api,
        waxpeer_api=waxpeer_api,
        config=config,
    )
