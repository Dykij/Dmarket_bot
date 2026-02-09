"""Модуль поиска арбитражных возможностей.

Содержит функции для поиска и анализа арбитражных возможностей
на рынке DMarket.
"""

from __future__ import annotations

import operator
import time
from datetime import datetime
from typing import TYPE_CHECKING, Any

import structlog

from .cache import get_arbitrage_cache, save_arbitrage_cache
from .calculations import calculate_commission
from .constants import GAMES, MIN_PROFIT_PERCENT, PRICE_RANGES
from .core import arbitrage_boost_async, arbitrage_mid_async, arbitrage_pro_async

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI
    from src.dmarket.models import SkinResult

logger = structlog.get_logger(__name__)


def _group_items_by_name(
    items: list[dict[str, Any]],
) -> dict[str, list[dict[str, Any]]]:
    """Группирует предметы по названию.

    Args:
        items: Список предметов

    Returns:
        Предметы, сгруппированные по названию

    """
    grouped: dict[str, list[dict[str, Any]]] = {}

    for item in items:
        name = item.get("title", "")
        if not name:
            continue

        if name not in grouped:
            grouped[name] = []

        grouped[name].append(item)

    return grouped


async def find_arbitrage_items(
    game: str,
    mode: str = "mid",
    min_price: float = 1.0,
    max_price: float = 100.0,
    limit: int = 20,
    api_client: DMarketAPI | None = None,
) -> list[SkinResult]:
    """Находит предметы для арбитража.

    Args:
        game: Код игры (csgo, dota2, tf2, rust)
        mode: Режим арбитража (low, mid, pro)
        min_price: Минимальная цена предмета
        max_price: Максимальная цена предмета
        limit: Максимальное количество результатов
        api_client: Опциональный клиент DMarket API

    Returns:
        Список найденных предметов для арбитража

    """
    if mode in {"low", "boost"}:
        results = await arbitrage_boost_async(
            game,
            min_price,
            max_price,
            limit,
            api_client,
        )
    elif mode == "mid":
        results = await arbitrage_mid_async(
            game,
            min_price,
            max_price,
            limit,
            api_client,
        )
    elif mode == "pro":
        results = await arbitrage_pro_async(
            game,
            min_price,
            max_price,
            limit,
            api_client,
        )
    else:
        # По умолчанию используем средний режим
        results = await arbitrage_mid_async(
            game,
            min_price,
            max_price,
            limit,
            api_client,
        )

    # Проверяем и преобразуем результаты, если они в формате кортежа
    processed_results: list[Any] = []
    for item in results:
        if isinstance(item, tuple):
            # Преобразуем кортеж в словарь с нужными ключами
            item_dict = {
                "market_hash_name": item[0] if len(item) > 0 else "",
                "buy_price": item[1] if len(item) > 1 else 0,
                "sell_price": item[2] if len(item) > 2 else 0,
                "profit": item[3] if len(item) > 3 else 0,
                "profit_percent": item[4] if len(item) > 4 else 0,
            }
            processed_results.append(item_dict)
        else:
            processed_results.append(item)

    return processed_results


