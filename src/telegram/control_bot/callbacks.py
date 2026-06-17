"""
callbacks.py — Inline-button callback handlers (btn:start, btn:stop, etc.)

Each handler responds to a specific callback_data and re-renders the message.
v13.2: Added portfolio, daily, analyze, sell_top callbacks with logging.
"""

import logging
import time
from typing import Optional

from aiogram import F, Router, types

from src.db.price_history import price_db

from .formatters import (
    format_balance,
    format_daily_summary,
    format_inventory_summary,
    format_portfolio_summary,
    format_profits_summary,
    format_status,
)
from .keyboards import (
    CB_ANALYZE,
    CB_BALANCE,
    CB_DAILY,
    CB_INVENTORY,
    CB_NOOP,
    CB_PORTFOLIO,
    CB_PROFITS,
    CB_REFRESH_STATUS,
    CB_SELL_TOP,
    CB_START,
    CB_STOP,
    get_inline_balance_kb,
    get_inline_daily_kb,
    get_inline_inventory_kb,
    get_inline_portfolio_kb,
    get_inline_profits_kb,
    get_inline_status_kb,
    get_inline_analyze_kb,
)
from .resilience import dmarket_client, fetch_balance_data, retry_async, safe_call
from .state import state

logger = logging.getLogger("TelegramControl.callbacks")
router = Router(name="telegram-control-callbacks")


@router.callback_query(F.data == CB_START)
@safe_call
async def cb_start(callback: types.CallbackQuery):
    if callback.message is None:
        return
    logger.info("cb_start triggered by admin %s", callback.from_user.id)
    await callback.message.answer("Use 🚀 START button or /start_bot command.")
    await callback.answer()


@router.callback_query(F.data == CB_STOP)
@safe_call
async def cb_stop(callback: types.CallbackQuery):
    if callback.message is None:
        return
    logger.info("cb_stop triggered by admin %s", callback.from_user.id)
    await callback.message.answer("Use 🛑 STOP button or /stop_bot command.")
    await callback.answer()


@router.callback_query(F.data == CB_BALANCE)
@safe_call
async def cb_balance(callback: types.CallbackQuery):
    if callback.message is None or not isinstance(callback.message, types.Message):
        return
    logger.info("cb_balance triggered")
    await callback.message.edit_text("💰 Fetching balance...")
    try:
        async with dmarket_client() as client:
            balance = await retry_async(
                lambda: client.get_real_balance(),
                operation="cb.balance",
            )
            equity = price_db.get_total_equity(balance)
            text = format_balance(balance, equity)
            await callback.message.edit_text(
                text, reply_markup=get_inline_balance_kb()
            )
            logger.debug("cb_balance ok — cash=%.2f available=%.2f", balance, equity["available"])
    except Exception as e:
        logger.exception("cb_balance error: %s", e)
        await callback.message.edit_text("❌ Error fetching balance. Check logs.")
    await callback.answer()


@router.callback_query(F.data == CB_INVENTORY)
@safe_call
async def cb_inventory(callback: types.CallbackQuery):
    if callback.message is None or not isinstance(callback.message, types.Message):
        return
    logger.info("cb_inventory triggered")
    idle = price_db.get_virtual_inventory(status='idle', only_unlocked=False)
    selling = price_db.get_virtual_inventory(status='selling')
    sold = price_db.get_virtual_inventory(status='sold')
    text = format_inventory_summary(idle, selling, sold, top_n=5)
    await callback.message.edit_text(
        text, reply_markup=get_inline_inventory_kb()
    )
    logger.debug("cb_inventory ok — idle=%d selling=%d sold=%d", len(idle), len(selling), len(sold))
    await callback.answer()


@router.callback_query(F.data == CB_PROFITS)
@safe_call
async def cb_profits(callback: types.CallbackQuery):
    if callback.message is None or not isinstance(callback.message, types.Message):
        return
    logger.info("cb_profits triggered")
    sold = price_db.get_virtual_inventory(status='sold')
    idle = price_db.get_virtual_inventory(status='idle', only_unlocked=True)
    text = format_profits_summary(sold, idle, [], detailed=False)
    await callback.message.edit_text(
        text, reply_markup=get_inline_profits_kb()
    )
    logger.debug("cb_profits ok — sold=%d idle=%d", len(sold), len(idle))
    await callback.answer()


@router.callback_query(F.data == CB_PORTFOLIO)
@safe_call
async def cb_portfolio(callback: types.CallbackQuery):
    if callback.message is None or not isinstance(callback.message, types.Message):
        return
    logger.info("cb_portfolio triggered")
    try:
        equity = price_db.get_total_equity(0.0)
        sold = price_db.get_virtual_inventory(status='sold')
        text = format_portfolio_summary(equity, sold)
        await callback.message.edit_text(
            text, reply_markup=get_inline_portfolio_kb()
        )
        logger.debug("cb_portfolio ok — total=%.2f frozen=%.2f", equity["total"], equity.get("frozen", 0))
    except Exception as e:
        logger.exception("cb_portfolio error: %s", e)
        await callback.message.edit_text("❌ Error loading portfolio. Check logs.")
    await callback.answer()


