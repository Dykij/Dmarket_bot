"""Модуль форматирования данных для сообщений Telegram бота.

Содержит функции для форматирования различных типов данных (предметы маркета,
возможности арбитража, баланс и т.д.) в читаемый текст для отправки в сообщениях Telegram.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Максимальная длина сообщения в Telegram
MAX_MESSAGE_LENGTH = 4096


def format_balance(balance_data: dict[str, Any]) -> str:
    """Форматирует данные о балансе в читаемый текст.

    Args:
        balance_data: Словарь с данными о балансе

    Returns:
        str: Отформатированный текст с информацией о балансе

    """
    if balance_data.get("error"):
        return f"❌ *Ошибка при получении баланса*: {balance_data.get('error_message', 'Неизвестная ошибка')}"

    # Получаем значения баланса
    balance = balance_data.get("balance", 0)
    avAlgolable_balance = balance_data.get("avAlgolable_balance", balance)
    total_balance = balance_data.get("total_balance", balance)

    # Форматируем сообщение
    message = [
        "💰 *Баланс DMarket*",
        "",
        f"💵 *Доступно*: ${avAlgolable_balance:.2f} USD",
    ]

    # Добавляем общий баланс, если он отличается от доступного
    if total_balance > avAlgolable_balance:
        message.append(
            f"🔒 *Заблокировано*: ${total_balance - avAlgolable_balance:.2f} USD",
        )

    message.append(f"📊 *Всего*: ${total_balance:.2f} USD")

    # Если баланс слишком мал для торговли
    if avAlgolable_balance < 1.0:
        message.extend(
            [
                "",
                "⚠️ *Внимание*: Доступный баланс меньше $1. Некоторые операции могут быть недоступны.",
            ],
        )

    return "\n".join(message)


def format_market_item(item: dict[str, Any], show_detAlgols: bool = True) -> str:
    """Форматирует информацию о предмете маркета.

    Args:
        item: Словарь с данными о предмете
        show_detAlgols: Показывать ли детальную информацию

    Returns:
        str: Отформатированный текст с информацией о предмете

    """
    # Базовая информация
    title = item.get("title", "Неизвестный предмет")
    price_cents = item.get("price", {}).get("USD", 0)
    price_usd = price_cents / 100 if price_cents else 0

    message = [f"🏷️ *{title}*", f"💲 Цена: *${price_usd:.2f}*"]

    # Добавляем детали, если нужно
    if show_detAlgols:
        # Внешний вид (для CS:GO)
        if "extra" in item and "exteriorName" in item["extra"]:
            message.append(f"🔍 Состояние: _{item['extra']['exteriorName']}_")

        # Float (для CS:GO)
        if "extra" in item and "floatValue" in item["extra"]:
            message.append(f"📊 Float: `{item['extra']['floatValue']}`")

        # Наклейки (для CS:GO)
        if (
            "extra" in item
            and "stickers" in item["extra"]
            and item["extra"]["stickers"]
        ):
            stickers = item["extra"]["stickers"]
            message.append(f"🏵️ Наклейки: {len(stickers)}")

        # Ссылка на предмет
        item_id = item.get("itemId", "")
        if item_id:
            message.append(
                f"🔗 [Открыть на DMarket](https://dmarket.com/ingame-items/item-list/csgo-skins?userOfferId={item_id})",
            )

    return "\n".join(message)


def format_market_items(
    items: list[dict[str, Any]],
    page: int = 0,
    items_per_page: int = 5,
) -> str:
    """Форматирует список предметов с маркета с пагинацией.

    Args:
        items: Список предметов
        page: Номер страницы (начиная с 0)
        items_per_page: Количество предметов на странице

    Returns:
        str: Отформатированный текст со списком предметов

    """
    if not items:
        return "🔍 *Предметы не найдены*"

    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(items))

    page_items = items[start_idx:end_idx]

    message = [f"📋 *Найдено предметов: {len(items)}*"]
    message.extend(
        (
            f"📄 Страница {page + 1}/{(len(items) + items_per_page - 1) // items_per_page}",
            "",
        )
    )

    for i, item in enumerate(page_items, start=start_idx + 1):
        item_text = format_market_item(item, show_detAlgols=False)
        message.extend((f"{i}. {item_text}", ""))  # Пустая строка между предметами

    return "\n".join(message)


def format_opportunities(
    opportunities: list[dict[str, Any]],
    page: int = 0,
    items_per_page: int = 3,
) -> str:
    """Форматирует список арбитражных возможностей с пагинацией.

    Args:
        opportunities: Список возможностей для арбитража
        page: Номер страницы (начиная с 0)
        items_per_page: Количество возможностей на странице

    Returns:
        str: Отформатированный текст со списком возможностей

    """
    if not opportunities:
        return "🔍 <b>Арбитражные возможности не найдены</b>"

    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(opportunities))

    page_items = opportunities[start_idx:end_idx]

    message = [f"💰 <b>Найдено возможностей: {len(opportunities)}</b>"]
    message.extend(
        (
            f"📄 Страница {page + 1}/{(len(opportunities) + items_per_page - 1) // items_per_page}",
            "",
        )
    )

    for i, opportunity in enumerate(page_items, start=start_idx + 1):
        # Извлекаем данные
        item_name = opportunity.get("item_name", "Неизвестный предмет")
        buy_price = opportunity.get("buy_price", 0)
        sell_price = opportunity.get("sell_price", 0)
        profit = opportunity.get("profit", 0)
        profit_percent = opportunity.get("profit_percent", 0)

        # Форматируем
        message.extend(
            (
                f"{i}. <b>{item_name}</b>",
                f"💲 Покупка: <b>${buy_price:.2f}</b> ➡️ Продажа: <b>${sell_price:.2f}</b>",
                f"📈 Прибыль: <b>${profit:.2f}</b> ({profit_percent:.2f}%)",
            )
        )

        # Добавляем ссылки если есть
        if "buy_link" in opportunity:
            message.append(
                f"🔗 <a href='{opportunity['buy_link']}'>Ссылка на покупку</a>",
            )

        message.append("")  # Пустая строка между возможностями

    # Добавляем время анализа
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message.append(f"🕒 <i>Время анализа: {current_time}</i>")

    return "\n".join(message)


def format_error_message(error: Exception, user_friendly: bool = True) -> str:
    """Форматирует сообщение об ошибке.

    Args:
        error: Объект исключения
        user_friendly: Если True, возвращает сообщение, понятное пользователю

    Returns:
        str: Отформатированное сообщение об ошибке

    """
    if user_friendly:
        return f"❌ *Произошла ошибка*\n\n{error!s}\n\nПожалуйста, попробуйте позже или обратитесь к команде /help для получения справки."

    # Техническое сообщение для отладки
    return f"❌ *Ошибка*: `{type(error).__name__}`\n\n```\n{error!s}\n```"


def format_sales_history(
    sales: list[dict[str, Any]],
    page: int = 0,
    items_per_page: int = 5,
) -> str:
    """Форматирует историю продаж.

    Args:
        sales: Список продаж
        page: Номер страницы (начиная с 0)
        items_per_page: Количество записей на странице

    Returns:
        str: Отформатированный текст с историей продаж

    """
    if not sales:
        return "📊 *История продаж пуста*"

    start_idx = page * items_per_page
    end_idx = min(start_idx + items_per_page, len(sales))

    page_items = sales[start_idx:end_idx]

    message = [f"📊 *История продаж (последние {len(sales)} записей)*"]
    message.extend(
        (
            f"📄 Страница {page + 1}/{(len(sales) + items_per_page - 1) // items_per_page}",
            "",
        )
    )

    for i, sale in enumerate(page_items, start=start_idx + 1):
        # Извлекаем данные
        item_name = sale.get("title", "Неизвестный предмет")
        price_cents = sale.get("price", {}).get("amount", 0)
        price_usd = price_cents / 100 if price_cents else 0

        date_str = sale.get("createdAt", "")
        if date_str:
            try:
                date = datetime.fromisoformat(date_str)
                date_formatted = date.strftime("%d.%m.%Y %H:%M")
            except (ValueError, TypeError):
                date_formatted = date_str
        else:
            date_formatted = "Неизвестно"

        # Форматируем
        message.extend(
            (
                f"{i}. *{item_name}*",
                f"💰 Сумма: *${price_usd:.2f}*",
                f"🕒 Дата: _{date_formatted}_",
                "",
            )
        )  # Пустая строка между продажами

    return "\n".join(message)


def format_sales_analysis(analysis: dict[str, Any], item_name: str) -> str:
    """Форматирует результаты анализа продаж предмета.

    Args:
        analysis: Словарь с данными анализа продаж
        item_name: Название предмета

    Returns:
        str: Отформатированный текст с анализом продаж

    """
    if not analysis.get("has_data"):
        return (
            f"⚠️ <b>Данные о продажах не найдены</b>\n\n"
            f"Предмет: <code>{item_name}</code>\n\n"
            f"Возможно, предмет редко продается или название указано неверно."
        )

    # Получаем эмодзи для тренда цены
    trend_emoji = {"up": "⬆️ Растет", "down": "⬇️ Падает", "stable": "➡️ Стабилен"}.get(
        analysis.get("price_trend", "stable"),
        "➡️ Стабилен",
    )

    message = [
        f"📊 <b>Анализ продаж:</b> <code>{item_name}</code>\n",
        f"💰 Средняя цена: <b>${analysis.get('avg_price', 0):.2f}</b>",
        f"⬆️ Максимальная цена: <b>${analysis.get('max_price', 0):.2f}</b>",
        f"⬇️ Минимальная цена: <b>${analysis.get('min_price', 0):.2f}</b>",
        f"📈 Тренд цены: {trend_emoji}",
        f"🔄 Продаж за период: <b>{analysis.get('sales_volume', 0)}</b>",
        f"📆 Продаж в день: <b>{analysis.get('sales_per_day', 0):.2f}</b>",
        f"⏱️ Период анализа: <b>{analysis.get('period_days', 0)} дней</b>\n",
    ]

    # Добавляем информацию о последних продажах
    recent_sales = analysis.get("recent_sales", [])
    if recent_sales:
        message.append("🕒 <b>Последние продажи:</b>")
        for sale in recent_sales[:5]:
            date = sale.get("date", "Неизвестно")
            price = sale.get("price", 0)
            currency = sale.get("currency", "USD")
            message.append(f"• {date} - <b>${price:.2f}</b> {currency}")

    return "\n".join(message)


def format_liquidity_analysis(analysis: dict[str, Any], item_name: str) -> str:
    """Форматирует результаты анализа ликвидности предмета.

    Args:
        analysis: Словарь с данными анализа ликвидности
        item_name: Название предмета

    Returns:
        str: Отформатированный текст с анализом ликвидности

    """
    sales_analysis = analysis.get("sales_analysis", {})

    if not sales_analysis.get("has_data"):
        return (
            f"⚠️ <b>Данные о продажах не найдены</b>\n\n"
            f"Предмет: <code>{item_name}</code>\n\n"
            f"Возможно, предмет редко продается или название указано неверно."
        )

    # Получаем эмодзи для категории ликвидности
    liquidity_emoji = {
        "Очень высокая": "💧💧💧💧",
        "Высокая": "💧💧💧",
        "Средняя": "💧💧",
        "Низкая": "💧",
    }.get(analysis.get("liquidity_category", "Низкая"), "💧")

    # Получаем эмодзи для тренда цены
    trend_emoji = {"up": "⬆️ Растет", "down": "⬇️ Падает", "stable": "➡️ Стабилен"}.get(
        sales_analysis.get("price_trend", "stable"),
        "➡️ Стабилен",
    )

    message = [
        f"💧 <b>Анализ ликвидности:</b> <code>{item_name}</code>\n",
        f"{liquidity_emoji} Категория: <b>{analysis.get('liquidity_category', 'Неизвестно')}</b>",
        f"📊 Оценка: <b>{analysis.get('liquidity_score', 0)}/7</b>\n",
        f"📈 Тренд цены: {trend_emoji}",
        f"🔄 Продаж в день: <b>{sales_analysis.get('sales_per_day', 0):.2f}</b>",
        f"📆 Всего продаж: <b>{sales_analysis.get('sales_volume', 0)}</b>",
        f"💰 Средняя цена: <b>${sales_analysis.get('avg_price', 0):.2f}</b>\n",
    ]

    # Добавляем информацию о рынке
    market_data = analysis.get("market_data", {})
    if market_data:
        message.extend(
            [
                f"🛒 Предложений на рынке: <b>{market_data.get('offers_count', 0)}</b>",
                f"⬇️ Минимальная цена: <b>${market_data.get('lowest_price', 0):.2f}</b>",
                f"⬆️ Максимальная цена: <b>${market_data.get('highest_price', 0):.2f}</b>\n",
            ],
        )

    # Добавляем рекомендацию по арбитражу
    liquidity_cat = analysis.get("liquidity_category", "")
    if liquidity_cat in {"Очень высокая", "Высокая"}:
        message.append("✅ <b>Рекомендация:</b> Отлично подходит для арбитража!")
    elif liquidity_cat == "Средняя":
        message.append(
            "⚠️ <b>Рекомендация:</b> Может подойти для арбитража, но с осторожностью.",
        )
    else:
        message.append(
            "❌ <b>Рекомендация:</b> Не рекомендуется для арбитража из-за низкой ликвидности.",
        )

    return "\n".join(message)


def get_trend_emoji(trend: str) -> str:
    """Возвращает эмодзи для тренда цены.

    Args:
        trend: Тренд цены ("up", "down", "stable")

    Returns:
        str: Эмодзи с описанием тренда

    """
    return {"up": "⬆️ Растет", "down": "⬇️ Падает", "stable": "➡️ Стабилен"}.get(
        trend,
        "➡️ Стабилен",
    )


def format_sales_volume_stats(stats: dict[str, Any], game: str) -> str:
    """Форматирует статистику объема продаж.

    Args:
        stats: Словарь со статистикой объема продаж
        game: Код игры

    Returns:
        str: Отформатированный текст со статистикой

    """
    game_display = {
        "csgo": "CS2",
        "dota2": "Dota 2",
        "tf2": "Team Fortress 2",
        "rust": "Rust",
    }.get(game, game.upper())

    items = stats.get("items", [])
    if not items:
        return f"⚠️ <b>Статистика объема продаж не найдена для {game_display}</b>"

    summary = stats.get("summary", {})

    message = [
        f"📊 <b>Статистика объема продаж для {game_display}</b>\n",
        f"🔎 Проанализировано предметов: <b>{stats.get('count', 0)}</b>",
        f"⬆️ Предметов с растущей ценой: <b>{summary.get('up_trend_count', 0)}</b>",
        f"⬇️ Предметов с падающей ценой: <b>{summary.get('down_trend_count', 0)}</b>",
        f"➡️ Предметов со стабильной ценой: <b>{summary.get('stable_trend_count', 0)}</b>\n",
        "📈 <b>Топ-5 предметов по объему продаж:</b>\n",
    ]

    # Добавляем информацию о предметах с наибольшим объемом продаж
    for i, item in enumerate(items[:5], 1):
        item_name = item.get("item_name", "Неизвестный предмет")
        sales_per_day = item.get("sales_per_day", 0)
        avg_price = item.get("avg_price", 0)
        price_trend = item.get("price_trend", "stable")

        message.extend(
            [
                f"{i}. <code>{item_name}</code>",
                f"   🔄 Продаж в день: <b>{sales_per_day:.2f}</b>",
                f"   💰 Средняя цена: <b>${avg_price:.2f}</b>",
                f"   📈 Тренд: {get_trend_emoji(price_trend)}\n",
            ],
        )

    return "\n".join(message)


def format_arbitrage_with_sales(results: dict[str, Any], game: str) -> str:
    """Форматирует арбитражные возможности с учетом истории продаж.

    Args:
        results: Словарь с результатами поиска арбитража
        game: Код игры

    Returns:
        str: Отформатированный текст с результатами

    """
    game_display = {
        "csgo": "CS2",
        "dota2": "Dota 2",
        "tf2": "Team Fortress 2",
        "rust": "Rust",
    }.get(game, game.upper())

    opportunities = results.get("opportunities", [])
    if not opportunities:
        return (
            f"⚠️ <b>Арбитражные возможности не найдены</b>\n\n"
            f"Игра: <b>{game_display}</b>\n\n"
            f"Попробуйте изменить параметры фильтрации или выбрать другую игру."
        )

    filters = results.get("filters", {})
    time_period = filters.get("time_period_days", 7)

    message = [
        f"📊 <b>Арбитражные возможности с учетом продаж для {game_display}</b>\n",
        f"🔎 Найдено предметов: <b>{len(opportunities)}</b>",
        f"📆 Период анализа: <b>{time_period} дней</b>\n",
    ]

    # Добавляем информацию о найденных предметах
    for i, item in enumerate(opportunities[:5], 1):
        item_name = item.get("market_hash_name", "Неизвестный предмет")
        profit = item.get("profit", 0)
        profit_percent = item.get("profit_percent", 0)
        buy_price = item.get("buy_price", 0)
        sell_price = item.get("sell_price", 0)

        sales_analysis = item.get("sales_analysis", {})
        price_trend = sales_analysis.get("price_trend", "stable")
        sales_per_day = sales_analysis.get("sales_per_day", 0)

        message.extend(
            [
                f"🏆 {i}. <code>{item_name}</code>",
                f"💰 Прибыль: <b>${profit:.2f}</b> ({profit_percent:.1f}%)",
                f"🛒 Цена покупки: <b>${buy_price:.2f}</b>",
                f"💵 Цена продажи: <b>${sell_price:.2f}</b>",
                f"📈 Тренд: {get_trend_emoji(price_trend)}",
                f"🔄 Продаж в день: <b>{sales_per_day:.2f}</b>\n",
            ],
        )

    # Если найдено больше 5 предметов, добавляем сообщение о показе только части
    if len(opportunities) > 5:
        message.append(
            f"<i>Показаны 5 из {len(opportunities)} найденных возможностей.</i>",
        )

    return "\n".join(message)


def format_dmarket_results(
    results: dict[str, Any],
    result_type: str = "market_items",
) -> str:
    """Форматирует результаты запроса к DMarket API.

    Args:
        results: Словарь с результатами запроса
        result_type: Тип результатов (market_items, opportunities, balance, etc.)

    Returns:
        str: Отформатированный текст с результатами

    """
    if not results:
        return "⚠️ <b>Результаты не найдены</b>"

    if result_type == "market_items":
        items = results.get("objects", [])
        total = results.get("total", {}).get("items", 0)
        if not items:
            return "🔍 <b>Предметы не найдены</b>"

        message = [f"📋 <b>Найдено предметов: {total}</b>\n"]
        for i, item in enumerate(items[:10], 1):
            title = item.get("title", "Неизвестный предмет")
            price_cents = item.get("price", {}).get("USD", 0)
            price_usd = price_cents / 100 if price_cents else 0
            message.append(f"{i}. <b>{title}</b> - ${price_usd:.2f}")

        if total > 10:
            message.append(f"\n<i>Показаны 10 из {total} предметов</i>")

        return "\n".join(message)

    if result_type == "opportunities":
        return format_best_opportunities(results.get("opportunities", []))

    if result_type == "balance":
        return format_balance(results)

    return "⚠️ <b>Неизвестный тип результатов</b>"


def format_best_opportunities(
    opportunities: list[dict[str, Any]],
    limit: int = 10,
) -> str:
    """Форматирует лучшие арбитражные возможности.

    Args:
        opportunities: Список возможностей для арбитража
        limit: Максимальное количество возможностей для отображения

    Returns:
        str: Отформатированный текст с лучшими возможностями

    """
    if not opportunities:
        return "🔍 <b>Арбитражные возможности не найдены</b>"

    # Ограничиваем количество возможностей
    top_opportunities = opportunities[:limit]

    message = [f"🏆 <b>Топ-{len(top_opportunities)} арбитражных возможностей</b>\n"]

    for i, opportunity in enumerate(top_opportunities, 1):
        # Извлекаем данные
        item_name = opportunity.get(
            "item_name", opportunity.get("market_hash_name", "Неизвестный предмет")
        )
        buy_price = opportunity.get("buy_price", 0)
        sell_price = opportunity.get("sell_price", 0)
        profit = opportunity.get("profit", 0)
        profit_percent = opportunity.get("profit_percent", 0)

        # Форматируем
        message.extend(
            (
                f"{i}. <b>{item_name}</b>",
                f"💲 Покупка: <b>${buy_price:.2f}</b> ➡️ Продажа: <b>${sell_price:.2f}</b>",
                f"📈 Прибыль: <b>${profit:.2f}</b> ({profit_percent:.2f}%)",
            )
        )

        # Добавляем информацию о ликвидности если есть
        if "sales_per_day" in opportunity:
            message.append(
                f"🔄 Продаж в день: <b>{opportunity['sales_per_day']:.2f}</b>"
            )

        message.append("")  # Пустая строка между возможностями

    # Добавляем время анализа
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    message.append(f"🕒 <i>Время анализа: {current_time}</i>")

    return "\n".join(message)


def split_long_message(message: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Разбивает длинное сообщение на части, подходящие для отправки в Telegram.

    Args:
        message: Исходное сообщение
        max_length: Максимальная длина части

    Returns:
        List[str]: Список частей сообщения

    """
    if len(message) <= max_length:
        return [message]

    parts = []
    lines = message.split("\n")
    current_part = ""

    for line in lines:
        # Если добавление этой строки превысит максимальную длину,
        # сохраняем текущую часть и начинаем новую
        if len(current_part) + len(line) + 1 > max_length:
            parts.append(current_part)
            current_part = line + "\n"
        else:
            current_part += line + "\n"

    # Добавляем последнюю часть, если она не пуста
    if current_part:
        parts.append(current_part)

    return parts


