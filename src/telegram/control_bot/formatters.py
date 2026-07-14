"""
formatters.py — Pure functions that format bot data into Markdown text.

These are shared between `cmd_*` and `cb_*` handlers to avoid duplication
(e.g., balance text is shown by both /balance and btn:balance).

v13.2: Added funds hold display, portfolio formatting, daily summary.
"""

import logging
import time

from src.config import Config
from src.utils.clock_sync import clock_sync

logger = logging.getLogger("TelegramControl.formatters")


def escape_md(text: str) -> str:
    """Escape Telegram MarkdownV2 special characters in user-supplied text.

    Full list from Telegram docs (v10.1):
    '_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!'
    """
    for ch in ("_", "*", "[", "]", "(", ")", "~", "`", ">", "#", "+", "-", "=", "|", "{", "}", ".", "!"):
        text = text.replace(ch, "\\" + ch)
    return text


def format_balance(balance: float, equity: dict) -> str:
    """Format the balance text shown in /balance and btn:balance."""
    frozen_str = ""
    if equity.get("frozen", 0) > 0:
        frozen_str = f"\n🔒 *Frozen (TP holds):* `${equity['frozen']:.2f}`"
    return (
        f"💰 *DMarket Balance*\n\n"
        f"💵 Cash: `${equity['cash']:.2f}`\n"
        f"💵 Available: `${equity['available']:.2f}`{frozen_str}\n"
        f"📦 Locked in items: `${equity['assets']:.2f}` ({equity['count']} items)\n"
        f"💎 *Total Equity:* `${equity['total']:.2f}`"
    )


def format_status(
    is_running: bool,
    balance_data: dict | None = None,
) -> str:
    """Format the status text shown in /status and btn:refresh_status."""
    state_str = "🟢 RUNNING" if is_running else "🔴 STOPPED"
    mode = "🧪 SIMULATION" if Config.DRY_RUN else "💸 LIVE TRADING"

    if balance_data is None:
        cash_str = locked_str = total_str = avail_str = frozen_str = "N/A"
    else:
        cash_str = balance_data.get("cash_str", "N/A")
        locked_str = balance_data.get("locked_str", "N/A")
        total_str = balance_data.get("total_str", "N/A")
        avail_str = balance_data.get("avail_str", cash_str)
        frozen_str = balance_data.get("frozen_str", "")

    cs = clock_sync.get_status()

    frozen_line = f"\n   🔒 Frozen: {frozen_str}" if frozen_str else ""

    return (
        f"📊 *Bot Status*\n\n"
        f"*State:* {escape_md(state_str)}\n"
        f"*Mode:* {escape_md(mode)}\n"
        f"*Strategy:* {escape_md(Config.ACTIVE_STRATEGY)}\n"
        f"*Version:* {escape_md(Config.BOT_VERSION)}\n\n"
        f"💰 *Equity:*\n"
        f"   Cash: {escape_md(cash_str)}\n"
        f"   Available: {escape_md(avail_str)}{escape_md(frozen_line)}\n"
        f"   Locked: {escape_md(locked_str)}\n"
        f"   *Total:* {escape_md(total_str)}\n\n"
        f"⚙️ *Risk:*\n"
        f"   Min spread: {Config.INTRA_MIN_SPREAD_PCT}%\n"
        f"   Max position: {Config.MAX_POSITION_RISK_PCT}%\n"
        f"   Fee rate: {Config.FEE_RATE*100:.1f}%\n"
        f"   TP lock: {Config.TRADE_LOCK_HOURS}h\n\n"
        f"💳 *v14.4 Balance-Aware:*\n"
        f"   Reserve: ${Config.BALANCE_RESERVE_USD:.2f}\n"
        f"   Kelly fraction: {Config.KELLY_FRACTION:.0%} Half Kelly\n"
        f"   Dynamic max item: {Config.MAX_SNIPING_PRICE_FLOOR:.0f}—{Config.MAX_SNIPING_PRICE_BALANCE_FRACTION:.0%}×eff_balance\n"
        f"   Lock-aware cap: {Config.LOCK_AWARE_LIQUID_FRACTION:.0%} liquid\n"
        f"   Velocity min: {Config.CAPITAL_VELOCITY_MIN}x/wk\n\n"
        f"🕐 *Clock Sync:*\n"
        f"   Offset: {cs['offset_seconds']}s\n"
        f"   Synced: {cs['sync_count']}x | Healthy: {cs['is_healthy']}"
    )


