"""
callback_data.py — Type-safe callback data factories (v15.6).

Uses aiogram's CallbackData factory for type-safe callback parsing.
Replaces raw string constants with validated, structured callback data.

Source: aiogram 3.x documentation — "CallbackData factory"
"""

from aiogram.filters.callback_data import CallbackData


class MenuCallback(CallbackData, prefix="menu"):
    """Main menu action callbacks.

    Usage:
        cb = MenuCallback(action="balance")
        cb.pack()  # "menu:balance"
        MenuCallback.unpack("menu:balance")  # MenuCallback(action="balance")
    """
    action: str


class SettingsCallback(CallbackData, prefix="settings"):
    """Settings menu callbacks.

    Usage:
        cb = SettingsCallback(action="set", key="min_spread", value="5")
        cb.pack()  # "settings:set:min_spread:5"
    """
    action: str
    key: str = ""
    value: str = ""


class ConfirmCallback(CallbackData, prefix="confirm"):
    """Confirmation dialog callbacks.

    Usage:
        cb = ConfirmCallback(action="yes", context="liquidate")
        cb.pack()  # "confirm:yes:liquidate"
    """
    action: str  # "yes" or "no"
    context: str = ""  # what we're confirming


class ItemCallback(CallbackData, prefix="item"):
    """Item-specific callbacks (for future inventory management).

    Usage:
        cb = ItemCallback(action="sell", item_id="abc123")
        cb.pack()  # "item:sell:abc123"
    """
    action: str
    item_id: str = ""
