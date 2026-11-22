"""
control.py — Start/stop/panic (bot lifecycle control).

Handles the commands that change the bot's running state, including
the kill-switch that cancels all DMarket offers.
"""

from __future__ import annotations

import contextlib
import logging
from typing import Any

from aiogram import F, Router, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

from src.api.dmarket_api_client import DMarketAPIClient
from src.api.dmarket_api_client.backoff import CircuitOpenError
from src.config import Config

from ..keyboards import BTN_PANIC, BTN_START, BTN_STOP
from ..callback_data import ConfirmCallback
from ..resilience import safe_call
from ..state import state

logger = logging.getLogger("TelegramControl.commands.control")
router = Router(name="telegram-control-control")


# ============================================================
# Control: start/stop/panic
# ============================================================
@router.message(Command("start_bot"))
@router.message(F.text == BTN_START)
@safe_call
async def cmd_start_bot(message):
    started = await state.start()
    if not started:
        await message.answer("⚠️ *Bot is already running!*\nUse /stop\\_bot to stop.")
        return
    mode = "🧪 SIMULATION" if Config.DRY_RUN else "💸 LIVE"
    await message.answer(
        f"✅ *Bot STARTED* in {mode} mode!\n\n"
        f"Strategy: {Config.ACTIVE_STRATEGY}\n"
        f"Game: {Config.GAME_ID}\n"
        f"Scan interval: {Config.SCAN_INTERVAL}s\n\n"
        f"Use 📊 STATUS to monitor progress."
    )
    logger.info(f"Bot started by admin {message.from_user.id}")


@router.message(Command("stop_bot"))
@router.message(F.text == BTN_STOP)
@safe_call
async def cmd_stop_bot(message):
    stopped = await state.stop()
    if not stopped:
        await message.answer("⚠️ *Bot is not running.*")
        return
    await message.answer(
        "🛑 *Bot STOPPED.*\n\n"
        "Active orders remain on DMarket (cancel manually if needed)."
    )
    logger.info(f"Bot stopped by admin {message.from_user.id}")


_PANIC_MAX_PAGES = 100
_PANIC_CHUNK_SIZE = 100


async def _fetch_all_offers_for_panic(
    client: Any, game_id: str
) -> tuple[list[dict[str, str | None]], int, str]:
    """Fetch active offers across pages up to _PANIC_MAX_PAGES.

    Returns:
        (unique_offers, skipped_no_id_count, list_complete_flag)
    """
    page_count = 0
    cursor: str | None = None
    seen_cursors: set[str] = set()
    collected_offers: list[dict[str, str | None]] = []
    seen_offer_ids: set[str] = set()
    skipped_no_id = 0
    list_complete = "yes"

    while True:
        if page_count >= _PANIC_MAX_PAGES:
            list_complete = "no"
            break

        try:
            resp = await client.get_user_offers_v2(game_id, limit=100, cursor=cursor)
        except Exception:
            logger.exception("PANIC: listing offers failed on page")
            list_complete = "no"
            break

        page_count += 1

        if not isinstance(resp, dict):
            list_complete = "no"
            break

        raw_items = resp.get("items")
        if not isinstance(raw_items, list):
            list_complete = "no"
            break

        if not raw_items:
            # Empty items list ends pagination; list is considered complete
            break

        for item in raw_items:
            if not isinstance(item, dict):
                skipped_no_id += 1
                continue

            raw_oid = item.get("offerId")
            if raw_oid is None:
                skipped_no_id += 1
                continue

            oid = str(raw_oid).strip()
            if not oid:
                skipped_no_id += 1
                continue

            if oid in seen_offer_ids:
                # Deduplication preserves first appearance; does not increment skipped_no_id
                continue

            asset_id: str | None = None
            attrs = item.get("attributes")
            if isinstance(attrs, dict):
                raw_aid = attrs.get("id")
                if raw_aid is not None:
                    aid = str(raw_aid).strip()
                    if aid:
                        asset_id = aid

            seen_offer_ids.add(oid)
            collected_offers.append({"offer_id": oid, "asset_id": asset_id})

        raw_cursor = resp.get("cursor")
        if raw_cursor is None or raw_cursor == "":
            # Missing, None, or empty cursor string ends pagination successfully
            break

        if not isinstance(raw_cursor, str):
            list_complete = "no"
            break

        next_cursor = raw_cursor.strip()
        if not next_cursor:
            break

        if next_cursor in seen_cursors:
            list_complete = "no"
            break

        seen_cursors.add(next_cursor)
        cursor = next_cursor

    return collected_offers, skipped_no_id, list_complete


