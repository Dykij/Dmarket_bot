"""Модуль для расширенного анализа рынка DMarket.

Этот модуль предоставляет функции для анализа тенденций цен на предметы,
отслеживания изменений на рынке и выявления потенциальных возможностей для торговли.
"""

import asyncio
import logging
import operator
import os
import time
from typing import Any

from dotenv import load_dotenv

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.performance import cached, profile_performance
from src.utils.rate_limiter import RateLimiter

# Загружаем переменные окружения
load_dotenv()

# НастSwarmка логирования
logger = logging.getLogger(__name__)

# Создаем ограничитель скорости запросов
rate_limiter = RateLimiter(is_authorized=True)

# Кэш для хранения истории цен
# Формат: {market_hash_name: [(timestamp, price), ...]}
price_history_cache = {}

# Кэш для хранения трендов предметов
# Формат: {game: {market_hash_name: {"trend": "up/down/stable", "change_percent": float}}}
market_trends_cache = {}

# Время жизни кэша (в секундах)
PRICE_HISTORY_TTL = 3600  # 1 час
TRENDS_CACHE_TTL = 1800  # 30 минут

# Последнее время обновления кэша
last_cache_update = {
    "price_history": 0,
    "market_trends": 0,
}

# Получение ключей API из переменных окружения
DMARKET_PUBLIC_KEY = os.getenv("DMARKET_PUBLIC_KEY", "")
DMARKET_SECRET_KEY = os.getenv("DMARKET_SECRET_KEY", "")
DMARKET_API_URL = os.getenv("DMARKET_API_URL", "https://api.dmarket.com")


