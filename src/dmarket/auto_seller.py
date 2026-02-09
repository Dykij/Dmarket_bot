"""Auto-seller module for DMarket automated trading.

Provides automatic selling of items after purchase with dynamic pricing:
- Post-buy sale scheduling with configurable delays
- Competitive pricing with undercut strategy
- Automatic price adjustment to maintain market position
- Stop-loss mechanism for stale items
- DRY_RUN support for strategy testing

Based on analysis of:
- timagr615/dmarket_bot (auto_sell.py)
- TrickmanOff/DMarket-Bot (pricing strategies)

Usage:
    ```python
    from src.dmarket.auto_seller import AutoSeller

    seller = AutoSeller(api_client=api, config=config)

    # Schedule auto-sale after purchase
    await seller.schedule_sale(
        item_id="abc123",
        item_name="AK-47 | Redline",
        buy_price=10.50,
        target_margin=0.08,  # 8% target margin
    )

    # Start background price adjustment
    await seller.start_price_monitor()
    ```
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI


logger = logging.getLogger(__name__)


class SaleStatus(StrEnum):
    """Status of a scheduled sale."""

    PENDING = "pending"  # Waiting to be listed
    LISTED = "listed"  # Listed on market
    ADJUSTING = "adjusting"  # Price being adjusted
    SOLD = "sold"  # Successfully sold
    CANCELLED = "cancelled"  # Cancelled by user
    STOP_LOSS = "stop_loss"  # Sold at stop-loss price
    FAILED = "failed"  # Failed to list/sell


class PricingStrategy(StrEnum):
    """Available pricing strategies."""

    UNDERCUT = "undercut"  # Undercut best offer by X cents
    MATCH = "match"  # Match best offer
    FIXED_MARGIN = "fixed_margin"  # Fixed percentage margin
    DYNAMIC = "dynamic"  # Dynamic based on market conditions


@dataclass
class SaleConfig:
    """Configuration for auto-selling.

    Attributes:
        enabled: Whether auto-sell is enabled
        min_margin_percent: Minimum acceptable margin (default: 4%)
        max_margin_percent: Maximum target margin (default: 12%)
        target_margin_percent: Default target margin (default: 8%)
        undercut_cents: Amount to undercut best offer (default: 1 cent)
        price_check_interval_minutes: How often to check/adjust prices
        stop_loss_hours: Hours before triggering stop-loss (default: 48)
        stop_loss_percent: Maximum loss from buy price (default: 5%)
        max_active_sales: Maximum concurrent sales (default: 50)
        delay_before_list_seconds: Delay before listing after purchase
    """

    enabled: bool = True
    min_margin_percent: float = 4.0
    max_margin_percent: float = 12.0
    target_margin_percent: float = 8.0
    undercut_cents: int = 1
    price_check_interval_minutes: int = 30
    stop_loss_hours: int = 48
    stop_loss_percent: float = 5.0
    max_active_sales: int = 50
    delay_before_list_seconds: int = 5
    pricing_strategy: PricingStrategy = PricingStrategy.UNDERCUT
    dmarket_fee_percent: float = 7.0  # DMarket commission


@dataclass
class ScheduledSale:
    """A scheduled sale item.

    Attributes:
        item_id: DMarket item ID
        item_name: Human-readable name
        buy_price: Price paid for item
        target_margin: Target profit margin (0.08 = 8%)
        game: Game code (csgo, dota2, etc.)
        status: Current sale status
        offer_id: DMarket offer ID (when listed)
        list_price: Price listed at
        current_price: Current offer price (may differ from list_price)
        created_at: When sale was scheduled
        listed_at: When item was listed
        sold_at: When item was sold
        final_price: Actual sale price
        adjustments_count: Number of price adjustments made
    """

    item_id: str
    item_name: str
    buy_price: float
    target_margin: float
    game: str = "csgo"
    status: SaleStatus = SaleStatus.PENDING
    offer_id: str | None = None
    list_price: float | None = None
    current_price: float | None = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    listed_at: datetime | None = None
    sold_at: datetime | None = None
    final_price: float | None = None
    adjustments_count: int = 0

    def calculate_profit(self, sale_price: float | None = None) -> tuple[float, float]:
        """Calculate profit for given or current sale price.

        Args:
            sale_price: Price to calculate profit for (uses current_price if None)

        Returns:
            Tuple of (profit_usd, profit_percent)
        """
        price = sale_price or self.current_price or self.list_price
        if not price:
            return 0.0, 0.0

        profit = price - self.buy_price
        profit_percent = (profit / self.buy_price) * 100 if self.buy_price > 0 else 0.0
        return profit, profit_percent

    def is_stale(self, stop_loss_hours: int = 48) -> bool:
        """Check if sale is stale (listed too long without selling).

        Args:
            stop_loss_hours: Hours threshold for considering sale stale

        Returns:
            True if sale has been listed longer than stop_loss_hours
        """
        if not self.listed_at or self.status != SaleStatus.LISTED:
            return False
        return datetime.now(UTC) - self.listed_at > timedelta(hours=stop_loss_hours)


class AutoSeller:
    """Automated seller for DMarket items.

    Handles the full lifecycle of selling purchased items:
    1. Schedule sale after purchase
    2. Calculate optimal pricing
    3. List item on market
    4. Monitor and adjust prices
    5. Handle stop-loss for stale items

    Attributes:
        api: DMarket API client
        config: Auto-sell configuration
        scheduled_sales: Dict of item_id -> ScheduledSale
        _monitor_task: Background price monitoring task
        _running: Whether monitor is running
    """

    def __init__(
        self,
        api: DMarketAPI,
        config: SaleConfig | None = None,
    ) -> None:
        """Initialize AutoSeller.

        Args:
            api: DMarket API client instance
            config: Auto-sell configuration (uses defaults if None)
        """
        self.api = api
        self.config = config or SaleConfig()
        self.scheduled_sales: dict[str, ScheduledSale] = {}
        self._monitor_task: asyncio.Task[None] | None = None
        self._running = False
        self._stats = AutoSellerStats()

    async def schedule_sale(
        self,
        item_id: str,
        item_name: str,
        buy_price: float,
        target_margin: float | None = None,
        game: str = "csgo",
        immediate: bool = False,
    ) -> ScheduledSale:
        """Schedule an item for automatic sale.

        Args:
            item_id: DMarket item ID
            item_name: Human-readable item name
            buy_price: Price paid for item in USD
            target_margin: Target profit margin (default from config)
            game: Game code
            immediate: If True, list immediately without delay

        Returns:
            ScheduledSale object

        Raises:
            ValueError: If auto-sell is disabled or max sales reached
        """
        if not self.config.enabled:
            raise ValueError("Auto-sell is disabled")

        if len(self.scheduled_sales) >= self.config.max_active_sales:
            raise ValueError(f"Maximum active sales reached ({self.config.max_active_sales})")

        margin = target_margin or (self.config.target_margin_percent / 100)

        sale = ScheduledSale(
            item_id=item_id,
            item_name=item_name,
            buy_price=buy_price,
            target_margin=margin,
            game=game,
        )

        self.scheduled_sales[item_id] = sale
        self._stats.scheduled_count += 1

        logger.info(
            "scheduled_sale",
            extra={
                "item_id": item_id,
                "item_name": item_name,
                "buy_price": buy_price,
                "target_margin": margin,
            },
        )

        # List immediately or with delay
        if immediate:
            await self._list_item(sale)
        else:
            # Schedule listing after delay
            _ = asyncio.create_task(self._delayed_list(sale))

        return sale

    async def _delayed_list(self, sale: ScheduledSale) -> None:
        """List item after configured delay.

        Args:
            sale: ScheduledSale to list
        """
        await asyncio.sleep(self.config.delay_before_list_seconds)
        if sale.status == SaleStatus.PENDING:
            await self._list_item(sale)

    async def _list_item(self, sale: ScheduledSale) -> bool:
        """List an item on the market.

        Args:
            sale: ScheduledSale to list

        Returns:
            True if listing was successful
        """
        try:
            # Calculate optimal price
            optimal_price = await self._calculate_optimal_price(sale)

            if optimal_price is None:
                logger.warning(
                    "cannot_calculate_price",
                    extra={"item_id": sale.item_id, "item_name": sale.item_name},
                )
                sale.status = SaleStatus.FAILED
                return False

            # Sell via API
            result = await self.api.sell_item(
                item_id=sale.item_id,
                price=optimal_price,
                game=sale.game,
                item_name=sale.item_name,
                buy_price=sale.buy_price,
                source="auto_sell",
            )

            # Update sale record
            sale.status = SaleStatus.LISTED
            sale.list_price = optimal_price
            sale.current_price = optimal_price
            sale.listed_at = datetime.now(UTC)

            # Extract offer ID if available
            if "offerId" in result:
                sale.offer_id = result["offerId"]
            elif "offer_id" in result:
                sale.offer_id = result["offer_id"]

            self._stats.listed_count += 1

            profit, profit_percent = sale.calculate_profit(optimal_price)
            logger.info(
                "item_listed",
                extra={
                    "item_id": sale.item_id,
                    "item_name": sale.item_name,
                    "price": optimal_price,
                    "buy_price": sale.buy_price,
                    "expected_profit": profit,
                    "expected_profit_percent": profit_percent,
                },
            )

            return True

        except Exception as e:
            logger.exception(
                "list_item_failed",
                extra={
                    "item_id": sale.item_id,
                    "item_name": sale.item_name,
                    "error": str(e),
                },
            )
            sale.status = SaleStatus.FAILED
            self._stats.failed_count += 1
            return False

    async def _calculate_optimal_price(self, sale: ScheduledSale) -> float | None:
        """Calculate optimal sale price based on strategy.

        Args:
            sale: ScheduledSale to price

        Returns:
            Optimal price in USD, or None if cannot calculate
        """
        strategy = self.config.pricing_strategy

        if strategy == PricingStrategy.FIXED_MARGIN:
            return self._calculate_fixed_margin_price(sale)

        if strategy == PricingStrategy.UNDERCUT:
            top_price = await self._get_top_offer_price(sale.item_id, sale.game)
            return self._calculate_undercut_price(sale, top_price)

        if strategy == PricingStrategy.MATCH:
            top_price = await self._get_top_offer_price(sale.item_id, sale.game)
            if top_price:
                return self._apply_minimum_margin(sale, top_price)
            return self._calculate_fixed_margin_price(sale)

        if strategy == PricingStrategy.DYNAMIC:
            return await self._calculate_dynamic_price(sale)

        return self._calculate_fixed_margin_price(sale)

    def _calculate_fixed_margin_price(self, sale: ScheduledSale) -> float:
        """Calculate price with fixed target margin.

        Args:
            sale: ScheduledSale to price

        Returns:
            Price with target margin applied
        """
        # Account for DMarket fee
        # sell_price * (1 - fee) = buy_price * (1 + margin)
        # sell_price = buy_price * (1 + margin) / (1 - fee)
        fee_multiplier = 1 - (self.config.dmarket_fee_percent / 100)
        gross_margin = 1 + sale.target_margin

        price = (sale.buy_price * gross_margin) / fee_multiplier
        return round(price, 2)

    def _calculate_undercut_price(
        self,
        sale: ScheduledSale,
        top_price: float | None,
    ) -> float:
        """Calculate price undercutting the top offer.

        Args:
            sale: ScheduledSale to price
            top_price: Current best market price

        Returns:
            Undercut price (bounded by min margin)
        """
        if not top_price:
            return self._calculate_fixed_margin_price(sale)

        # Undercut by configured amount
        undercut_price = top_price - (self.config.undercut_cents / 100)

        # Apply minimum margin protection
        return self._apply_minimum_margin(sale, undercut_price)

    def _apply_minimum_margin(self, sale: ScheduledSale, price: float) -> float:
        """Ensure price meets minimum margin requirement.

        Args:
            sale: ScheduledSale being priced
            price: Proposed price

        Returns:
            Price adjusted to meet minimum margin
        """
        min_margin = self.config.min_margin_percent / 100
        fee_multiplier = 1 - (self.config.dmarket_fee_percent / 100)

        # Calculate minimum acceptable price
        min_price = (sale.buy_price * (1 + min_margin)) / fee_multiplier

        return max(price, round(min_price, 2))

    async def _calculate_dynamic_price(self, sale: ScheduledSale) -> float:
        """Calculate price dynamically based on market conditions.

        Considers:
        - Current best offers
        - Recent sales history
        - Market depth
        - Time item has been listed

        Args:
            sale: ScheduledSale to price

        Returns:
            Dynamically calculated price
        """
        top_price = await self._get_top_offer_price(sale.item_id, sale.game)

        # Start with undercut strategy
        base_price = self._calculate_undercut_price(sale, top_price)

        # If item has been listed for a while, be more aggressive
        if sale.listed_at and sale.adjustments_count > 3:
            hours_listed = (datetime.now(UTC) - sale.listed_at).total_seconds() / 3600
            if hours_listed > 24:
                # Reduce price by 1% per day after first 24 hours
                days_over = (hours_listed - 24) / 24
                reduction = min(0.05, days_over * 0.01)  # Max 5% reduction
                base_price *= 1 - reduction

        return self._apply_minimum_margin(sale, base_price)

    async def _get_top_offer_price(
        self,
        item_id: str,
        game: str,
    ) -> float | None:
        """Get the best (lowest) offer price for an item.

        Args:
            item_id: Item to check
            game: Game code

        Returns:
            Best offer price in USD, or None if no offers found
        """
        try:
            # Use market items endpoint to get current offers
            # This is a simplification - in production would use specific offer endpoint
            best_offers = await self.api.get_best_offers(
                game=game,
                title=item_id,  # May need adjustment based on API
                limit=1,
            )

            if best_offers and "objects" in best_offers:
                objects = best_offers["objects"]
                if objects:
                    price_data = objects[0].get("price", {})
                    # Handle both string and int prices (in cents)
                    price_str = price_data.get("USD", price_data.get("amount", "0"))
                    if isinstance(price_str, str):
                        return float(price_str) / 100
                    return float(price_str) / 100

            return None

        except Exception as e:
            logger.warning(
                "get_top_offer_failed",
                extra={"item_id": item_id, "error": str(e)},
            )
            return None

    async def adjust_price(
        self,
        sale: ScheduledSale,
        new_price: float | None = None,
    ) -> bool:
        """Adjust the price of a listed item.

        Args:
            sale: ScheduledSale to adjust
            new_price: New price (auto-calculates if None)

        Returns:
            True if adjustment was successful
        """
        if sale.status != SaleStatus.LISTED or not sale.offer_id:
            return False

        try:
            sale.status = SaleStatus.ADJUSTING

            # Calculate new price if not provided
            if new_price is None:
                new_price = await self._calculate_optimal_price(sale)

            if new_price is None or new_price == sale.current_price:
                sale.status = SaleStatus.LISTED
                return False

            # Update via API
            await self.api.update_offer_prices(
                offers=[
                    {
                        "OfferID": sale.offer_id,
                        "Price": {
                            "Amount": int(new_price * 100),
                            "Currency": "USD",
                        },
                    }
                ]
            )

            old_price = sale.current_price
            sale.current_price = new_price
            sale.adjustments_count += 1
            sale.status = SaleStatus.LISTED

            self._stats.adjustments_count += 1

            logger.info(
                "price_adjusted",
                extra={
                    "item_id": sale.item_id,
                    "old_price": old_price,
                    "new_price": new_price,
                    "adjustments_count": sale.adjustments_count,
                },
            )

            return True

        except Exception as e:
            logger.exception(
                "price_adjustment_failed",
                extra={"item_id": sale.item_id, "error": str(e)},
            )
            sale.status = SaleStatus.LISTED
            return False

    async def trigger_stop_loss(self, sale: ScheduledSale) -> bool:
        """Trigger stop-loss for a stale item.

        Reduces price to sell quickly, accepting a small loss.

        Args:
            sale: ScheduledSale to stop-loss

        Returns:
            True if stop-loss was triggered
        """
        if sale.status != SaleStatus.LISTED:
            return False

        # Calculate stop-loss price
        stop_loss_multiplier = 1 - (self.config.stop_loss_percent / 100)
        stop_loss_price = round(sale.buy_price * stop_loss_multiplier, 2)

        logger.warning(
            "triggering_stop_loss",
            extra={
                "item_id": sale.item_id,
                "item_name": sale.item_name,
                "buy_price": sale.buy_price,
                "stop_loss_price": stop_loss_price,
            },
        )

        success = await self.adjust_price(sale, stop_loss_price)
        if success:
            sale.status = SaleStatus.STOP_LOSS
            self._stats.stop_loss_count += 1

        return success

    async def cancel_sale(self, item_id: str) -> bool:
        """Cancel a scheduled or listed sale.

        Args:
            item_id: Item ID to cancel

        Returns:
            True if cancellation was successful
        """
        sale = self.scheduled_sales.get(item_id)
        if not sale:
            return False

        if sale.status == SaleStatus.LISTED and sale.offer_id:
            try:
                await self.api.remove_offers([sale.offer_id])
            except Exception as e:
                logger.exception(
                    "cancel_offer_failed",
                    extra={"item_id": item_id, "error": str(e)},
                )
                return False

        sale.status = SaleStatus.CANCELLED
        del self.scheduled_sales[item_id]

        logger.info("sale_cancelled", extra={"item_id": item_id})
        return True

    def mark_sold(self, item_id: str, final_price: float) -> bool:
        """Mark an item as sold.

        Should be called when sale confirmation is received.

        Args:
            item_id: Item that was sold
            final_price: Actual sale price

        Returns:
            True if item was found and marked
        """
        sale = self.scheduled_sales.get(item_id)
        if not sale:
            return False

        sale.status = SaleStatus.SOLD
        sale.sold_at = datetime.now(UTC)
        sale.final_price = final_price

        profit, profit_percent = sale.calculate_profit(final_price)
        self._stats.sold_count += 1
        self._stats.total_profit += profit

        logger.info(
            "item_sold",
            extra={
                "item_id": item_id,
                "item_name": sale.item_name,
                "buy_price": sale.buy_price,
                "sale_price": final_price,
                "profit": profit,
                "profit_percent": profit_percent,
            },
        )

        # Remove from active sales
        del self.scheduled_sales[item_id]

        return True

    async def start_price_monitor(self) -> None:
        """Start background price monitoring task.

        Periodically checks and adjusts prices for listed items.
        """
        if self._running:
            return

        self._running = True
        self._monitor_task = asyncio.create_task(self._price_monitor_loop())
        logger.info("price_monitor_started")

    async def stop_price_monitor(self) -> None:
        """Stop background price monitoring task."""
        self._running = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
            self._monitor_task = None
        logger.info("price_monitor_stopped")

    async def _price_monitor_loop(self) -> None:
        """Background loop for price monitoring and adjustment."""
        interval = self.config.price_check_interval_minutes * 60

        while self._running:
            try:
                await self._check_and_adjust_prices()
                await asyncio.sleep(interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("price_monitor_error", extra={"error": str(e)})
                await asyncio.sleep(60)  # Wait a minute before retrying

    async def _check_and_adjust_prices(self) -> None:
        """Check all listed items and adjust prices if needed."""
        listed_sales = [s for s in self.scheduled_sales.values() if s.status == SaleStatus.LISTED]

        for sale in listed_sales:
            # Check for stop-loss
            if sale.is_stale(self.config.stop_loss_hours):
                await self.trigger_stop_loss(sale)
                continue

            # Adjust price for competitiveness
            await self.adjust_price(sale)

    def get_statistics(self) -> dict[str, Any]:
        """Get auto-seller statistics.

        Returns:
            Dict with statistics
        """
        return {
            "scheduled_count": self._stats.scheduled_count,
            "listed_count": self._stats.listed_count,
            "sold_count": self._stats.sold_count,
            "failed_count": self._stats.failed_count,
            "stop_loss_count": self._stats.stop_loss_count,
            "adjustments_count": self._stats.adjustments_count,
            "total_profit": self._stats.total_profit,
            "active_sales": len(self.scheduled_sales),
            "pending": sum(
                1 for s in self.scheduled_sales.values() if s.status == SaleStatus.PENDING
            ),
            "listed": sum(
                1 for s in self.scheduled_sales.values() if s.status == SaleStatus.LISTED
            ),
        }

    def get_active_sales(self) -> list[dict[str, Any]]:
        """Get list of active sales with details.

        Returns:
            List of sale dictionaries
        """
        return [
            {
                "item_id": s.item_id,
                "item_name": s.item_name,
                "buy_price": s.buy_price,
                "current_price": s.current_price,
                "status": s.status.value,
                "profit": s.calculate_profit()[0],
                "profit_percent": s.calculate_profit()[1],
                "listed_at": s.listed_at.isoformat() if s.listed_at else None,
                "adjustments": s.adjustments_count,
            }
            for s in self.scheduled_sales.values()
        ]

    async def process_inventory(self) -> int:
        """Process inventory and list new items for sale.

        This is the "bridge" function that connects auto-buyer with auto-seller.
        It checks the inventory for items that were purchased but not yet listed,
        and schedules them for sale automatically.

        Returns:
            Number of items scheduled for sale
        """
        if not self.config.enabled:
            return 0

        items_scheduled = 0

        try:
            # Get current inventory
            # game_id for CS:GO is "a8db99ca-dc45-4c0e-9989-11ba71ed97a2" (default)
            inventory_response = await self.api.get_user_inventory(limit=100)

            if not inventory_response:
                return 0

            # Extract items from response
            items = inventory_response.get("objects", inventory_response.get("Items", []))

            for item in items:
                item_id = item.get("itemId") or item.get("assetId") or item.get("id")

                if not item_id:
                    continue

                # Skip if already scheduled
                if item_id in self.scheduled_sales:
                    continue

                # Check if item is available for sale (not already listed)
                status = item.get("status", "").lower()
                in_market = item.get("inMarket", False)

                if in_market or status == "on_sale":
                    continue

                # Get item details
                title = item.get("title", "Unknown Item")

                # Get buy price from item data or use suggested price
                buy_price = self._extract_buy_price(item)

                if buy_price <= 0:
                    logger.warning(
                        "cannot_determine_buy_price",
                        extra={"item_id": item_id, "title": title},
                    )
                    continue

                # Schedule for sale
                try:
                    await self.schedule_sale(
                        item_id=item_id,
                        item_name=title,
                        buy_price=buy_price,
                        game=item.get("gameId", "csgo"),
                        immediate=False,
                    )
                    items_scheduled += 1

                    logger.info(
                        "auto_scheduled_from_inventory",
                        extra={
                            "item_id": item_id,
                            "title": title,
                            "buy_price": buy_price,
                        },
                    )
                except ValueError as e:
                    # Max sales reached or disabled
                    logger.warning("schedule_sale_skipped", extra={"error": str(e)})
                    break

        except Exception as e:
            logger.exception("process_inventory_error", extra={"error": str(e)})

        return items_scheduled

    def _extract_buy_price(self, item: dict[str, Any]) -> float:
        """Extract buy price from item data.

        Tries multiple sources:
        1. buyPrice field (if we stored it during purchase)
        2. price field (current market price as fallback)
        3. suggestedPrice field

        Args:
            item: Item data dictionary

        Returns:
            Buy price in USD (0 if not found)
        """
        # Try buyPrice first (stored during purchase)
        buy_price_data = item.get("buyPrice") or item.get("buy_price")
        if buy_price_data:
            if isinstance(buy_price_data, dict):
                amount = buy_price_data.get("amount", buy_price_data.get("USD", 0))
                return float(amount) / 100  # Convert cents to USD
            return float(buy_price_data) / 100

        # Try current price
        price_data = item.get("price", {})
        if isinstance(price_data, dict):
            amount = price_data.get("amount", price_data.get("USD", 0))
            if amount:
                return float(amount) / 100

        # Try suggested price
        suggested = item.get("suggestedPrice", {})
        if isinstance(suggested, dict):
            amount = suggested.get("amount", suggested.get("USD", 0))
            if amount:
                return float(amount) / 100
        elif suggested:
            return float(suggested) / 100

        return 0.0


@dataclass
class AutoSellerStats:
    """Statistics for AutoSeller."""

    scheduled_count: int = 0
    listed_count: int = 0
    sold_count: int = 0
    failed_count: int = 0
    stop_loss_count: int = 0
    adjustments_count: int = 0
    total_profit: float = 0.0


def load_sale_config(config_path: str = "config/config.yaml") -> SaleConfig:
    """Load SaleConfig from YAML configuration file.

    Args:
        config_path: Path to YAML config file

    Returns:
        SaleConfig instance
    """
    import yaml

    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        auto_sell_config = data.get("auto_sell", {})

        return SaleConfig(
            enabled=auto_sell_config.get("enabled", True),
            min_margin_percent=auto_sell_config.get("min_margin_percent", 4.0),
            max_margin_percent=auto_sell_config.get("max_margin_percent", 12.0),
            target_margin_percent=auto_sell_config.get("target_margin_percent", 8.0),
            undercut_cents=auto_sell_config.get("undercut_cents", 1),
            price_check_interval_minutes=auto_sell_config.get("price_check_interval_minutes", 30),
            stop_loss_hours=auto_sell_config.get("stop_loss_hours", 48),
            stop_loss_percent=auto_sell_config.get("stop_loss_percent", 5.0),
            max_active_sales=auto_sell_config.get("max_active_sales", 50),
            delay_before_list_seconds=auto_sell_config.get("delay_before_list_seconds", 5),
            pricing_strategy=PricingStrategy(auto_sell_config.get("pricing_strategy", "undercut")),
            dmarket_fee_percent=auto_sell_config.get("dmarket_fee_percent", 7.0),
        )

    except Exception as e:
        logger.warning("Error loading auto_sell config: %s, using defaults", e)
        return SaleConfig()
