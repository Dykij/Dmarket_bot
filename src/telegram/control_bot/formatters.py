"""
formatters.py — Pure functions that format bot data into Markdown text.

These are shared between `cmd_*` and `cb_*` handlers to avoid duplication
(e.g., balance text is shown by both /balance and btn:balance).
"""

import time
from typing import Optional

from src.config import Config
from src.utils.clock_sync import clock_sync


def format_balance(balance: float, equity: dict) -> str:
    """Format the balance text shown in /balance and btn:balance."""
    return (
        f"💰 *DMarket Balance*\n\n"
        f"💵 Cash: `${balance:.2f}`\n"
        f"📦 Locked in items: `${equity['assets']:.2f}` ({equity['count']} items)\n"
        f"💎 *Total Equity:* `${equity['total']:.2f}`"
    )


def format_status(
    is_running: bool,
    balance_data: Optional[dict] = None,
) -> str:
    """Format the status text shown in /status and btn:refresh_status.

    balance_data has keys: cash_str, locked_str, total_str (or None for "N/A").
    """
    state_str = "🟢 RUNNING" if is_running else "🔴 STOPPED"
    mode = "🧪 SIMULATION" if Config.DRY_RUN else "💸 LIVE TRADING"

    if balance_data is None:
        cash_str = locked_str = total_str = "N/A"
    else:
        cash_str = balance_data["cash_str"]
        locked_str = balance_data["locked_str"]
        total_str = balance_data["total_str"]

    cs = clock_sync.get_status()

    return (
        f"📊 *Bot Status*\n\n"
        f"*State:* {state_str}\n"
        f"*Mode:* {mode}\n"
        f"*Strategy:* {Config.ACTIVE_STRATEGY}\n"
        f"*Version:* v{Config.BOT_VERSION}\n\n"
        f"💰 *Equity:*\n"
        f"   Cash: {cash_str}\n"
        f"   Locked: {locked_str}\n"
        f"   *Total:* {total_str}\n\n"
        f"⚙️ *Risk:*\n"
        f"   Min spread: {Config.INTRA_MIN_SPREAD_PCT}%\n"
        f"   Max position: {Config.MAX_POSITION_RISK_PCT}%\n"
        f"   Fee rate: {Config.FEE_RATE*100:.1f}%\n\n"
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
    locked = [it for it in idle if it['unlock_at'] > time.time()]
    unlocked = [it for it in idle if it['unlock_at'] <= time.time()]

    text = (
        f"📦 *Virtual Inventory*\n\n"
        f"🔒 Locked (trade protection): {len(locked)}\n"
        f"🔓 Unlocked (ready to sell): {len(unlocked)}\n"
        f"🏪 Listed for sale: {len(selling)}\n"
        f"✅ Sold: {len(sold)}\n"
        f"━━━━━━━━━━━━━━\n"
        f"📊 *Total items:* {len(idle) + len(selling) + len(sold)}\n"
    )

    all_items = list(idle) + list(selling)
    if all_items:
        top = sorted(all_items, key=lambda x: -x['buy_price'])[:top_n]
        text += f"\n*Top {top_n} items by value:*\n"
        for it in top:
            status_emoji = "🔒" if it['unlock_at'] > time.time() else "🔓"
            text += f"  {status_emoji} `{it['hash_name'][:30]}` — ${it['buy_price']:.2f}\n"

    return text


def format_profits_summary(
    sold: list,
    idle: list,
    selling: list,
    detailed: bool = True,
) -> str:
    """Format P&L text. Used by /profits and btn:profits.

    If detailed=True, shows the full breakdown (used by /profits).
    If detailed=False, shows short version (used by btn:profits in inline).
    """
    realized = sum(it['profit'] or 0 for it in sold)
    realized_count = len(sold)
    win_count = sum(1 for it in sold if (it['profit'] or 0) > 0)
    win_rate = (win_count / realized_count * 100) if realized_count > 0 else 0

    # Unrealized estimate: 5% target, 95% of spread after fees
    unrealized = 0.0
    for it in idle:
        target = it['buy_price'] * 1.05
        unrealized += (target - it['buy_price']) * 0.95

    total = realized + unrealized
    total_fees = sum(it['fee_paid'] or 0 for it in sold)

    if detailed:
        return (
            f"📈 *Profit & Loss*\n\n"
            f"💵 *Realized:*\n"
            f"   Total: `${realized:+.2f}`\n"
            f"   Trades: {realized_count} (win rate: {win_rate:.1f}%)\n"
            f"   Fees paid: `${total_fees:.2f}`\n\n"
            f"📊 *Unrealized (estimated):*\n"
            f"   Items listed: {len(idle) + len(selling)}\n"
            f"   Estimated value: `${unrealized:+.2f}`\n\n"
            f"💎 *Total P&L:* `${total:+.2f}`\n"
        )
    else:
        return (
            f"📈 *P&L Summary*\n\n"
            f"💵 Realized: `${realized:+.2f}` ({realized_count} trades, {win_rate:.0f}% win)\n"
            f"📊 Unrealized: `${unrealized:+.2f}` ({len(idle)} items)\n"
            f"💎 *Total:* `${total:+.2f}`"
        )
