"""
keyboards.py — Reply and inline keyboards with constants.

Constants:
- BTN_* — text labels for the 16 reply-keyboard buttons
- CB_* — callback_data strings for inline buttons (legacy, kept for backward compat)

v15.6: Added CallbackData factories for type-safe callbacks.
v13.2: Added SELL-TOP, PORTFOLIO, DAILY-BRIEF, ANALYZE buttons.
       Added inline keyboards for new features.
"""

import logging

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from .callback_data import MenuCallback

logger = logging.getLogger("TelegramControl.keyboards")

# ============================================================
# Reply keyboard button text constants
# ============================================================
BTN_START = "🚀 START"
BTN_STOP = "🛑 STOP"
BTN_BALANCE = "💰 BALANCE"
BTN_STATUS = "📊 STATUS"
BTN_INVENTORY = "📦 INVENTORY"
BTN_PROFITS = "📈 PROFITS"
BTN_PORTFOLIO = "💼 PORTFOLIO"
BTN_SELL_TOP = "🔍 SELL-TOP"
BTN_DAILY = "📅 DAILY"
BTN_ANALYZE = "🧠 ANALYZE"
BTN_PANIC = "🔥 PANIC"
BTN_SETTINGS = "⚙️ SETTINGS"
BTN_PRICES = "📊 PRICES"
BTN_TEST = "🧪 TEST"
BTN_CLOCK = "🕐 CLOCK"
BTN_REFRESH = "🔄 REFRESH"

# ============================================================
# Inline keyboard callback_data constants (legacy, kept for compat)
# ============================================================
CB_START = "btn:start"
CB_STOP = "btn:stop"
CB_BALANCE = "btn:balance"
CB_INVENTORY = "btn:inventory"
CB_PROFITS = "btn:profits"
CB_PORTFOLIO = "btn:portfolio"
CB_SELL_TOP = "btn:sell_top"
CB_DAILY = "btn:daily"
CB_ANALYZE = "btn:analyze"
CB_REFRESH_STATUS = "btn:refresh_status"
CB_NOOP = "noop"


# ============================================================
# Keyboards
# ============================================================
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Main reply keyboard — always visible at the bottom of the chat.

    Layout (8 rows, 2 cols):
      1. 🚀 START     │ 🛑 STOP
      2. 💰 BALANCE   │ 📊 STATUS
      3. 📦 INVENTORY │ 📈 PROFITS
      4. 💼 PORTFOLIO │ 🔍 SELL-TOP
      5. 📅 DAILY     │ 🧠 ANALYZE
      6. 📊 PRICES    │ 🧪 TEST
      7. 🕐 CLOCK     │ 🔄 REFRESH
      8. 🔥 PANIC     │ ⚙️ SETTINGS
    """
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_START), KeyboardButton(text=BTN_STOP)],
            [KeyboardButton(text=BTN_BALANCE), KeyboardButton(text=BTN_STATUS)],
            [KeyboardButton(text=BTN_INVENTORY), KeyboardButton(text=BTN_PROFITS)],
            [KeyboardButton(text=BTN_PORTFOLIO), KeyboardButton(text=BTN_SELL_TOP)],
            [KeyboardButton(text=BTN_DAILY), KeyboardButton(text=BTN_ANALYZE)],
            [KeyboardButton(text=BTN_PRICES), KeyboardButton(text=BTN_TEST)],
            [KeyboardButton(text=BTN_CLOCK), KeyboardButton(text=BTN_REFRESH)],
            [KeyboardButton(text=BTN_PANIC), KeyboardButton(text=BTN_SETTINGS)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Choose action or /help",
    )
    logger.debug("Main keyboard created: 16 buttons, 8 rows")
    return kb


def get_inline_status_kb(is_running: bool) -> InlineKeyboardMarkup:
    """Inline keyboard for status message. Buttons are state-dependent."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🟡 RUNNING" if is_running else "🟢 START",
                callback_data=CB_NOOP if is_running else MenuCallback(action="start").pack(),
            ),
            InlineKeyboardButton(
                text="🔴 STOP" if is_running else "⚪ STOPPED",
                callback_data=MenuCallback(action="stop").pack() if is_running else CB_NOOP,
            ),
        ],
        [
            InlineKeyboardButton(text="💰 Balance", callback_data=MenuCallback(action="balance").pack()),
            InlineKeyboardButton(text="📦 Inventory", callback_data=MenuCallback(action="inventory").pack()),
        ],
        [
            InlineKeyboardButton(text="📈 Profits", callback_data=MenuCallback(action="profits").pack()),
            InlineKeyboardButton(text="💼 Portfolio", callback_data=MenuCallback(action="portfolio").pack()),
        ],
        [
            InlineKeyboardButton(text="📅 Daily", callback_data=MenuCallback(action="daily").pack()),
            InlineKeyboardButton(text="🔄 Refresh", callback_data=MenuCallback(action="refresh_status").pack()),
        ],
    ])


def get_inline_inventory_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for inventory message."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Refresh", callback_data=MenuCallback(action="inventory").pack()),
            InlineKeyboardButton(text="📈 Profits", callback_data=MenuCallback(action="profits").pack()),
        ],
        [InlineKeyboardButton(text="⬅️ Back to Status", callback_data=MenuCallback(action="refresh_status").pack())],
    ])


def get_inline_balance_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for balance message."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data=MenuCallback(action="balance").pack())],
    ])


def get_inline_profits_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for profits message."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data=MenuCallback(action="profits").pack())],
        [InlineKeyboardButton(text="⬅️ Status", callback_data=MenuCallback(action="refresh_status").pack())],
    ])


def get_inline_portfolio_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for portfolio message."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data=MenuCallback(action="portfolio").pack())],
        [InlineKeyboardButton(text="⬅️ Status", callback_data=MenuCallback(action="refresh_status").pack())],
    ])


def get_inline_daily_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for daily briefing message."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Refresh", callback_data=MenuCallback(action="daily").pack()),
            InlineKeyboardButton(text="🧠 Analyze", callback_data=MenuCallback(action="analyze").pack()),
        ],
        [InlineKeyboardButton(text="⬅️ Status", callback_data=MenuCallback(action="refresh_status").pack())],
    ])


def get_inline_analyze_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for analyze/reflection message."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Re-run", callback_data=MenuCallback(action="analyze").pack())],
        [InlineKeyboardButton(text="⬅️ Status", callback_data=MenuCallback(action="refresh_status").pack())],
    ])