async def find_arbitrage_opportunities_advanced(
    api_client: DMarketAPI,
    mode: str = "normal",
    game: str = "csgo",
    max_items: int = 100,
    min_profit_percent: float | None = None,
    price_from: float | None = None,
    price_to: float | None = None,
) -> list[dict[str, Any]]:
    """Ищет арбитражные возможности на DMarket.

    Args:
        api_client: Экземпляр API клиента DMarket
        mode: Режим арбитража (normal, best, low, medium, high, boost, pro)
              или game_X для конкретной игры (где X - код игры)
        game: Идентификатор игры (csgo, dota2, rust, tf2) -
              используется если не указан в mode как game_X
        max_items: Максимальное количество предметов для анализа
        min_profit_percent: Минимальная прибыль в процентах
        price_from: Минимальная цена предмета
        price_to: Максимальная цена предмета

    Returns:
        Список возможностей для арбитража

    """
    start_time = time.time()
    logger.info(
        "arbitrage_search_started",
        mode=mode,
        game=game,
        max_items=max_items,
    )

    # Обработка режима игры (если указан как game_X)
    if mode.startswith("game_") and len(mode) > 5:
        game = mode[5:]  # Извлекаем код игры из mode (например, game_csgo -> csgo)
        mode = "normal"  # Устанавливаем стандартный режим

    # Приведение режима к стандартному формату
    if mode == "normal":
        mode = "medium"
    elif mode == "best":
        mode = "high"
    elif mode == "quick":
        # Быстрый скан - ищем низкорисковые возможности с высокой ликвидностью
        mode = "low"
    elif mode == "deep":
        # Глубокий скан - ищем все возможности включая высокорисковые
        mode = "high"

    # Проверяем корректность параметров с подробным логированием ошибок
    if game not in GAMES:
        logger.warning(
            "unknown_game_fallback_to_csgo",
            game=game,
            available_games=list(GAMES.keys()),
        )
        game = "csgo"

    valid_modes = {"low", "medium", "high", "boost", "pro"}
    if mode not in MIN_PROFIT_PERCENT and mode not in valid_modes:
        logger.warning(
            "unknown_mode_fallback_to_medium",
            mode=mode,
            available_modes=list(MIN_PROFIT_PERCENT.keys()),
        )
        mode = "medium"

    # Устанавливаем параметры поиска
    min_profit = min_profit_percent or MIN_PROFIT_PERCENT.get(mode, 5.0)

    # Определяем диапазон цен на основе режима, если не указаны явно
    if price_from is None and price_to is None:
        price_range = PRICE_RANGES.get(mode, (1.0, 100.0))
        price_from = price_range[0]
        price_to = price_range[1]

    # Устанавливаем значения по умолчанию, если не указаны
    price_lower = price_from if price_from is not None else 1.0
    price_upper = price_to if price_to is not None else 100.0

    logger.info(
        "arbitrage_search_params",
        game=GAMES.get(game, game),
        mode=mode,
        min_profit=min_profit,
        price_range=(price_lower, price_upper),
    )

    # Проверяем кэш
    cache_key = (game, mode, price_lower, price_upper, min_profit)
    cached_results = get_arbitrage_cache(cache_key)
    if cached_results:
        logger.info(
            "arbitrage_cache_hit",
            count=len(cached_results),
        )
        return cached_results

    try:
        # Получаем предметы маркета
        market_items = await api_client.get_market_items(
            game=game,
            max_items=max_items,
            price_from=price_lower,
            price_to=price_upper,
            sort="price",
        )

        if not market_items:
            logger.warning(
                "no_market_items_found",
                game=game,
                price_range=(price_lower, price_upper),
            )
            return []

        logger.info(
            "market_items_received",
            count=len(market_items),
        )

        # Группируем предметы по названию для анализа
        grouped_items = _group_items_by_name(market_items)

        # Анализируем возможности для арбитража
        opportunities = _analyze_arbitrage_opportunities(
            grouped_items=grouped_items,
            min_profit=min_profit,
            game=game,
        )

        # Сортируем возможности по проценту прибыли (от большего к меньшему)
        opportunities.sort(key=operator.itemgetter("profit_percent"), reverse=True)

        # Логируем статистику поиска
        elapsed_time = time.time() - start_time
        logger.info(
            "arbitrage_search_completed",
            opportunities_found=len(opportunities),
            items_analyzed=len(grouped_items),
            elapsed_seconds=round(elapsed_time, 2),
        )

        # Обрезаем список до разумного размера для возврата
        max_return = min(50, len(opportunities))
        result = opportunities[:max_return]

        # Сохраняем результат в кэш
        save_arbitrage_cache(cache_key, result)

        return result

    except Exception:
        logger.exception("arbitrage_search_error")
        return []


