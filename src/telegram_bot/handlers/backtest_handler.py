"""Telegram handler for backtesting commands.

Provides commands for running and viewing backtests:
- /backtest <strategy> [days] - Run backtest
- /backtest_results - View recent results
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes

from src.analytics import (
    Backtester,
    BacktestResult,
    HistoricalDataCollector,
    SimpleArbitrageStrategy,
)

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI


logger = logging.getLogger(__name__)


class BacktestHandler:
    """Handler for backtesting Telegram commands.

    Provides user interface for running backtests and viewing results.
    """

    def __init__(
        self,
        api: IDMarketAPI | None = None,
        initial_balance: float = 100.0,
    ) -> None:
        """Initialize handler.

        Args:
            api: DMarket API client
            initial_balance: Default initial balance for backtests
        """
        self._api = api
        self._initial_balance = Decimal(str(initial_balance))
        self._recent_results: list[BacktestResult] = []

    def set_api(self, api: IDMarketAPI) -> None:
        """Set the API client.

        Args:
            api: DMarket API client
        """
        self._api = api

    async def handle_backtest_command(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle /backtest command.

        Args:
            update: Telegram update
            context: Callback context
        """
        if not update.message:
            return

        if not self._api:
            await update.message.reply_text("❌ API not configured")
            return

        # Parse arguments
        args = context.args or []
        days = 30  # Default

        if args:
            try:
                days = int(args[0])
                days = min(max(days, 7), 90)  # Limit 7-90 days
            except ValueError:
                pass

        keyboard = [
            [
                InlineKeyboardButton(
                    "📈 Simple Arbitrage",
                    callback_data=f"backtest:run:simple:{days}",
                ),
            ],
            [
                InlineKeyboardButton(
                    "📊 View Results",
                    callback_data="backtest:results",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⚙️ Settings",
                    callback_data="backtest:settings",
                ),
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"🔬 *Backtesting*\n\n"
            f"Period: {days} days\n"
            f"Initial Balance: ${float(self._initial_balance):.2f}\n\n"
            f"Select a strategy to test:",
            reply_markup=reply_markup,
            parse_mode="Markdown",
        )

    async def handle_callback(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
    ) -> None:
        """Handle backtest callback queries.

        Args:
            update: Telegram update
            context: Callback context
        """
        query = update.callback_query
        if not query or not query.data:
            return

        await query.answer()

        data = query.data
        if data.startswith("backtest:run:"):
            parts = data.split(":")
            strategy = parts[2]
            days = int(parts[3]) if len(parts) > 3 else 30
            await self._run_backtest(query, strategy, days)
        elif data == "backtest:results":
            await self._show_results(query)
        elif data == "backtest:settings":
            await self._show_settings(query)
        elif data.startswith("backtest:balance:"):
            balance = float(data.split(":")[-1])
            self._initial_balance = Decimal(str(balance))
            await self._show_settings(query)

    async def _run_backtest(
        self,
        query,
        strategy_name: str,
        days: int,
    ) -> None:
        """Run a backtest.

        Args:
            query: Callback query
            strategy_name: Name of strategy to run
            days: Number of days to backtest
        """
        if not self._api:
            await query.edit_message_text("❌ API not configured")
            return

        await query.edit_message_text(
            f"⏳ Running backtest...\n\n"
            f"Strategy: {strategy_name}\n"
            f"Period: {days} days\n\n"
            f"This may take a moment..."
        )

        try:
            # Initialize components
            collector = HistoricalDataCollector(self._api)
            backtester = Backtester(fee_rate=0.07)

            # Select strategy
            if strategy_name == "simple":
                strategy = SimpleArbitrageStrategy(
                    buy_threshold=0.05,
                    sell_margin=0.08,
                    max_position_pct=0.1,
                )
            else:
                strategy = SimpleArbitrageStrategy()

            # Collect sample items for testing
            # In production, this would come from user's watchlist or popular items
            sample_items = [
                "AK-47 | Redline (Field-Tested)",
                "AWP | Asiimov (Field-Tested)",
                "M4A1-S | Hyper Beast (Field-Tested)",
            ]

            # Collect historical data
            price_histories = await collector.collect_batch(
                game="csgo",
                titles=sample_items,
                days=days,
            )

            # Run backtest
            end_date = datetime.now(UTC)
            start_date = end_date - timedelta(days=days)

            result = await backtester.run(
                strategy=strategy,
                price_histories=price_histories,
                start_date=start_date,
                end_date=end_date,
                initial_balance=self._initial_balance,
            )

            # Store result
            self._recent_results.append(result)
            if len(self._recent_results) > 10:
                self._recent_results.pop(0)

            # Display result
            await self._display_result(query, result)

        except Exception as e:
            logger.exception("backtest_error", extra={"error": str(e)})
            await query.edit_message_text(
                f"❌ Backtest failed: {e!s}\n\nPlease try again later.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("« Back", callback_data="backtest:back")]]
                ),
            )

    async def _display_result(
        self,
        query,
        result: BacktestResult,
    ) -> None:
        """Display backtest result.

        Args:
            query: Callback query
            result: Backtest result
        """
        # Format profit/loss
        profit_str = (
            f"+${float(result.total_profit):.2f}"
            if result.total_profit >= 0
            else f"-${abs(float(result.total_profit)):.2f}"
        )
        profit_emoji = "📈" if result.total_profit >= 0 else "📉"

        text = (
            f"🔬 *Backtest Results*\n\n"
            f"*Strategy:* {result.strategy_name}\n"
            f"*Period:* {result.start_date.strftime('%Y-%m-%d')} to "
            f"{result.end_date.strftime('%Y-%m-%d')}\n\n"
            f"*Performance:*\n"
            f"  Initial: ${float(result.initial_balance):.2f}\n"
            f"  Final: ${float(result.final_balance):.2f}\n"
            f"  {profit_emoji} Profit: {profit_str} ({result.total_return:.1f}%)\n\n"
            f"*Statistics:*\n"
            f"  Trades: {result.total_trades}\n"
            f"  Win Rate: {result.win_rate:.1f}%\n"
            f"  Max Drawdown: {float(result.max_drawdown):.1f}%\n"
            f"  Sharpe Ratio: {result.sharpe_ratio:.2f}\n\n"
            f"_Based on historical data - past performance does not guarantee future results._"
        )

        keyboard = [[InlineKeyboardButton("« Back", callback_data="backtest:back")]]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    async def _show_results(self, query) -> None:
        """Show recent backtest results."""
        if not self._recent_results:
            await query.edit_message_text(
                "📊 *Recent Results*\n\nNo backtests run yet.",
                reply_markup=InlineKeyboardMarkup(
                    [[InlineKeyboardButton("« Back", callback_data="backtest:back")]]
                ),
                parse_mode="Markdown",
            )
            return

        lines = ["📊 *Recent Backtest Results*\n"]
        for i, result in enumerate(reversed(self._recent_results[-5:]), 1):
            profit_str = (
                f"+${float(result.total_profit):.2f}"
                if result.total_profit >= 0
                else f"-${abs(float(result.total_profit)):.2f}"
            )
            lines.append(
                f"{i}. *{result.strategy_name}*\n"
                f"   {result.total_trades} trades | "
                f"{result.win_rate:.0f}% win | {profit_str}"
            )

        await query.edit_message_text(
            "\n".join(lines),
            reply_markup=InlineKeyboardMarkup(
                [[InlineKeyboardButton("« Back", callback_data="backtest:back")]]
            ),
            parse_mode="Markdown",
        )

    async def _show_settings(self, query) -> None:
        """Show backtest settings."""
        text = (
            f"⚙️ *Backtest Settings*\n\n"
            f"*Initial Balance:* ${float(self._initial_balance):.2f}\n\n"
            f"Select a new balance:"
        )

        keyboard = [
            [
                InlineKeyboardButton("$50", callback_data="backtest:balance:50"),
                InlineKeyboardButton("$100", callback_data="backtest:balance:100"),
                InlineKeyboardButton("$250", callback_data="backtest:balance:250"),
            ],
            [
                InlineKeyboardButton("$500", callback_data="backtest:balance:500"),
                InlineKeyboardButton("$1000", callback_data="backtest:balance:1000"),
            ],
            [InlineKeyboardButton("« Back", callback_data="backtest:back")],
        ]

        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )

    def get_handlers(self) -> list:
        """Get list of handlers for registration.

        Returns:
            List of handler objects
        """
        return [
            CommandHandler("backtest", self.handle_backtest_command),
            CallbackQueryHandler(
                self.handle_callback,
                pattern=r"^backtest:",
            ),
        ]


__all__ = [
    "BacktestHandler",
]
