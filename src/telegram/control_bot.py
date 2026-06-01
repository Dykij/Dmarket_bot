"""
Telegram Control Bot v12.2 — entry point.

Real implementation lives in the `control_bot/` package. This thin facade
preserves the command `python -m src.telegram.control_bot` and re-exports
all public symbols for backward compatibility with existing tests/scripts.

Run:
    python -m src.telegram.control_bot
or:
    ./scripts/start_telegram_bot.sh
"""

import asyncio
import sys

# Re-export everything from the package so existing imports still work
# (e.g., tests, the launcher, the bot.py file in tests/dmarket/).
# This is the same surface the old monolithic control_bot.py exposed.
from src.telegram.control_bot import (  # noqa: F401, F403
    # State
    BotState, _ADMIN_ID, _TOKEN, _load_config, is_admin, state,
    # Resilience
    dmarket_client, retry_async, safe_call,
    # Keyboards
    CB_BALANCE, CB_INVENTORY, CB_NOOP, CB_PROFITS, CB_REFRESH_STATUS,
    CB_START, CB_STOP, get_inline_balance_kb, get_inline_inventory_kb,
    get_inline_profits_kb, get_inline_status_kb, get_main_keyboard,
    # Formatters
    format_balance, format_inventory_summary, format_profits_summary, format_status,
    # Commands
    BTN_PANIC, BTN_START, BTN_STOP, BTN_TEST, TestItemFSM,
    cmd_balance, cmd_cancel, cmd_clock, cmd_help, cmd_inventory, cmd_panic,
    cmd_profits, cmd_refresh, cmd_settings, cmd_start, cmd_start_bot,
    cmd_status, cmd_stop_bot, cmd_test, cmd_test_receive,
    # Callbacks
    cb_balance, cb_inventory, cb_noop, cb_profits, cb_refresh_status,
    cb_start, cb_stop,
    # Filters
    on_router_error, reject_non_admin, reject_non_admin_callback,
    # Lifecycle
    _graceful_shutdown, _install_signal_handlers, on_shutdown, on_startup,
    set_commands,
    # Bot
    _lazy_bot, create_bot, main, master_router, router,
)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Bot stopped by user (KeyboardInterrupt)")
    except Exception as e:
        print(f"Bot crashed: {e}")
        sys.exit(1)
