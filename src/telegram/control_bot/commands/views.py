"""
views.py — Read-only info commands: balance, status, inventory, profits,
portfolio, daily briefing, analysis, prices, sell-top.

v13.2: Added portfolio, daily, analyze, prices, sell-top with logging.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command

from src.db.price_history import price_db

from ..formatters import (
    format_balance,
    format_daily_summary,
    format_inventory_summary,
    format_portfolio_summary,
    format_profits_summary,
    format_status,
)
from ..keyboards import (
    BTN_ANALYZE,
    BTN_CLOCK,
    BTN_DAILY,
    BTN_PORTFOLIO,
    BTN_PRICES,
    BTN_REFRESH,
    BTN_SELL_TOP,
    BTN_TEST,
    get_inline_analyze_kb,
    get_inline_balance_kb,
    get_inline_daily_kb,
    get_inline_inventory_kb,
    get_inline_portfolio_kb,
    get_inline_profits_kb,
    get_inline_status_kb,
)
from ..resilience import dmarket_client, fetch_balance_data, retry_async, safe_call
from ..state import state

logger = logging.getLogger("TelegramControl.commands.views")
router = Router(name="telegram-control-views")


# ============================================================
# Info: balance / status / inventory / profits
# ============================================================
@router.message(Command("balance"))
@router.message(F.text == "💰 BALANCE")
@safe_call
async def cmd_balance(message):
    logger.info("cmd_balance by user %s", message.from_user.id)
    async with dmarket_client() as client:
        balance = await retry_async(
            lambda: client.get_real_balance(),
            operation="balance",
        )
        equity = price_db.get_total_equity(balance)
        await message.answer(
            format_balance(balance, equity),
            reply_markup=get_inline_balance_kb(),
        )
        logger.debug("cmd_balance ok — cash=%.2f available=%.2f frozen=%.2f",
                      balance, equity["available"], equity.get("frozen", 0))


@router.message(Command("status"))
@router.message(F.text == "📊 STATUS")
@safe_call
async def cmd_status(message):
    logger.info("cmd_status by user %s", message.from_user.id)
    st = await state.status()
    is_running = st["is_running"]
    balance_data = await fetch_balance_data()
    await message.answer(
        format_status(is_running, balance_data),
        reply_markup=get_inline_status_kb(is_running),
    )
    logger.debug("cmd_status ok — running=%s", is_running)


@router.message(Command("inventory"))
@router.message(F.text == "📦 INVENTORY")
@safe_call
async def cmd_inventory(message):
    logger.info("cmd_inventory by user %s", message.from_user.id)
    idle = price_db.get_virtual_inventory(status="idle", only_unlocked=False)
    selling = price_db.get_virtual_inventory(status="selling")
    sold = price_db.get_virtual_inventory(status="sold")
    await message.answer(
        format_inventory_summary(idle, selling, sold),
        reply_markup=get_inline_inventory_kb(),
    )
    logger.debug("cmd_inventory ok — idle=%d selling=%d sold=%d", len(idle), len(selling), len(sold))


@router.message(Command("profits"))
@router.message(F.text == "📈 PROFITS")
@safe_call
async def cmd_profits(message):
    logger.info("cmd_profits by user %s", message.from_user.id)
    sold = price_db.get_virtual_inventory(status="sold")
    idle = price_db.get_virtual_inventory(status="idle", only_unlocked=True)
    selling = price_db.get_virtual_inventory(status="selling")
    await message.answer(
        format_profits_summary(sold, idle, selling, detailed=True),
        reply_markup=get_inline_profits_kb(),
    )
    logger.debug("cmd_profits ok — sold=%d idle=%d", len(sold), len(idle))


# ============================================================
# Portfolio / Daily / Analyze
# ============================================================
@router.message(Command("portfolio"))
@router.message(F.text == BTN_PORTFOLIO)
@safe_call
async def cmd_portfolio(message):
    logger.info("cmd_portfolio by user %s", message.from_user.id)
    equity = price_db.get_total_equity(0.0)
    sold = price_db.get_virtual_inventory(status="sold")
    await message.answer(
        format_portfolio_summary(equity, sold),
        reply_markup=get_inline_portfolio_kb(),
    )
    logger.debug("cmd_portfolio ok — total=%.2f frozen=%.2f",
                  equity["total"], equity.get("frozen", 0))


@router.message(Command("daily"))
@router.message(F.text == BTN_DAILY)
@safe_call
async def cmd_daily(message):
    logger.info("cmd_daily by user %s", message.from_user.id)
    now = time.time()
    day_start = now - 86400
    sold_today = price_db.get_recent_sales(day_start)
    today_pnl = sum(it["profit"] or 0 for it in sold_today)
    today_trades = len(sold_today)
    today_wins = sum(1 for it in sold_today if (it["profit"] or 0) > 0)
    equity = price_db.get_total_equity(0.0)
    await message.answer(
        format_daily_summary(today_pnl, today_trades, today_wins,
                             equity["total"], equity["assets"],
                             equity.get("frozen", 0)),
        reply_markup=get_inline_daily_kb(),
    )
    logger.debug("cmd_daily ok — pnl=%.2f trades=%d frozen=%.2f",
                  today_pnl, today_trades, equity.get("frozen", 0))


@router.message(Command("analyze"))
@router.message(F.text == BTN_ANALYZE)
@safe_call
async def cmd_analyze(message):
    logger.info("cmd_analyze by user %s", message.from_user.id)
    try:
        from src.analytics.self_reflection import self_reflection
        report = await self_reflection.analyze_recent_trades()
        if report:
            text = (
                f"🧠 *Strategy Analysis*\n\n"
                f"Sharpe: {getattr(report, 'sharpe_ratio', 0):.2f}\n"
                f"Sortino: {getattr(report, 'sortino_ratio', 0):.2f}\n"
                f"Max Drawdown: {getattr(report, 'max_drawdown_pct', 0):.1f}%\n"
                f"Win Rate: {getattr(report, 'win_rate', 0):.1f}%\n"
                f"Total Trades: {getattr(report, 'total_trades', 0)}\n"
                f"Avg Profit/Trade: {getattr(report, 'avg_profit', 0):+.2f}\n\n"
                f"Recommendations:\n{getattr(report, 'recommendations', 'None')}\n\n"
                f"_Minimum 10 trades for adjustments._"
            )
        else:
            text = "🧠 *Strategy Analysis* — Not enough trade data yet.\nMinimum 10 trades required."
        await message.answer(text, reply_markup=get_inline_analyze_kb())
        logger.debug("cmd_analyze ok — report=%s", bool(report))
    except Exception as e:
        logger.exception("cmd_analyze failed: %s", e)
        await message.answer("❌ Analysis failed. Check logs.")


# ============================================================
# Sell-Top
# ============================================================
@router.message(Command("sell"))
@router.message(F.text == BTN_SELL_TOP)
@safe_call
async def cmd_sell_top(message):
    logger.info("cmd_sell_top by user %s", message.from_user.id)
    try:
        from src.core.resale_pipeline import ResalePipeline
        async with dmarket_client() as client:
            pipeline = ResalePipeline(client)
            result = await pipeline.sell_inventory_items(max_items=5)
            listed_count = len(result) if isinstance(result, list) else (result if isinstance(result, int) else 0)
            if listed_count > 0:
                text = f"🔍 *Sell Complete*\n\nListed {listed_count} item(s) for sale."
            else:
                text = "🔍 *Sell* — No idle items to list or all are trade-locked."
            await message.answer(text)
            logger.info("cmd_sell_top ok — listed=%s items", result)
    except Exception as e:
        logger.exception("cmd_sell_top failed: %s", e)
        await message.answer("❌ Sell failed. Check logs.")


# ============================================================
# Prices — CS2Cap price check for held items
# ============================================================
@router.message(Command("prices"))
@router.message(F.text == BTN_PRICES)
@safe_call
async def cmd_prices(message):
    logger.info("cmd_prices by user %s", message.from_user.id)
    try:
        from src.api.cs2cap_oracle import CS2CapOracle
        from src.api.oracle_factory import OracleFactory
        idle = price_db.get_virtual_inventory(status="idle", only_unlocked=False)
        if not idle:
            await message.answer("📊 *Prices* — No items in inventory.")
            return
        oracle = OracleFactory.get_oracle("a8db")
        if oracle is None:
            await message.answer("📊 *Prices* — CS2Cap oracle unavailable.")
            return
        text = "📊 *CS2Cap Prices* (41 marketplaces)\n\n"
        for it in list(idle)[:10]:
            title = it["hash_name"]
            try:
                cs_price = await oracle.get_item_price(title)
                buy_price = it["buy_price"]
                if cs_price > 0:
                    margin = (cs_price - buy_price) / buy_price * 100 if buy_price > 0 else 0
                    text += f"`{title[:25]}`\n  Buy: ${buy_price:.2f} → CS2Cap: ${cs_price:.2f} ({margin:+.1f}%)\n"
                else:
                    text += f"`{title[:25]}` — no CS2Cap data\n"
            except Exception:
                text += f"`{title[:25]}` — error fetching\n"
        await message.answer(text)
        logger.debug("cmd_prices ok — checked %d items", len(idle[:10]))
    except Exception as e:
        logger.exception("cmd_prices failed: %s", e)
        await message.answer("❌ Price check failed. Check logs.")


# ============================================================
# Charts (v14.5)
# ============================================================
@router.message(Command("chart"))
@router.message(F.text == "📈 CHART")
async def cmd_chart(message):
    """Send equity curve chart."""
    try:
        from src.utils.charts import generate_equity_chart
        buf = generate_equity_chart(days=30)
        if buf is None:
            await message.answer("📈 Not enough data for equity chart yet. Build some trade history first.")
            return
        from aiogram.types import BufferedInputFile
        await message.answer_photo(
            BufferedInputFile(buf.read(), "equity_chart.png"),
            caption="📈 *Equity Curve* (30 days)",
        )
    except Exception as e:
        logger.exception("cmd_chart failed: %s", e)
        await message.answer("❌ Chart generation failed. Check matplotlib availability.")


@router.message(Command("pnl"))
@router.message(F.text == "📊 PNL")
async def cmd_pnl_chart(message):
    """Send daily P&L chart."""
    try:
        from src.utils.charts import generate_pnl_chart
        buf = generate_pnl_chart(days=30)
        if buf is None:
            await message.answer("📊 Not enough P&L history yet.")
            return
        from aiogram.types import BufferedInputFile
        await message.answer_photo(
            BufferedInputFile(buf.read(), "pnl_chart.png"),
            caption="📊 *Daily P&L* (30 days)",
        )
    except Exception as e:
        logger.exception("cmd_pnl_chart failed: %s", e)
        await message.answer("❌ Chart generation failed.")


# ============================================================
# Live Shadow (v14.5)
# ============================================================
@router.message(Command("shadow"))
async def cmd_shadow(message):
    """Show live shadow trading status + real-vs-shadow comparison."""
    try:
        from src.core.live_shadow import live_shadow

        if not live_shadow.enabled:
            await message.answer("🕶️ *Shadow mode is disabled.* Set `LIVE_SHADOW_ENABLED=true` in `.env`")
            return

        status = live_shadow.get_status()
        text = (
            f"🕶️ *Live Shadow Trading*\n\n"
            f"Cycles: {status['cycles']} | Balance: ${status['balance']:.2f}\n"
            f"Total Equity: ${status['total_equity']:.2f}\n"
            f"Shadow P&L: ${status['total_pnl']:+.2f} "
            f"(ROI {status['roi_pct']:+.1f}%)\n"
            f"Drawdown: {status['drawdown_pct']:.1f}%\n"
            f"Trades: {status['total_trades']} | WR: {status['win_rate']:.0f}%\n"
            f"Avg Profit: ${status['avg_profit']:.2f} | "
            f"Avg Loss: ${status['avg_loss']:.2f}\n\n"
            f"📦 Positions: idle={status['positions']['idle']} | "
            f"selling={status['positions']['selling']} | "
            f"sold={status['positions']['sold']}"
        )
        await message.answer(text)
    except Exception as e:
        logger.exception("cmd_shadow failed: %s", e)
        await message.answer("❌ Shadow status unavailable.")
