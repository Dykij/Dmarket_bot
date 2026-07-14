"""
settings_fsm.py — FSM for bot settings management via Telegram (v15.6).

Allows admins to change bot settings through a conversational interface.
Uses aiogram's FSM (Finite State Machine) for multi-step flows.

Supported settings:
- MIN_SPREAD_PCT — minimum spread percentage
- MAX_POSITION_RISK_PCT — maximum position risk
- DRAWDOWN_FREEZE_THRESHOLD — drawdown freeze threshold
- KELLY_FRACTION — Kelly criterion fraction
- TRADE_LOCK_HOURS — trade lock period in hours
"""

from __future__ import annotations

import logging

from aiogram import F, Router, types
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from .callback_data import SettingsCallback
from .resilience import safe_call
from .state import is_admin

logger = logging.getLogger("TelegramControl.settings_fsm")
router = Router(name="telegram-control-settings")


class SettingsFSM(StatesGroup):
    """FSM states for settings management."""
    choosing_setting = State()
    entering_value = State()


# Settings that can be changed via bot
CHANGEABLE_SETTINGS = {
    "min_spread": {
        "name": "MIN_SPREAD_PCT",
        "description": "Minimum spread percentage for trades",
        "current_cmd": "/settings",
        "unit": "%",
        "min_val": 1.0,
        "max_val": 50.0,
    },
    "max_risk": {
        "name": "MAX_POSITION_RISK_PCT",
        "description": "Maximum position risk percentage",
        "current_cmd": "/settings",
        "unit": "%",
        "min_val": 1.0,
        "max_val": 100.0,
    },
    "drawdown": {
        "name": "DRAWDOWN_FREEZE_THRESHOLD",
        "description": "Drawdown freeze threshold",
        "current_cmd": "/settings",
        "unit": "%",
        "min_val": 5.0,
        "max_val": 50.0,
    },
    "kelly": {
        "name": "KELLY_FRACTION",
        "description": "Kelly criterion fraction (0.5 = Half Kelly)",
        "current_cmd": "/settings",
        "unit": "",
        "min_val": 0.1,
        "max_val": 1.0,
    },
    "lock_hours": {
        "name": "TRADE_LOCK_HOURS",
        "description": "Trade lock period in hours",
        "current_cmd": "/settings",
        "unit": "h",
        "min_val": 1,
        "max_val": 720,
    },
}


@router.message(F.text == "⚙️ SETTINGS")
@safe_call
async def cmd_settings_menu(message: types.Message, state_fsm: FSMContext | None = None):
    """Show settings menu with current values."""
    if not is_admin(message.from_user.id if message.from_user else 0):
        return

    from src.config import Config

    text = "⚙️ *Bot Settings*\n\nSelect a setting to change:\n\n"
    for key, setting in CHANGEABLE_SETTINGS.items():
        current_val = getattr(Config, setting["name"], "N/A")
        text += f"• `{key}`: {current_val}{setting['unit']} — {setting['description']}\n"

    text += "\nTo change, use: /set <setting> <value>"
    text += "\nExample: /set min_spread 5"

    await message.answer(text, parse_mode="Markdown")


@router.message(F.text.startswith("/set"))
@safe_call
async def cmd_set_setting(message: types.Message):
    """Handle /set command to change a setting.

    Usage: /set <setting_name> <value>
    Example: /set min_spread 5
    """
    if not is_admin(message.from_user.id if message.from_user else 0):
        return

    parts = message.text.split() if message.text else []
    if len(parts) < 3:
        await message.answer(
            "❌ Usage: /set <setting> <value>\n"
            "Example: /set min_spread 5\n\n"
            "Available settings: " + ", ".join(CHANGEABLE_SETTINGS.keys())
        )
        return

    setting_key = parts[1].lower()
    value_str = parts[2]

    if setting_key not in CHANGEABLE_SETTINGS:
        await message.answer(
            f"❌ Unknown setting: `{setting_key}`\n"
            f"Available: {', '.join(CHANGEABLE_SETTINGS.keys())}",
            parse_mode="Markdown",
        )
        return

    setting = CHANGEABLE_SETTINGS[setting_key]

    # Validate value
    try:
        value = float(value_str)
    except ValueError:
        await message.answer(f"❌ Invalid value: `{value_str}`. Must be a number.", parse_mode="Markdown")
        return

    if value < setting["min_val"] or value > setting["max_val"]:
        await message.answer(
            f"❌ Value must be between {setting['min_val']} and {setting['max_val']}{setting['unit']}"
        )
        return

    # Apply setting (via environment variable override)
    import os
    os.environ[setting["name"]] = str(value)

    # Reload config
    try:
        from src.config import Config
        # Force reload by re-reading env
        setattr(Config, setting["name"], value)
    except Exception as e:
        logger.warning(f"Failed to reload config: {e}")

    await message.answer(
        f"✅ *Setting Updated*\n\n"
        f"• {setting['name']}: `{value}{setting['unit']}`\n"
        f"• {setting['description']}\n\n"
        f"⚠️ Changes take effect on next bot restart.",
        parse_mode="Markdown",
    )
    logger.info(f"Admin changed {setting['name']} to {value}")