@router.callback_query(F.data == CB_DAILY)
@safe_call
async def cb_daily(callback: types.CallbackQuery):
    if callback.message is None or not isinstance(callback.message, types.Message):
        return
    logger.info("cb_daily triggered")
    try:
        now = time.time()
        day_start = now - 86400
        sold_today = price_db.get_recent_sales(day_start)
        today_pnl = sum(it["profit"] or 0 for it in sold_today)
        today_trades = len(sold_today)
        today_wins = sum(1 for it in sold_today if (it["profit"] or 0) > 0)
        equity = price_db.get_total_equity(0.0)
        text = format_daily_summary(
            today_pnl, today_trades, today_wins,
            equity["total"], equity["assets"], equity.get("frozen", 0),
        )
        await callback.message.edit_text(
            text, reply_markup=get_inline_daily_kb()
        )
        logger.debug("cb_daily ok — pnl=%.2f trades=%d frozen=%.2f",
                      today_pnl, today_trades, equity.get("frozen", 0))
    except Exception as e:
        logger.exception("cb_daily error: %s", e)
        await callback.message.edit_text("❌ Error loading daily briefing. Check logs.")
    await callback.answer()


@router.callback_query(F.data == CB_ANALYZE)
@safe_call
async def cb_analyze(callback: types.CallbackQuery):
    if callback.message is None or not isinstance(callback.message, types.Message):
        return
    logger.info("cb_analyze triggered")
    await callback.message.edit_text("🧠 Running analysis...")
    try:
        from src.analytics.self_reflection import self_reflection
        report = await self_reflection.analyze_recent_trades()
        if report:
            text = (
                f"🧠 *Strategy Analysis*\n\n"
                f"Sharpe: {report.get('sharpe_ratio', 0):.2f}\n"
                f"Sortino: {report.get('sortino_ratio', 0):.2f}\n"
                f"Max Drawdown: {report.get('max_drawdown_pct', 0):.1f}%\n"
                f"Win Rate: {report.get('win_rate', 0):.1f}%\n"
                f"Total Trades: {report.get('total_trades', 0)}\n"
                f"Avg Profit/Trade: {report.get('avg_profit', 0):+.2f}\n\n"
                f"Recommendations:\n{report.get('recommendations', 'None')}"
            )
        else:
            text = "🧠 *Analysis* — Not enough trade data yet.\nMinimum 10 trades required."
        await callback.message.edit_text(
            text, reply_markup=get_inline_analyze_kb()
        )
        logger.debug("cb_analyze ok — report_available=%s", bool(report))
    except Exception as e:
        logger.exception("cb_analyze error: %s", e)
        await callback.message.edit_text("❌ Analysis failed. Check logs.")
    await callback.answer()


@router.callback_query(F.data == CB_SELL_TOP)
@safe_call
async def cb_sell_top(callback: types.CallbackQuery):
    if callback.message is None or not isinstance(callback.message, types.Message):
        return
    logger.info("cb_sell_top triggered")
    await callback.message.edit_text("🔍 Finding items to sell...")
    try:
        from src.core.resale_pipeline import ResalePipeline
        async with dmarket_client() as client:
            pipeline = ResalePipeline(client)
            result = await pipeline.sell_inventory_items(max_items=5)
            listed_count = len(result) if isinstance(result, list) else (result if isinstance(result, int) else 0)
            if listed_count > 0:
                text = f"🔍 *Sell Complete*\n\nListed {result} item(s) for sale."
            else:
                text = "🔍 *Sell* — No idle items to list or all are trade-locked."
            await callback.message.edit_text(text)
            logger.info("cb_sell_top ok — listed=%s", result)
    except Exception as e:
        logger.exception("cb_sell_top error: %s", e)
        await callback.message.edit_text("❌ Sell failed. Check logs.")
    await callback.answer()


@router.callback_query(F.data == CB_REFRESH_STATUS)
@safe_call
async def cb_refresh_status(callback: types.CallbackQuery):
    if callback.message is None or not isinstance(callback.message, types.Message):
        return
    logger.info("cb_refresh_status triggered")
    st = await state.status()
    is_running = st["is_running"]
    balance_data = await fetch_balance_data()
    text = format_status(is_running, balance_data)
    await callback.message.edit_text(
        text, reply_markup=get_inline_status_kb(is_running)
    )
    logger.debug("cb_refresh_status ok — running=%s", is_running)
    await callback.answer()


@router.callback_query(F.data == CB_NOOP)
@safe_call
async def cb_noop(callback: types.CallbackQuery):
    """No-op for buttons that reflect state (e.g., '🟡 RUNNING' shows but does nothing)."""
    await callback.answer()
