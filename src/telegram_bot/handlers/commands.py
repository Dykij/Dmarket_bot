"""Обработчики команд Telegram бота.

Этот модуль содержит функции обработки команд от пользователей.
Все обработчики команд, начинающихся с / собраны здесь.
"""

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from src.telegram_bot.handlers.dashboard_handler import show_dashboard
from src.telegram_bot.handlers.dmarket_status import dmarket_status_impl
from src.telegram_bot.handlers.main_keyboard import get_main_keyboard
from src.telegram_bot.keyboards import (
    get_marketplace_comparison_keyboard,
)
from src.utils.canonical_logging import get_logger
from src.utils.telegram_error_handlers import telegram_error_boundary

logger = get_logger(__name__)


@telegram_error_boundary(user_friendly_message="❌ Ошибка при запуске бота")
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /start.

    Args:
        update: Объект Update от Telegram
        context: Контекст взаимодействия с ботом

    """
    if not update.message:
        return

    # Запускаем главную клавиатуру
    from src.telegram_bot.handlers.main_keyboard import start_command as main_start

    await main_start(update, context)


@telegram_error_boundary(user_friendly_message="❌ Ошибка при отображении справки")
async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает команду /help.

    Args:
        update: Объект Update от Telegram
        context: Контекст взаимодействия с ботом

    """
    if not update.message:
        return

    await update.message.reply_text(
        "❓ <b>Доступные команды:</b>\n"
        "/start - Начать работу с ботом\n"
        "/menu - Главное меню\n"
        "/balance - Проверить баланс",
        parse_mode=ParseMode.HTML,
        reply_markup=get_main_keyboard(),
    )


@telegram_error_boundary(user_friendly_message="❌ Ошибка при открытии WebApp")
async def webapp_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает команду /webapp.

    Args:
        update: Объект Update от Telegram
        context: Контекст взаимодействия с ботом

    """
    if not update.message:
        return

    try:
        from src.telegram_bot.keyboards.webapp import get_dmarket_webapp_keyboard

        await update.message.reply_text(
            "🌐 <b>DMarket WebApp</b>\n\nНажмите кнопку ниже, чтобы открыть DMarket прямо в Telegram:",
            reply_markup=get_dmarket_webapp_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        logger.exception(f"Error in webapp_command: {e}")
        await update.message.reply_text(
            "❌ Ошибка при открытии WebApp",
            parse_mode=ParseMode.HTML,
        )


@telegram_error_boundary(user_friendly_message="❌ Ошибка при загрузке дашборда")
async def dashboard_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает команду /dashboard.

    Args:
        update: Объект Update от Telegram
        context: Контекст взаимодействия с ботом

    """
    await show_dashboard(update, context)


@telegram_error_boundary(user_friendly_message="❌ Ошибка при загрузке рынков")
async def markets_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает команду /markets.

    Args:
        update: Объект Update от Telegram
        context: Контекст взаимодействия с ботом

    """
    if not update.message:
        return

    await update.message.reply_text(
        "📊 <b>Сравнение рынков</b>\n\nВыберите рынки для сравнения:",
        reply_markup=get_marketplace_comparison_keyboard(),
        parse_mode=ParseMode.HTML,
    )


@telegram_error_boundary(user_friendly_message="❌ Ошибка при получении статуса")
async def dmarket_status_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает команду /status или /dmarket.

    Args:
        update: Объект Update от Telegram
        context: Контекст взаимодействия с ботом

    """
    await dmarket_status_impl(update, context, status_message=update.message)


