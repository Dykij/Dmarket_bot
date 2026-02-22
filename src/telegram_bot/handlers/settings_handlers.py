"""
Refactored settings handlers with early returns and separation of concerns.

Phase 2 Refactoring (Week 5-6):
- Applied early returns pattern
- Split 227-line function into 10 focused functions
- Reduced nesting depth (<3 levels)
- Improved readability and testability
"""

from telegram import Update
from telegram.ext import ContextTypes

from src.telegram_bot.keyboards import (
    get_back_to_settings_keyboard,
    get_language_keyboard,
    get_settings_keyboard,
)
from src.telegram_bot.localization import LANGUAGES, get_localized_text
from src.telegram_bot.profiles import get_user_profile, save_user_profiles


async def settings_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """MAlgon settings callback handler with routing to specific handlers."""
    if not update.callback_query:
        return

    query = update.callback_query
    if not query.data:
        return

    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # Route to specific handler based on callback data
    handlers = {
        "settings": _handle_main_settings,
        "settings_language": _handle_language_menu,
        "settings_api_keys": _handle_api_keys_display,
        "settings_toggle_trading": _handle_toggle_trading,
        "settings_limits": _handle_limits_display,
        "settings_notifications": _handle_notifications_menu,
    }

    # Check for handlers with prefixes
    if data in handlers:
        await handlers[data](query, user_id)
    elif data.startswith("language:"):
        await _handle_language_selection(query, user_id, data)
    elif data.startswith("limit_"):
        await _handle_limit_adjustment(query, user_id, data)
    elif data.startswith("notif_"):
        await _handle_notification_toggle(query, user_id, data)


async def _handle_main_settings(query, user_id: int) -> None:
    """Display main settings menu."""
    settings_text = get_localized_text(user_id, "settings")
    keyboard = get_settings_keyboard()

    await query.edit_message_text(
        text=settings_text,
        reply_markup=keyboard,
    )


async def _handle_language_menu(query, user_id: int) -> None:
    """Display language selection menu."""
    profile = get_user_profile(user_id)
    current_language = profile.get("language", "ru")
    lang_display_name = LANGUAGES.get(current_language, current_language)

    language_text = get_localized_text(
        user_id,
        "language",
        lang=lang_display_name,
    )
    keyboard = get_language_keyboard(current_language)

    await query.edit_message_text(
        text=language_text,
        reply_markup=keyboard,
    )


async def _handle_language_selection(query, user_id: int, data: str) -> None:
    """Handle language selection from callback data."""
    lang_code = data.split(":")[1]

    if lang_code not in LANGUAGES:
        await _send_unsupported_language_error(query, lang_code)
        return

    _save_language_preference(user_id, lang_code)

    lang_display = LANGUAGES.get(lang_code, lang_code)
    confirmation_text = get_localized_text(
        user_id,
        "language_set",
        lang=lang_display,
    )

    keyboard = get_back_to_settings_keyboard()
    await query.edit_message_text(
        text=confirmation_text,
        reply_markup=keyboard,
    )


def _save_language_preference(user_id: int, lang_code: str) -> None:
    """Save user's language preference to profile."""
    profile = get_user_profile(user_id)

    if "settings" in profile:
        profile["settings"]["language"] = lang_code
    else:
        profile["language"] = lang_code

    save_user_profiles()


async def _send_unsupported_language_error(query, lang_code: str) -> None:
    """Send error message for unsupported language selection."""
    error_text = f"⚠️ Язык {lang_code} не поддерживается."
    keyboard = get_language_keyboard("ru")

    await query.edit_message_text(
        text=error_text,
        reply_markup=keyboard,
    )


async def _handle_api_keys_display(query, user_id: int) -> None:
    """Display API keys settings (masked for security)."""
    profile = get_user_profile(user_id)
    api_key = profile.get("api_key", "")
    api_secret = profile.get("api_secret", "")

    api_key_display = _mask_api_key(api_key)
    api_secret_display = _mask_api_secret(api_secret)

    api_text = _format_api_keys_text(api_key_display, api_secret_display)

    keyboard = get_back_to_settings_keyboard()
    await query.edit_message_text(
        text=api_text,
        reply_markup=keyboard,
    )


def _mask_api_key(api_key: str) -> str:
    """Mask API key for display."""
    if not api_key:
        return "Не установлен"

    return f"{api_key[:5]}...{api_key[-5:]}"


def _mask_api_secret(api_secret: str) -> str:
    """Mask API secret for display."""
    if not api_secret:
        return "Не установлен"  # noqa: S105 - display text, not password

    return f"{api_secret[:3]}...{api_secret[-3:]}"


def _format_api_keys_text(api_key_display: str, api_secret_display: str) -> str:
    """Format API keys display text."""
    return (
        f"🔑 НастSwarmки API DMarket\n\n"
        f"Публичный ключ: {api_key_display}\n"
        f"Секретный ключ: {api_secret_display}\n\n"
        f"Для изменения ключей используйте команду /setup"
    )


