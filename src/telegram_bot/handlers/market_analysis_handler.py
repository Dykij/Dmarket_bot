"""Обработчики команд для анализа рынка и отслеживания тенденций."""

import logging
from typing import Any

from telegram import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes

from src.dmarket.arbitrage import GAMES
from src.dmarket.market_analysis import (
    analyze_market_volatility,
    analyze_price_changes,
    find_trending_items,
    generate_market_report,
)
from src.telegram_bot.keyboards import create_pagination_keyboard
from src.telegram_bot.pagination import pagination_manager
from src.telegram_bot.utils.api_client import create_api_client_from_env
from src.telegram_bot.utils.formatters import format_market_items

# Импортируем новые функции из улучшенного анализатора цен
from src.utils.price_analyzer import (
    find_undervalued_items,
    get_investment_recommendations,
)

# Настройка логирования
logger = logging.getLogger(__name__)


# ============================================================================
# Helper functions for market analysis (Phase 2 refactoring)
# ============================================================================


def _create_analysis_keyboard(game: str) -> list[list[InlineKeyboardButton]]:
    """Create analysis options keyboard for a game.

    Args:
        game: Game code

    Returns:
        Keyboard button rows
    """
    return [
        [
            InlineKeyboardButton(
                "📈 Изменения цен",
                callback_data=f"analysis:price_changes:{game}",
            ),
            InlineKeyboardButton(
                "🔥 Трендовые предметы",
                callback_data=f"analysis:trending:{game}",
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Волатильность",
                callback_data=f"analysis:volatility:{game}",
            ),
            InlineKeyboardButton(
                "📑 Полный отчет",
                callback_data=f"analysis:report:{game}",
            ),
        ],
        [
            InlineKeyboardButton(
                "💰 Недооцененные предметы",
                callback_data=f"analysis:undervalued:{game}",
            ),
            InlineKeyboardButton(
                "📊 Рекомендации",
                callback_data=f"analysis:recommendations:{game}",
            ),
        ],
    ]


def _add_game_selection_rows(
    keyboard: list[list[InlineKeyboardButton]],
    current_game: str,
) -> None:
    """Add game selection rows to keyboard.

    Args:
        keyboard: Keyboard to modify
        current_game: Currently selected game
    """
    game_row: list[InlineKeyboardButton] = []
    for game_code, game_name in GAMES.items():
        button_text = f"✅ {game_name}" if game_code == current_game else game_name
        game_row.append(
            InlineKeyboardButton(
                button_text,
                callback_data=f"analysis:select_game:{game_code}",
            ),
        )
        if len(game_row) == 2:
            keyboard.append(game_row)
            game_row = []

    if game_row:
        keyboard.append(game_row)

    keyboard.append(
        [InlineKeyboardButton("⬅️ Назад к арбитражу", callback_data="arbitrage")],
    )


