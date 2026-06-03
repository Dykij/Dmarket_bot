"""
filters.py — Reject non-admin messages, plus global error handler.

These are bound to the router and act as the first line of access control.
"""

import logging

from aiogram import Router, types

from .state import is_admin

logger = logging.getLogger("TelegramControl.filters")
router = Router(name="telegram-control-filters")


@router.message(lambda m: not is_admin(m.from_user.id))
async def reject_non_admin(message: types.Message):
    """Silently ignore messages from non-admin users."""
    logger.warning(
        f"Unauthorized access attempt from user_id={message.from_user.id}"
    )


@router.callback_query(lambda c: not is_admin(c.from_user.id))
async def reject_non_admin_callback(callback: types.CallbackQuery):
    """Silently ignore callbacks from non-admin users, but show alert."""
    logger.warning(
        f"Unauthorized callback from user_id={callback.from_user.id}"
    )
    await callback.answer("⛔ Access denied", show_alert=True)


@router.errors()
async def on_router_error(event: types.ErrorEvent):
    """Catches exceptions raised inside any handler — never lets the dispatcher die."""
    logger.exception(
        f"Router error in update {event.update.update_id}: {event.exception}"
    )
