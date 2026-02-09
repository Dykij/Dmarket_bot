"""Модуль с обработчиками для работы с историей продаж и анализа ликвидности."""

import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from src.dmarket.arbitrage_sales_analysis import (
    analyze_item_liquidity,
    enhanced_arbitrage_search,
    get_sales_volume_stats,
)
from src.dmarket.sales_history import analyze_sales_history
from src.telegram_bot.utils.formatters import (
    format_arbitrage_with_sales,
    format_liquidity_analysis,
    format_sales_analysis,
    format_sales_volume_stats,
    get_trend_emoji,
)
from src.utils.exceptions import APIError

# Настройка логирования
logger = logging.getLogger(__name__)

# Экспортируемые функции и объекты
__all__ = [
    "GAMES",
    "get_liquidity_emoji",
    "get_trend_emoji",
    "handle_arbitrage_with_sales",
    "handle_liquidity_analysis",
    "handle_sales_analysis",
    "handle_sales_volume_stats",
]

# Константы для games.py
GAMES = {
    "csgo": "CS2",
    "dota2": "Dota 2",
    "tf2": "Team Fortress 2",
    "rust": "Rust",
}


def get_liquidity_emoji(liquidity_score: float) -> str:
    """Возвращает эмодзи для уровня ликвидности.

    Args:
        liquidity_score: Оценка ликвидности (0-100)

    Returns:
        str: Эмодзи, соответствующий уровню ликвидности

    """
    if liquidity_score >= 80:
        return "💎"  # Очень высокая ликвидность
    if liquidity_score >= 60:
        return "💧"  # Высокая ликвидность
    if liquidity_score >= 40:
        return "💦"  # Средняя ликвидность
    if liquidity_score >= 20:
        return "🌊"  # Низкая ликвидность
    return "❄️"  # Очень низкая ликвидность


