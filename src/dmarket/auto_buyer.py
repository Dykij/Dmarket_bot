"""Auto-buyer module for instant item purchases (sniping).

This module implements:
- Instant buy functionality with Telegram buttons
- Auto-buy based on discount threshold
- Purchase validation and safety checks
- DRY_RUN mode support
- Persistent storage of purchases (survives restarts)

Created: January 2, 2026
Updated: February 9, 2026 - Refactored to use Service Layer (TradingEngine)
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog

from src.trading.engine import TradingEngine, TradingConfig

if TYPE_CHECKING:
    from src.utils.trading_persistence import TradingPersistence

logger = structlog.get_logger(__name__)


class AutoBuyConfig:
    """Configuration for auto-buy functionality."""

    def __init__(
        self,
        enabled: bool = False,
        min_discount_percent: float = 30.0,
        max_price_usd: float = 100.0,
        check_sales_history: bool = True,
        check_trade_lock: bool = True,
        max_trade_lock_hours: int = 168,  # 7 days
        dry_run: bool = True,
    ):
        """Initialize auto-buy configuration.

        Args:
            enabled: Enable/disable auto-buy
            min_discount_percent: Minimum discount to trigger auto-buy (%)
            max_price_usd: Maximum price for auto-buy (USD)
            check_sales_history: Verify price trend before buying
            check_trade_lock: Check trade lock duration
            max_trade_lock_hours: Maximum acceptable trade lock (hours)
            dry_run: Simulate purchases without real transactions
        """
        self.enabled = enabled
        self.min_discount_percent = min_discount_percent
        self.max_price_usd = max_price_usd
        self.check_sales_history = check_sales_history
        self.check_trade_lock = check_trade_lock
        self.max_trade_lock_hours = max_trade_lock_hours
        self.dry_run = dry_run


class PurchaseResult:
    """Result of a purchase attempt."""

    def __init__(
        self,
        success: bool,
        item_id: str,
        item_title: str,
        price_usd: float,
        message: str,
        order_id: str | None = None,
        error: str | None = None,
    ):
        self.success = success
        self.item_id = item_id
        self.item_title = item_title
        self.price_usd = price_usd
        self.message = message
        self.order_id = order_id
        self.error = error
        self.timestamp = datetime.now()

    def to_dict(self) -> dict[str, Any]:
        """Convert result to dictionary."""
        return {
            "success": self.success,
            "item_id": self.item_id,
            "item_title": self.item_title,
            "price_usd": self.price_usd,
            "message": self.message,
            "order_id": self.order_id,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
        }


class AutoBuyer:
    """Automatic item buyer with instant purchase capability (Controller)."""

    def __init__(self, api_client, config: AutoBuyConfig | None = None):
        """Initialize AutoBuyer.

        Args:
            api_client: DMarket API client instance
            config: Auto-buy configuration
        """
        self.api = api_client
        self.config = config or AutoBuyConfig()

        # Initialize Service Layer (Trading Engine)
        # This delegates business logic to a specialized service
        self.engine = TradingEngine(
            TradingConfig(
                min_discount_percent=self.config.min_discount_percent,
                max_price_usd=self.config.max_price_usd,
                check_sales_history=self.config.check_sales_history,
                check_trade_lock=self.config.check_trade_lock,
                max_trade_lock_hours=self.config.max_trade_lock_hours,
            )
        )

        self.purchase_history: list[PurchaseResult] = []
        self._auto_seller = None  # Will be set via set_auto_seller()
        self._trading_persistence: TradingPersistence | None = None  # Persistence layer

        logger.info(
            "auto_buyer_initialized",
            enabled=self.config.enabled,
            min_discount=self.config.min_discount_percent,
            max_price=self.config.max_price_usd,
            dry_run=self.config.dry_run,
        )

    def set_trading_persistence(self, persistence: "TradingPersistence") -> None:
        """Set persistence layer for saving purchases to database.

        This ensures purchases survive bot restarts.

        Args:
            persistence: TradingPersistence instance
        """
        self._trading_persistence = persistence
        logger.info(
            "trading_persistence_linked", has_persistence=persistence is not None
        )

    def set_auto_seller(self, auto_seller) -> None:
        """Link auto-seller for automatic sale scheduling after purchase.

        This creates the "bridge" between buying and selling:
        When an item is purchased, it will be automatically scheduled for sale.

        Args:
            auto_seller: AutoSeller instance
        """
        self._auto_seller = auto_seller
        logger.info("auto_seller_linked", has_seller=auto_seller is not None)

    async def should_auto_buy(self, item: dict) -> tuple[bool, str]:
        """Check if item meets auto-buy criteria using TradingEngine service.

        Args:
            item: Item data from DMarket API

        Returns:
            Tuple of (should_buy: bool, reason: str)
        """
        # Early return: Auto-buy disabled
        if not self.config.enabled:
            return False, "Auto-buy is disabled"

        # Delegate logic to Service Layer
        decision = self.engine.evaluate_deal(item)

        if not decision.should_buy:
            return False, decision.reason

        # Perform Async Liquidity Check (Engine Helper)
        # Note: We pass self.api because Engine is stateless regarding API connection
        if self.config.check_sales_history:
            title = item.get("title", "")
            is_liquid = await self._check_liquidity_proxy(title)
            if not is_liquid:
                return False, "Low liquidity (< 5 sales/day)"

        return True, decision.reason

    async def _check_liquidity_proxy(self, title: str) -> bool:
        """Wrapper for liquidity check to maintain compatibility or custom logic."""
        # This could also move to Engine fully if we pass API client to it
        try:
            # Get item title
            if not title:
                return True  # Skip check if no title

            # Request sales history (last 7 days)
            # Note: This requires sales_history module
            from src.dmarket.sales_history import get_item_sales_history

            history = await get_item_sales_history(
                api_client=self.api, item_title=title, days=7
            )

            if not history:
                logger.warning("no_sales_history", title=title)
                return True  # Assume liquid if no data

            # Calculate daily sales
            daily_sales = len(history) / 7

            # Require at least 5 sales per day
            if daily_sales < 5:
                logger.debug(
                    "low_liquidity_detected",
                    title=title,
                    daily_sales=daily_sales,
                )
                return False

            logger.debug("liquidity_check_passed", title=title, daily_sales=daily_sales)
            return True

        except ImportError:
            # Sales history module not available, skip check
            logger.warning("sales_history_module_unavailable")
            return True
        except Exception as e:
            logger.exception("liquidity_check_failed", error=str(e))
            return True  # Assume liquid on error

    async def buy_item(
        self, item_id: str, price_usd: float, force: bool = False
    ) -> PurchaseResult:
        """Purchase an item instantly.

        Args:
            item_id: DMarket item ID
            price_usd: Item price in USD
            force: Bypass auto-buy checks (manual purchase)

        Returns:
            PurchaseResult with purchase details
        """
        logger.info(
            "purchase_attempt",
            item_id=item_id,
            price=price_usd,
            force=force,
            dry_run=self.config.dry_run,
        )

        # Check balance before purchase (not in DRY_RUN)
        if not self.config.dry_run:
            has_balance = await self._check_balance(price_usd)
            if not has_balance:
                result = PurchaseResult(
                    success=False,
                    item_id=item_id,
                    item_title="Unknown",
                    price_usd=price_usd,
                    message="? Insufficient balance",
                    error="Insufficient funds",
                )
                self.purchase_history.append(result)
                return result

        # DRY_RUN mode: Simulate purchase
        if self.config.dry_run:
            result = PurchaseResult(
                success=True,
                item_id=item_id,
                item_title="DRY_RUN_ITEM",
                price_usd=price_usd,
                message="? DRY_RUN: Purchase simulated successfully",
                order_id=f"DRY_RUN_{item_id}",
            )
            self.purchase_history.append(result)

            logger.info(
                "purchase_simulated",
                item_id=item_id,
                price=price_usd,
                order_id=result.order_id,
            )

            # Save to database for persistence (even in DRY_RUN for testing)
            await self._save_purchase_to_db(item_id, "DRY_RUN_ITEM", price_usd, "csgo")

            # Schedule auto-sell even in DRY_RUN mode (for testing)
            await self._schedule_auto_sell(item_id, "DRY_RUN_ITEM", price_usd, "csgo")

            return result

        # Real purchase
        try:
            # Call DMarket API to buy item
            response = await self.api.buy_item(item_id, price_usd)

            if response.get("success"):
                item_title = response.get("title", "Unknown")
                game = response.get("game", "csgo")

                result = PurchaseResult(
                    success=True,
                    item_id=item_id,
                    item_title=item_title,
                    price_usd=price_usd,
                    message="? Purchase completed successfully",
                    order_id=response.get("orderId"),
                )

                logger.info(
                    "purchase_completed",
                    item_id=item_id,
                    price=price_usd,
                    order_id=result.order_id,
                )

                # CRITICAL: Save purchase to database for persistence
                # This ensures bot remembers the purchase after restart
                await self._save_purchase_to_db(item_id, item_title, price_usd, game)

                # Auto-schedule for sale after successful purchase
                await self._schedule_auto_sell(
                    item_id=item_id,
                    item_title=result.item_title,
                    buy_price=price_usd,
                    game=response.get("game", "csgo"),
                )
            else:
                result = PurchaseResult(
                    success=False,
                    item_id=item_id,
                    item_title="Unknown",
                    price_usd=price_usd,
                    message="? Purchase failed",
                    error=response.get("error", "Unknown error"),
                )

                logger.error(
                    "purchase_failed",
                    item_id=item_id,
                    error=result.error,
                )

            self.purchase_history.append(result)
            return result

        except Exception as e:
            result = PurchaseResult(
                success=False,
                item_id=item_id,
                item_title="Unknown",
                price_usd=price_usd,
                message=f"? Exception during purchase: {e!s}",
                error=str(e),
            )

            logger.exception(
                "purchase_exception",
                item_id=item_id,
                error=str(e),
            )

            self.purchase_history.append(result)
            return result

    async def process_opportunity(self, item: dict) -> PurchaseResult | None:
        """Process arbitrage opportunity and auto-buy if criteria met.

        Args:
            item: Item data from scanner

        Returns:
            PurchaseResult if purchased, None if skipped
        """
        should_buy, reason = await self.should_auto_buy(item)

        if not should_buy:
            logger.debug("auto_buy_skipped", item_id=item.get("itemId"), reason=reason)
            return None

        # Extract item details
        item_id = item.get("itemId") or item.get("extra", {}).get("offerId")
        price_usd = float(item.get("price", {}).get("USD", 0)) / 100

        logger.info(
            "auto_buy_triggered",
            item_id=item_id,
            item_title=item.get("title"),
            price=price_usd,
            reason=reason,
        )

        # Execute purchase
        return await self.buy_item(item_id, price_usd, force=False)

    def get_purchase_stats(self) -> dict[str, Any]:
        """Get purchase statistics.

        Returns:
            Dictionary with purchase stats
        """
        if not self.purchase_history:
            return {
                "total_purchases": 0,
                "successful": 0,
                "failed": 0,
                "total_spent_usd": 0.0,
                "success_rate": 0.0,
            }

        successful = [p for p in self.purchase_history if p.success]
        failed = [p for p in self.purchase_history if not p.success]
        total_spent = sum(p.price_usd for p in successful)

        return {
            "total_purchases": len(self.purchase_history),
            "successful": len(successful),
            "failed": len(failed),
            "total_spent_usd": total_spent,
            "success_rate": len(successful) / len(self.purchase_history) * 100,
            "dry_run_mode": self.config.dry_run,
        }

    def clear_history(self):
        """Clear purchase history."""
        self.purchase_history.clear()
        logger.info("purchase_history_cleared")

    async def _check_balance(self, required_usd: float) -> bool:
        """Check if there's enough balance for purchase.

        Args:
            required_usd: Required amount in USD

        Returns:
            True if balance is sufficient
        """
        try:
            balance = await self.api.get_balance()
            # DMarket API returns "usd" key in lowercase, value in cents
            available_cents = balance.get("usd", balance.get("USD", 0))
            available_usd = float(available_cents) / 100

            logger.debug(
                "balance_check",
                available=available_usd,
                required=required_usd,
            )

            if available_usd < required_usd:
                logger.warning(
                    "insufficient_balance",
                    available=available_usd,
                    required=required_usd,
                    deficit=required_usd - available_usd,
                )
                return False

            return True

        except Exception as e:
            logger.exception("balance_check_failed", error=str(e))
            # On error, assume balance is sufficient to not block purchases
            return True

    async def _schedule_auto_sell(
        self,
        item_id: str,
        item_title: str,
        buy_price: float,
        game: str = "csgo",
    ) -> bool:
        """Schedule item for automatic sale after purchase.

        This is the "bridge" function that connects auto-buyer with auto-seller.
        After a successful purchase, the item is automatically scheduled for sale
        with a target profit margin.

        Args:
            item_id: DMarket item ID
            item_title: Human-readable item name
            buy_price: Price paid for item in USD
            game: Game code (csgo, dota2, etc.)

        Returns:
            True if scheduled successfully
        """
        if not self._auto_seller:
            logger.debug("auto_seller_not_linked", item_id=item_id)
            return False

        try:
            # Schedule sale with auto-seller
            sale = await self._auto_seller.schedule_sale(
                item_id=item_id,
                item_name=item_title,
                buy_price=buy_price,
                game=game,
                immediate=False,  # Wait for item to appear in inventory
            )

            logger.info(
                "auto_sale_scheduled",
                item_id=item_id,
                item_title=item_title,
                buy_price=buy_price,
                target_margin=sale.target_margin,
                expected_sell_price=sale.list_price,
            )

            return True

        except ValueError as e:
            # Auto-sell disabled or max sales reached
            logger.warning("auto_sell_skipped", item_id=item_id, reason=str(e))
            return False

        except Exception as e:
            logger.exception("auto_sell_schedule_failed", item_id=item_id, error=str(e))
            return False

    async def _save_purchase_to_db(
        self,
        item_id: str,
        item_title: str,
        buy_price: float,
        game: str = "csgo",
    ) -> bool:
        """Save purchase to database for persistence.

        This is CRITICAL for surviving bot restarts. Without this,
        the bot would "forget" about purchases after shutdown.

        Args:
            item_id: DMarket item/asset ID
            item_title: Human-readable item name
            buy_price: Price paid for item in USD
            game: Game code (csgo, dota2, etc.)

        Returns:
            True if saved successfully
        """
        if not self._trading_persistence:
            logger.debug("trading_persistence_not_linked", item_id=item_id)
            return False

        try:
            await self._trading_persistence.save_purchase(
                asset_id=item_id,
                title=item_title,
                buy_price=buy_price,
                game=game,
            )

            logger.info(
                "purchase_persisted",
                item_id=item_id,
                item_title=item_title,
                buy_price=buy_price,
            )

            return True

        except Exception as e:
            logger.exception(
                "purchase_persistence_failed", item_id=item_id, error=str(e)
            )
            return False