@cached("price_change_analysis", ttl=1800)
async def analyze_price_changes(
    game: str = "csgo",
    period: str = "24h",
    min_price: float = 1.0,
    max_price: float = 500.0,
    min_change_percent: float = 5.0,
    limit: int = 50,
    direction: str = "any",
    dmarket_api: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Анализирует изменения цен на предметы за указанный период.

    Args:
        game: Код игры (csgo, dota2, rust, tf2)
        period: Период анализа (1h, 3h, 6h, 12h, 24h, 7d, 30d)
        min_price: Минимальная цена предмета (USD)
        max_price: Максимальная цена предмета (USD)
        min_change_percent: Минимальный процент изменения цены для учета
        limit: Максимальное количество результатов
        direction: Направление изменения цены (up, down, any)
        dmarket_api: Экземпляр DMarketAPI или None для создания нового

    Returns:
        Список предметов с информацией об изменении цены

    """
    # Создаем API клиент, если не предоставлен
    close_client = False
    if dmarket_api is None:
        dmarket_api = DMarketAPI(
            DMARKET_PUBLIC_KEY,
            DMARKET_SECRET_KEY,
            DMARKET_API_URL,
        )
        close_client = True

    try:
        logger.info(f"Анализ изменений цен для {game} за период {period}")

        # Определяем параметры периода
        period_hours = {
            "1h": 1,
            "3h": 3,
            "6h": 6,
            "12h": 12,
            "24h": 24,
            "7d": 24 * 7,
            "30d": 24 * 30,
        }.get(period, 24)

        # Получаем текущие цены
        await rate_limiter.wait_if_needed("market")

        current_items = await dmarket_api.get_market_items(
            game=game,
            limit=200,
            min_price=min_price * 100,  # в центах
            max_price=max_price * 100,  # в центах
            sort_by="best_deal",
        )

        if not current_items or "items" not in current_items:
            logger.warning(f"Не удалось получить текущие цены для {game}")
            return []

        # Получаем исторические данные о ценах
        historical_prices = await _get_historical_prices(
            game=game,
            period_hours=period_hours,
            dmarket_api=dmarket_api,
        )

        # Анализируем изменения цен
        price_changes = []

        for item in current_items.get("items", []):
            market_hash_name = item.get("title", "")
            if not market_hash_name:
                continue

            # Текущая цена
            current_price = _extract_price_from_item(item)
            if current_price <= 0:
                continue

            # Исторические цены для этого предмета
            if market_hash_name in historical_prices:
                old_price = historical_prices[market_hash_name]

                # Если есть историческая цена, рассчитываем изменение
                if old_price > 0:
                    change_amount = current_price - old_price
                    change_percent = (change_amount / old_price) * 100

                    # Фильтруем по направлению изменения
                    if direction == "up" and change_percent <= 0:
                        continue
                    if direction == "down" and change_percent >= 0:
                        continue

                    # Фильтруем по минимальному проценту изменения
                    if abs(change_percent) < min_change_percent:
                        continue

                    # Добавляем в результаты
                    price_changes.append(
                        {
                            "market_hash_name": market_hash_name,
                            "current_price": current_price,
                            "old_price": old_price,
                            "change_amount": change_amount,
                            "change_percent": change_percent,
                            "direction": "up" if change_percent > 0 else "down",
                            "game": game,
                            "sales_volume": item.get("salesVolume", 0),
                            "image_url": item.get("imageUrl", ""),
                            "item_url": (
                                f"https://dmarket.com/ingame-items/{game}/{market_hash_name.lower().replace(' ', '-')}"
                            ),
                            "timestamp": int(time.time()),
                        },
                    )

        # Сортируем по абсолютному значению процента изменения (по убыванию)
        price_changes.sort(key=lambda x: abs(x["change_percent"]), reverse=True)

        return price_changes[:limit]

    except Exception as e:
        logger.exception(f"Ошибка при анализе изменений цен: {e}")
        return []
    finally:
        if close_client and hasattr(dmarket_api, "_close_client"):
            try:
                await dmarket_api._close_client()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии клиента API: {e}")


@cached("trending_items", ttl=1800)
async def find_trending_items(
    game: str = "csgo",
    min_price: float = 1.0,
    max_price: float = 500.0,
    limit: int = 20,
    min_sales: int = 5,
    dmarket_api: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Находит предметы, набирающие популярность на рынке.

    Args:
        game: Код игры (csgo, dota2, rust, tf2)
        min_price: Минимальная цена предмета (USD)
        max_price: Максимальная цена предмета (USD)
        limit: Максимальное количество результатов
        min_sales: Минимальное количество продаж для учета
        dmarket_api: Экземпляр DMarketAPI или None для создания нового

    Returns:
        Список трендовых предметов

    """
    # Создаем API клиент, если не предоставлен
    close_client = False
    if dmarket_api is None:
        dmarket_api = DMarketAPI(
            DMARKET_PUBLIC_KEY,
            DMARKET_SECRET_KEY,
            DMARKET_API_URL,
        )
        close_client = True

    try:
        logger.info(f"Поиск трендовых предметов для {game}")

        # Получаем предметы, отсортированные по объему продаж
        await rate_limiter.wait_if_needed("market")

        trending_response = await dmarket_api.get_market_items(
            game=game,
            limit=200,
            min_price=min_price * 100,  # в центах
            max_price=max_price * 100,  # в центах
            sort_by="qty_offers",  # Сортировка по количеству предложений
        )

        if not trending_response or "items" not in trending_response:
            logger.warning(f"Не удалось получить трендовые предметы для {game}")
            return []

        # Фильтруем и форматируем результаты
        trending_items = []

        for item in trending_response.get("items", []):
            sales_volume = item.get("salesVolume", 0)

            # Пропускаем предметы с низким объемом продаж
            if sales_volume < min_sales:
                continue

            market_hash_name = item.get("title", "")
            if not market_hash_name:
                continue

            # Получаем цену
            price = _extract_price_from_item(item)
            if price <= 0:
                continue

            # Добавляем в результаты
            trending_items.append(
                {
                    "market_hash_name": market_hash_name,
                    "price": price,
                    "sales_volume": sales_volume,
                    "popularity_score": _calculate_popularity_score(item),
                    "image_url": item.get("imageUrl", ""),
                    "item_url": (
                        f"https://dmarket.com/ingame-items/{game}/{market_hash_name.lower().replace(' ', '-')}"
                    ),
                    "timestamp": int(time.time()),
                    "game": game,
                    "offers_count": item.get("offersCount", 0),
                },
            )

        # Сортируем по показателю популярности
        trending_items.sort(key=operator.itemgetter("popularity_score"), reverse=True)

        return trending_items[:limit]

    except Exception as e:
        logger.exception(f"Ошибка при поиске трендовых предметов: {e}")
        return []
    finally:
        if close_client and hasattr(dmarket_api, "_close_client"):
            try:
                await dmarket_api._close_client()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии клиента API: {e}")


@cached("market_volatility", ttl=1800)
async def analyze_market_volatility(
    game: str = "csgo",
    min_price: float = 1.0,
    max_price: float = 500.0,
    limit: int = 20,
    dmarket_api: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Анализирует волатильность цен на рынке.

    Args:
        game: Код игры (csgo, dota2, rust, tf2)
        min_price: Минимальная цена предмета (USD)
        max_price: Максимальная цена предмета (USD)
        limit: Максимальное количество результатов
        dmarket_api: Экземпляр DMarketAPI или None для создания нового

    Returns:
        Список предметов с высокой волатильностью цен

    """
    # Создаем API клиент, если не предоставлен
    close_client = False
    if dmarket_api is None:
        dmarket_api = DMarketAPI(
            DMARKET_PUBLIC_KEY,
            DMARKET_SECRET_KEY,
            DMARKET_API_URL,
        )
        close_client = True

    try:
        # Получаем исторические данные о ценах за разные периоды
        historical_24h = await _get_historical_prices(
            game=game,
            period_hours=24,
            dmarket_api=dmarket_api,
        )
        historical_7d = await _get_historical_prices(
            game=game,
            period_hours=24 * 7,
            dmarket_api=dmarket_api,
        )

        # Получаем текущие цены
        await rate_limiter.wait_if_needed("market")

        current_items = await dmarket_api.get_market_items(
            game=game,
            limit=100,
            min_price=min_price * 100,
            max_price=max_price * 100,
            sort_by="best_bargAlgon",
        )

        if not current_items or "items" not in current_items:
            return []

        # Рассчитываем волатильность
        volatility_items = []

        for item in current_items.get("items", []):
            market_hash_name = item.get("title", "")
            if not market_hash_name:
                continue

            # Текущая цена
            current_price = _extract_price_from_item(item)
            if current_price <= 0:
                continue

            # Получаем исторические цены
            price_24h = historical_24h.get(market_hash_name, 0)
            price_7d = historical_7d.get(market_hash_name, 0)

            # Пропускаем, если нет исторических данных
            if price_24h <= 0 or price_7d <= 0:
                continue

            # Рассчитываем изменения цен
            change_24h_percent = ((current_price - price_24h) / price_24h) * 100
            change_7d_percent = ((current_price - price_7d) / price_7d) * 100

            # Рассчитываем волатильность как разницу между изменениями за разные периоды
            volatility_score = abs(change_24h_percent - change_7d_percent)

            # Добавляем в результаты
            volatility_items.append(
                {
                    "market_hash_name": market_hash_name,
                    "current_price": current_price,
                    "price_24h": price_24h,
                    "price_7d": price_7d,
                    "change_24h_percent": change_24h_percent,
                    "change_7d_percent": change_7d_percent,
                    "volatility_score": volatility_score,
                    "game": game,
                    "image_url": item.get("imageUrl", ""),
                    "timestamp": int(time.time()),
                },
            )

        # Сортируем по волатильности
        volatility_items.sort(key=operator.itemgetter("volatility_score"), reverse=True)

        return volatility_items[:limit]

    except Exception as e:
        logger.exception(f"Ошибка при анализе волатильности рынка: {e}")
        return []
    finally:
        if close_client and hasattr(dmarket_api, "_close_client"):
            try:
                await dmarket_api._close_client()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии клиента API: {e}")


@profile_performance
async def generate_market_report(
    game: str = "csgo",
    dmarket_api: DMarketAPI | None = None,
) -> dict[str, Any]:
    """Генерирует комплексный отчет о состоянии рынка.

    Args:
        game: Код игры (csgo, dota2, rust, tf2)
        dmarket_api: Экземпляр DMarketAPI или None для создания нового

    Returns:
        Словарь с данными отчета

    """
    # Создаем API клиент, если не предоставлен
    close_client = False
    if dmarket_api is None:
        dmarket_api = DMarketAPI(
            DMARKET_PUBLIC_KEY,
            DMARKET_SECRET_KEY,
            DMARKET_API_URL,
        )
        close_client = True

    try:
        # Запускаем задачи параллельно (добавлен анализ глубины рынка)
        tasks = [
            analyze_price_changes(
                game=game,
                period="24h",
                dmarket_api=dmarket_api,
                limit=10,
            ),
            find_trending_items(game=game, dmarket_api=dmarket_api, limit=10),
            analyze_market_volatility(game=game, dmarket_api=dmarket_api, limit=10),
            analyze_market_depth(
                game=game,
                items=None,  # Автоматически выбирает популярные
                limit=20,
                dmarket_api=dmarket_api,
            ),
        ]

        results = await asyncio.gather(*tasks)

        # Формируем отчет с данными о глубине рынка
        market_depth = results[3]

        return {
            "game": game,
            "timestamp": int(time.time()),
            "price_changes": results[0],
            "trending_items": results[1],
            "volatile_items": results[2],
            "market_depth": market_depth,
            "market_summary": {
                "price_change_direction": _get_market_direction(results[0]),
                "top_trending_categories": _extract_trending_categories(results[1]),
                "market_volatility_level": _calculate_market_volatility_level(
                    results[2],
                ),
                "average_market_liquidity": (
                    market_depth.get("summary", {}).get("average_liquidity_score", 0)
                ),
                "market_health": market_depth.get("summary", {}).get(
                    "market_health", "unknown"
                ),
                "recommended_actions": _generate_market_recommendations(results),
            },
        }

    except Exception as e:
        logger.exception(f"Ошибка при создании отчета о рынке: {e}")
        return {
            "game": game,
            "timestamp": int(time.time()),
            "error": str(e),
            "price_changes": [],
            "trending_items": [],
            "volatile_items": [],
            "market_summary": {},
        }
    finally:
        if close_client and hasattr(dmarket_api, "_close_client"):
            try:
                await dmarket_api._close_client()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии клиента API: {e}")


@cached("market_depth_analysis", ttl=600)
async def analyze_market_depth(
    game: str = "csgo",
    items: list[str] | None = None,
    limit: int = 50,
    dmarket_api: DMarketAPI | None = None,
) -> dict[str, Any]:
    """Анализ глубины рынка с использованием API v1.1.0 aggregated-prices.

    Показывает спрос/предложение для списка предметов, помогая определить
    ликвидность и потенциал для арбитража.

    Args:
        game: Код игры (csgo, dota2, rust, tf2)
        items: Список названий предметов (если None, берутся популярные)
        limit: Максимальное количество предметов для анализа
        dmarket_api: Экземпляр DMarketAPI или None для создания нового

    Returns:
        Словарь с анализом глубины рынка

    Example:
        >>> analysis = await analyze_market_depth(
        ...     game="csgo", items=["AK-47 | Redline (Field-Tested)", "AWP | Asiimov (FT)"]
        ... )
        >>> print(f"Глубина рынка: {analysis['average_depth_score']:.1f}/100")

    """
    close_client = False
    if dmarket_api is None:
        dmarket_api = DMarketAPI(
            DMARKET_PUBLIC_KEY,
            DMARKET_SECRET_KEY,
            DMARKET_API_URL,
        )
        close_client = True

    try:
        logger.info(f"Анализ глубины рынка для {game}")

        # Если список предметов не указан, получаем популярные
        if items is None:
            await rate_limiter.wait_if_needed("market")
            market_items = await dmarket_api.get_market_items(
                game=game,
                limit=limit,
                sort_by="best_deal",
            )
            items = [
                item.get("title")
                for item in market_items.get("items", [])
                if item.get("title")
            ][:limit]

        if not items:
            logger.warning("Нет предметов для анализа глубины рынка")
            return {
                "game": game,
                "items_analyzed": 0,
                "market_depth": [],
                "summary": {},
            }

        # Используем новый API v1.1.0 для получения aggregated prices
        await rate_limiter.wait_if_needed("market")
        aggregated = await dmarket_api.get_aggregated_prices_bulk(
            game=game,
            titles=items,
            limit=len(items),
        )

        if not aggregated or "aggregatedPrices" not in aggregated:
            logger.warning("Не удалось получить aggregated prices")
            return {
                "game": game,
                "items_analyzed": 0,
                "market_depth": [],
                "summary": {},
            }

        # Анализируем каждый предмет
        depth_analysis = []

        for price_data in aggregated["aggregatedPrices"]:
            title = price_data["title"]
            order_count = price_data.get("orderCount", 0)
            offer_count = price_data.get("offerCount", 0)
            order_price = float(price_data.get("orderBestPrice", 0)) / 100
            offer_price = float(price_data.get("offerBestPrice", 0)) / 100

            # Рассчитываем показатели глубины рынка
            total_volume = order_count + offer_count
            buy_pressure = (order_count / total_volume * 100) if total_volume > 0 else 0
            sell_pressure = (
                (offer_count / total_volume * 100) if total_volume > 0 else 0
            )

            # Спред между лучшей ценой покупки и продажи
            spread = offer_price - order_price
            spread_percent = (spread / order_price * 100) if order_price > 0 else 0

            # Оценка ликвидности (0-100)
            liquidity_score = min(100, total_volume * 2)

            # Определяем баланс рынка
            if buy_pressure > 60:
                market_balance = "buyer_dominated"
                balance_description = "Преобладают покупатели"
            elif sell_pressure > 60:
                market_balance = "seller_dominated"
                balance_description = "Преобладают продавцы"
            else:
                market_balance = "balanced"
                balance_description = "Сбалансированный рынок"

            depth_analysis.append(
                {
                    "title": title,
                    "order_count": order_count,
                    "offer_count": offer_count,
                    "total_volume": total_volume,
                    "order_price": order_price,
                    "offer_price": offer_price,
                    "spread": spread,
                    "spread_percent": spread_percent,
                    "buy_pressure": buy_pressure,
                    "sell_pressure": sell_pressure,
                    "liquidity_score": liquidity_score,
                    "market_balance": market_balance,
                    "balance_description": balance_description,
                    "arbitrage_potential": spread_percent > 5.0,
                }
            )

        # Рассчитываем сводные показатели
        if depth_analysis:
            avg_liquidity = sum(
                item["liquidity_score"] for item in depth_analysis
            ) / len(depth_analysis)
            avg_spread = sum(item["spread_percent"] for item in depth_analysis) / len(
                depth_analysis
            )
            high_liquidity_count = sum(
                1 for item in depth_analysis if item["liquidity_score"] >= 50
            )
            arbitrage_opportunities = sum(
                1 for item in depth_analysis if item["arbitrage_potential"]
            )

            summary = {
                "items_analyzed": len(depth_analysis),
                "average_liquidity_score": round(avg_liquidity, 1),
                "average_spread_percent": round(avg_spread, 2),
                "high_liquidity_items": high_liquidity_count,
                "arbitrage_opportunities": arbitrage_opportunities,
                "market_health": (
                    "excellent"
                    if avg_liquidity >= 75
                    else (
                        "good"
                        if avg_liquidity >= 50
                        else "moderate" if avg_liquidity >= 25 else "poor"
                    )
                ),
            }
        else:
            summary = {}

        logger.info(
            f"Проанализировано {len(depth_analysis)} предметов, "
            f"средняя ликвидность: {summary.get('average_liquidity_score', 0):.1f}"
        )

        return {
            "game": game,
            "timestamp": int(time.time()),
            "items_analyzed": len(depth_analysis),
            "market_depth": depth_analysis,
            "summary": summary,
        }

    except Exception as e:
        logger.exception(f"Ошибка при анализе глубины рынка: {e}")
        return {
            "game": game,
            "items_analyzed": 0,
            "market_depth": [],
            "summary": {},
            "error": str(e),
        }
    finally:
        if close_client and hasattr(dmarket_api, "_close_client"):
            try:
                await dmarket_api._close_client()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии клиента API: {e}")


# Вспомогательные функции


async def _get_historical_prices(
    game: str,
    period_hours: int = 24,
    dmarket_api: DMarketAPI = None,
) -> dict[str, float]:
    """Получает исторические цены предметов.

    Args:
        game: Код игры
        period_hours: Период в часах
        dmarket_api: Экземпляр DMarketAPI

    Returns:
        Словарь {market_hash_name: historical_price}

    """
    # В реальном приложении здесь был бы запрос к базе данных или API истории цен
    # Для прототипа используем симуляцию исторических данных

    # Получаем текущие цены для нескольких предметов
    await rate_limiter.wait_if_needed("market")

    items_response = await dmarket_api.get_market_items(
        game=game,
        limit=200,
        sort_by="best_bargAlgon",
    )

    if not items_response or "items" not in items_response:
        return {}

    # Симулируем исторические цены на основе текущих с небольшими отклонениями
    historical_prices = {}

    import random

    for item in items_response.get("items", []):
        market_hash_name = item.get("title", "")
        if not market_hash_name:
            continue

        current_price = _extract_price_from_item(item)
        if current_price <= 0:
            continue

        # Симулируем историческую цену с отклонением -20% до +20%
        # Non-cryptographic use - just for simulation/testing
        variation = random.uniform(-0.2, 0.2)  # noqa: S311
        historical_price = current_price * (1 + variation)

        historical_prices[market_hash_name] = historical_price

    return historical_prices


def _extract_price_from_item(item: dict[str, Any]) -> float:
    """Извлекает цену из объекта предмета.

    Args:
        item: Словарь с данными предмета

    Returns:
        Цена в USD (в долларах, не в центах)

    """
    try:
        # Проверяем различные форматы цен
        if "price" in item:
            price_data = item["price"]

            if isinstance(price_data, dict) and "amount" in price_data:
                # Формат: {"price": {"amount": 1000, "currency": "USD"}}
                return float(price_data["amount"]) / 100
            if isinstance(price_data, int | float):
                # Формат: {"price": 1000}
                return float(price_data) / 100
            if isinstance(price_data, str):
                # Формат: {"price": "$10.00"}
                return float(price_data.replace("$", "").strip())

        # Альтернативные поля цен
        if "bestPrice" in item:
            best_price = item["bestPrice"]
            if isinstance(best_price, dict) and "amount" in best_price:
                return float(best_price["amount"]) / 100
            if isinstance(best_price, int | float):
                return float(best_price) / 100

        # Проверяем другие возможные поля
        for price_field in ["suggestedPrice", "marketPrice", "averagePrice"]:
            if price_field in item:
                price_value = item[price_field]
                if isinstance(price_value, int | float):
                    return float(price_value) / 100
                if isinstance(price_value, dict) and "amount" in price_value:
                    return float(price_value["amount"]) / 100

        return 0.0
    except (TypeError, ValueError) as e:
        logger.exception(f"Ошибка при извлечении цены: {e}")
        return 0.0


def _calculate_popularity_score(item: dict[str, Any]) -> float:
    """Рассчитывает показатель популярности предмета.

    Args:
        item: Словарь с данными предмета

    Returns:
        Показатель популярности

    """
    sales_volume = item.get("salesVolume", 0)
    offers_count = item.get("offersCount", 0)

    # Базовая популярность на основе объема продаж
    popularity = sales_volume * 2

    # Корректируем в зависимости от количества предложений
    if offers_count > 0:
        # Более высокое соотношение продаж к предложениям = более высокая популярность
        popularity *= sales_volume / (offers_count + 1)

    return popularity


def _get_market_direction(price_changes: list[dict[str, Any]]) -> str:
    """Определяет общее направление рынка.

    Args:
        price_changes: Список предметов с изменениями цен

    Returns:
        Строка с направлением рынка: "up", "down" или "stable"

    """
    if not price_changes:
        return "stable"

    up_count = sum(1 for item in price_changes if item.get("direction") == "up")
    down_count = sum(1 for item in price_changes if item.get("direction") == "down")

    if up_count > down_count * 1.5:
        return "up"
    if down_count > up_count * 1.5:
        return "down"
    return "stable"


def _extract_trending_categories(trending_items: list[dict[str, Any]]) -> list[str]:
    """Извлекает категории трендовых предметов.

    Args:
        trending_items: Список трендовых предметов

    Returns:
        Список популярных категорий

    """
    # В реальном приложении здесь была бы логика определения категорий предметов
    # Для прототипа возвращаем заглушку

    if not trending_items:
        return ["Нет данных"]

    # Категории определяются на основе названий предметов (примитивная реализация)
    keywords = {
        "knife": "Ножи",
        "karambit": "Ножи",
        "bayonet": "Ножи",
        "butterfly": "Ножи",
        "awp": "Снайперские винтовки",
        "ak-47": "Штурмовые винтовки",
        "ak47": "Штурмовые винтовки",
        "m4a1": "Штурмовые винтовки",
        "m4a4": "Штурмовые винтовки",
        "gloves": "Перчатки",
        "case": "Кейсы",
        "sticker": "Наклейки",
        "pistol": "Пистолеты",
        "glock": "Пистолеты",
        "usp": "Пистолеты",
        "desert eagle": "Пистолеты",
        "eagle": "Пистолеты",
    }

    category_counts = {}

    for item in trending_items:
        name = item.get("market_hash_name", "").lower()

        for keyword, category in keywords.items():
            if keyword in name:
                category_counts[category] = category_counts.get(category, 0) + 1
                break
        else:
            # Если ни одно ключевое слово не найдено
            category_counts["Другое"] = category_counts.get("Другое", 0) + 1

    # Сортируем категории по количеству предметов
    sorted_categories = sorted(
        category_counts.items(),
        key=operator.itemgetter(1),
        reverse=True,
    )

    # Возвращаем до 3 самых популярных категорий
    return [category for category, _ in sorted_categories[:3]]


def _calculate_market_volatility_level(volatile_items: list[dict[str, Any]]) -> str:
    """Рассчитывает общий уровень волатильности рынка.

    Args:
        volatile_items: Список предметов с данными о волатильности

    Returns:
        Уровень волатильности: "low", "medium" или "high"

    """
    if not volatile_items:
        return "low"

    # Рассчитываем среднюю волатильность
    avg_volatility = sum(
        item.get("volatility_score", 0) for item in volatile_items
    ) / len(volatile_items)

    if avg_volatility < 10:
        return "low"
    if avg_volatility < 20:
        return "medium"
    return "high"


def _generate_market_recommendations(results: list[list[dict[str, Any]]]) -> list[str]:
    """Генерирует рекомендации на основе анализа рынка.

    Args:
        results: Список результатов различных анализов

    Returns:
        Список рекомендаций

    """
    price_changes = results[0]
    trending_items = results[1]
    volatile_items = results[2]

    recommendations = []

    # Проверяем наличие растущих предметов
    rising_items = [item for item in price_changes if item.get("direction") == "up"]
    if rising_items:
        recommendations.append(
            f"Рассмотрите возможность покупки предметов с быстрым ростом цены: "
            f"{', '.join([item['market_hash_name'] for item in rising_items[:3]])}",
        )

    # Проверяем наличие падающих предметов
    falling_items = [item for item in price_changes if item.get("direction") == "down"]
    if falling_items:
        recommendations.append(
            f"Избегайте покупки предметов с падающей ценой: "
            f"{', '.join([item['market_hash_name'] for item in falling_items[:3]])}",
        )

    # Рекомендации по трендовым предметам
    if trending_items:
        recommendations.append(
            f"Обратите внимание на популярные предметы с высоким спросом: "
            f"{', '.join([item['market_hash_name'] for item in trending_items[:3]])}",
        )

    # Рекомендации по волатильности
    if volatile_items:
        recommendations.append(
            f"Будьте осторожны с волатильными предметами, их цены нестабильны: "
            f"{', '.join([item['market_hash_name'] for item in volatile_items[:3]])}",
        )

    # Если нет данных, даем общую рекомендацию
    if not recommendations:
        recommendations.append(
            "Недостаточно данных для формирования конкретных рекомендаций. "
            "Следите за тенденциями рынка и проводите регулярный анализ.",
        )

    return recommendations
