"""Обработчик команд для внутрирыночного арбитража на DMarket."""

from typing import Any

import structlog
from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, ContextTypes

from src.dmarket.arbitrage import GAMES
from src.dmarket.intramarket_arbitrage import (
    PriceAnomalyType,
    find_mispriced_rare_items,
    find_price_anomalies,
    find_trending_items,
)
from src.telegram_bot.keyboards import create_pagination_keyboard
from src.telegram_bot.pagination import pagination_manager
from src.telegram_bot.utils.api_client import create_api_client_from_env
from src.utils.exceptions import handle_exceptions

logger = structlog.get_logger(__name__)

# Константы для callback данных
INTRA_ARBITRAGE_ACTION = "intra"
ANOMALY_ACTION = "anomaly"
TRENDING_ACTION = "trend"
RARE_ACTION = "rare"


def format_intramarket_results(
    items: list[dict[str, Any]],
    current_page: int,
    _items_per_page: int,
) -> str:
    """Форматирует результаты внутрирыночного арбитража для отображения.

    Args:
        items: Список результатов арбитража
        current_page: Текущая страница
        items_per_page: Количество элементов на странице

    Returns:
        Отформатированный текст

    """
    if not items:
        return "Нет результатов для отображения."

    header = f"📄 Страница {current_page + 1}\n\n"

    formatted_items = []
    for item in items:
        formatted_items.append(format_intramarket_item(item))

    return header + "\n\n".join(formatted_items)


def format_intramarket_item(result: dict[str, Any]) -> str:
    """Форматирует результат внутрирыночного арбитража для отображения.

    Args:
        result: Результат арбитража

    Returns:
        Отформатированный текст

    """
    result_type = result.get("type", "")

    if result_type == PriceAnomalyType.UNDERPRICED:
        # Ценовая аномалия (недооцененный предмет)
        item_to_buy = result.get("item_to_buy", {})
        item_title = item_to_buy.get("title", "Неизвестный предмет")
        buy_price = result.get("buy_price", 0.0)
        sell_price = result.get("sell_price", 0.0)
        profit_percentage = result.get("profit_percentage", 0.0)
        profit_after_fee = result.get("profit_after_fee", 0.0)
        similarity = result.get("similarity", 0.0)

        return (
            f"🔍 *{item_title}*\n"
            f"💰 Купить за ${buy_price:.2f}, продать за ${sell_price:.2f}\n"
            f"📈 Прибыль: ${profit_after_fee:.2f} ({profit_percentage:.1f}%)\n"
            f"🔄 Схожесть: {similarity:.0%}\n"
            f"🏷️ ID для покупки: `{item_to_buy.get('itemId', '')}`"
        )

    if result_type == PriceAnomalyType.TRENDING_UP:
        # Растущая цена
        item = result.get("item", {})
        item_title = item.get("title", "Неизвестный предмет")
        current_price = result.get("current_price", 0.0)
        projected_price = result.get("projected_price", 0.0)
        price_change_percent = result.get("price_change_percent", 0.0)
        potential_profit_percent = result.get("potential_profit_percent", 0.0)
        sales_velocity = result.get("sales_velocity", 0)

        return (
            f"📈 *{item_title}*\n"
            f"💰 Текущая цена: ${current_price:.2f}\n"
            f"🚀 Прогноз цены: ${projected_price:.2f} (+{price_change_percent:.1f}%)\n"
            f"💵 Потенциальная прибыль: "
            f"${projected_price - current_price:.2f} "
            f"({potential_profit_percent:.1f}%)\n"
            f"🔄 Объем продаж: {sales_velocity} шт.\n"
            f"🏷️ ID для покупки: `{item.get('itemId', '')}`"
        )

    if result_type == PriceAnomalyType.RARE_TRAlgoTS:
        # Предмет с редкими характеристиками
        item = result.get("item", {})
        item_title = item.get("title", "Неизвестный предмет")
        current_price = result.get("current_price", 0.0)
        estimated_value = result.get("estimated_value", 0.0)
        price_difference_percent = result.get("price_difference_percent", 0.0)
        rare_trAlgots = result.get("rare_trAlgots", [])

        trAlgots_text = "\n".join([f"  • {trAlgot}" for trAlgot in rare_trAlgots])

        return (
            f"💎 *{item_title}*\n"
            f"💰 Текущая цена: ${current_price:.2f}\n"
            f"⭐ Оценочная стоимость: ${estimated_value:.2f} "
            f"(+{price_difference_percent:.1f}%)\n"
            f"✨ Редкие особенности:\n{trAlgots_text}\n"
            f"🏷️ ID для покупки: `{item.get('itemId', '')}`"
        )

    # Неизвестный тип
    return "❓ Неизвестный тип результата"