def format_target_item(target: dict[str, Any]) -> str:
    """Форматирует информацию о таргете.

    Args:
        target: Словарь с данными о таргете

    Returns:
        str: Отформатированный текст с информацией о таргете

    """
    title = target.get("Title", "Неизвестный предмет")
    price_cents = target.get("Price", {}).get("Amount", 0)
    price_usd = price_cents / 100 if price_cents else 0
    amount = target.get("Amount", 1)
    status = target.get("Status", "Unknown")

    status_emoji = {
        "TargetStatusActive": "✅ Активен",
        "TargetStatusInactive": "❌ Неактивен",
        "Created": "🆕 Создан",
    }.get(status, status)

    message = [
        f"🎯 *{title}*",
        f"💰 Цена: *${price_usd:.2f}*",
        f"📦 Количество: {amount}",
        f"📊 Статус: {status_emoji}",
    ]

    # Добавляем ID если есть
    target_id = target.get("TargetID", "")
    if target_id:
        message.append(f"🔑 ID: `{target_id}`")

    return "\n".join(message)


def format_target_competition_analysis(
    analysis: dict[str, Any], item_title: str
) -> str:
    """Форматирует результаты анализа конкуренции buy orders.

    Args:
        analysis: Словарь с данными анализа конкуренции
        item_title: Название предмета

    Returns:
        str: Отформатированный текст с анализом конкуренции

    """
    if not analysis:
        return (
            f"⚠️ *Данные о конкуренции не найдены*\n\n"
            f"Предмет: `{item_title}`\n\n"
            f"Возможно, для этого предмета нет активных buy orders."
        )

    competition_level = analysis.get("competition_level", "unknown")
    total_orders = analysis.get("total_buy_orders", 0)
    best_price = analysis.get("highest_buy_order_price", 0)
    recommended_price = analysis.get("recommended_price", 0)
    strategy = analysis.get("strategy", "Unknown")

    # Эмодзи для уровня конкуренции
    level_emoji = {
        "low": "🟢 Низкая",
        "medium": "🟡 Средняя",
        "high": "🔴 Высокая",
    }.get(competition_level, competition_level)

    message = [
        "🎯 *Анализ конкуренции*\n",
        f"📦 Предмет: `{item_title}`\n",
        f"👥 Активных buy orders: *{total_orders}*",
        f"📊 Уровень конкуренции: {level_emoji}",
        f"💎 Лучшая цена buy order: *${best_price:.2f}*\n",
        f"💡 *Рекомендуемая цена*: *${recommended_price:.2f}*",
        f"📋 Стратегия: _{strategy}_\n",
    ]

    # Добавляем детали по существующим ордерам
    orders = analysis.get("existing_orders", [])
    if orders:
        message.append("📑 *Существующие buy orders:*")
        for i, order in enumerate(orders[:5], 1):
            order_price = order.get("price", 0)
            order_amount = order.get("amount", 0)
            message.append(f"  {i}. ${order_price:.2f} x {order_amount}")

        if len(orders) > 5:
            message.append(f"  ... и еще {len(orders) - 5}")

    # Рекомендации
    message.append("\n💡 *Рекомендации:*")
    if competition_level == "low":
        message.extend(
            (
                "• Отличная возможность для создания таргета",
                "• Можно установить более низкую цену",
            )
        )
    elif competition_level == "medium":
        message.extend(
            ("• Средняя конкуренция", "• Установите цену чуть выше лучшего buy order")
        )
    else:  # high
        message.extend(
            ("• Высокая конкуренция", "• Рекомендуется поднять цену для приоритета")
        )

    return "\n".join(message)


