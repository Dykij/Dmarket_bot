"""
commands — All /command and reply-keyboard button handlers.

Composed from focused sub-modules, each with its own router:
    lifecycle.py  — /start, /help, /settings
    control.py    — /start_bot, /stop_bot, /panic (and _cancel_all_offers)
    views.py      — /balance, /status, /inventory, /profits, /portfolio, /daily, /analyze, /sell, /prices
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
from .test import TestItemFSM, _do_test, cmd_cancel, cmd_test, cmd_test_btn, cmd_test_receive
from .utils import cmd_clock, cmd_refresh
from .views import (
    cmd_analyze,
    cmd_balance,
    cmd_daily,
    cmd_inventory,
    cmd_portfolio,
    cmd_prices,
    cmd_profits,
    cmd_sell_top,
    cmd_status,
)

router = Router(name="telegram-control-commands")
router.include_router(lifecycle.router)
router.include_router(control.router)
router.include_router(views.router)
router.include_router(test.router)
router.include_router(utils.router)

__all__ = [
    "router",
    "BTN_PANIC", "BTN_START", "BTN_STOP", "BTN_TEST",
    "TestItemFSM",
    "cmd_start", "cmd_help", "cmd_settings",
    "cmd_start_bot", "cmd_stop_bot", "cmd_panic", "_cancel_all_offers",
    "cmd_balance", "cmd_status", "cmd_inventory", "cmd_profits",
    "cmd_portfolio", "cmd_daily", "cmd_analyze", "cmd_sell_top", "cmd_prices",
    "cmd_test", "cmd_test_btn", "cmd_test_receive", "cmd_cancel", "_do_test",
    "cmd_clock", "cmd_refresh",
]
