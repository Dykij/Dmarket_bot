"""
commands — All /command and reply-keyboard button handlers.

Composed from focused sub-modules, each with its own router:
    lifecycle.py  — /start, /help, /settings
    control.py    — /start_bot, /stop_bot, /panic (and _cancel_all_offers)
    views.py      — /balance, /status, /inventory, /profits
    test.py       — /test (with FSM), /cancel (TestItemFSM, _do_test)
    utils.py      — /clock, /refresh

The combined `router` here is what `bot.py` mounts on the dispatcher.
"""

from __future__ import annotations

from aiogram import Router

from ..keyboards import BTN_PANIC, BTN_START, BTN_STOP, BTN_TEST
from . import control, lifecycle, test, utils, views
from .control import _cancel_all_offers, cmd_panic, cmd_start_bot, cmd_stop_bot
from .lifecycle import cmd_help, cmd_settings, cmd_start
from .test import TestItemFSM, _do_test, cmd_cancel, cmd_test, cmd_test_receive
from .utils import cmd_clock, cmd_refresh
from .views import _fetch_balance_data, cmd_balance, cmd_inventory, cmd_profits, cmd_status

# Combined router — order matters for filters, but aiogram routes by handler
# type not by order, so it's fine to combine all sub-routers into one.
router = Router(name="telegram-control-commands")
router.include_router(lifecycle.router)
router.include_router(control.router)
router.include_router(views.router)
router.include_router(test.router)
router.include_router(utils.router)

__all__ = [
    # Master router
    "router",
    # Buttons
    "BTN_PANIC",
    "BTN_START",
    "BTN_STOP",
    "BTN_TEST",
    # FSM
    "TestItemFSM",
    # Lifecycle
    "cmd_start",
    "cmd_help",
    "cmd_settings",
    # Control
    "cmd_start_bot",
    "cmd_stop_bot",
    "cmd_panic",
    "_cancel_all_offers",
    # Views
    "cmd_balance",
    "cmd_status",
    "cmd_inventory",
    "cmd_profits",
    "_fetch_balance_data",
    # Test
    "cmd_test",
    "cmd_test_receive",
    "cmd_cancel",
    "_do_test",
    # Utils
    "cmd_clock",
    "cmd_refresh",
]
