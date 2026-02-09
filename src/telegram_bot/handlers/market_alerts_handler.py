"""Обработчики для управления уведомлениями о рынке.

Этот модуль предоставляет обработчики для подписки на уведомления
о значимых изменениях на рынке, трендах и арбитражных возможностях.
"""

from typing import Any

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from src.telegram_bot.market_alerts import get_alerts_manager
from src.telegram_bot.notifier import (
    NOTIFICATION_TYPES,
    get_user_alerts,
    load_user_alerts,
    register_notification_handlers,
    remove_price_alert,
)
from src.utils.canonical_logging import get_logger
from src.utils.exceptions import handle_exceptions
from src.utils.telegram_error_handlers import telegram_error_boundary

# Настройка логирования
logger = get_logger(__name__)


# Функция преобразования типов уведомлений в человекочитаемые названия
ALERT_TYPES = {
    "price_changes": "📈 Изменения цен",
    "trending": "🔥 Трендовые предметы",
    "volatility": "📊 Волатильность рынка",
    "arbitrage": "💰 Арбитражные возможности",
    "price_drop": "⬇️ Падение цены",
    "price_rise": "⬆️ Рост цены",
    "volume_increase": "📊 Рост объема торгов",
    "good_deal": "💰 Выгодное предложение",
    "trend_change": "📊 Изменение тренда",
}


