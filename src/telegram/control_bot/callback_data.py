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


class ConfirmCallback(CallbackData, prefix="confirm"):
    """Confirmation dialog callbacks.

    Usage:
        cb = ConfirmCallback(action="yes", context="liquidate")
        cb.pack()  # "confirm:yes:liquidate"
    """
    action: str  # "yes" or "no"
    context: str = ""  # what we're confirming
