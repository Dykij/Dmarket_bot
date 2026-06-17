"""
utils.py — Utility commands: /clock (view sync status) + /refresh (re-sync).

Small commands for clock sync and cache refresh — separate from the
main lifecycle/control/views groups.
"""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command

from src.utils.clock_sync import clock_sync

from ..keyboards import BTN_CLOCK, BTN_REFRESH
from ..resilience import safe_call

logger = logging.getLogger("TelegramControl.commands.utils")
router = Router(name="telegram-control-utils")


# ============================================================
# Misc: clock, refresh
# ============================================================
@router.message(Command("clock"))
@router.message(F.text == BTN_CLOCK)
@safe_call
async def cmd_clock(message):
    cs = clock_sync.get_status()
    text = (
        f"🕐 *Clock Sync Status*\n\n"
        f"   Offset: `{cs['offset_seconds']}s`\n"
        f"   Last sync: `{cs['last_sync_ago_seconds']}s ago`\n"
        f"   Sync count: `{cs['sync_count']}`\n"
        f"   Drift warnings: `{cs['drift_warnings']}`\n"
        f"   Needs refresh: `{cs['needs_refresh']}`\n"
        f"   *Healthy:* `{cs['is_healthy']}`\n\n"
        f"   ⚠️ DMarket rejects X-Sign-Date if drift > 120s"
    )
    await message.answer(text)


@router.message(Command("refresh"))
@router.message(F.text == BTN_REFRESH)
@safe_call
async def cmd_refresh(message):
    await message.answer("🔄 Refreshing clocksync + caches...")
    try:
        await clock_sync.sync_with_dmarket()
        cs = clock_sync.get_status()
        await message.answer(
            f"✅ *Refreshed!*\n\n"
            f"   New offset: `{cs['offset_seconds']}s`\n"
            f"   Healthy: `{cs['is_healthy']}`\n"
            f"   Last sync: `{cs['last_sync_ago_seconds']}s ago`"
        )
    except Exception as e:
        logger.warning(f"Refresh failed: {e}", exc_info=False)
        await message.answer("❌ Refresh failed. Check logs for details.")