async def _handle_toggle_trading(query, user_id: int) -> None:
    """Toggle automatic trading on/off."""
    profile = get_user_profile(user_id)
    current_state = profile.get("auto_trading_enabled", False)

    profile["auto_trading_enabled"] = not current_state
    save_user_profiles()

    status_text = _get_trading_status_text(user_id, profile["auto_trading_enabled"])
    settings_text = get_localized_text(user_id, "settings")
    keyboard = get_settings_keyboard()

    await query.edit_message_text(
        text=f"{settings_text}\n\n{status_text}",
        reply_markup=keyboard,
    )


def _get_trading_status_text(user_id: int, is_enabled: bool) -> str:
    """Get localized trading status text."""
    if is_enabled:
        return get_localized_text(user_id, "auto_trading_on")

    return get_localized_text(user_id, "auto_trading_off")


async def _handle_limits_display(query, user_id: int) -> None:
    """Display trading limits settings."""
    profile = get_user_profile(user_id)
    trade_settings = profile.get("trade_settings", {})

    limits_text = _format_limits_text(trade_settings)
    keyboard = get_back_to_settings_keyboard()

    await query.edit_message_text(
        text=limits_text,
        reply_markup=keyboard,
    )


def _format_limits_text(trade_settings: dict) -> str:
    """Format trading limits display text."""
    min_profit = trade_settings.get("min_profit", 2.0)
    max_price = trade_settings.get("max_price", 50.0)
    max_daily_trades = trade_settings.get("max_daily_trades", 10)

    return (
        f"📊 Лимиты торговли\n\n"
        f"Минимальная прибыль: {min_profit}%\n"
        f"Максимальная цена: ${max_price}\n"
        f"Максимум сделок в день: {max_daily_trades}\n\n"
        f"Для изменения используйте команды:\n"
        f"/set_min_profit <значение>\n"
        f"/set_max_price <значение>\n"
        f"/set_max_trades <значение>"
    )


async def _handle_limit_adjustment(query, user_id: int, data: str) -> None:
    """Handle limit adjustment from callback."""
    # Parse limit type and value from callback data
    # Format: limit_<type>_<action> (e.g., limit_profit_increase)
    parts = data.split("_")
    if len(parts) < 3:
        return

    limit_type = parts[1]
    action = parts[2]

    profile = get_user_profile(user_id)
    trade_settings = profile.setdefault("trade_settings", {})

    _adjust_limit_value(trade_settings, limit_type, action)
    save_user_profiles()

    await _handle_limits_display(query, user_id)


def _adjust_limit_value(trade_settings: dict, limit_type: str, action: str) -> None:
    """Adjust specific limit value based on action."""
    adjustments = {
        "profit": ("min_profit", 0.5, 0.1, 50.0),  # (key, step, min, max)
        "price": ("max_price", 5.0, 1.0, 1000.0),
        "trades": ("max_daily_trades", 5, 1, 100),
    }

    if limit_type not in adjustments:
        return

    key, step, min_val, max_val = adjustments[limit_type]
    current = trade_settings.get(key, step)

    if action == "increase":
        new_value = min(current + step, max_val)
    elif action == "decrease":
        new_value = max(current - step, min_val)
    else:
        return

    trade_settings[key] = new_value


async def _handle_notifications_menu(query, user_id: int) -> None:
    """Display notifications settings menu."""
    profile = get_user_profile(user_id)
    notif_settings = profile.get("notification_settings", {})

    notifications_text = _format_notifications_text(notif_settings)
    # keyboard = get_notifications_keyboard(notif_settings)  # TODO: implement

    await query.edit_message_text(
        text=notifications_text,
        # reply_markup=keyboard,  # TODO: implement
    )


def _format_notifications_text(notif_settings: dict) -> str:
    """Format notifications settings display text."""
    arbitrage_enabled = notif_settings.get("arbitrage_alerts", True)
    target_filled = notif_settings.get("target_filled", True)
    price_alerts = notif_settings.get("price_alerts", False)

    def status_emoji(enabled):
        return "✅" if enabled else "❌"

    return (
        f"🔔 НастSwarmки уведомлений\n\n"
        f"{status_emoji(arbitrage_enabled)} Алерты об арбитраже\n"
        f"{status_emoji(target_filled)} Заполнение таргетов\n"
        f"{status_emoji(price_alerts)} Алерты о ценах\n\n"
        f"Нажмите на переключатель для изменения"
    )


async def _handle_notification_toggle(query, user_id: int, data: str) -> None:
    """Toggle specific notification setting."""
    # Format: notif_<type>_toggle (e.g., notif_arbitrage_toggle)
    parts = data.split("_")
    if len(parts) < 2:
        return

    notif_type = parts[1]

    profile = get_user_profile(user_id)
    notif_settings = profile.setdefault("notification_settings", {})

    _toggle_notification_setting(notif_settings, notif_type)
    save_user_profiles()

    await _handle_notifications_menu(query, user_id)


def _toggle_notification_setting(notif_settings: dict, notif_type: str) -> None:
    """Toggle specific notification setting value."""
    setting_keys = {
        "arbitrage": "arbitrage_alerts",
        "target": "target_filled",
        "price": "price_alerts",
    }

    if notif_type not in setting_keys:
        return

    key = setting_keys[notif_type]
    current = notif_settings.get(key, True)
    notif_settings[key] = not current