async def _delete_offers_in_chunks(
    client: Any, offers: list[dict[str, str | None]]
) -> dict[str, Any]:
    """Delete gathered offers in chunks of _PANIC_CHUNK_SIZE without retries."""
    confirmed = 0
    failed = 0
    unconfirmed = 0
    unknown = 0
    not_sent = 0
    simulated = 0
    failure_codes: list[str] = []

    if not offers:
        return {
            "confirmed": 0,
            "failed": 0,
            "unconfirmed": 0,
            "unknown": 0,
            "not_sent": 0,
            "simulated": 0,
            "failure_codes": "-",
        }

    chunks = [
        offers[i : i + _PANIC_CHUNK_SIZE]
        for i in range(0, len(offers), _PANIC_CHUNK_SIZE)
    ]

    for idx, chunk in enumerate(chunks):
        chunk_ids = [str(o["offer_id"]) for o in chunk]
        try:
            resp = await client.batch_delete_offers_v2(chunk_ids)
        except CircuitOpenError:
            logger.warning("PANIC: circuit breaker open during cancellation")
            remaining_chunks = chunks[idx:]
            remaining_count = sum(len(c) for c in remaining_chunks)
            not_sent += remaining_count
            break
        except Exception:
            logger.exception("PANIC: chunk delete failed")
            unknown += len(chunk)
            continue

        if not isinstance(resp, dict):
            unconfirmed += len(chunk)
            continue

        if resp.get("simulated") is True:
            simulated += len(chunk)
            continue

        raw_offers = resp.get("offers")
        raw_failed = resp.get("failed")

        if not isinstance(raw_offers, list) and not isinstance(raw_failed, list):
            unconfirmed += len(chunk)
            continue

        failed_offers_map: dict[str, str | None] = {}
        failed_assets_map: dict[str, str | None] = {}

        if isinstance(raw_failed, list):
            for f in raw_failed:
                if isinstance(f, dict):
                    raw_code = f.get("code")
                    code_str = str(raw_code).strip() if raw_code is not None else None
                    if code_str:
                        if code_str not in failure_codes:
                            failure_codes.append(code_str)

                    raw_f_oid = f.get("offerId")
                    if raw_f_oid is not None:
                        f_oid = str(raw_f_oid).strip()
                        if f_oid:
                            failed_offers_map[f_oid] = code_str

                    raw_f_aid = f.get("assetId")
                    if raw_f_aid is not None:
                        f_aid = str(raw_f_aid).strip()
                        if f_aid:
                            failed_assets_map[f_aid] = code_str

        confirmed_offer_ids: set[str] = set()
        confirmed_asset_ids: set[str] = set()

        if isinstance(raw_offers, list):
            for o in raw_offers:
                if isinstance(o, dict):
                    raw_o_id = o.get("id") or o.get("offerId")
                    if raw_o_id is not None:
                        o_id = str(raw_o_id).strip()
                        if o_id:
                            confirmed_offer_ids.add(o_id)

                    raw_o_aid = o.get("assetId")
                    if raw_o_aid is not None:
                        o_aid = str(raw_o_aid).strip()
                        if o_aid:
                            confirmed_asset_ids.add(o_aid)

        for item in chunk:
            item_oid = str(item["offer_id"])
            item_aid = item.get("asset_id")

            # Priority 1: Check failed[]
            is_failed = False
            if item_oid in failed_offers_map:
                is_failed = True
            elif item_aid and item_aid in failed_assets_map:
                is_failed = True

            if is_failed:
                failed += 1
                continue

            # Priority 2: Check offers[]
            is_confirmed = False
            if item_oid in confirmed_offer_ids:
                is_confirmed = True
            elif item_aid and item_aid in confirmed_asset_ids:
                is_confirmed = True

            if is_confirmed:
                confirmed += 1
                continue

            # Priority 3: Unconfirmed
            unconfirmed += 1

    codes_str = ", ".join(failure_codes[:5]) if failure_codes else "-"

    return {
        "confirmed": confirmed,
        "failed": failed,
        "unconfirmed": unconfirmed,
        "unknown": unknown,
        "not_sent": not_sent,
        "simulated": simulated,
        "failure_codes": codes_str,
    }