def format_inventory_summary(
    idle: list,
    selling: list,
    sold: list,
    top_n: int = 5,
) -> str:
    """Format inventory text shown in /inventory and btn:inventory."""

    def _row_bool(row, key: str) -> bool:
        try:
            return bool(row[key])
        except (KeyError, IndexError, TypeError):
            return False

    locked = [it for it in idle if it['unlock_at'] > time.time()]
    unlocked = [it for it in idle if it['unlock_at'] <= time.time()]
    exclusive_count = sum(1 for it in idle if _row_bool(it, "exclusive"))

    text = (
        f"📦 *Virtual Inventory*\n\n"
        f"🔒 Locked (trade protection): {len(locked)}\n"
        f"🔓 Unlocked (ready to sell): {len(unlocked)}\n"
        f"⭐ Exclusive (keep forever): {exclusive_count}\n"
        f"🏪 Listed for sale: {len(selling)}\n"
        f"✅ Sold: {len(sold)}\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 *Total items:* {len(idle) + len(selling) + len(sold)}\n"
    )

    all_items = list(idle) + list(selling)
    if all_items:
        top = sorted(all_items, key=lambda x: -x['buy_price'])[:top_n]
        text += f"\n*Top {min(top_n, len(top))} items by value:*\n"
        for it in top:
            exclusive_mark = " ⭐" if _row_bool(it, "exclusive") else ""
            status_emoji = "🔒" if it['unlock_at'] > time.time() else "🔓"
            text += f"  {status_emoji} `{it['hash_name'][:30]}` — ${it['buy_price']:.2f}{exclusive_mark}\n"

    return text


def format_profits_summary(
    sold: list,
    idle: list,
    selling: list,
    detailed: bool = True,
) -> str:
    """Format P&L text. Used by /profits and btn:profits."""
    realized = sum(it['profit'] or 0 for it in sold)
    realized_count = len(sold)
    win_count = sum(1 for it in sold if (it['profit'] or 0) > 0)
    win_rate = (win_count / realized_count * 100) if realized_count > 0 else 0

    rollback_count = sum(1 for it in sold if it.get("rollback_refund"))

    # Unrealized estimate: 5% target, 95% of spread after fees
    unrealized = 0.0
    for it in idle:
        target = it['buy_price'] * 1.05
        unrealized += (target - it['buy_price']) * 0.95

    total = realized + unrealized
    total_fees = sum(it['fee_paid'] or 0 for it in sold)

    rollback_line = f"\n   Rollbacks (refunded): {rollback_count}" if rollback_count > 0 else ""

    if detailed:
        return (
            f"📈 *Profit & Loss*\n\n"
            f"💵 *Realized:*\n"
            f"   Total: `${realized:+.2f}`\n"
            f"   Trades: {realized_count} (win rate: {win_rate:.1f}%)\n"
            f"   Fees paid: `${total_fees:.2f}`{rollback_line}\n\n"
            f"📊 *Unrealized (estimated):*\n"
            f"   Items listed: {len(idle) + len(selling)}\n"
            f"   Estimated value: `${unrealized:+.2f}`\n\n"
            f"💎 *Total P&L:* `${total:+.2f}`\n"
        )
    else:
        return (
            f"📈 *P&L Summary*\n\n"
            f"💵 Realized: `${realized:+.2f}` ({realized_count} trades, {win_rate:.0f}% win){rollback_line}\n"
            f"📊 Unrealized: `${unrealized:+.2f}` ({len(idle)} items)\n"
            f"💎 *Total:* `${total:+.2f}`"
        )


def format_portfolio_summary(equity: dict, sold: list) -> str:
    """Format portfolio summary text shown in /portfolio and btn:portfolio."""
    cash = equity["cash"]
    available = equity["available"]
    assets = equity["assets"]
    frozen = equity.get("frozen", 0)
    total = equity["total"]
    count = equity["count"]
    realized = sum(it["profit"] or 0 for it in sold)
    return (
        f"💼 *Portfolio Summary*\n\n"
        f"💵 Cash: `${cash:.2f}`\n"
        f"💵 Available: `${available:.2f}`\n"
        f"🔒 Frozen (TP holds): `${frozen:.2f}`\n"
        f"📦 Assets: `${assets:.2f}` ({count} items)\n"
        f"━━━━━━━━━━━━━━\n"
        f"📈 Realized P&L: `${realized:+.2f}`\n"
        f"💎 *Total Equity:* `${total:.2f}`\n"
    )


def format_daily_summary(
    today_pnl: float,
    today_trades: int,
    today_wins: int,
    total_equity: float,
    inventory_value: float,
    frozen: float = 0.0,
) -> str:
    """Format daily briefing shown in /daily and btn:daily."""
    win_rate = (today_wins / today_trades * 100) if today_trades > 0 else 0
    frozen_line = f"\n🔒 Frozen funds: `${frozen:.2f}`" if frozen > 0 else ""
    return (
        f"📅 *Daily Briefing*\n\n"
        f"📈 Today's P&L: `${today_pnl:+.2f}`\n"
        f"🔄 Trades today: {today_trades} (win: {today_wins}, {win_rate:.0f}%)\n"
        f"━━━━━━━━━━━━━━\n"
        f"💰 Total Equity: `${total_equity:.2f}`\n"
        f"📦 Inventory Value: `${inventory_value:.2f}`{frozen_line}\n"
    )
