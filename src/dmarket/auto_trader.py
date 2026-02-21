"""Refactored auto trading module with improved readability.

This module implements automatic trading logic with:
- Early returns pattern for reduced nesting
- Smaller focused functions (< 50 lines each)
- Clear separation of concerns
- Better error handling

Phase 2 Refactoring (January 1, 2026)
"""

import asyncio
import logging
from typing import Any

from src.dmarket.arbitrage import ArbitrageTrader

logger = logging.getLogger(__name__)

__all__ = [
    "AutoTrader",
    "RiskConfig",
    "TradeResult",
]


class RiskConfig:
    """Risk management configuration for trading."""

    def __init__(
        self,
        level: str,
        max_trades: int,
        max_price: float,
        min_profit: float,
        balance: float,
    ):
        """Initialize risk configuration.

        Args:
            level: Risk level (low, medium, high)
            max_trades: Maximum number of trades
            max_price: Maximum price per item
            min_profit: Minimum profit threshold
            balance: Available balance
        """
        self.level = level
        self.max_trades = max_trades
        self.max_price = max_price
        self.min_profit = min_profit
        self.balance = balance

    @classmethod
    def from_level(
        cls,
        level: str,
        max_trades: int,
        max_price: float,
        min_profit: float,
        balance: float,
    ) -> "RiskConfig":
        """Create risk config based on risk level.

        Args:
            level: Risk level (low, medium, high)
            max_trades: Initial max trades
            max_price: Initial max price
            min_profit: Initial min profit
            balance: Available balance

        Returns:
            Configured RiskConfig instance
        """
        if level == "low":
            return cls(
                level=level,
                max_trades=min(max_trades, 2),
                max_price=min(max_price, 20.0),
                min_profit=max(min_profit, 1.0),
                balance=balance,
            )

        if level == "medium":
            return cls(
                level=level,
                max_trades=min(max_trades, 5),
                max_price=min(max_price, 50.0),
                min_profit=min_profit,
                balance=balance,
            )

        # high risk
        return cls(
            level=level,
            max_trades=max_trades,
            max_price=min(max_price, balance * 0.8),
            min_profit=min_profit,
            balance=balance,
        )


class TradeResult:
    """Result of auto trading session."""

    def __init__(self):
        """Initialize trade result."""
        self.purchases = 0
        self.sales = 0
        self.total_profit = 0.0
        self.trades_count = 0
        self.remaining_balance = 0.0

    def add_purchase(self, price: float) -> None:
        """Record successful purchase.

        Args:
            price: Purchase price in USD
        """
        self.purchases += 1
        self.remaining_balance -= price

    def add_sale(self, profit: float) -> None:
        """Record successful sale.

        Args:
            profit: Profit from sale in USD
        """
        self.sales += 1
        self.total_profit += profit

    def increment_trades(self) -> None:
        """Increment trade counter."""
        self.trades_count += 1

    def to_tuple(self) -> tuple[int, int, float]:
        """Convert to tuple format.

        Returns:
            Tuple of (purchases, sales, total_profit)
        """
        return self.purchases, self.sales, self.total_profit


