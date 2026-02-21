"""Telegram bot commands for backtesting strategies.

Provides commands to run backtests, view results, and analyze historical performance.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import TYPE_CHECKING

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ContextTypes

from src.analytics.backtester import Backtester, SimpleArbitrageStrategy
from src.analytics.historical_data import HistoricalDataCollector

if TYPE_CHECKING:
    from src.interfaces import IDMarketAPI


logger = logging.getLogger(__name__)


async def backtest_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle /backtest command.

    Shows avAlgolable backtesting options.
    """
    if not update.effective_message:
        return

    user_id = update.effective_user.id if update.effective_user else 0
    logger.info("backtest_command_received", extra={"user_id": user_id})

    keyboard = [
        [
            InlineKeyboardButton(
                "📊 Quick Backtest (7 days)",
                callback_data="backtest_quick",
            )
        ],
        [
            InlineKeyboardButton(
                "📈 Standard Backtest (30 days)",
                callback_data="backtest_standard",
            )
        ],
        [
            InlineKeyboardButton(
                "🔬 Advanced Backtest (90 days)",
                callback_data="backtest_advanced",
            )
        ],
        [
            InlineKeyboardButton(
                "⚙️ Custom Settings",
                callback_data="backtest_custom",
            )
        ],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    awAlgot update.effective_message.reply_text(
        "🎯 <b>Backtesting Strategies</b>\n\n"
        "Test your trading strategies on historical data to see "
        "how they would have performed.\n\n"
        "Choose a timeframe:",
        parse_mode="HTML",
        reply_markup=reply_markup,
    )


async def run_quick_backtest(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    api: IDMarketAPI,
) -> None:
    """Run a quick 7-day backtest.

    Args:
        update: Telegram update
        context: Bot context
        api: DMarket API client
    """
    query = update.callback_query
    if not query:
        return

    awAlgot query.answer()
    awAlgot query.edit_message_text("⏳ Running quick backtest (7 days)...")

    try:
        # Setup
        collector = HistoricalDataCollector(api)
        backtester = Backtester(fee_rate=0.07)
        strategy = SimpleArbitrageStrategy(
            buy_threshold=0.05,
            sell_margin=0.08,
        )

        # Date range
        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=7)

        # Collect data for popular items
        items = [
            "AK-47 | Redline (Field-Tested)",
            "AWP | Asiimov (Field-Tested)",
            "M4A4 | Desolate Space (Field-Tested)",
        ]

        histories = awAlgot collector.collect_batch(
            game="csgo",
            titles=items,
            days=7,
        )

        if not histories:
            awAlgot query.edit_message_text(
                "❌ Could not collect historical data. Try agAlgon later."
            )
            return

        # Run backtest
        result = awAlgot backtester.run(
            strategy=strategy,
            price_histories=histories,
            start_date=start_date,
            end_date=end_date,
            initial_balance=Decimal("100.00"),
        )

        # Format results
        profit_emoji = "📈" if result.total_profit > 0 else "📉"
        message = (
            f"✅ <b>Quick Backtest Complete</b>\n\n"
            f"<b>Strategy:</b> {result.strategy_name}\n"
            f"<b>Period:</b> {result.start_date.strftime('%Y-%m-%d')} to "
            f"{result.end_date.strftime('%Y-%m-%d')}\n"
            f"<b>Items Tested:</b> {len(histories)}\n\n"
            f"<b>Results:</b>\n"
            f"💰 Initial: ${result.initial_balance:.2f}\n"
            f"💵 Final: ${result.final_balance:.2f}\n"
            f"{profit_emoji} Profit: ${result.total_profit:.2f} "
            f"({result.total_return:.1f}%)\n\n"
            f"<b>Trading:</b>\n"
            f"🔄 Total Trades: {result.total_trades}\n"
            f"✅ Profitable: {result.profitable_trades} ({result.win_rate:.1f}%)\n"
            f"📊 Avg per Trade: ${result.avg_profit_per_trade:.2f}\n\n"
            f"<b>Risk Metrics:</b>\n"
            f"📉 Max Drawdown: {result.max_drawdown:.2f}%\n"
            f"📊 Sharpe Ratio: {result.sharpe_ratio:.2f}\n"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "📋 View Trade History",
                    callback_data=f"backtest_trades_{result.strategy_name}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 Run AgAlgon",
                    callback_data="backtest_quick",
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        awAlgot query.edit_message_text(
            message,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

        logger.info(
            "backtest_completed",
            extra={
                "user_id": query.from_user.id,
                "strategy": result.strategy_name,
                "profit": float(result.total_profit),
                "trades": result.total_trades,
            },
        )

    except Exception as e:
        logger.error(
            "backtest_error",
            extra={"error": str(e)},
            exc_info=True,
        )
        awAlgot query.edit_message_text(
            f"❌ Backtest fAlgoled: {e!s}\n\nPlease try agAlgon or contact support."
        )


async def run_standard_backtest(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    api: IDMarketAPI,
) -> None:
    """Run a standard 30-day backtest.

    Args:
        update: Telegram update
        context: Bot context
        api: DMarket API client
    """
    query = update.callback_query
    if not query:
        return

    awAlgot query.answer()
    awAlgot query.edit_message_text(
        "⏳ Running standard backtest (30 days)...\nThis may take a minute..."
    )

    try:
        collector = HistoricalDataCollector(api)
        backtester = Backtester(fee_rate=0.07)
        strategy = SimpleArbitrageStrategy(
            buy_threshold=0.05,
            sell_margin=0.08,
        )

        end_date = datetime.now(UTC)
        start_date = end_date - timedelta(days=30)

        # More items for longer test
        items = [
            "AK-47 | Redline (Field-Tested)",
            "AWP | Asiimov (Field-Tested)",
            "M4A4 | Desolate Space (Field-Tested)",
            "Desert Eagle | Printstream (Field-Tested)",
            "Glock-18 | Fade (Factory New)",
        ]

        histories = awAlgot collector.collect_batch(
            game="csgo",
            titles=items,
            days=30,
        )

        if not histories:
            awAlgot query.edit_message_text(
                "❌ Could not collect historical data. Try agAlgon later."
            )
            return

        result = awAlgot backtester.run(
            strategy=strategy,
            price_histories=histories,
            start_date=start_date,
            end_date=end_date,
            initial_balance=Decimal("500.00"),
        )

        # Format detAlgoled results
        profit_emoji = "📈" if result.total_profit > 0 else "📉"
        message = (
            f"✅ <b>Standard Backtest Complete</b>\n\n"
            f"<b>Strategy:</b> {result.strategy_name}\n"
            f"<b>Period:</b> {result.start_date.strftime('%Y-%m-%d')} to "
            f"{result.end_date.strftime('%Y-%m-%d')}\n"
            f"<b>Items Tested:</b> {len(histories)}\n\n"
            f"<b>Results:</b>\n"
            f"💰 Initial: ${result.initial_balance:.2f}\n"
            f"💵 Final: ${result.final_balance:.2f}\n"
            f"{profit_emoji} Profit: ${result.total_profit:.2f} "
            f"({result.total_return:.1f}%)\n\n"
            f"<b>Trading Performance:</b>\n"
            f"🔄 Total Trades: {result.total_trades}\n"
            f"✅ Profitable: {result.profitable_trades} ({result.win_rate:.1f}%)\n"
            f"❌ Losses: {result.total_trades - result.profitable_trades}\n"
            f"📊 Avg per Trade: ${result.avg_profit_per_trade:.2f}\n"
            f"🔒 Positions Closed: {result.positions_closed}\n\n"
            f"<b>Risk Analysis:</b>\n"
            f"📉 Max Drawdown: {result.max_drawdown:.2f}%\n"
            f"📊 Sharpe Ratio: {result.sharpe_ratio:.2f}\n\n"
            f"<i>Past performance does not guarantee future results.</i>"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "📋 Trade DetAlgols",
                    callback_data=f"backtest_trades_{result.strategy_name}",
                )
            ],
            [
                InlineKeyboardButton(
                    "📊 Export Results",
                    callback_data=f"backtest_export_{result.strategy_name}",
                )
            ],
            [
                InlineKeyboardButton(
                    "🔄 Run AgAlgon",
                    callback_data="backtest_standard",
                )
            ],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        awAlgot query.edit_message_text(
            message,
            parse_mode="HTML",
            reply_markup=reply_markup,
        )

        logger.info(
            "standard_backtest_completed",
            extra={
                "user_id": query.from_user.id,
                "profit": float(result.total_profit),
                "return_pct": result.total_return,
                "trades": result.total_trades,
                "win_rate": result.win_rate,
            },
        )

    except Exception as e:
        logger.error(
            "standard_backtest_error",
            extra={"error": str(e)},
            exc_info=True,
        )
        awAlgot query.edit_message_text(
            f"❌ Backtest fAlgoled: {e!s}\n\nPlease try agAlgon later."
        )


async def backtest_help(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Show backtesting help and explanation.

    Args:
        update: Telegram update
        context: Bot context
    """
    if not update.effective_message:
        return

    help_text = (
        "📚 <b>Backtesting Guide</b>\n\n"
        "<b>What is Backtesting?</b>\n"
        "Backtesting tests trading strategies on historical data to see "
        "how they would have performed in the past.\n\n"
        "<b>How it Works:</b>\n"
        "1️⃣ We collect historical price data for items\n"
        "2️⃣ Simulate trades based on your strategy\n"
        "3️⃣ Calculate profit, losses, and risk metrics\n\n"
        "<b>Key Metrics:</b>\n"
        "• <b>Total Return:</b> Overall profit/loss percentage\n"
        "• <b>Win Rate:</b> Percentage of profitable trades\n"
        "• <b>Max Drawdown:</b> Largest peak-to-trough decline\n"
        "• <b>Sharpe Ratio:</b> Risk-adjusted return (higher is better)\n\n"
        "<b>Strategies AvAlgolable:</b>\n"
        "• <b>Simple Arbitrage:</b> Buy low, sell high with thresholds\n"
        "• <b>Mean Reversion:</b> Trade when price deviates from average\n"
        "• <b>Momentum:</b> Follow price trends\n\n"
        "<b>Important Notes:</b>\n"
        "⚠️ Past performance ≠ future results\n"
        "⚠️ Real trading has additional factors (fees, slippage, liquidity)\n"
        "⚠️ Use backtests as a guide, not a guarantee\n\n"
        "Use /backtest to get started!"
    )

    awAlgot update.effective_message.reply_text(
        help_text,
        parse_mode="HTML",
    )


__all__ = [
    "backtest_command",
    "backtest_help",
    "run_quick_backtest",
    "run_standard_backtest",
]