def _format_panic_report(
    scope: str,
    stop_ok: str,
    counts: dict[str, Any],
    list_complete: str,
    skipped_no_id: int,
) -> str:
    """Format single plain-text report message with exact required keys."""
    return (
        f"scope: {scope}\n"
        f"stop_ok: {stop_ok}\n"
        f"confirmed: {counts['confirmed']}\n"
        f"failed: {counts['failed']}\n"
        f"unconfirmed: {counts['unconfirmed']}\n"
        f"unknown: {counts['unknown']}\n"
        f"not_sent: {counts['not_sent']}\n"
        f"simulated: {counts['simulated']}\n"
        f"skipped_no_id: {skipped_no_id}\n"
        f"list_complete: {list_complete}\n"
        f"failure_codes: {counts['failure_codes']}"
    )


async def _cancel_all_offers() -> tuple[dict[str, Any], int, str]:
    """Cancel all active offers on DMarket under state.lock.

    Returns:
        (counts, skipped_no_id, list_complete)
    """
    async with state.lock:
        client_to_close = None
        if state.client is None:
            # Bot was not running — create a temp client just for cancellation
            from ..resilience import get_dmarket_secret

            state.client = DMarketAPIClient(Config.PUBLIC_KEY, get_dmarket_secret())  # type: ignore[arg-type]
            client_to_close = state.client

        try:
            offers, skipped_no_id, list_complete = await _fetch_all_offers_for_panic(
                state.client, Config.GAME_ID
            )
            counts = await _delete_offers_in_chunks(state.client, offers)
            return counts, skipped_no_id, list_complete
        finally:
            if client_to_close is not None:
                with contextlib.suppress(Exception):
                    await client_to_close.close()
                state.client = None


@router.message(Command("panic"))
@router.message(F.text == BTN_PANIC)
@safe_call
async def cmd_panic(message):
    await message.answer(
        "🔥 *PANIC PROTOCOL INITIATED*\n"
        "Stopping bot and cancelling all offers..."
    )

    # 1. Stop sniping task, close and reset running client in state.py (re-creation handled in _cancel_all_offers if needed)
    stop_ok = "no"
    try:
        await state.stop()
        stop_ok = "yes"
    except Exception:
        logger.exception("PANIC: state.stop() failed")
        stop_ok = "no"

    # 2. Cancel all offers
    counts = {
        "confirmed": 0,
        "failed": 0,
        "unconfirmed": 0,
        "unknown": 0,
        "not_sent": 0,
        "simulated": 0,
        "failure_codes": "-",
    }
    skipped_no_id = 0
    list_complete = "no"

    try:
        counts, skipped_no_id, list_complete = await _cancel_all_offers()
    except Exception:
        logger.exception("PANIC: _cancel_all_offers failed unexpectedly")

    confirmed = counts["confirmed"]
    is_empty_full = (
        confirmed == 0
        and list_complete == "yes"
        and counts["failed"] == 0
        and counts["unconfirmed"] == 0
        and counts["unknown"] == 0
        and counts["not_sent"] == 0
        and counts["simulated"] == 0
        and skipped_no_id == 0
    )

    if confirmed > 0:
        await message.answer(f"🗑 Cancelled {confirmed} offers.")
    elif is_empty_full:
        await message.answer("✅ No active offers found.")

    report_text = _format_panic_report(
        scope=Config.GAME_ID,
        stop_ok=stop_ok,
        counts=counts,
        list_complete=list_complete,
        skipped_no_id=skipped_no_id,
    )
    await message.answer(report_text, parse_mode=None)

    is_safe = (
        list_complete == "yes"
        and stop_ok == "yes"
        and counts["failed"] == 0
        and counts["unconfirmed"] == 0
        and counts["unknown"] == 0
        and counts["not_sent"] == 0
        and counts["simulated"] == 0
        and skipped_no_id == 0
    )

    if is_safe:
        await message.answer("🔥 *Panic complete. You are safe.*")
    else:
        await message.answer(
            "⚠️ PANIC: Cancellation was NOT confirmed on DMarket. Check your account manually!"
        )

    logger.warning(f"PANIC executed by admin {message.from_user.id}")