async def _handle_game_selection(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    game: str,
) -> None:
    """Handle game selection action.

    Args:
        query: Callback query
        context: Bot context
        game: Selected game code
    """
    context.user_data["market_analysis"]["current_game"] = game
    keyboard = _create_analysis_keyboard(game)
    _add_game_selection_rows(keyboard, game)
    game_name = GAMES.get(game, game)

    await query.edit_message_text(
        f"🔎 *Анализ рынка DMarket*\n\n"
        f"Выберите тип анализа и игру для исследования тенденций рынка "
        f"и поиска выгодных возможностей.\n\n"
        f"Текущая игра: *{game_name}*",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def _run_price_changes_analysis(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    api_client: Any,
    user_settings: dict,
    current_game: str,
    user_id: int,
) -> None:
    """Run price changes analysis."""
    results = await analyze_price_changes(
        game=current_game,
        period=user_settings.get("period", "24h"),
        min_price=user_settings.get("min_price", 1.0),
        max_price=user_settings.get("max_price", 500.0),
        dmarket_api=api_client,
        limit=20,
    )
    pagination_manager.set_items(user_id, results, "price_changes")
    await show_price_changes_results(query, context, current_game)


async def _run_trending_analysis(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    api_client: Any,
    user_settings: dict,
    current_game: str,
    user_id: int,
) -> None:
    """Run trending items analysis."""
    results = await find_trending_items(
        game=current_game,
        min_price=user_settings.get("min_price", 1.0),
        max_price=user_settings.get("max_price", 500.0),
        dmarket_api=api_client,
        limit=20,
    )
    pagination_manager.set_items(user_id, results, "trending")
    await show_trending_items_results(query, context, current_game)


async def _run_volatility_analysis(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    api_client: Any,
    user_settings: dict,
    current_game: str,
    user_id: int,
) -> None:
    """Run volatility analysis."""
    results = await analyze_market_volatility(
        game=current_game,
        min_price=user_settings.get("min_price", 1.0),
        max_price=user_settings.get("max_price", 500.0),
        dmarket_api=api_client,
        limit=20,
    )
    pagination_manager.set_items(user_id, results, "volatility")
    await show_volatility_results(query, context, current_game)


async def _run_undervalued_analysis(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    api_client: Any,
    user_settings: dict,
    current_game: str,
    user_id: int,
) -> None:
    """Run undervalued items analysis."""
    results = await find_undervalued_items(
        api_client,
        game=current_game,
        price_from=user_settings.get("min_price", 1.0),
        price_to=user_settings.get("max_price", 500.0),
        discount_threshold=15.0,
        max_results=20,
    )
    pagination_manager.set_items(user_id, results, "undervalued")
    await show_undervalued_items_results(query, context, current_game)


async def _run_recommendations_analysis(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    api_client: Any,
    user_settings: dict,
    current_game: str,
    user_id: int,
) -> None:
    """Run investment recommendations analysis."""
    results = await get_investment_recommendations(
        api_client,
        game=current_game,
        budget=user_settings.get("max_price", 100.0),
        risk_level="medium",
    )
    pagination_manager.set_items(user_id, results, "recommendations")
    await show_investment_recommendations_results(query, context, current_game)


# ============================================================================
# End of helper functions
# ============================================================================


async def market_analysis_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает команду /market_analysis для начала анализа рынка.

    Args:
        update: Объект обновления Telegram
        context: Контекст бота

    """
    if not update.message:
        return

    # Создаем клавиатуру с опциями анализа
    keyboard = [
        [
            InlineKeyboardButton(
                "📈 Изменения цен",
                callback_data="analysis:price_changes:csgo",
            ),
            InlineKeyboardButton(
                "🔥 Трендовые предметы",
                callback_data="analysis:trending:csgo",
            ),
        ],
        [
            InlineKeyboardButton(
                "📊 Волатильность",
                callback_data="analysis:volatility:csgo",
            ),
            InlineKeyboardButton(
                "📑 Полный отчет",
                callback_data="analysis:report:csgo",
            ),
        ],
        [
            InlineKeyboardButton(
                "💰 Недооцененные предметы",
                callback_data="analysis:undervalued:csgo",
            ),
            InlineKeyboardButton(
                "📊 Рекомендации",
                callback_data="analysis:recommendations:csgo",
            ),
        ],
        [
            InlineKeyboardButton("⬅️ Назад к арбитражу", callback_data="arbitrage"),
        ],
    ]

    # Добавляем выбор игры
    game_row = []
    for game_code, game_name in GAMES.items():
        game_row.append(
            InlineKeyboardButton(
                game_name,
                callback_data=f"analysis:select_game:{game_code}",
            ),
        )

        # Создаем новую строку после каждой второй игры
        if len(game_row) == 2:
            keyboard.insert(-2, game_row)
            game_row = []

    # Добавляем оставшиеся игры, если есть
    if game_row:
        keyboard.insert(-2, game_row)

    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        "🔎 *Анализ рынка DMarket*\n\n"
        "Выберите тип анализа и игру для исследования тенденций рынка "
        "и поиска выгодных возможностей.\n\n"
        "Текущая игра: *CS2*",
        reply_markup=reply_markup,
        parse_mode="Markdown",
    )


async def market_analysis_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает колбэки для анализа рынка.

    Args:
        update: Объект обновления Telegram
        context: Контекст бота

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    user_id = query.from_user.id

    # Разбираем данные колбэка
    parts = query.data.split(":")

    if len(parts) < 2:
        return

    action = parts[1]
    game = parts[2] if len(parts) > 2 else "csgo"

    # Инициализируем данные пользователя, если их нет
    if context.user_data is None:
        return
    if not context.user_data.get("market_analysis"):
        context.user_data["market_analysis"] = {
            "current_game": "csgo",
            "period": "24h",
            "min_price": 1.0,
            "max_price": 500.0,
        }

    # Обновляем текущую игру (Phase 2 - use helper)
    if action == "select_game":
        await _handle_game_selection(query, context, game)
        return

    # Получаем текущие настройки пользователя
    user_settings = context.user_data["market_analysis"]
    current_game = user_settings.get("current_game", game)

    game_name = GAMES.get(current_game, current_game)
    await query.edit_message_text(
        f"⏳ Загрузка данных анализа рынка для {game_name}...",
        parse_mode="Markdown",
    )

    # Создаем API клиент
    try:
        api_client = create_api_client_from_env()

        if api_client is None:
            await query.edit_message_text(
                "❌ Не удалось создать API клиент. Проверьте настройки API ключей.",
                reply_markup=get_back_to_market_analysis_keyboard(current_game),
                parse_mode="Markdown",
            )
            return

        # Dispatch to appropriate handler (Phase 2 - use helpers)
        if action == "price_changes":
            await _run_price_changes_analysis(
                query, context, api_client, user_settings, current_game, user_id
            )
        elif action == "trending":
            await _run_trending_analysis(
                query, context, api_client, user_settings, current_game, user_id
            )
        elif action == "volatility":
            await _run_volatility_analysis(
                query, context, api_client, user_settings, current_game, user_id
            )
        elif action == "report":
            report = await generate_market_report(
                game=current_game,
                dmarket_api=api_client,
            )
            await show_market_report(query, context, report)
        elif action == "undervalued":
            await _run_undervalued_analysis(
                query, context, api_client, user_settings, current_game, user_id
            )
        elif action == "recommendations":
            await _run_recommendations_analysis(
                query, context, api_client, user_settings, current_game, user_id
            )

    except Exception as e:
        logger.exception(f"Ошибка при анализе рынка: {e}")
        import traceback

        logger.exception(traceback.format_exc())

        await query.edit_message_text(
            f"❌ Произошла ошибка при анализе рынка:\n\n{e!s}",
            reply_markup=get_back_to_market_analysis_keyboard(current_game),
        )
    finally:
        # Закрываем клиент API
        api_client_ref = locals().get("api_client")
        if api_client_ref is not None and hasattr(api_client_ref, "_close_client"):
            try:
                await api_client_ref._close_client()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии клиента API: {e}")


async def handle_pagination_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает пагинацию для результатов анализа рынка.

    Args:
        update: Объект обновления Telegram
        context: Контекст бота

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    user_id = query.from_user.id
    data = query.data

    # Разбираем данные колбэка
    parts = data.split(":")
    if len(parts) < 3:
        return

    direction = parts[1]  # prev/next
    analysis_type = parts[2]  # price_changes/trending/volatility/etc.
    game = parts[3] if len(parts) > 3 else "csgo"

    # Навигация по страницам с использованием менеджера пагинации
    if direction == "next":
        pagination_manager.next_page(user_id)
    elif direction == "prev":
        pagination_manager.prev_page(user_id)

    # Отображаем выбранную страницу в зависимости от типа анализа
    if analysis_type == "price_changes":
        await show_price_changes_results(query, context, game)
    elif analysis_type == "trending":
        await show_trending_items_results(query, context, game)
    elif analysis_type == "volatility":
        await show_volatility_results(query, context, game)
    elif analysis_type == "undervalued":
        await show_undervalued_items_results(query, context, game)
    elif analysis_type == "recommendations":
        await show_investment_recommendations_results(query, context, game)


async def show_price_changes_results(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    game: str,
) -> None:
    """Отображает результаты анализа изменений цен с пагинацией.

    Args:
        query: Объект запроса обратного вызова
        context: Контекст бота
        game: Код игры

    """
    user_id = query.from_user.id

    # Получаем текущую страницу с результатами из менеджера пагинации
    items, current_page, total_pages = pagination_manager.get_page(user_id)

    if not items:
        # Если нет результатов
        await query.edit_message_text(
            f"📉 *Анализ изменений цен*\n\n"
            f"Не найдено изменений цен для игры {GAMES.get(game, game)} "
            f"с текущими настройками фильтрации.",
            reply_markup=get_back_to_market_analysis_keyboard(game),
            parse_mode="Markdown",
        )
        return

    # Используем унифицированный форматтер для рыночных предметов
    # При необходимости создаем специализированный форматтер
    # для ценовых изменений
    formatted_text = format_market_items(
        items=items,
        page=current_page,
        items_per_page=pagination_manager.get_items_per_page(user_id),
    )

    # Добавляем заголовок для анализа цен
    header_text = (
        f"📉 *Анализ изменений цен - {GAMES.get(game, game)}*\n\n"
        f"Показаны предметы с наибольшими изменениями цен "
        f"за последние 24 часа.\n"
    )

    # Добавляем периоды сравнения
    period_buttons = [
        InlineKeyboardButton("24 часа", callback_data=f"period_change:24h:{game}"),
        InlineKeyboardButton("7 дней", callback_data=f"period_change:7d:{game}"),
        InlineKeyboardButton("30 дней", callback_data=f"period_change:30d:{game}"),
    ]

    # Создаем унифицированную клавиатуру пагинации
    pagination_keyboard = create_pagination_keyboard(
        current_page=current_page,
        total_pages=total_pages,
        prefix=f"paginate:price_changes:{game}_",
        show_first_last=True,
    )

    # Добавляем кнопки периодов и возврата к анализу рынка
    keyboard = list(pagination_keyboard.inline_keyboard)
    keyboard.extend((
        tuple(period_buttons),
        (
            InlineKeyboardButton(
                "⬅️ Назад к анализу рынка",
                callback_data=f"analysis:select_game:{game}",
            ),
        ),
    ))

    # Отображаем результаты
    await query.edit_message_text(
        header_text + formatted_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def show_trending_items_results(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    game: str,
) -> None:
    """Отображает результаты анализа трендовых предметов с пагинацией.

    Args:
        query: Объект запроса обратного вызова
        context: Контекст бота
        game: Код игры

    """
    user_id = query.from_user.id

    # Получаем текущую страницу с результатами из менеджера пагинации
    items, current_page, total_pages = pagination_manager.get_page(user_id)

    if not items:
        # Если нет результатов
        await query.edit_message_text(
            f"🔥 *Трендовые предметы*\n\n"
            f"Не найдено трендовых предметов для игры {GAMES.get(game, game)} "
            f"с текущими настройками фильтрации.",
            reply_markup=get_back_to_market_analysis_keyboard(game),
            parse_mode="Markdown",
        )
        return

    # Используем унифицированный форматтер для рыночных предметов
    formatted_text = format_market_items(
        items=items,
        page=current_page,
        items_per_page=pagination_manager.get_items_per_page(user_id),
    )

    # Добавляем заголовок для трендовых предметов
    header_text = (
        f"🔥 *Трендовые предметы - {GAMES.get(game, game)}*\n\n"
        f"Показаны самые популярные предметы за последние 7 дней.\n"
    )

    # Создаем унифицированную клавиатуру пагинации
    pagination_keyboard = create_pagination_keyboard(
        current_page=current_page,
        total_pages=total_pages,
        prefix=f"paginate:trending:{game}_",
    )

    # Добавляем фильтры цены и возврат к анализу рынка
    keyboard = list(pagination_keyboard.inline_keyboard)
    keyboard.extend((
        (
            InlineKeyboardButton("🔽 Цена $1-50", callback_data=f"price_filter:1:50:{game}"),
            InlineKeyboardButton("🔼 Цена $50+", callback_data=f"price_filter:50:500:{game}"),
        ),
        (
            InlineKeyboardButton(
                "⬅️ Назад к анализу рынка",
                callback_data=f"analysis:select_game:{game}",
            ),
        ),
    ))

    # Отображаем результаты
    await query.edit_message_text(
        header_text + formatted_text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def show_volatility_results(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    game: str,
) -> None:
    """Отображает результаты анализа волатильности рынка.

    Args:
        query: Объект запроса колбэка
        context: Контекст бота
        game: Код игры

    """
    user_id = query.from_user.id

    # Получаем данные из пагинации
    items, current_page, total_pages = pagination_manager.get_page(user_id)

    if not items:
        await query.edit_message_text(
            f"ℹ️ Нет данных о волатильности для {GAMES.get(game, game)}",
            reply_markup=get_back_to_market_analysis_keyboard(game),
        )
        return

    # Форматируем результаты
    text = f"📊 *Анализ волатильности {GAMES.get(game, game)}*\n\n"

    # Добавляем информацию о предметах
    for i, item in enumerate(items, 1):
        name = item.get("market_hash_name", "Неизвестный предмет")
        current_price = item.get("current_price", 0)
        change_24h = item.get("change_24h_percent", 0)
        change_7d = item.get("change_7d_percent", 0)
        volatility_score = item.get("volatility_score", 0)

        # Определяем уровень волатильности
        if volatility_score > 30:
            volatility_level = "Очень высокая"
        elif volatility_score > 20:
            volatility_level = "Высокая"
        elif volatility_score > 10:
            volatility_level = "Средняя"
        else:
            volatility_level = "Низкая"

        # Форматируем текст предмета
        item_text = (
            f"{i}. *{name}*\n"
            f"   💰 Цена: ${current_price:.2f}\n"
            f"   📈 Изменение (24ч): {change_24h:.1f}%\n"
            f"   📈 Изменение (7д): {change_7d:.1f}%\n"
            f"   🔄 Волатильность: {volatility_level} "
            f"({volatility_score:.1f})\n\n"
        )

        text += item_text

    # Добавляем информацию о странице
    text += f"Страница {current_page + 1} из {total_pages}"

    # Создаем клавиатуру с пагинацией
    keyboard = []

    # Кнопки пагинации
    pagination_row = []
    if current_page > 0:
        pagination_row.append(
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data=f"analysis_page:prev:volatility:{game}",
            ),
        )

    if current_page < total_pages - 1:
        pagination_row.append(
            InlineKeyboardButton(
                "➡️ Вперед",
                callback_data=f"analysis_page:next:volatility:{game}",
            ),
        )

    if pagination_row:
        keyboard.append(pagination_row)

    # Кнопка возврата к анализу
    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ Назад к анализу",
                callback_data=f"analysis:select_game:{game}",
            ),
        ],
    )

    # Отображаем результаты
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def show_market_report(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    report: dict[str, Any],
) -> None:
    """Отображает полный отчет о состоянии рынка.

    Args:
        query: Объект запроса колбэка
        context: Контекст бота
        report: Словарь с данными отчета

    """
    game = report.get("game", "csgo")
    game_name = GAMES.get(game, game)

    # Проверяем наличие ошибки
    if "error" in report:
        await query.edit_message_text(
            f"❌ Произошла ошибка при создании отчета:\n\n{report['error']}",
            reply_markup=get_back_to_market_analysis_keyboard(game),
        )
        return

    # Форматируем отчет
    market_summary = report.get("market_summary", {})

    # Определяем общее направление рынка
    market_direction = market_summary.get("price_change_direction", "stable")
    direction_icon = {
        "up": "🔼 Растущий",
        "down": "🔽 Падающий",
        "stable": "➡️ Стабильный",
    }.get(market_direction, "➡️ Стабильный")

    # Определяем волатильность рынка
    volatility_level = market_summary.get("market_volatility_level", "low")
    volatility_display = {
        "low": "Низкая",
        "medium": "Средняя",
        "high": "Высокая",
    }.get(volatility_level, "Низкая")

    # Получаем популярные категории
    trending_categories = market_summary.get("top_trending_categories", ["Нет данных"])

    # Получаем рекомендации
    recommendations = market_summary.get("recommended_actions", ["Нет рекомендаций"])

    # Форматируем текст отчета
    text = (
        f"📑 *Отчет о состоянии рынка {game_name}*\n\n"
        f"*Общее направление рынка:* {direction_icon}\n"
        f"*Волатильность:* {volatility_display}\n"
        f"*Популярные категории:* {', '.join(trending_categories)}\n\n"
        f"*Рекомендации:*\n"
    )

    # Добавляем рекомендации
    for i, rec in enumerate(recommendations, 1):
        text += f"{i}. {rec}\n"

    # Добавляем краткую статистику по изменениям цен
    price_changes = report.get("price_changes", [])
    if price_changes:
        text += "\n*Топ изменения цен:*\n"
        for i, item in enumerate(price_changes[:3], 1):
            name = item.get("market_hash_name", "")
            change_percent = item.get("change_percent", 0)
            direction = "🔼" if change_percent > 0 else "🔽"
            text += f"{i}. {name}: {direction} {abs(change_percent):.1f}%\n"

    # Добавляем краткую статистику по трендовым предметам
    trending_items = report.get("trending_items", [])
    if trending_items:
        text += "\n*Топ трендовые предметы:*\n"
        for i, item in enumerate(trending_items[:3], 1):
            name = item.get("market_hash_name", "")
            sales = item.get("sales_volume", 0)
            text += f"{i}. {name}: {sales} продаж\n"

    # Создаем клавиатуру
    keyboard = [
        [
            InlineKeyboardButton(
                "📈 Подробные изменения цен",
                callback_data=f"analysis:price_changes:{game}",
            ),
        ],
        [
            InlineKeyboardButton(
                "🔥 Все трендовые предметы",
                callback_data=f"analysis:trending:{game}",
            ),
        ],
        [
            InlineKeyboardButton(
                "⬅️ Назад к анализу",
                callback_data=f"analysis:select_game:{game}",
            ),
        ],
    ]

    # Отображаем отчет
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def handle_period_change(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обрабатывает изменение периода анализа.

    Args:
        update: Объект обновления Telegram
        context: Контекст бота

    """
    query = update.callback_query
    if not query or not query.data:
        return

    await query.answer()

    # Разбираем данные колбэка
    parts = query.data.split(":")

    if len(parts) < 2:
        return

    period = parts[1]
    game = parts[2] if len(parts) > 2 else "csgo"

    # Обновляем период в настройках пользователя
    if context.user_data is None:
        return
    if not context.user_data.get("market_analysis"):
        context.user_data["market_analysis"] = {}

    context.user_data["market_analysis"]["period"] = period

    # Запускаем новый анализ с обновленным периодом
    await query.answer("Период анализа обновлен")

    # Симулируем нажатие на кнопку анализа изменений цен
    query.data = f"analysis:price_changes:{game}"
    await market_analysis_callback(update, context)


def get_back_to_market_analysis_keyboard(game: str) -> InlineKeyboardMarkup:
    """Создает клавиатуру для возврата к анализу рынка.

    Args:
        game: Код игры

    Returns:
        Клавиатура с кнопкой возврата

    """
    keyboard = [
        [
            InlineKeyboardButton(
                "⬅️ Назад к анализу рынка",
                callback_data=f"analysis:select_game:{game}",
            ),
        ],
    ]

    return InlineKeyboardMarkup(keyboard)


def register_market_analysis_handlers(
    dispatcher: Application,  # type: ignore[type-arg]
) -> None:
    """Регистрирует обработчики для анализа рынка.

    Args:
        dispatcher: Диспетчер для регистрации обработчиков

    """
    dispatcher.add_handler(CommandHandler("market_analysis", market_analysis_command))
    dispatcher.add_handler(
        CallbackQueryHandler(market_analysis_callback, pattern="^analysis:"),
    )
    dispatcher.add_handler(
        CallbackQueryHandler(handle_pagination_analysis, pattern="^analysis_page:"),
    )
    dispatcher.add_handler(
        CallbackQueryHandler(handle_period_change, pattern="^analysis_period:"),
    )
    # Добавляем обработчик для изменения уровня риска
    dispatcher.add_handler(
        CallbackQueryHandler(handle_risk_level_change, pattern="^analysis_risk:"),
    )


async def show_undervalued_items_results(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    game: str,
) -> None:
    """Отображает результаты поиска недооцененных предметов.

    Args:
        query: Объект запроса колбэка
        context: Контекст бота
        game: Код игры

    """
    user_id = query.from_user.id

    # Получаем данные из пагинации
    items, current_page, total_pages = pagination_manager.get_page(user_id)

    if not items:
        game_name = GAMES.get(game, game)
        await query.edit_message_text(
            f"ℹ️ Не найдено недооцененных предметов для {game_name}",
            reply_markup=get_back_to_market_analysis_keyboard(game),
        )
        return

    # Форматируем результаты
    text = f"💰 *Недооцененные предметы на {GAMES.get(game, game)}*\n\n"

    # Добавляем информацию о предметах
    for i, item in enumerate(items, 1):
        name = item.get("title", "Неизвестный предмет")
        current_price = item.get("current_price", 0)
        avg_price = item.get("avg_price", 0)
        discount = item.get("discount", 0)
        trend = item.get("trend", "stable")
        volume = item.get("volume", 0)

        # Определяем иконку тренда
        trend_icon = "➡️"
        if trend == "upward":
            trend_icon = "🔼"
        elif trend == "downward":
            trend_icon = "🔽"

        # Форматируем текст предмета
        item_text = (
            f"{i}. *{name}*\n"
            f"   💰 Цена: ${current_price:.2f} (средняя: ${avg_price:.2f})\n"
            f"   🔖 Скидка: {discount:.1f}%\n"
            f"   {trend_icon} Тренд: {trend}\n"
            f"   📊 Объем продаж: {volume}\n\n"
        )

        text += item_text

    # Добавляем информацию о странице
    text += f"Страница {current_page + 1} из {total_pages}"

    # Создаем клавиатуру с пагинацией
    keyboard = []

    # Кнопки пагинации
    pagination_row = []
    if current_page > 0:
        pagination_row.append(
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data=f"analysis_page:prev:undervalued:{game}",
            ),
        )

    if current_page < total_pages - 1:
        pagination_row.append(
            InlineKeyboardButton(
                "➡️ Вперед",
                callback_data=f"analysis_page:next:undervalued:{game}",
            ),
        )

    if pagination_row:
        keyboard.append(pagination_row)

    # Кнопка возврата к анализу
    keyboard.append(
        [
            InlineKeyboardButton(
                "⬅️ Назад к анализу",
                callback_data=f"analysis:select_game:{game}",
            ),
        ],
    )

    # Отображаем результаты
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def show_investment_recommendations_results(
    query: CallbackQuery,
    context: ContextTypes.DEFAULT_TYPE,
    game: str,
) -> None:
    """Отображает результаты инвестиционных рекомендаций.

    Args:
        query: Объект запроса колбэка
        context: Контекст бота
        game: Код игры

    """
    user_id = query.from_user.id

    # Получаем данные из пагинации
    items, current_page, total_pages = pagination_manager.get_page(user_id)

    if not items:
        game_name = GAMES.get(game, game)
        await query.edit_message_text(
            f"ℹ️ Не удалось сформировать инвестиционные рекомендации для {game_name}",
            reply_markup=get_back_to_market_analysis_keyboard(game),
        )
        return

    # Форматируем результаты
    text = f"💼 *Инвестиционные рекомендации для {GAMES.get(game, game)}*\n\n"

    # Добавляем информацию о рекомендациях
    for i, item in enumerate(items, 1):
        name = item.get("title", "Неизвестный предмет")
        current_price = item.get("current_price", 0)
        discount = item.get("discount", 0)
        liquidity = item.get("liquidity", "low")
        investment_score = item.get("investment_score", 0)
        reason = item.get("reason", "Нет информации")

        # Определяем иконку ликвидности
        liquidity_icon = "🟡"  # Средняя ликвидность
        if liquidity == "high":
            liquidity_icon = "🟢"  # Высокая ликвидность
        elif liquidity == "low":
            liquidity_icon = "🔴"  # Низкая ликвидность

        # Форматируем текст рекомендации
        item_text = (
            f"{i}. *{name}*\n"
            f"   💰 Цена: ${current_price:.2f}\n"
            f"   🔖 Скидка: {discount:.1f}%\n"
            f"   {liquidity_icon} Ликвидность: {liquidity}\n"
            f"   ⭐ Оценка: {investment_score:.1f}\n"
            f"   📝 Почему: {reason}\n\n"
        )

        text += item_text

    # Добавляем информацию о странице
    text += f"Страница {current_page + 1} из {total_pages}"

    # Создаем клавиатуру с пагинацией
    keyboard = []

    # Кнопки пагинации
    pagination_row = []
    if current_page > 0:
        pagination_row.append(
            InlineKeyboardButton(
                "⬅️ Назад",
                callback_data=f"analysis_page:prev:recommendations:{game}",
            ),
        )

    if current_page < total_pages - 1:
        pagination_row.append(
            InlineKeyboardButton(
                "➡️ Вперед",
                callback_data=f"analysis_page:next:recommendations:{game}",
            ),
        )

    if pagination_row:
        keyboard.append(pagination_row)

    # Добавляем кнопки для выбора уровня риска
    risk_row = []
    for risk, label in [
        ("low", "🔵 Низкий"),
        ("medium", "🟡 Средний"),
        ("high", "🔴 Высокий"),
    ]:
        risk_row.append(
            InlineKeyboardButton(label, callback_data=f"analysis_risk:{risk}:{game}"),
        )

    keyboard.extend([
        risk_row,
        [
            InlineKeyboardButton(
                "⬅️ Назад к анализу",
                callback_data=f"analysis:select_game:{game}",
            ),
        ],
    ])

    # Отображаем результаты
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def handle_risk_level_change(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Обрабатывает изменение уровня риска для инвестиционных рекомендаций.

    Args:
        update: Объект обновления Telegram
        context: Контекст бота

    """
    query = update.callback_query
    if not query or not query.data:
        return
    await query.answer()

    # Разбираем данные колбэка
    parts = query.data.split(":")

    if len(parts) < 3:
        return

    risk_level = parts[1]  # low, medium, high
    game = parts[2]

    # Обновляем уровень риска в настройках пользователя
    if context.user_data is None:
        return
    if not context.user_data.get("market_analysis"):
        context.user_data["market_analysis"] = {}

    context.user_data["market_analysis"]["risk_level"] = risk_level

    # Запускаем новый анализ с обновленным уровнем риска
    await query.answer(f"Уровень риска обновлен: {risk_level}")

    # Симулируем нажатие на кнопку рекомендаций
    query.data = f"analysis:recommendations:{game}"
    await market_analysis_callback(update, context)