def _analyze_arbitrage_opportunities(
    grouped_items: dict[str, list[dict[str, Any]]],
    min_profit: float,
    game: str,
) -> list[dict[str, Any]]:
    """Анализирует сгруппированные предметы для поиска арбитражных возможностей.

    Args:
        grouped_items: Предметы, сгруппированные по названию
        min_profit: Минимальный процент прибыли
        game: Код игры

    Returns:
        Список арбитражных возможностей

    """
    opportunities: list[dict[str, Any]] = []

    for item_name, items in grouped_items.items():
        # Если в группе меньше 2 предметов, арбитраж невозможен
        if len(items) < 2:
            continue

        # Сортируем по возрастанию цены
        items.sort(key=lambda x: x.get("price", {}).get("USD", 0))

        # Анализируем разницу между самым дешевым и остальными предметами
        cheapest = items[0]
        cheapest_price = cheapest.get("price", {}).get("USD", 0) / 100

        # Получаем данные о предмете для определения комиссии
        item_rarity = cheapest.get("extra", {}).get("rarity", "")
        item_type = cheapest.get("extra", {}).get("category", "")
        item_popularity = cheapest.get("extra", {}).get("popularity", 0.5)

        # Определяем комиссию на основе характеристик предмета
        commission_percent = calculate_commission(
            rarity=item_rarity,
            item_type=item_type,
            popularity=item_popularity,
            game=game,
        )

        # Проверяем остальные предметы
        for item in items[1:]:
            opportunity = _create_opportunity_if_profitable(
                item_name=item_name,
                cheapest=cheapest,
                cheapest_price=cheapest_price,
                sell_item=item,
                commission_percent=commission_percent,
                min_profit=min_profit,
                game=game,
                item_rarity=item_rarity,
                item_type=item_type,
                item_popularity=item_popularity,
            )
            if opportunity:
                opportunities.append(opportunity)

    return opportunities


def _create_opportunity_if_profitable(
    *,
    item_name: str,
    cheapest: dict[str, Any],
    cheapest_price: float,
    sell_item: dict[str, Any],
    commission_percent: float,
    min_profit: float,
    game: str,
    item_rarity: str,
    item_type: str,
    item_popularity: float,
) -> dict[str, Any] | None:
    """Создает запись об арбитражной возможности, если она прибыльна.

    Args:
        item_name: Название предмета
        cheapest: Самый дешевый предмет (для покупки)
        cheapest_price: Цена самого дешевого предмета
        sell_item: Предмет для продажи
        commission_percent: Процент комиссии
        min_profit: Минимальный процент прибыли
        game: Код игры
        item_rarity: Редкость предмета
        item_type: Тип предмета
        item_popularity: Популярность предмета

    Returns:
        Словарь с информацией о возможности или None

    """
    sell_price = sell_item.get("price", {}).get("USD", 0) / 100

    # Рассчитываем прибыль с учетом комиссий
    gross_profit = sell_price - cheapest_price
    commission_amount = sell_price * commission_percent / 100
    net_profit = gross_profit - commission_amount
    profit_percent = (net_profit / cheapest_price) * 100 if cheapest_price > 0 else 0

    # Если прибыль превышает минимальный порог
    if profit_percent >= min_profit and net_profit > 0:
        opportunity: dict[str, Any] = {
            "item_name": item_name,
            "buy_price": cheapest_price,
            "sell_price": sell_price,
            "profit": net_profit,
            "profit_percent": profit_percent,
            "commission_percent": commission_percent,
            "commission_amount": commission_amount,
            "buy_item_id": cheapest.get("itemId"),
            "sell_item_id": sell_item.get("itemId"),
            "game": game,
            "rarity": item_rarity,
            "type": item_type,
            "popularity": item_popularity,
            "timestamp": datetime.now().isoformat(),
        }

        # Добавляем изображение предмета, если доступно
        if "imageUrl" in cheapest:
            opportunity["image_url"] = cheapest.get("imageUrl")

        # Добавляем ссылки на покупку и продажу
        buy_id = cheapest.get("itemId", "")
        sell_id = sell_item.get("itemId", "")

        if buy_id:
            opportunity["buy_link"] = (
                f"https://dmarket.com/ingame-items/item-list/{game}-skins?userOfferId={buy_id}"
            )
        if sell_id:
            opportunity["sell_link"] = (
                f"https://dmarket.com/ingame-items/item-list/{game}-skins?userOfferId={sell_id}"
            )

        return opportunity

    return None


__all__ = [
    "find_arbitrage_items",
    "find_arbitrage_opportunities_advanced",
]