# ============================================================
# Liquidate: sell all unlocked inventory at market bid
# ============================================================
@router.message(Command("liquidate"))
@safe_call
async def cmd_liquidate(message):
    """Show confirmation dialog before force-selling ALL unlocked inventory."""
    if state.client is None:
        await message.answer("❌ Bot is not running. Start the bot first with /start_bot")
        return

    # P1 FIX: Show inventory summary and require confirmation
    from src.db.price_history import price_db

    idle_items = price_db.get_virtual_inventory(status="idle", only_unlocked=True)
    if not idle_items:
        await message.answer("💧 *Liquidate* — No unlocked items in inventory.")
        return

    total_value = sum(float(item.get("buy_price", 0)) for item in idle_items)
    item_count = len(idle_items)
    sample_names = [item.get("hash_name", "?") for item in idle_items[:5]]
    names_text = "\n".join(f"  • {n}" for n in sample_names)
    if item_count > 5:
        names_text += f"\n  ... and {item_count - 5} more"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="✅ Yes, sell ALL",
                callback_data=ConfirmCallback(action="yes", context="liquidate").pack(),
            ),
            InlineKeyboardButton(
                text="❌ Cancel",
                callback_data=ConfirmCallback(action="no", context="liquidate").pack(),
            ),
        ]
    ])
    await message.answer(
        f"⚠️ *LIQUIDATION CONFIRMATION*\n\n"
        f"Items to sell: **{item_count}**\n"
        f"Total cost basis: **${total_value:.2f}**\n\n"
        f"Items:\n{names_text}\n\n"
        f"This will list ALL items at best bid. This action is **irreversible**.\n"
        f"Confirm?",
        reply_markup=kb,
    )


@router.callback_query(ConfirmCallback.filter((F.action == "yes") & (F.context == "liquidate")))
@safe_call
async def cb_liquidate_confirm(callback: types.CallbackQuery):
    """Execute liquidation after confirmation."""
    if callback.message is None or not isinstance(callback.message, types.Message):
        await callback.answer()
        return

    if state.client is None:
        await callback.message.edit_text("❌ Bot client unavailable. Start the bot first.")
        await callback.answer()
        return

    # Remove buttons immediately to prevent double-click
    await callback.message.edit_text("💧 *LIQUIDATION IN PROGRESS*\nSelling all unlocked inventory at best bid...")
    await callback.answer()

    from src.core.target_sniping.position_guard import _PositionGuardMixin
    guard = _PositionGuardMixin()
    guard.client = state.client

    try:
        result = await guard.emergency_liquidate_all(Config.GAME_ID)
    except Exception:
        logger.exception("Liquidation failed")
        await callback.message.edit_text("❌ Liquidation failed. Check logs for details.")
        return

    await callback.message.edit_text(
        f"💧 *Liquidation Complete*\n\n"
        f"Items listed: {result['liquidated']}\n"
        f"Total value: ${result['total_value']:.2f}\n"
        f"Errors: {result['errors']}"
    )
    logger.warning(f"LIQUIDATION executed by admin {callback.from_user.id}: {result}")


@router.callback_query(ConfirmCallback.filter((F.action == "no") & (F.context == "liquidate")))
@safe_call
async def cb_liquidate_cancel(callback: types.CallbackQuery):
    """Cancel liquidation."""
    if callback.message is not None and isinstance(callback.message, types.Message):
        await callback.message.edit_text("❌ Liquidation cancelled.")
    await callback.answer()