@handle_exceptions
async def display_results_with_pagination(
    query: CallbackQuery,
    results: list[dict[str, Any]],
    title: str,
    user_id: int,
    action_type: str,
    game: str,
) -> None:
    """Отображает результаты с пагинацией.

    Args:
        query: Запрос от пользователя
        results: Список результатов для отображения
        title: Заголовок сообщения
        user_id: ID пользователя
        action_type: Тип действия (anomaly, trending, rare)
        game: Код игры

    """
    # Если результаты не найдены
    if not results:
        msg = f"ℹ️ *{title}*\n\nВозможности не найдены. Попробуйте другой тип сканирования или игру."
        await query.edit_message_text(
            msg,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ Назад",
                            callback_data=f"{INTRA_ARBITRAGE_ACTION}",
                        ),
                    ],
                ],
            ),
        )
        return

    # Создаем пагинацию для результатов используя унифицированный подход
    pagination_manager.add_items_for_user(
        user_id,
        results,
        f"intra_{action_type}",
    )

    # Получаем текущую страницу
    items, current_page, total_pages = pagination_manager.get_page(user_id)

    # Форматируем результаты
    formatted_text = format_intramarket_results(
        items,
        current_page,
        pagination_manager.get_items_per_page(user_id),
    )

    # Создаем клавиатуру с пагинацией
    pagination_keyboard = create_pagination_keyboard(
        current_page=current_page,
        total_pages=total_pages,
        prefix=f"intra_paginate:{action_type}_{game}_",
    )

    # Добавляем заголовок к тексту
    final_text = f"*{title}*\n\n{formatted_text}"

    # Отправляем сообщение с результатами
    await query.edit_message_text(
        final_text,
        parse_mode="Markdown",
        reply_markup=pagination_keyboard,
    )