def format_aggregated_prices(
    prices: list[dict[str, Any]], show_detAlgols: bool = True
) -> str:
    """Форматирует агрегированные цены из API v1.1.0.

    Args:
        prices: Список агрегированных цен
        show_detAlgols: Показывать ли детальную информацию

    Returns:
        str: Отформатированный текст с ценами

    """
    if not prices:
        return "🔍 *Цены не найдены*"

    message = [f"💰 *Агрегированные цены* ({len(prices)} предметов)\n"]

    for i, price_data in enumerate(prices[:10], 1):
        title = price_data.get("title", "Неизвестный предмет")
        best_buy = price_data.get("orderBestPrice", 0) / 100
        buy_count = price_data.get("orderCount", 0)
        best_sell = price_data.get("offerBestPrice", 0) / 100
        sell_count = price_data.get("offerCount", 0)

        # Рассчитываем спред
        spread = best_sell - best_buy if best_sell and best_buy else 0
        spread_percent = (spread / best_buy * 100) if best_buy > 0 else 0

        message.extend(
            (
                f"{i}. *{title}*",
                f"   \U0001f7e2 Buy: ${best_buy:.2f} ({buy_count} orders)",
                f"   🔴 Sell: ${best_sell:.2f} ({sell_count} offers)",
            )
        )

        if show_detAlgols and spread > 0:
            message.append(f"   📊 Спред: ${spread:.2f} ({spread_percent:.1f}%)")

        message.append("")  # Пустая строка

    if len(prices) > 10:
        message.append(f"_... и еще {len(prices) - 10} предметов_")

    return "\n".join(message)


