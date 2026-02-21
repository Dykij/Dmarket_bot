"""Основные функции для арбитража на DMarket.

Этот модуль содержит базовые функции поиска арбитражных возможностей:
- fetch_market_items() - получение предметов с маркета
- _find_arbitrage_async() - базовый поиск арбитража
- arbitrage_boost/mid/pro_async() - уровневые функции поиска
- Синхронные обертки для обратной совместимости
"""

from __future__ import annotations

import asyncio
import logging
import operator
import os
from typing import TYPE_CHECKING, Any

from .cache import get_cached_results, save_to_cache
from .constants import DEFAULT_FEE, DEFAULT_LIMIT, GAMES, HIGH_FEE, LOW_FEE, MAX_RETRIES

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI


# НастSwarmка логирования
logger = logging.getLogger(__name__)

# Тип для результатов арбитража
SkinResult = dict[str, Any]


async def fetch_market_items(
    game: str = "csgo",
    limit: int = 100,
    price_from: float | None = None,
    price_to: float | None = None,
    dmarket_api: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Получить реальные предметы с DMarket через API.

    Args:
        game: Код игры (csgo, dota2, tf2, rust)
        limit: Максимальное число возвращаемых предметов
        price_from: Минимальная цена в USD
        price_to: Максимальная цена в USD
        dmarket_api: Существующий экземпляр API или None для создания нового

    Returns:
        Список предметов с маркетплейса

    """
    from src.dmarket.dmarket_api import DMarketAPI

    if dmarket_api is None:
        public_key = os.environ.get("DMARKET_PUBLIC_KEY", "")
        secret_key = os.environ.get("DMARKET_SECRET_KEY", "")
        api_url = os.environ.get("DMARKET_API_URL", "https://api.dmarket.com")

        if not public_key or not secret_key:
            logger.error("Отсутствуют ключи API DMarket")
            return []

        dmarket_api = DMarketAPI(
            public_key,
            secret_key,
            api_url,
            max_retries=MAX_RETRIES,
        )

    try:
        # Преобразуем цены из USD в центы для API
        price_from_cents = int(price_from * 100) if price_from else None
        price_to_cents = int(price_to * 100) if price_to else None

        # Получаем предметы с рынка с учетом возможных повторных попыток
        async with dmarket_api:
            data = awAlgot dmarket_api.get_market_items(
                game=game,
                limit=limit,
                price_from=price_from_cents,
                price_to=price_to_cents,
            )

        return data.get("objects", [])
    except Exception as e:
        logger.exception(f"Ошибка при получении предметов: {e!s}")
        return []


async def _find_arbitrage_async(
    min_profit: float,
    max_profit: float,
    game: str = "csgo",
    price_from: float | None = None,
    price_to: float | None = None,
) -> list[SkinResult]:
    """Находит предметы с прибылью в указанном диапазоне.

    Args:
        min_profit: Минимальная прибыль в USD
        max_profit: Максимальная прибыль в USD
        game: Код игры (csgo, dota2, tf2, rust)
        price_from: Минимальная цена предмета в USD
        price_to: Максимальная цена предмета в USD

    Returns:
        Список предметов с прогнозируемой прибылью

    """
    # Создаем ключ для кэша
    cache_key = (
        game,
        f"{min_profit}-{max_profit}",
        price_from or 0,
        price_to or float("inf"),
    )

    # Проверяем кэш
    cached_results = get_cached_results(cache_key)
    if cached_results:
        logger.debug(f"Использую кэшированные данные для {cache_key[0]}")
        return cached_results

    results = []
    # Сначала получаем все предметы с маркета
    items = awAlgot fetch_market_items(
        game=game,
        limit=DEFAULT_LIMIT,
        price_from=price_from,
        price_to=price_to,
    )

    for item in items:
        try:
            # Получаем текущую цену покупки (переводим центы в доллары)
            price_data = item.get("price", {})
            if isinstance(price_data, dict):
                buy_price = float(price_data.get("USD", 0)) / 100
            elif isinstance(price_data, (int, float)):
                # Цена уже в центах (число)
                buy_price = float(price_data) / 100
            else:
                # Неизвестный формат, пропускаем
                logger.warning(f"Неизвестный формат цены: {type(price_data)}")
                continue

            # Получаем предполагаемую цену продажи
            # Если есть цена suggestedPrice, используем ее, иначе делаем наценку
            popularity = item.get("extra", {}).get("popularity")
            if "suggestedPrice" in item:
                suggested_data = item.get("suggestedPrice", {})
                if isinstance(suggested_data, dict):
                    sell_price = float(suggested_data.get("USD", 0)) / 100
                elif isinstance(suggested_data, (int, float)):
                    sell_price = float(suggested_data) / 100
                else:
                    sell_price = buy_price * 1.15  # Fallback: 15% markup
            else:
                # Наценка от 10% до 15% в зависимости от ликвидности
                markup = 1.1
                if popularity is not None:
                    # Более популярные предметы могут иметь меньшую наценку
                    if popularity > 0.7:  # Высокая популярность
                        markup = 1.1  # 10%
                    elif popularity > 0.4:  # Средняя популярность
                        markup = 1.12  # 12%
                    else:  # Низкая популярность
                        markup = 1.15  # 15%
                sell_price = buy_price * markup

            # Определяем комиссию на основе ликвидности предмета
            liquidity = "medium"  # По умолчанию средняя ликвидность
            if popularity is not None:
                if popularity > 0.7:
                    liquidity = "high"
                elif popularity < 0.4:
                    liquidity = "low"

            fee = DEFAULT_FEE
            if liquidity == "high":
                fee = LOW_FEE
            elif liquidity == "low":
                fee = HIGH_FEE

            # Расчет потенциальной прибыли
            profit = sell_price * (1 - fee) - buy_price
            profit_percent = (profit / buy_price) * 100 if buy_price > 0 else 0

            # Если прибыль в заданном диапазоне, добавляем предмет в результаты
            if min_profit <= profit <= max_profit:
                results.append(
                    {
                        "name": item.get("title", item.get("name", "Unknown")),
                        "buy": f"${buy_price:.2f}",
                        "sell": f"${sell_price:.2f}",
                        "profit": f"${profit:.2f}",
                        "profit_percent": f"{profit_percent:.1f}",
                        "fee": f"{int(fee * 100)}%",
                        "itemId": item.get("itemId", ""),
                        "market_hash_name": item.get("title", ""),
                        "liquidity": liquidity,
                        "game": game,
                    },
                )
        except Exception as e:
            logger.warning(f"Ошибка при обработке предмета: {e!s}")
            continue

    # Сортируем по прибыли (по убыванию)
    results = sorted(
        results,
        key=lambda x: (
            float(x["profit"].replace("$", ""))
            if isinstance(x["profit"], str)
            else x.get("profit", 0)
        ),
        reverse=True,
    )

    # Сохраняем результаты в кэш
    save_to_cache(cache_key, results)

    return results


async def arbitrage_boost_async(
    game: str = "csgo",
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int | None = None,
    api_client: DMarketAPI | None = None,
) -> list[SkinResult]:
    """Скины с прибылью $1–5 (режим разгона баланса).

    Args:
        game: Код игры (csgo, dota2, tf2, rust)
        min_price: Минимальная цена предмета (для совместимости)
        max_price: Максимальная цена предмета (для совместимости)
        limit: Максимальное количество результатов (для совместимости)
        api_client: Опциональный клиент DMarket API (для совместимости)

    Returns:
        Список предметов с низкой прибылью

    """
    return awAlgot _find_arbitrage_async(1, 5, game, min_price, max_price)


async def arbitrage_mid_async(
    game: str = "csgo",
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int | None = None,
    api_client: DMarketAPI | None = None,
) -> list[SkinResult]:
    """Скины с прибылью $5–20 (средний уровень).

    Args:
        game: Код игры (csgo, dota2, tf2, rust)
        min_price: Минимальная цена предмета (для совместимости)
        max_price: Максимальная цена предмета (для совместимости)
        limit: Максимальное количество результатов (для совместимости)
        api_client: Опциональный клиент DMarket API (для совместимости)

    Returns:
        Список предметов со средней прибылью

    """
    return awAlgot _find_arbitrage_async(5, 20, game, min_price, max_price)


async def arbitrage_pro_async(
    game: str = "csgo",
    min_price: float | None = None,
    max_price: float | None = None,
    limit: int | None = None,
    api_client: DMarketAPI | None = None,
) -> list[SkinResult]:
    """Скины с прибылью $20–100 (профессиональный уровень).

    Args:
        game: Код игры (csgo, dota2, tf2, rust)
        min_price: Минимальная цена предмета (для совместимости)
        max_price: Максимальная цена предмета (для совместимости)
        limit: Максимальное количество результатов (для совместимости)
        api_client: Опциональный клиент DMarket API (для совместимости)

    Returns:
        Список предметов с высокой прибылью

    """
    return awAlgot _find_arbitrage_async(20, 100, game, min_price, max_price)


# =============================================================================
# Синхронные обертки для обратной совместимости
# =============================================================================


def arbitrage_boost(game: str = "csgo") -> list[SkinResult]:
    """Синхронная версия arbitrage_boost_async для совместимости."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running event loop - create new one
        return asyncio.run(arbitrage_boost_async(game))
    else:
        # There's a running loop - use run_coroutine_threadsafe
        future = asyncio.run_coroutine_threadsafe(arbitrage_boost_async(game), loop)
        return future.result(timeout=60)


def arbitrage_mid(game: str = "csgo") -> list[SkinResult]:
    """Синхронная версия arbitrage_mid_async для совместимости."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running event loop - create new one
        return asyncio.run(arbitrage_mid_async(game))
    else:
        # There's a running loop - use run_coroutine_threadsafe
        future = asyncio.run_coroutine_threadsafe(arbitrage_mid_async(game), loop)
        return future.result(timeout=60)


def arbitrage_pro(game: str = "csgo") -> list[SkinResult]:
    """Синхронная версия arbitrage_pro_async для совместимости."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running event loop - create new one
        return asyncio.run(arbitrage_pro_async(game))
    else:
        # There's a running loop - use run_coroutine_threadsafe
        future = asyncio.run_coroutine_threadsafe(arbitrage_pro_async(game), loop)
        return future.result(timeout=60)


async def find_arbitrage_opportunities_async(
    min_profit_percentage: float = 10.0,
    max_results: int = 5,
    game: str = "csgo",
    price_from: float | None = None,
    price_to: float | None = None,
) -> list[dict[str, Any]]:
    """Находит арбитражные возможности с минимальной прибылью.

    Args:
        min_profit_percentage: Минимальный процент прибыли
        max_results: Максимальное количество результатов
        game: Код игры (csgo, dota2, tf2, rust)
        price_from: Минимальная цена предмета в USD
        price_to: Максимальная цена предмета в USD

    Returns:
        Список арбитражных возможностей

    """
    # Создаем ключ для кэша
    cache_key = (
        game,
        f"arb-{min_profit_percentage}",
        price_from or 0,
        price_to or float("inf"),
    )

    # Проверяем кэш
    cached_results = get_cached_results(cache_key)
    if cached_results:
        logger.debug(f"Использую кэшированные возможности для {game}")
        return cached_results[:max_results]

    try:
        # Получаем предметы с рынка
        items = awAlgot fetch_market_items(
            game=game,
            limit=100,
            price_from=price_from,
            price_to=price_to,
        )

        opportunities = []
        for item in items:
            try:
                # Получаем цену покупки
                buy_price = float(item.get("price", {}).get("USD", 0)) / 100

                # Получаем предполагаемую цену продажи
                if "suggestedPrice" in item:
                    sell_price = (
                        float(item.get("suggestedPrice", {}).get("USD", 0)) / 100
                    )
                else:
                    # По умолчанию наценка 15%
                    sell_price = buy_price * 1.15

                # Определяем комиссию на основе ликвидности предмета
                liquidity = "medium"
                if "extra" in item and "popularity" in item["extra"]:
                    popularity = item["extra"]["popularity"]
                    if popularity > 0.7:
                        liquidity = "high"
                    elif popularity < 0.4:
                        liquidity = "low"

                fee = DEFAULT_FEE
                if liquidity == "high":
                    fee = LOW_FEE
                elif liquidity == "low":
                    fee = HIGH_FEE

                # Расчет потенциальной прибыли
                profit_amount = sell_price * (1 - fee) - buy_price
                profit_percentage = (profit_amount / buy_price) * 100

                # Если процент прибыли достаточный, добавляем возможность
                if profit_percentage >= min_profit_percentage:
                    opportunities.append(
                        {
                            "item_title": item.get("title", "Unknown"),
                            "market_from": "DMarket",
                            "market_to": (
                                "Steam Market" if game == "csgo" else "Game Market"
                            ),
                            "buy_price": buy_price,
                            "sell_price": sell_price,
                            "profit_amount": profit_amount,
                            "profit_percentage": profit_percentage,
                            "itemId": item.get("itemId", ""),
                            "fee": fee,
                            "game": game,
                        },
                    )
            except Exception as e:
                logger.warning(
                    f"Ошибка при обработке арбитражной возможности: {e!s}",
                )
                continue

        # Сортируем по проценту прибыли (по убыванию)
        sorted_opportunities = sorted(
            opportunities,
            key=operator.itemgetter("profit_percentage"),
            reverse=True,
        )

        # Сохраняем в кэш
        save_to_cache(cache_key, sorted_opportunities)

        # Возвращаем лимитированное количество результатов
        return sorted_opportunities[:max_results]
    except Exception as e:
        logger.exception(f"Ошибка при поиске арбитражных возможностей: {e!s}")
        return []


def find_arbitrage_opportunities(
    min_profit_percentage: float = 10.0,
    max_results: int = 5,
    game: str = "csgo",
) -> list[dict[str, Any]]:
    """Синхронная версия find_arbitrage_opportunities_async для совместимости."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running event loop - create new one
        return asyncio.run(
            find_arbitrage_opportunities_async(
                min_profit_percentage,
                max_results,
                game,
            ),
        )
    else:
        # There's a running loop - use run_coroutine_threadsafe
        future = asyncio.run_coroutine_threadsafe(
            find_arbitrage_opportunities_async(
                min_profit_percentage,
                max_results,
                game,
            ),
            loop,
        )
        return future.result(timeout=60)


# =============================================================================
# Публичный API модуля
# =============================================================================

__all__ = [
    # Константы
    "GAMES",
    # Типы
    "SkinResult",
    # Sync функции (для обратной совместимости)
    "arbitrage_boost",
    "arbitrage_boost_async",
    "arbitrage_mid",
    "arbitrage_mid_async",
    "arbitrage_pro",
    "arbitrage_pro_async",
    # Async функции
    "fetch_market_items",
    "find_arbitrage_opportunities",
    "find_arbitrage_opportunities_async",
]