@handle_exceptions
async def handle_intramarket_pagination(
    update: Update,
    _context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает навигацию по страницам результатов."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if not update.effective_user:
        return
    user_id = update.effective_user.id
    callback_data = query.data
    if not callback_data:
        return

    # Парсим данные callback
    # Формат: intra_paginate:direction:action_type:game
    data_parts = callback_data.split(":")
    if len(data_parts) < 3:
        return

    direction = data_parts[1]  # next или prev
    action_type = data_parts[2]
    game = data_parts[3] if len(data_parts) > 3 else "csgo"

    # Обновляем страницу
    if direction == "next":
        pagination_manager.next_page(user_id)
    elif direction == "prev":
        pagination_manager.prev_page(user_id)

    # Получаем заголовок на основе типа действия
    default_title = f"Результаты для {GAMES.get(game, game)}"
    title_map = {
        ANOMALY_ACTION: f"🔍 Ценовые аномалии для {GAMES.get(game, game)}",
        TRENDING_ACTION: f"📈 Растущие в цене {GAMES.get(game, game)}",
        RARE_ACTION: f"💎 Редкие предметы {GAMES.get(game, game)}",
    }
    title = title_map.get(action_type, default_title)

    # Получаем текущую страницу
    items, current_page, total_pages = pagination_manager.get_page(user_id)

    # Форматируем результаты
    formatted_text = format_intramarket_results(
        items,
        current_page,
        pagination_manager.get_items_per_page(user_id),
    )

    # Создаем клавиатуру с пагинацией
    pagination_keyboard = create_pagination_keyboard(
        current_page=current_page,
        total_pages=total_pages,
        prefix=f"intra_paginate:{action_type}_{game}_",
    )

    # Добавляем заголовок к тексту
    final_text = f"*{title}*\n\n{formatted_text}"

    # Отправляем сообщение с результатами
    await query.edit_message_text(
        final_text,
        parse_mode="Markdown",
        reply_markup=pagination_keyboard,
    )


@handle_exceptions
async def start_intramarket_arbitrage(
    update: Update,
    _context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает команду запуска внутрирыночного арбитража."""
    query = update.callback_query
    if query:
        await query.answer()

    if not update.effective_user:
        return
    user_id = update.effective_user.id

    anomaly_cb = f"{INTRA_ARBITRAGE_ACTION}_{ANOMALY_ACTION}"
    trending_cb = f"{INTRA_ARBITRAGE_ACTION}_{TRENDING_ACTION}"
    rare_cb = f"{INTRA_ARBITRAGE_ACTION}_{RARE_ACTION}"

    # Отправляем сообщение о начале сканирования
    await _context.bot.send_message(
        chat_id=user_id,
        text=(
            "🔍 *Поиск возможностей арбитража внутри DMarket*\n\nВыберите тип арбитража:"
        ),
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton(
                        "🔄 Ценовые аномалии",
                        callback_data=anomaly_cb,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "📈 Растущие в цене",
                        callback_data=trending_cb,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "💎 Редкие предметы",
                        callback_data=rare_cb,
                    ),
                ],
                [
                    InlineKeyboardButton(
                        "⬅️ Назад",
                        callback_data="arbitrage_menu",
                    ),
                ],
            ],
        ),
    )


@handle_exceptions
async def handle_intramarket_callback(
    update: Update,
    _context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает callback-запросы для внутрирыночного арбитража."""
    query = update.callback_query
    if not query:
        return
    await query.answer()

    if not update.effective_user:
        return
    user_id = update.effective_user.id

    if not query.data:
        return
    callback_data = query.data

    # Парсим данные callback
    data_parts = callback_data.split("_")
    if len(data_parts) < 2:
        await query.edit_message_text(
            "⚠️ Некорректные данные запроса.",
            parse_mode="Markdown",
        )
        return

    action_type = data_parts[1]
    game = "csgo"  # По умолчанию CS2

    # Если указана игра
    if len(data_parts) >= 3:
        game = data_parts[2]

    # Показываем сообщение о начале сканирования
    await query.edit_message_text(
        f"🔍 *Сканирование {GAMES.get(game, game)}*\n\n"
        f"Идет поиск выгодных предложений. Пожалуйста, подождите...",
        parse_mode="Markdown",
    )

    # Определяем тип сканирования и запускаем соответствующую функцию
    results = []

    # Получаем API клиент с использованием улучшенного подхода
    api_client = create_api_client_from_env()

    if api_client is None:
        await query.edit_message_text(
            "❌ Не удалось создать API клиент. Проверьте настSwarmки API ключей.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ Назад",
                            callback_data=INTRA_ARBITRAGE_ACTION,
                        ),
                    ],
                ],
            ),
        )
        return

    if action_type == ANOMALY_ACTION:
        # Поиск ценовых аномалий
        anomalies = await find_price_anomalies(
            game=game,
            max_results=50,
            dmarket_api=api_client,
        )
        results = anomalies
        title = f"🔍 Ценовые аномалии для {GAMES.get(game, game)}"

    elif action_type == TRENDING_ACTION:
        # Поиск предметов с растущей ценой
        trending = await find_trending_items(
            game=game,
            max_results=50,
            dmarket_api=api_client,
        )
        results = trending
        title = f"📈 Растущие в цене {GAMES.get(game, game)}"

    elif action_type == RARE_ACTION:
        # Поиск редких предметов
        rare_items = await find_mispriced_rare_items(
            game=game,
            max_results=50,
            dmarket_api=api_client,
        )
        results = rare_items
        title = f"💎 Редкие предметы {GAMES.get(game, game)}"

    else:
        # Неизвестный тип действия
        await query.edit_message_text(
            "⚠️ Неизвестный тип сканирования.",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(
                [
                    [
                        InlineKeyboardButton(
                            "⬅️ Назад",
                            callback_data=INTRA_ARBITRAGE_ACTION,
                        ),
                    ],
                ],
            ),
        )
        return

    # Отображаем результаты с использованием унифицированной функции
    await display_results_with_pagination(
        query=query,
        results=results,
        title=title,
        user_id=user_id,
        action_type=action_type,
        game=game,
    )


def register_intramarket_handlers(dispatcher: Any) -> None:
    """Регистрирует обработчики для внутрирыночного арбитража.

    Args:
        dispatcher: Диспетчер бота

    """
    # Основные обработчики
    dispatcher.add_handler(
        CallbackQueryHandler(
            start_intramarket_arbitrage,
            pattern=f"^{INTRA_ARBITRAGE_ACTION}$",
        ),
    )
    dispatcher.add_handler(
        CallbackQueryHandler(
            handle_intramarket_callback,
            pattern=f"^{INTRA_ARBITRAGE_ACTION}_",
        ),
    )

    # Обработчик пагинации
    dispatcher.add_handler(
        CallbackQueryHandler(
            handle_intramarket_pagination,
            pattern="^intra_paginate:",
        ),
    )