@telegram_error_boundary(user_friendly_message="❌ Ошибка в меню арбитража")
async def arbitrage_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает команду /arbitrage.

    Args:
        update: Объект Update от Telegram
        context: Контекст взаимодействия с ботом

    """
    if not update.effective_chat or not update.message:
        return

    await update.effective_chat.send_action(ChatAction.TYPING)

    # Redirect to main menu
    keyboard = get_main_keyboard()
    await update.message.reply_text(
        "🔍 <b>Арбитраж</b>\n\nИспользуйте главное меню для доступа к авто-торговле:",
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )


@telegram_error_boundary(user_friendly_message="❌ Ошибка обработки команды")
async def handle_text_buttons(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает текстовые сообщения от постоянной клавиатуры.

    Args:
        update: Объект Update от Telegram
        context: Контекст взаимодействия с ботом

    """
    if not update.message or not update.message.text:
        return

    text = update.message.text

    # Кнопки для главного меню
    if text == "⚡ Упрощенное меню":
        # Вызываем главное меню
        from src.telegram_bot.handlers.main_keyboard import start_command as main_start

        await main_start(update, context)
        return
    if text in {"💰 Баланс", "📊 Баланс"}:
        # Показываем баланс

        # Создаём mock update с callback_query
        await dmarket_status_impl(
            update,
            context,
            status_message=update.message,
        )
        return
    if text in {"📈 Статистика", "📊 Статистика"}:
        # Показываем статистику
        await dmarket_status_impl(
            update,
            context,
            status_message=update.message,
        )
        return

    # Обрабатываем старые текстовые команды от клавиатуры
    if text in {"📊 Арбитраж", "🔍 Арбитраж"}:
        # Перенаправляем на главное меню
        from src.telegram_bot.handlers.main_keyboard import start_command as main_start

        await main_start(update, context)
    elif text in {"💰 Баланс", "📊 Баланс"}:
        await dmarket_status_impl(
            update,
            context,
            status_message=update.message,
        )
    elif text == "🎯 Таргеты":
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        await update.message.reply_text(
            "🎯 <b>Таргеты (Buy Orders)</b>\n\n"
            "Управление целевыми ордерами на покупку:\n\n"
            "• Создайте таргет на нужный предмет\n"
            "• Система автоматически выставит buy order\n"
            "• Получайте уведомления о выполнении",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "➕ Создать таргет", callback_data="target_create"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "📋 Мои таргеты", callback_data="target_list"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "📊 Статистика", callback_data="target_stats"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "◀️ Главное меню", callback_data="main_menu"
                        )
                    ],
                ]
            ),
            parse_mode=ParseMode.HTML,
        )
    elif text == "📦 Инвентарь":
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        await update.message.reply_text(
            "📦 <b>Ваш инвентарь</b>\n\n"
            "⚠️ Для просмотра инвентаря необходимо настроить API ключи DMarket.",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "🔑 Настроить API", callback_data="settings_api"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "◀️ Главное меню", callback_data="main_menu"
                        )
                    ],
                ]
            ),
            parse_mode=ParseMode.HTML,
        )
    elif text in {"📈 Аналитика", "📈 Анализ рынка"}:
        from telegram import InlineKeyboardButton, InlineKeyboardMarkup

        await update.message.reply_text(
            "📈 <b>Аналитика рынка</b>\n\nВыберите раздел аналитики:",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "📊 Тренды", callback_data="analysis_trends"
                        ),
                        InlineKeyboardButton(
                            "💹 Волатильность", callback_data="analysis_vol"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "🔥 Топ продаж", callback_data="analysis_top"
                        ),
                        InlineKeyboardButton(
                            "📉 Падающие", callback_data="analysis_drop"
                        ),
                    ],
                    [
                        InlineKeyboardButton(
                            "🎯 Рекомендации", callback_data="analysis_rec"
                        )
                    ],
                    [
                        InlineKeyboardButton(
                            "◀️ Главное меню", callback_data="main_menu"
                        )
                    ],
                ]
            ),
            parse_mode=ParseMode.HTML,
        )
    elif text == "🔔 Оповещения":
        from src.telegram_bot.keyboards import get_alert_keyboard

        await update.message.reply_text(
            "🔔 <b>Управление оповещениями</b>\n\n"
            "НастSwarmте оповещения о изменении цен и "
            "других рыночных событиях:",
            reply_markup=get_alert_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    elif text == "🌐 Открыть DMarket":
        await webapp_command(update, context)
    elif text == "⚙️ НастSwarmки":
        from src.telegram_bot.keyboards import get_settings_keyboard

        await update.message.reply_text(
            "⚙️ <b>НастSwarmки бота</b>\n\nВыберите раздел для настSwarmки:",
            reply_markup=get_settings_keyboard(),
            parse_mode=ParseMode.HTML,
        )
    elif text == "❓ Помощь":
        await help_command(update, context)


# Экспортируем обработчики команд
__all__ = [
    "arbitrage_command",
    "dmarket_status_command",
    "handle_text_buttons",
    "help_command",
    "markets_command",
    "start_command",
    "webapp_command",
]
