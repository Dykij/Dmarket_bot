"""
keyboards.py — Reply and inline keyboards with constants.

Constants:
- BTN_* — text labels for the 10 reply-keyboard buttons
- CB_* — callback_data strings for inline buttons
"""

from aiogram.types import (
    ReplyKeyboardMarkup,
    KeyboardButton,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)


# ============================================================
# Reply keyboard button text constants
# ============================================================
BTN_START = "🚀 START BOT"
BTN_STOP = "🛑 STOP BOT"
BTN_BALANCE = "💰 BALANCE"
BTN_STATUS = "📊 STATUS"
BTN_INVENTORY = "📦 INVENTORY"
BTN_PROFITS = "📈 PROFITS"
BTN_TEST = "🧪 TEST ITEM"
BTN_SETTINGS = "⚙️ SETTINGS"
BTN_PANIC = "🔥 PANIC"
BTN_HELP = "🆘 HELP"


# ============================================================
# Inline keyboard callback_data constants
# ============================================================
CB_START = "btn:start"
CB_STOP = "btn:stop"
CB_BALANCE = "btn:balance"
CB_INVENTORY = "btn:inventory"
CB_PROFITS = "btn:profits"
CB_REFRESH_STATUS = "btn:refresh_status"
CB_NOOP = "noop"


# ============================================================
# Keyboards
# ============================================================
def get_main_keyboard() -> ReplyKeyboardMarkup:
    """Main reply keyboard — always visible at the bottom of the chat."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=BTN_START), KeyboardButton(text=BTN_STOP)],
            [KeyboardButton(text=BTN_BALANCE), KeyboardButton(text=BTN_STATUS)],
            [KeyboardButton(text=BTN_INVENTORY), KeyboardButton(text=BTN_PROFITS)],
            [KeyboardButton(text=BTN_TEST), KeyboardButton(text=BTN_SETTINGS)],
            [KeyboardButton(text=BTN_PANIC), KeyboardButton(text=BTN_HELP)],
        ],
        resize_keyboard=True,
        input_field_placeholder="Choose action or /help",
    )


def get_inline_status_kb(is_running: bool) -> InlineKeyboardMarkup:
    """Inline keyboard for status message. Buttons are state-dependent."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(
                text="🟡 RUNNING" if is_running else "🟢 START",
                callback_data=CB_NOOP if is_running else CB_START,
            ),
            InlineKeyboardButton(
                text="🔴 STOP" if is_running else "⚪ STOPPED",
                callback_data=CB_STOP if is_running else CB_NOOP,
            ),
        ],
        [
            InlineKeyboardButton(text="💰 Balance", callback_data=CB_BALANCE),
            InlineKeyboardButton(text="📦 Inventory", callback_data=CB_INVENTORY),
        ],
        [
            InlineKeyboardButton(text="📈 Profits", callback_data=CB_PROFITS),
            InlineKeyboardButton(text="🔄 Refresh", callback_data=CB_REFRESH_STATUS),
        ],
    ])


def get_inline_inventory_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for inventory message."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔄 Refresh", callback_data=CB_INVENTORY),
            InlineKeyboardButton(text="📈 Profits", callback_data=CB_PROFITS),
        ],
        [InlineKeyboardButton(text="⬅️ Back to Status", callback_data=CB_REFRESH_STATUS)],
    ])


def get_inline_balance_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for balance message (used by /balance and btn:balance)."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data=CB_BALANCE)],
    ])


def get_inline_profits_kb() -> InlineKeyboardMarkup:
    """Inline keyboard for profits message."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Refresh", callback_data=CB_PROFITS)],
        [InlineKeyboardButton(text="⬅️ Status", callback_data=CB_REFRESH_STATUS)],
    ])
