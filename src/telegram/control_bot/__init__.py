"""
control_bot/ — Telegram Control Bot v13.2 package.

Re-exports everything for backward compatibility with the old control_bot.py:
    from src.telegram.control_bot import is_admin, state, cmd_*, cb_*, etc.
    from src.telegram.control_bot import BotState, TestItemFSM, safe_call, retry_async

Run:    python -m src.telegram.control_bot
Module: src.telegram.control_bot.bot (provides main())
"""

# --- State & access control ---
from .state import (
    BotState,
    _ADMIN_IDS,
    _TOKEN,
    _load_config,
    is_admin,
    state,
)

# --- Resilience utilities ---
from .resilience import dmarket_client, retry_async, safe_call

# --- Keyboards (with BTN_* and CB_* constants) ---
from .keyboards import (
    BTN_ANALYZE,
    BTN_BALANCE,
    BTN_DAILY,
    BTN_INVENTORY,
    BTN_PANIC,
    BTN_PORTFOLIO,
    BTN_PROFITS,
    BTN_SELL_TOP,
    BTN_SETTINGS,
    BTN_START,
    BTN_STATUS,
    BTN_STOP,
    BTN_TEST,
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
    get_inline_analyze_kb,
    get_inline_balance_kb,
    get_inline_daily_kb,
    get_inline_inventory_kb,
    get_inline_portfolio_kb,
    get_inline_profits_kb,
    get_inline_status_kb,
    get_main_keyboard,
)

# --- Formatters ---
from .formatters import (
    format_balance,
    format_daily_summary,
    format_inventory_summary,
    format_portfolio_summary,
    format_profits_summary,
    format_status,
)

# --- Commands & FSM ---
from .commands import (
    BTN_PANIC,
    BTN_START,
    BTN_STOP,
    BTN_TEST,
    TestItemFSM,
    cmd_analyze,
    cmd_balance,
    cmd_cancel,
    cmd_clock,
    cmd_daily,
    cmd_help,
    cmd_inventory,
    cmd_panic,
    cmd_portfolio,
    cmd_prices,
    cmd_profits,
    cmd_refresh,
    cmd_sell_top,
    cmd_settings,
    cmd_start,
    cmd_start_bot,
    cmd_status,
    cmd_stop_bot,
    cmd_test,
    cmd_test_receive,
)

# --- Callbacks ---
from .callbacks import (
    cb_analyze,
    cb_balance,
    cb_daily,
    cb_inventory,
    cb_noop,
    cb_portfolio,
    cb_profits,
    cb_refresh_status,
    cb_sell_top,
    cb_start,
    cb_stop,
)

# --- Filters & error handler ---
from .filters import (
    on_router_error,
    reject_non_admin,
    reject_non_admin_callback,
)

# --- Lifecycle ---
from .lifecycle import (
    _graceful_shutdown,
    _install_signal_handlers,
    on_shutdown,
    on_startup,
    set_commands,
)

# --- Bot wiring (entry point) ---
from .bot import _lazy_bot, create_bot, main, master_router, router

__all__ = [
    # State
    "BotState", "_ADMIN_IDS", "_TOKEN", "_load_config", "is_admin", "state",
    # Resilience
    "dmarket_client", "retry_async", "safe_call",
    # Keyboards (constants)
    "BTN_ANALYZE", "BTN_BALANCE", "BTN_DAILY",
    "BTN_INVENTORY", "BTN_PANIC", "BTN_PORTFOLIO", "BTN_PROFITS",
    "BTN_SELL_TOP", "BTN_SETTINGS", "BTN_START", "BTN_STATUS", "BTN_STOP", "BTN_TEST",
    "CB_ANALYZE", "CB_BALANCE", "CB_DAILY", "CB_INVENTORY",
    "CB_NOOP", "CB_PORTFOLIO", "CB_PROFITS", "CB_REFRESH_STATUS",
    "CB_SELL_TOP", "CB_START", "CB_STOP",
    "get_inline_analyze_kb", "get_inline_balance_kb", "get_inline_daily_kb",
    "get_inline_inventory_kb", "get_inline_portfolio_kb",
    "get_inline_profits_kb", "get_inline_status_kb", "get_main_keyboard",
    # Formatters
    "format_balance", "format_daily_summary", "format_inventory_summary",
    "format_portfolio_summary", "format_profits_summary", "format_status",
    # Commands & FSM
    "TestItemFSM",
    "cmd_analyze", "cmd_balance", "cmd_cancel", "cmd_clock", "cmd_daily",
    "cmd_help", "cmd_inventory", "cmd_panic", "cmd_portfolio", "cmd_prices",
    "cmd_profits", "cmd_refresh", "cmd_sell_top", "cmd_settings", "cmd_start",
    "cmd_start_bot", "cmd_status", "cmd_stop_bot", "cmd_test", "cmd_test_receive",
    # Callbacks
    "cb_analyze", "cb_balance", "cb_daily", "cb_inventory", "cb_noop",
    "cb_portfolio", "cb_profits", "cb_refresh_status", "cb_sell_top",
    "cb_start", "cb_stop",
    # Filters
    "on_router_error", "reject_non_admin", "reject_non_admin_callback",
    # Lifecycle
    "_graceful_shutdown", "_install_signal_handlers",
    "on_shutdown", "on_startup", "set_commands",
    # Bot
    "_lazy_bot", "create_bot", "main", "master_router", "router",
]