@telegram_error_boundary(
    user_friendly_message="❌ Произошла ошибка при обработке команды /alerts",
)
async def alerts_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает команду /alerts для управления подписками на уведомления.

    Args:
        update: Объект обновления от Telegram
        context: Контекст бота

    """
    if not update.effective_user or not update.message:
        return
    user_id = update.effective_user.id

    # Получаем менеджер уведомлений
    # Передаем bot из context, если менеджер еще не инициализирован
    alerts_manager = get_alerts_manager(bot=context.bot)

    # Получаем текущие подписки пользователя
    user_subscriptions = alerts_manager.get_user_subscriptions(user_id)

    # Получаем настроенные оповещения о ценах из нового модуля
    price_alerts = await get_user_alerts(user_id)

    # Создаем клавиатуру для управления подписками
    keyboard = []

    # Кнопки для глобального мониторинга рынка
    for alert_type, alert_name in ALERT_TYPES.items():
        if alert_type in {
            "price_changes",
            "trending",
            "volatility",
            "arbitrage",
        }:
            if alert_type in user_subscriptions:
                button_text = f"✅ {alert_name}"
            else:
                button_text = alert_name
            keyboard.append(
                [
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"alerts:{alert_type}",
                    ),
                ],
            )

    # Добавляем кнопки управления
    keyboard.extend((
        [InlineKeyboardButton("📊 Мои оповещения", callback_data="alerts:my_alerts")],
        [InlineKeyboardButton("➕ Добавить оповещение", callback_data="alerts:create_alert")],
    ))

    # Добавляем кнопки управления
    control_row = []

    # Кнопка "Подписаться на все", если есть неактивные подписки
    if len(user_subscriptions) < 4:  # Только для основных 4 типов
        control_row.append(
            InlineKeyboardButton(
                "🔔 Подписаться на все",
                callback_data="alerts:subscribe_all",
            ),
        )

    # Кнопка "Отписаться от всех", если есть активные подписки
    if user_subscriptions:
        control_row.append(
            InlineKeyboardButton(
                "🔕 Отписаться от всех",
                callback_data="alerts:unsubscribe_all",
            ),
        )

    if control_row:
        keyboard.append(control_row)

    # Добавляем кнопку настроек, если есть хотя бы одна подписка
    if user_subscriptions or price_alerts:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "⚙️ Настройки уведомлений",
                    callback_data="alerts:settings",
                ),
            ],
        )

    # Добавляем кнопку возврата к основному меню
    keyboard.append(
        [
            InlineKeyboardButton("⬅️ Назад в меню", callback_data="arbitrage"),
        ],
    )

    # Формируем сообщение
    message_text = "🔔 *Управление уведомлениями*\n\n"

    if user_subscriptions:
        message_text += "Вы подписаны на следующие типы уведомлений о рынке:\n"
        for alert_type in user_subscriptions:
            message_text += f"• {ALERT_TYPES.get(alert_type, alert_type)}\n"
        message_text += "\n"

    if price_alerts:
        message_text += f"У вас {len(price_alerts)} активных оповещений о ценах предметов.\n"
        message_text += "Нажмите 'Мои оповещения' для просмотра и управления.\n\n"

    if not user_subscriptions and not price_alerts:
        message_text += (
            "Вы не подписаны ни на какие уведомления. "
            "Выберите типы уведомлений, которые хотите получать:\n\n"
            "• 📈 *Изменения цен* - уведомления о значительных "
            "изменениях цен на предметы\n"
            "• 🔥 *Трендовые предметы* - уведомления о популярных "
            "предметах с высоким спросом\n"
            "• 📊 *Волатильность рынка* - уведомления о нестабильности "
            "цен и возможностях для трейдинга\n"
            "• 💰 *Арбитражные возможности* - уведомления о выгодных "
            "возможностях для арбитража\n\n"
            "Также вы можете настроить персональные оповещения "
            "для конкретных предметов."
        )

    # Отправляем сообщение с клавиатурой
    await update.message.reply_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


@handle_exceptions(
    logger_instance=logger,
    default_error_message="Ошибка при обработке колбэка уведомлений",
    reraise=False,
)
# ==================== Alert Action Handlers ====================
async def _handle_toggle_alert(
    query,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
    user_id: int,
    alerts_manager,
) -> None:
    """Handle toggle alert subscription action."""
    if len(parts) < 3:
        await query.answer("Неверный формат данных")
        return

    alert_type = parts[2]
    user_subscriptions = alerts_manager.get_user_subscriptions(user_id)

    if alert_type in user_subscriptions:
        # Unsubscribe
        success = alerts_manager.unsubscribe(user_id, alert_type)
        if success:
            alert_name = ALERT_TYPES.get(alert_type, alert_type)
            await query.answer(f"Вы отписались от уведомлений: {alert_name}")
        else:
            await query.answer("Не удалось отписаться от уведомлений")
    else:
        # Subscribe
        success = alerts_manager.subscribe(user_id, alert_type)
        if success:
            alert_name = ALERT_TYPES.get(alert_type, alert_type)
            await query.answer(f"Вы подписались на уведомления: {alert_name}")
        else:
            await query.answer("Не удалось подписаться на уведомления")

    await update_alerts_keyboard(query, alerts_manager, user_id)


async def _handle_subscribe_all(
    query,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
    user_id: int,
    alerts_manager,
) -> None:
    """Handle subscribe all action."""
    count = 0
    for alert_type in ALERT_TYPES:
        if alerts_manager.subscribe(user_id, alert_type):
            count += 1

    await query.answer(f"Подписано на {count} типов уведомлений")
    await update_alerts_keyboard(query, alerts_manager, user_id)


async def _handle_unsubscribe_all(
    query,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
    user_id: int,
    alerts_manager,
) -> None:
    """Handle unsubscribe all action."""
    if hasattr(alerts_manager, "unsubscribe_all"):
        success = alerts_manager.unsubscribe_all(user_id)
    else:
        # Fallback to loop
        user_subscriptions = alerts_manager.get_user_subscriptions(user_id)
        success = True
        for alert_type in user_subscriptions:
            if not alerts_manager.unsubscribe(user_id, alert_type):
                success = False

    if success:
        await query.answer("Вы отписались от всех уведомлений")
    else:
        await query.answer("Возникли ошибки при отписке от уведомлений")

    await update_alerts_keyboard(query, alerts_manager, user_id)


async def _handle_settings_action(
    query,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
    user_id: int,
    alerts_manager,
) -> None:
    """Handle settings action."""
    await show_alerts_settings(query, alerts_manager, user_id)


async def _handle_my_alerts_action(
    query,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
    user_id: int,
    alerts_manager,
) -> None:
    """Handle my alerts action."""
    await show_user_alerts_list(query, user_id)


async def _handle_create_alert_action(
    query,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
    user_id: int,
    alerts_manager,
) -> None:
    """Handle create alert action."""
    await show_create_alert_form(query, user_id)


async def _handle_remove_alert(
    query,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
    user_id: int,
    alerts_manager,
) -> None:
    """Handle remove alert action."""
    if len(parts) < 3:
        await query.answer("Неверный формат данных")
        return

    alert_id = parts[2]
    success = await remove_price_alert(user_id, alert_id)

    if success:
        await query.answer("Оповещение удалено")
        await show_user_alerts_list(query, user_id)
    else:
        await query.answer("Ошибка при удалении оповещения")


async def _handle_threshold_action(
    query,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
    user_id: int,
    alerts_manager,
) -> None:
    """Handle threshold change action."""
    if len(parts) < 4:
        await query.answer("Неверный формат данных")
        return

    alert_type = parts[2]
    direction = parts[3]

    threshold_key = f"{alert_type}_threshold"
    current_threshold = alerts_manager.alert_thresholds.get(threshold_key, 0)

    if direction == "up":
        new_threshold = current_threshold * 1.5
    elif direction == "down":
        new_threshold = max(current_threshold * 0.7, 1.0)
    else:
        new_threshold = current_threshold

    success = alerts_manager.update_alert_threshold(alert_type, new_threshold)

    if success:
        await query.answer(f"Порог уведомлений изменен: {new_threshold:.1f}")
    else:
        await query.answer("Не удалось изменить порог уведомлений")

    await show_alerts_settings(query, alerts_manager, user_id)


async def _handle_interval_action(
    query,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
    user_id: int,
    alerts_manager,
) -> None:
    """Handle interval change action."""
    if len(parts) < 4:
        await query.answer("Неверный формат данных")
        return

    alert_type = parts[2]
    direction = parts[3]

    current_interval = alerts_manager.check_intervals.get(alert_type, 3600)

    if direction == "up":
        new_interval = min(current_interval * 2, 86400)  # Max 24 hours
    elif direction == "down":
        new_interval = max(current_interval // 2, 300)  # Min 5 minutes
    else:
        new_interval = current_interval

    success = alerts_manager.update_check_interval(alert_type, new_interval)

    if success:
        interval_display = f"{new_interval // 60} мин"
        if new_interval >= 3600:
            interval_display = f"{new_interval // 3600} ч"
        await query.answer(f"Интервал проверки изменен: {interval_display}")
    else:
        await query.answer("Не удалось изменить интервал проверки")

    await show_alerts_settings(query, alerts_manager, user_id)


async def _handle_back_to_alerts_action(
    query,
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    parts: list[str],
    user_id: int,
    alerts_manager,
) -> None:
    """Handle back to alerts action."""
    await update_alerts_keyboard(query, alerts_manager, user_id)


# Alert action dispatcher mapping
_ALERT_ACTION_HANDLERS = {
    "toggle": _handle_toggle_alert,
    "subscribe_all": _handle_subscribe_all,
    "unsubscribe_all": _handle_unsubscribe_all,
    "settings": _handle_settings_action,
    "my_alerts": _handle_my_alerts_action,
    "create_alert": _handle_create_alert_action,
    "remove_alert": _handle_remove_alert,
    "threshold": _handle_threshold_action,
    "interval": _handle_interval_action,
    "back_to_alerts": _handle_back_to_alerts_action,
}


async def alerts_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает нажатия на кнопки управления уведомлениями.

    Args:
        update: Объект обновления от Telegram
        context: Контекст бота

    """
    query = update.callback_query
    if not query:
        return
    user_id = query.from_user.id

    # Разбираем данные колбэка
    parts = query.data.split(":")  # type: ignore

    if len(parts) < 2:
        await query.answer("Неверный формат данных")
        return

    action = parts[1]

    try:
        alerts_manager = get_alerts_manager(bot=context.bot)
    except Exception:
        await query.answer("Ошибка инициализации менеджера уведомлений")
        return

    # Dispatch to appropriate handler
    handler = _ALERT_ACTION_HANDLERS.get(action)
    if handler:
        await handler(query, update, context, parts, user_id, alerts_manager)
    else:
        await query.answer("Неизвестное действие")