def format_market_depth(depth_data: dict[str, Any]) -> str:
    """Форматирует данные глубины рынка.

    Args:
        depth_data: Данные анализа глубины рынка

    Returns:
        str: Отформатированный текст

    """
    if not depth_data:
        return "⚠️ *Данные о глубине рынка не найдены*"

    summary = depth_data.get("summary", {})
    items = depth_data.get("items", [])

    avg_liquidity = summary.get("average_liquidity_score", 0)
    avg_spread = summary.get("average_spread_percent", 0)
    high_liquidity_count = summary.get("high_liquidity_items", 0)
    arb_opportunities = summary.get("arbitrage_opportunities", 0)
    market_health = summary.get("market_health", "unknown")

    # Эмодзи для здоровья рынка
    health_emoji = {
        "excellent": "🟢 Отличное",
        "good": "🟡 Хорошее",
        "moderate": "🟠 Среднее",
        "poor": "🔴 Низкое",
    }.get(market_health, market_health)

    message = [
        "📊 *Глубина рынка*\n",
        f"💧 Средняя ликвидность: *{avg_liquidity:.1f}/100*",
        f"📈 Средний спред: *{avg_spread:.2f}%*",
        f"⭐ Высоколиквидных предметов: *{high_liquidity_count}*",
        f"🎯 Арбитражных возможностей: *{arb_opportunities}*",
        f"🏥 Здоровье рынка: {health_emoji}\n",
    ]

    # Топ предметов по ликвидности
    if items:
        message.append("🏆 *Топ по ликвидности:*\n")
        for i, item in enumerate(items[:5], 1):
            title = item.get("title", "Неизвестный предмет")
            liquidity = item.get("liquidity_score", 0)
            spread_pct = item.get("spread_percent", 0)

            emoji = "🟢" if liquidity >= 80 else "🟡" if liquidity >= 60 else "🔴"

            message.extend(
                (
                    f"{i}. {emoji} *{title}*",
                    f"   💧 Ликвидность: {liquidity:.0f}/100",
                    f"   📊 Спред: {spread_pct:.2f}%",
                    "",
                )
            )

    return "\n".join(message)