async def handle_sales_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /sales_analysis для анализа истории продаж предмета.

    Пример использования:
    /sales_analysis AWP | Asiimov (Field-Tested)

    Args:
        update: Объект обновления Telegram
        context: Контекст бота

    """
    if not update.message or not update.message.text:
        return

    # Извлекаем название предмета из сообщения
    message = update.message.text.strip()
    parts = message.split(" ", 1)

    if len(parts) < 2:
        await update.message.reply_text(
            "⚠️ <b>Необходимо указать название предмета!</b>\n\n"
            "Пример: <code>/sales_analysis AWP | Asiimov (Field-Tested)</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    item_name = parts[1].strip()

    # Отправляем сообщение о начале анализа
    reply_message = await update.message.reply_text(
        f"🔍 Анализ истории продаж для предмета:\n<code>{item_name}</code>\n\n"
        "⏳ Пожалуйста, подождите...",
        parse_mode=ParseMode.HTML,
    )

    try:
        # Выполняем анализ истории продаж напрямую
        analysis = await analyze_sales_history(
            item_name=item_name,
            days=14,  # Анализируем за 2 недели
        )

        # Форматируем результаты анализа с использованием функции форматирования
        formatted_message = format_sales_analysis(analysis, item_name)

        # Добавляем кнопку для показа полной истории продаж
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📊 Подробная история",
                        callback_data=f"sales_history:{item_name}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "💧 Анализ ликвидности",
                        callback_data=f"liquidity:{item_name}",
                    ),
                ],
            ],
        )

        # Отправляем результаты анализа
        await reply_message.edit_text(
            text=formatted_message,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )

    except APIError as e:
        # Обработка ошибок API
        logger.exception(f"Ошибка API при анализе продаж: {e}")
        await reply_message.edit_text(
            f"❌ <b>Ошибка при получении данных о продажах:</b> {e.message}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        # Обработка прочих ошибок
        logger.exception(f"Ошибка при анализе продаж: {e!s}")
        await reply_message.edit_text(
            f"❌ <b>Произошла ошибка:</b> {e!s}",
            parse_mode=ParseMode.HTML,
        )


async def handle_arbitrage_with_sales(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает команду /arbitrage_sales для поиска арбитражных возможностей
    с учетом истории продаж.

    Args:
        update: Объект обновления Telegram
        context: Контекст бота

    """
    if not update.message:
        return

    # Получаем текущую игру из контекста или используем CSGO по умолчанию
    game = "csgo"
    if context.user_data and "current_game" in context.user_data:
        game = context.user_data["current_game"]

    # Отправляем сообщение о начале поиска
    game_name = GAMES.get(game, game)
    reply_message = await update.message.reply_text(
        f"🔍 Поиск арбитражных возможностей для {game_name}...\n\n⏳ Пожалуйста, подождите...",
        parse_mode=ParseMode.HTML,
    )

    try:
        # Выполняем поиск арбитражных возможностей напрямую
        results = await enhanced_arbitrage_search(
            game=game,
            min_profit=1.0,
        )

        # Форматируем результаты поиска с использованием функции форматирования
        # Format expects a dict with 'opportunities' key
        results_dict = {"opportunities": results, "game": game}
        formatted_message = format_arbitrage_with_sales(results_dict, game)

        # Добавляем кнопки управления
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📊 Все возможности",
                        callback_data=f"all_arbitrage_sales:{game}",
                    ),
                    InlineKeyboardButton(
                        "🔍 Обновить",
                        callback_data=f"refresh_arbitrage_sales:{game}",
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "⚙️ Настроить фильтры",
                        callback_data=f"setup_sales_filters:{game}",
                    ),
                ],
            ],
        )

        # Отправляем результаты поиска
        await reply_message.edit_text(
            text=formatted_message,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )

    except APIError as e:
        # Обработка ошибок API
        logger.exception(f"Ошибка API при поиске арбитража с учетом продаж: {e}")
        await reply_message.edit_text(
            f"❌ <b>Ошибка при поиске арбитражных возможностей:</b> {e.message}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        # Обработка прочих ошибок
        logger.exception(f"Ошибка при поиске арбитража с учетом продаж: {e!s}")
        await reply_message.edit_text(
            f"❌ <b>Произошла ошибка:</b> {e!s}",
            parse_mode=ParseMode.HTML,
        )


async def handle_liquidity_analysis(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает команду /liquidity для анализа ликвидности предмета.

    Пример использования:
    /liquidity AWP | Asiimov (Field-Tested)

    Args:
        update: Объект обновления Telegram
        context: Контекст бота

    """
    if not update.message or not update.message.text:
        return

    # Извлекаем название предмета из сообщения
    message = update.message.text.strip()
    parts = message.split(" ", 1)

    if len(parts) < 2:
        await update.message.reply_text(
            "⚠️ <b>Необходимо указать название предмета!</b>\n\n"
            "Пример: <code>/liquidity AWP | Asiimov (Field-Tested)</code>",
            parse_mode=ParseMode.HTML,
        )
        return

    item_name = parts[1].strip()
    # Note: Game filtering reserved for future implementation

    # Отправляем сообщение о начале анализа
    reply_message = await update.message.reply_text(
        f"🔍 Анализ ликвидности предмета:\n<code>{item_name}</code>\n\n⏳ Пожалуйста, подождите...",
        parse_mode=ParseMode.HTML,
    )

    try:
        # Выполняем анализ ликвидности напрямую
        # Note: analyze_item_liquidity expects item_id, using item_name as ID
        analysis = await analyze_item_liquidity(item_id=item_name)

        # Форматируем результаты анализа с использованием функции форматирования
        formatted_message = format_liquidity_analysis(analysis, item_name)

        # Добавляем кнопки управления
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📊 История продаж",
                        callback_data=f"sales_history:{item_name}",
                    ),
                    InlineKeyboardButton(
                        "🔍 Обновить анализ",
                        callback_data=f"refresh_liquidity:{item_name}",
                    ),
                ],
            ],
        )

        # Отправляем результаты анализа
        await reply_message.edit_text(
            text=formatted_message,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )

    except APIError as e:
        # Обработка ошибок API
        logger.exception(f"Ошибка API при анализе ликвидности: {e}")
        await reply_message.edit_text(
            f"❌ <b>Ошибка при анализе ликвидности:</b> {e.message}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        # Обработка прочих ошибок
        logger.exception(f"Ошибка при анализе ликвидности: {e!s}")
        await reply_message.edit_text(
            f"❌ <b>Произошла ошибка:</b> {e!s}",
            parse_mode=ParseMode.HTML,
        )


async def handle_sales_volume_stats(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает команду /sales_volume для просмотра статистики.

    Args:
        update: Объект обновления Telegram
        context: Контекст бота

    """
    if not update.message:
        return

    # Получаем текущую игру из контекста или используем CSGO по умолчанию
    game = "csgo"
    if context.user_data and "current_game" in context.user_data:
        game = context.user_data["current_game"]

    # Отправляем сообщение о начале запроса
    game_name = GAMES.get(game, game)
    reply_message = await update.message.reply_text(
        f"🔍 Получение статистики объема продаж для {game_name}...\n\n⏳ Пожалуйста, подождите...",
        parse_mode=ParseMode.HTML,
    )

    try:
        # Выполняем запрос статистики напрямую
        stats = await get_sales_volume_stats(game=game)

        # Форматируем результаты с использованием функции форматирования
        formatted_message = format_sales_volume_stats(stats, game)

        # Добавляем кнопки управления
        keyboard = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "📊 Показать все предметы",
                        callback_data=f"all_volume_stats:{game}",
                    ),
                    InlineKeyboardButton(
                        "🔍 Обновить",
                        callback_data=f"refresh_volume_stats:{game}",
                    ),
                ],
            ],
        )

        # Отправляем результаты
        await reply_message.edit_text(
            text=formatted_message,
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )

    except APIError as e:
        # Обработка ошибок API
        logger.exception(f"Ошибка API при получении статистики объема продаж: {e}")
        await reply_message.edit_text(
            f"❌ <b>Ошибка при получении статистики:</b> {e.message}",
            parse_mode=ParseMode.HTML,
        )
    except Exception as e:
        # Обработка прочих ошибок
        logger.exception(f"Ошибка при получении статистики объема продаж: {e!s}")
        await reply_message.edit_text(
            f"❌ <b>Произошла ошибка:</b> {e!s}",
            parse_mode=ParseMode.HTML,
        )