async def update_alerts_keyboard(query: CallbackQuery, alerts_manager: Any, user_id: int) -> None:
    """Обновляет клавиатуру управления уведомлениями.

    Args:
        query: Объект запроса колбэка
        alerts_manager: Экземпляр менеджера уведомлений
        user_id: ID пользователя

    """
    # Получаем текущие подписки пользователя
    user_subscriptions = alerts_manager.get_user_subscriptions(user_id)

    # Получаем настроенные оповещения о ценах из нового модуля
    price_alerts = await get_user_alerts(user_id)

    # Создаем клавиатуру для управления подписками
    keyboard = []

    # Кнопки для глобального мониторинга рынка
    for alert_type, alert_name in ALERT_TYPES.items():
        if alert_type in {
            "price_changes",
            "trending",
            "volatility",
            "arbitrage",
        }:
            # Отмечаем активные подписки
            if alert_type in user_subscriptions:
                button_text = f"✅ {alert_name}"
            else:
                button_text = alert_name

            keyboard.append(
                [
                    InlineKeyboardButton(
                        button_text,
                        callback_data=f"alerts:toggle:{alert_type}",
                    ),
                ],
            )

    # Кнопки для управления оповещениями о конкретных предметах
    keyboard.extend((
        [InlineKeyboardButton("📊 Мои оповещения", callback_data="alerts:my_alerts")],
        [InlineKeyboardButton("➕ Добавить оповещение", callback_data="alerts:create_alert")],
    ))

    # Добавляем кнопки управления
    control_row = []

    # Кнопка "Подписаться на все", если есть неактивные подписки
    if len(user_subscriptions) < 4:  # Только для основных 4 типов
        control_row.append(
            InlineKeyboardButton(
                "🔔 Подписаться на все",
                callback_data="alerts:subscribe_all",
            ),
        )

    # Кнопка "Отписаться от всех", если есть активные подписки
    if user_subscriptions:
        control_row.append(
            InlineKeyboardButton(
                "🔕 Отписаться от всех",
                callback_data="alerts:unsubscribe_all",
            ),
        )

    if control_row:
        keyboard.append(control_row)

    # Добавляем кнопку настроек, если есть хотя бы одна подписка
    if user_subscriptions or price_alerts:
        keyboard.append(
            [
                InlineKeyboardButton(
                    "⚙️ Настройки уведомлений",
                    callback_data="alerts:settings",
                ),
            ],
        )

    # Добавляем кнопку возврата к основному меню
    keyboard.append(
        [
            InlineKeyboardButton("⬅️ Назад в меню", callback_data="arbitrage"),
        ],
    )

    # Формируем сообщение
    message_text = "🔔 *Управление уведомлениями*\n\n"

    if user_subscriptions:
        message_text += "Вы подписаны на следующие типы уведомлений о рынке:\n"
        for alert_type in user_subscriptions:
            message_text += f"• {ALERT_TYPES.get(alert_type, alert_type)}\n"
        message_text += "\n"

    if price_alerts:
        message_text += f"У вас {len(price_alerts)} активных оповещений о ценах предметов.\n"
        message_text += "Нажмите 'Мои оповещения' для просмотра и управления.\n\n"

    if not user_subscriptions and not price_alerts:
        message_text += (
            "Вы не подписаны ни на какие уведомления. Выберите типы "
            "уведомлений, которые хотите получать:\n\n"
            "• 📈 *Изменения цен* - уведомления о значительных изменениях "
            "цен на предметы\n"
            "• 🔥 *Трендовые предметы* - уведомления о популярных "
            "предметах с высоким спросом\n"
            "• 📊 *Волатильность рынка* - уведомления о нестабильности "
            "цен и возможностях для трейдинга\n"
            "• 💰 *Арбитражные возможности* - уведомления о выгодных "
            "возможностях для арбитража\n\n"
            "Также вы можете настроить персональные оповещения для "
            "конкретных предметов."
        )

    # Обновляем сообщение
    await query.edit_message_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def show_user_alerts_list(query: CallbackQuery, user_id: int) -> None:
    """Показывает список оповещений пользователя из нового модуля notifier.

    Args:
        query: Объект запроса колбэка
        user_id: ID пользователя

    """
    # Получаем оповещения пользователя
    alerts = await get_user_alerts(user_id)

    if not alerts:
        # Если нет оповещений
        keyboard = [
            [
                InlineKeyboardButton(
                    "➕ Создать оповещение",
                    callback_data="alerts:create_alert",
                ),
            ],
            [
                InlineKeyboardButton(
                    "⬅️ Назад к уведомлениям",
                    callback_data="alerts:back_to_alerts",
                ),
            ],
        ]

        await query.edit_message_text(
            "🔔 *Мои оповещения*\n\n"
            "У вас нет активных оповещений о ценах предметов.\n"
            "Создайте новое оповещение, чтобы получать уведомления "
            "о значимых изменениях цен.",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown",
        )
        return

    # Форматируем список оповещений
    message_text = f"🔔 *Мои оповещения ({len(alerts)})*\n\n"

    for i, alert in enumerate(alerts, 1):
        alert_type = NOTIFICATION_TYPES.get(alert["type"], alert["type"])
        title = alert["title"]
        threshold = alert["threshold"]

        if alert["type"] == "price_drop":
            message_text += f"{i}. ⬇️ *{title}*\n"
            message_text += f"   Тип: {alert_type}\n"
            message_text += f"   Порог: ${threshold:.2f}\n\n"
        elif alert["type"] == "price_rise":
            message_text += f"{i}. ⬆️ *{title}*\n"
            message_text += f"   Тип: {alert_type}\n"
            message_text += f"   Порог: ${threshold:.2f}\n\n"
        elif alert["type"] == "volume_increase":
            message_text += f"{i}. 📊 *{title}*\n"
            message_text += f"   Тип: {alert_type}\n"
            message_text += f"   Порог: {int(threshold)}\n\n"
        elif alert["type"] == "good_deal":
            message_text += f"{i}. 💰 *{title}*\n"
            message_text += f"   Тип: {alert_type}\n"
            message_text += f"   Порог: {threshold:.2f}%\n\n"
        elif alert["type"] == "trend_change":
            message_text += f"{i}. 📈 *{title}*\n"
            message_text += f"   Тип: {alert_type}\n"
            message_text += f"   Порог: {threshold:.2f}%\n\n"

    # Создаем клавиатуру
    keyboard = []

    # Кнопки для удаления оповещений
    for i, alert in enumerate(alerts, 1):
        if i <= 5:  # Ограничиваем количество кнопок
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"❌ Удалить #{i} ({alert['title'][:15]}...)",
                        callback_data=f"alerts:remove_alert:{alert['id']}",
                    ),
                ],
            )

    # Кнопки управления
    keyboard.append(
        [
            InlineKeyboardButton(
                "➕ Создать оповещение",
                callback_data="alerts:create_alert",
            ),
        ],
    )

    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ Назад к уведомлениям",
                callback_data="alerts:back_to_alerts",
            ),
        ],
    )

    # Обновляем сообщение
    await query.edit_message_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def show_create_alert_form(query: CallbackQuery, _user_id: int) -> None:
    """Показывает форму создания оповещения.

    Args:
        query: Объект запроса колбэка
        _user_id: ID пользователя

    """
    # Форматируем инструкцию
    message_text = (
        "➕ *Создание нового оповещения*\n\n"
        "Для создания оповещения используйте команду:\n"
        "`/alert <item_id> <тип_оповещения> <порог>`\n\n"
        "*Типы оповещений:*\n"
        "• `price_drop` - цена упала ниже порога (в $)\n"
        "• `price_rise` - цена выросла выше порога (в $)\n"
        "• `volume_increase` - объем торгов превысил порог (кол-во)\n"
        "• `good_deal` - найдено предложение со скидкой больше порога (%)\n"
        "• `trend_change` - изменился тренд цены (порог в % уверенности)\n\n"
        "*Пример:*\n"
        "`/alert 12345abcde price_drop 50.0`\n\n"
        "Для получения ID предмета, найдите его на DMarket и скопируйте "
        "из URL."
    )

    # Создаем клавиатуру
    keyboard = [
        [
            InlineKeyboardButton(
                "⬅️ Назад к списку оповещений",
                callback_data="alerts:my_alerts",
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Назад к уведомлениям",
                callback_data="alerts:back_to_alerts",
            ),
        ],
    ]

    # Обновляем сообщение
    await query.edit_message_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def show_alerts_settings(query: CallbackQuery, alerts_manager: Any, user_id: int) -> None:
    """Показывает настройки уведомлений.

    Args:
        query: Объект запроса колбэка
        alerts_manager: Экземпляр менеджера уведомлений
        user_id: ID пользователя

    """
    # Получаем текущие подписки пользователя
    user_subscriptions = alerts_manager.get_user_subscriptions(user_id)

    # Формируем сообщение с настройками
    message_text = "⚙️ *Настройки уведомлений*\n\n"

    if user_subscriptions:
        message_text += "*Уведомления о рынке:*\n"

        for alert_type in user_subscriptions:
            alert_name = ALERT_TYPES.get(alert_type, alert_type)
            threshold = 0
            interval = "неизвестно"

            # Получаем текущие настройки порогов и интервалов
            if alert_type == "price_changes":
                threshold = alerts_manager.alert_thresholds.get(
                    "price_change_percent",
                    15.0,
                )
                message_text += f"• {alert_name}\n"
                message_text += f"  Порог изменения цены: {threshold}%\n"
            elif alert_type == "trending":
                threshold = alerts_manager.alert_thresholds.get(
                    "trending_popularity",
                    50.0,
                )
                message_text += f"• {alert_name}\n"
                message_text += f"  Порог популярности: {threshold}\n"
            elif alert_type == "volatility":
                threshold = alerts_manager.alert_thresholds.get(
                    "volatility_threshold",
                    25.0,
                )
                message_text += f"• {alert_name}\n"
                message_text += f"  Порог волатильности: {threshold}\n"
            elif alert_type == "arbitrage":
                threshold = alerts_manager.alert_thresholds.get(
                    "arbitrage_profit_percent",
                    10.0,
                )
                message_text += f"• {alert_name}\n"
                message_text += f"  Минимальная прибыль: {threshold}%\n"

            # Форматируем интервал для отображения
            current_interval = alerts_manager.check_intervals.get(
                alert_type,
                3600,
            )
            if current_interval >= 3600:
                interval = f"{current_interval // 3600} ч"
            else:
                interval = f"{current_interval // 60} мин"

            message_text += f"  Интервал проверки: {interval}\n\n"

    # Добавляем настройки личных оповещений
    message_text += "*Настройки личных оповещений:*\n"
    message_text += "Для настройки параметров личных оповещений используйте команду:\n"
    message_text += "`/alertsettings <параметр>=<значение>`\n\n"
    message_text += "Доступные параметры:\n"
    message_text += "• `enabled=true|false` - включить/выключить оповещения\n"
    message_text += "• `min_interval=минуты` - минимальный интервал между оповещениями\n"
    message_text += "• `quiet_start=час` - начало тихих часов (не отправлять оповещения)\n"
    message_text += "• `quiet_end=час` - конец тихих часов\n"
    message_text += "• `max_alerts=число` - максимальное количество оповещений в день\n\n"
    message_text += "Пример: `/alertsettings enabled=true min_interval=30`"

    # Создаем клавиатуру для управления настройками
    keyboard = []

    # Кнопки управления порогами и интервалами для подписок
    for alert_type in user_subscriptions:
        # Кнопки управления порогами
        threshold_row = [
            InlineKeyboardButton(
                f"⬇️ Порог {alert_type}",
                callback_data=f"alerts:threshold:{alert_type}:down",
            ),
            InlineKeyboardButton(
                f"⬆️ Порог {alert_type}",
                callback_data=f"alerts:threshold:{alert_type}:up",
            ),
        ]
        keyboard.append(threshold_row)

        # Кнопки управления интервалами
        interval_row = [
            InlineKeyboardButton(
                f"⬇️ Интервал {alert_type}",
                callback_data=f"alerts:interval:{alert_type}:down",
            ),
            InlineKeyboardButton(
                f"⬆️ Интервал {alert_type}",
                callback_data=f"alerts:interval:{alert_type}:up",
            ),
        ]
        keyboard.append(interval_row)

    # Кнопка возврата
    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ Назад к уведомлениям",
                callback_data="alerts:back_to_alerts",
            ),
        ],
    )

    # Обновляем сообщение
    await query.edit_message_text(
        message_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


def register_alerts_handlers(application: Application) -> None:
    """Регистрирует обработчики для уведомлений о рыночных событиях.

    Args:
        application: Экземпляр приложения Telegram

    """
    # Загружаем настройки оповещений о ценах предметов
    load_user_alerts()

    # Регистрируем обработчики для управления уведомлениями о рынке
    application.add_handler(CommandHandler("alerts", alerts_command))
    application.add_handler(
        CallbackQueryHandler(alerts_callback, pattern="^alerts:"),
    )

    # Регистрируем обработчики для управления оповещениями о ценах предметов
    register_notification_handlers(application)


@handle_exceptions(
    logger_instance=logger,
    default_error_message="Ошибка при инициализации менеджера уведомлений",
    reraise=False,
)
async def initialize_alerts_manager(_application: Application) -> None:
    """Инициализирует менеджер уведомлений.

    Args:
        _application: Экземпляр приложения Telegram

    """
    # Пока ничего не инициализируем, это заглушка
    logger.info("Инициализация менеджера уведомлений")
