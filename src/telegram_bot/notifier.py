"""Модуль для отправки уведомлений о рыночных изменениях пользователям.

FACADE MODULE - Re-exports from notifications/ package for backward compatibility.

Поддерживаемые типы уведомлений:
- Цена предмета упала ниже порога
- Появление выгодного предложения для покупки/продажи
- Изменение цен в наблюдаемом списке предметов
- Рост объема торгов предмета

Note:
    This module is deprecated. Please import directly from
    src.telegram_bot.notifications package instead.

Example:
    # Old (deprecated):
    from src.telegram_bot.notifier import add_price_alert

    # New (recommended):
    from src.telegram_bot.notifications import add_price_alert
"""

# Re-export all public functions from notifications package
# for backward compatibility
from src.telegram_bot.notifications import (  # Constants; Storage; Alerts management; Price checking; Handlers; Formatters; Trading notifications
    DEFAULT_USER_SETTINGS,
    NOTIFICATION_PRIORITIES,
    NOTIFICATION_TYPES,
    AlertStorage,
    add_price_alert,
    can_send_notification,
    check_all_alerts,
    check_good_deal_alerts,
    check_price_alert,
    create_alert_command,
    format_alert_message,
    format_alerts_list,
    format_item_brief,
    format_price,
    format_profit,
    format_user_settings,
    get_current_price,
    get_storage,
    get_user_alerts,
    get_user_settings,
    handle_alert_callback,
    handle_buy_cancel_callback,
    increment_notification_count,
    list_alerts_command,
    load_user_alerts,
    register_notification_handlers,
    remove_alert_command,
    remove_price_alert,
    reset_daily_counter,
    run_alerts_checker,
    save_user_alerts,
    send_buy_failed_notification,
    send_buy_intent_notification,
    send_buy_success_notification,
    send_crash_notification,
    send_critical_shutdown_notification,
    send_sell_success_notification,
    settings_command,
    update_user_settings,
)

# Re-export price analyzer functions for backward compatibility
# Tests patch these on notifier module, so they must be avAlgolable here
from src.utils.price_analyzer import calculate_price_trend, get_item_price_history

# Backward compatibility: expose _user_alerts at module level
# for existing code/tests that access notifier._user_alerts
_storage = get_storage()
_user_alerts = _storage.user_alerts
_current_prices_cache = _storage.prices_cache

# Add send_arbitrage_report to Notifier class if it exists in notifications
# Since this is a facade module, we can't easily add methods to a class that isn't defined here.
# However, the user asked to add it to src/telegram_bot/notifier.py.
# Given this file is a facade, we should probably add the function to src/telegram_bot/notifications/__init__.py
# and then export it here. But for now, let's define a standalone function here that mimics the behavior.


async def send_arbitrage_report(
    bot,
    chat_id: int,
    item_name: str,
    buy_price: float,
    sell_price: float,
    profit: float,
    roi: float,
) -> None:
    """Отправляет отчет о проведенной сделке в Telegram.

    Args:
        bot: Telegram bot instance
        chat_id: Chat ID to send to
        item_name: Название предмета
        buy_price: Цена покупки в USD
        sell_price: Цена продажи в USD
        profit: Ожидаемая прибыль в USD
        roi: ROI в процентах
    """
    message = (
        f"💰 <b>Успешная сделка!</b>\n\n"
        f"🏷 <b>Предмет:</b> <code>{item_name}</code>\n"
        f"📉 <b>Цена покупки:</b> <code>${buy_price:.2f}</code>\n"
        f"📈 <b>Цена продажи:</b> <code>${sell_price:.2f}</code>\n"
        f"💸 <b>Чистая прибыль:</b> <code>+${profit:.2f} ({roi:.1f}%)</code>\n"
        f"--- \n"
        f"🤖 <i>DMarket Bot Auto-Trade</i>"
    )

    try:
        await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
    except Exception as e:
        # Use print as logger might not be configured for this specific ad-hoc function
        print(f"Failed to send arbitrage report: {e}")


__all__ = [
    "DEFAULT_USER_SETTINGS",
    "NOTIFICATION_PRIORITIES",
    "NOTIFICATION_TYPES",
    "AlertStorage",
    "_current_prices_cache",
    "_user_alerts",
    "add_price_alert",
    "calculate_price_trend",
    "can_send_notification",
    "check_all_alerts",
    "check_good_deal_alerts",
    "check_price_alert",
    "create_alert_command",
    "format_alert_message",
    "format_alerts_list",
    "format_item_brief",
    "format_price",
    "format_profit",
    "format_user_settings",
    "get_current_price",
    "get_item_price_history",
    "get_storage",
    "get_user_alerts",
    "get_user_settings",
    "handle_alert_callback",
    "handle_buy_cancel_callback",
    "increment_notification_count",
    "list_alerts_command",
    "load_user_alerts",
    "register_notification_handlers",
    "remove_alert_command",
    "remove_price_alert",
    "reset_daily_counter",
    "run_alerts_checker",
    "save_user_alerts",
    "send_arbitrage_report",
    "send_buy_failed_notification",
    "send_buy_intent_notification",
    "send_buy_success_notification",
    "send_crash_notification",
    "send_critical_shutdown_notification",
    "send_sell_success_notification",
    "settings_command",
    "update_user_settings",
]