class AutoTrader:
    """Automatic trading engine with risk management."""

    def __init__(self, scanner):
        """Initialize auto trader.

        Args:
            scanner: ArbitrageScanner instance
        """
        self.scanner = scanner

    async def auto_trade_items(
        self,
        items_by_game: dict[str, list[dict[str, Any]]],
        min_profit: float | None = None,
        max_price: float | None = None,
        max_trades: int | None = None,
        risk_level: str = "medium",
    ) -> tuple[int, int, float]:
        """Execute automatic trading with risk management.

        Args:
            items_by_game: Items grouped by game
            min_profit: Minimum profit in USD
            max_price: Maximum purchase price in USD
            max_trades: Maximum number of trades
            risk_level: Risk level (low, medium, high)

        Returns:
            Tuple of (purchases, sales, total_profit)
        """
        # Set defaults
        min_profit = min_profit or self.scanner.min_profit
        max_price = max_price or self.scanner.max_price
        max_trades = max_trades or self.scanner.max_trades

        # Check balance
        balance_data = await self.scanner.check_user_balance()
        if not self._has_sufficient_balance(balance_data):
            return 0, 0, 0.0

        balance = balance_data["balance"]

        # Configure risk management
        risk_config = RiskConfig.from_level(
            level=risk_level,
            max_trades=max_trades,
            max_price=max_price,
            min_profit=min_profit,
            balance=balance,
        )

        self._log_trading_params(risk_config)

        # Setup trader
        api_client = await self.scanner.get_api_client()
        trader = self._setup_trader(risk_config, api_client)

        # Prepare items
        sorted_items = self._prepare_items_for_trading(items_by_game)

        # Execute trades
        result = await self._execute_trades(
            sorted_items=sorted_items,
            risk_config=risk_config,
            trader=trader,
            api_client=api_client,
        )

        # Update statistics
        self._update_statistics(result)

        return result.to_tuple()

    def _has_sufficient_balance(self, balance_data: dict) -> bool:
        """Check if user has sufficient balance.

        Args:
            balance_data: Balance information

        Returns:
            True if balance is sufficient
        """
        balance = balance_data.get("balance", 0.0)
        has_funds = balance_data.get("has_funds", False)

        if not has_funds or balance < 1.0:
            logger.warning(
                f"Auto-trading impossible: insufficient funds (${balance:.2f})"
            )
            return False

        return True

    def _log_trading_params(self, config: RiskConfig):
        """Log trading parameters.

        Args:
            config: Risk configuration
        """
        logger.info(
            f"Trading params: risk={config.level}, balance=${config.balance:.2f}, "
            f"max_trades={config.max_trades}, max_price=${config.max_price:.2f}"
        )

    def _setup_trader(self, config: RiskConfig, api_client) -> ArbitrageTrader:
        """Setup arbitrage trader with limits.

        Args:
            config: Risk configuration
            api_client: API client instance

        Returns:
            Configured ArbitrageTrader
        """
        trader = ArbitrageTrader(api_client=self.scanner.api_client)
        trader.set_trading_limits(
            max_trade_value=config.max_price,
            daily_limit=config.balance * 0.9,  # Use max 90% of balance
        )
        return trader

    def _prepare_items_for_trading(
        self,
        items_by_game: dict[str, list[dict[str, Any]]],
    ) -> list[dict[str, Any]]:
        """Prepare and sort items for trading.

        Args:
            items_by_game: Items grouped by game

        Returns:
            Sorted list of items by profitability
        """
        all_items = []
        for game_code, items in items_by_game.items():
            for item in items:
                item["game"] = game_code
                all_items.append(item)

        # Sort by profit (highest first)
        return sorted(
            all_items,
            key=lambda x: x.get("profit", 0),
            reverse=True,
        )

    async def _execute_trades(
        self,
        sorted_items: list[dict[str, Any]],
        risk_config: RiskConfig,
        trader: ArbitrageTrader,
        api_client,
    ) -> TradeResult:
        """Execute trades for sorted items.

        Args:
            sorted_items: Items sorted by profitability
            risk_config: Risk configuration
            trader: ArbitrageTrader instance
            api_client: API client instance

        Returns:
            TradeResult with statistics
        """
        result = TradeResult()
        result.remaining_balance = risk_config.balance

        for item in sorted_items:
            # Check limits
            if not self._should_continue_trading(result, risk_config):
                break

            # Validate item
            if not self._is_item_suitable(item, risk_config, result):
                continue

            # Execute trade
            await self._trade_item(item, risk_config, result, api_client)

        self._log_trading_summary(result)
        return result

    def _should_continue_trading(
        self,
        result: TradeResult,
        config: RiskConfig,
    ) -> bool:
        """Check if should continue trading.

        Args:
            result: Current trade result
            config: Risk configuration

        Returns:
            True if should continue
        """
        if result.trades_count >= config.max_trades:
            logger.info(f"Trade limit reached ({config.max_trades})")
            return False

        if result.remaining_balance < 1.0:
            logger.info("Insufficient balance to continue trading")
            return False

        return True

    def _is_item_suitable(
        self,
        item: dict[str, Any],
        config: RiskConfig,
        result: TradeResult,
    ) -> bool:
        """Check if item is suitable for trading.

        Args:
            item: Item to check
            config: Risk configuration
            result: Current trade result

        Returns:
            True if item is suitable
        """
        buy_price = item.get("price", {}).get("amount", 0) / 100.0
        profit = item.get("profit", 0)
        title = item.get("title", "")

        if buy_price > config.max_price:
            logger.debug(
                f"Item '{title}' skipped: price ${buy_price:.2f} > limit ${config.max_price:.2f}"
            )
            return False

        if profit < config.min_profit:
            logger.debug(
                f"Item '{title}' skipped: profit ${profit:.2f} < min ${config.min_profit:.2f}"
            )
            return False

        if buy_price > result.remaining_balance:
            logger.debug(
                f"Item '{title}' skipped: price ${buy_price:.2f} > balance ${result.remaining_balance:.2f}"
            )
            return False

        return True

    async def _trade_item(
        self,
        item: dict[str, Any],
        config: RiskConfig,
        result: TradeResult,
        api_client,
    ):
        """Execute trade for single item.

        Args:
            item: Item to trade
            config: Risk configuration
            result: Trade result to update
            api_client: API client instance
        """
        try:
            buy_price = item.get("price", {}).get("amount", 0) / 100.0
            profit = item.get("profit", 0)
            title = item.get("title", "")
            item_id = item.get("itemId", "")
            game = item.get("game", "csgo")

            # Get current item data
            updated_item = await self.scanner._get_current_item_data(
                item_id=item_id,
                game=game,
                api_client=api_client,
            )

            if not self._is_price_acceptable(updated_item, buy_price, title):
                return

            # Purchase item
            purchase_result = await self._purchase_item_safe(
                item_id=item_id,
                buy_price=buy_price,
                title=title,
                api_client=api_client,
            )

            if not purchase_result:
                result.increment_trades()
                return

            # Record purchase
            result.add_purchase(buy_price)
            logger.info(f"Successfully purchased '{title}' for ${buy_price:.2f}")

            # List for sale
            await self._sell_item(
                item_id=purchase_result.get("new_item_id", ""),
                buy_price=buy_price,
                profit=profit,
                title=title,
                result=result,
                api_client=api_client,
            )

            result.increment_trades()

            # Pause between trades
            await asyncio.sleep(1.0)

        except Exception as e:
            logger.exception(f"Error trading item '{item.get('title', '')}': {e!s}")
            result.increment_trades()

    def _is_price_acceptable(
        self,
        updated_item: dict | None,
        original_price: float,
        title: str,
    ) -> bool:
        """Check if current price is acceptable.

        Args:
            updated_item: Updated item data
            original_price: Original buy price
            title: Item title

        Returns:
            True if price is acceptable
        """
        if not updated_item:
            logger.warning(f"Item '{title}' unavailable (not found)")
            return False

        current_price = updated_item.get("price", original_price)
        if current_price > original_price * 1.05:  # Price increased > 5%
            logger.warning(
                f"Item '{title}' skipped: price increased from "
                f"${original_price:.2f} to ${current_price:.2f}"
            )
            return False

        return True

    async def _purchase_item_safe(
        self,
        item_id: str,
        buy_price: float,
        title: str,
        api_client,
    ) -> dict | None:
        """Safely purchase item with error handling.

        Args:
            item_id: Item ID
            buy_price: Buy price
            title: Item title
            api_client: API client

        Returns:
            Purchase result or None if failed
        """
        purchase_result = await self.scanner._purchase_item(
            item_id=item_id,
            max_price=buy_price * 1.02,  # Allow small price increase
            api_client=api_client,
        )

        if not purchase_result.get("success", False):
            error = purchase_result.get("error", "Unknown error")
            logger.warning(f"Failed to purchase '{title}': {error}")
            return None

        return purchase_result

    async def _sell_item(
        self,
        item_id: str,
        buy_price: float,
        profit: float,
        title: str,
        result: TradeResult,
        api_client,
    ):
        """List item for sale.

        Args:
            item_id: Item ID
            buy_price: Purchase price
            profit: Expected profit
            title: Item title
            result: Trade result to update
            api_client: API client
        """
        sell_price = buy_price + profit
        sell_result = await self.scanner._list_item_for_sale(
            item_id=item_id,
            price=sell_price,
            api_client=api_client,
        )

        if sell_result.get("success", False):
            result.add_sale(profit)
            logger.info(
                f"Item '{title}' listed for sale at ${sell_price:.2f} (profit ${profit:.2f})"
            )
        else:
            error = sell_result.get("error", "Unknown error")
            logger.warning(f"Failed to list item '{title}' for sale: {error}")

    def _update_statistics(self, result: TradeResult):
        """Update scanner statistics.

        Args:
            result: Trade result
        """
        self.scanner.successful_trades += result.sales
        self.scanner.total_profit += result.total_profit

    def _log_trading_summary(self, result: TradeResult):
        """Log trading session summary.

        Args:
            result: Trade result
        """
        logger.info(
            f"Trading summary: purchased {result.purchases}, "
            f"listed {result.sales}, expected profit ${result.total_profit:.2f}"
        )
