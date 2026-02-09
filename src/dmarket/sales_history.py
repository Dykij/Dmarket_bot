"""Модуль для работы с историей продаж предметов на DMarket.

Позволяет получать исторические данные о продажах предметов,
анализировать тренды цен и выявлять аномалии в продажах.

Документация DMarket API: https://docs.dmarket.com/v1/swagger.html
"""

import json
import logging
import operator
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from src.dmarket.dmarket_api import DMarketAPI
from src.utils.rate_limiter import RateLimiter

# Загружаем переменные окружения
load_dotenv()

# Настройка логирования
logger = logging.getLogger(__name__)

# Export compatibility functions for tests
__all__ = [
    "SalesHistoryAnalyzer",
    "analyze_sales_history",
    "execute_api_request",
    "get_arbitrage_opportunities_with_sales_history",
    "get_sales_history",
]


class SalesHistoryAnalyzer:
    """Analyzer for sales history data to detect trends and liquidity."""

    def __init__(self, dmarket_api: DMarketAPI | None = None):
        """Initialize the sales history analyzer.

        Args:
            dmarket_api: DMarket API client instance
        """
        self.dmarket_api = dmarket_api

    async def analyze_item(
        self,
        item_name: str,
        game: str = "csgo",
        period: str = "7d",
    ) -> dict[str, Any]:
        """Analyze sales history for a single item.

        Args:
            item_name: Item name to analyze
            game: Game code (csgo, dota2, rust, tf2)
            period: Analysis period (1h, 12h, 24h, 7d, 30d)

        Returns:
            Dictionary with analysis results
        """
        return await analyze_sales_history(
            item_name=item_name,
            api_client=self.dmarket_api,
        )

    async def check_liquidity(
        self,
        item_name: str,
        min_sales_per_day: float = 1.0,
    ) -> bool:
        """Check if item has sufficient liquidity.

        Args:
            item_name: Item name to check
            min_sales_per_day: Minimum required sales per day

        Returns:
            True if item has sufficient liquidity
        """
        analysis = await self.analyze_item(item_name)

        if not analysis.get("has_data", False):
            return False

        sales_per_day = analysis.get("sales_per_day", 0.0)
        return sales_per_day >= min_sales_per_day

    async def get_price_trend(
        self,
        item_name: str,
        game: str = "csgo",
        period: str = "7d",
    ) -> str:
        """Get price trend for an item.

        Args:
            item_name: Item name
            game: Game code
            period: Analysis period

        Returns:
            Price trend: "up", "down", "stable", or "unknown"
        """
        trend_info = await calculate_price_trend(
            item_name=item_name,
            game=game,
            period=period,
            dmarket_api=self.dmarket_api,
        )

        return trend_info.get("trend", "unknown")


# Константы для методов истории продаж
SALES_HISTORY_TYPES = {
    "last_day": "24h",
    "last_week": "7d",
    "last_month": "30d",
    "last_hour": "1h",
    "last_12_hours": "12h",
}

# Каталог для кеширования истории продаж
SALES_CACHE_DIR = Path(__file__).parents[2] / "data" / "sales_history"
# Создаем директорию, если её нет
SALES_CACHE_DIR.mkdir(parents=True, exist_ok=True)

# Время жизни кеша (в секундах)
CACHE_TTL = {
    "1h": 15 * 60,  # 15 минут
    "12h": 30 * 60,  # 30 минут
    "24h": 60 * 60,  # 1 час
    "7d": 6 * 60 * 60,  # 6 часов
    "30d": 24 * 60 * 60,  # 24 часа
}

# Создаем ограничитель скорости запросов
rate_limiter = RateLimiter(is_authorized=True)

# Ключи API из переменных окружения
DMARKET_PUBLIC_KEY = os.getenv("DMARKET_PUBLIC_KEY", "")
DMARKET_SECRET_KEY = os.getenv("DMARKET_SECRET_KEY", "")
DMARKET_API_URL = os.getenv("DMARKET_API_URL", "https://api.dmarket.com")


async def get_item_sales_history(
    item_name: str,
    game: str = "csgo",
    period: str = "24h",
    use_cache: bool = True,
    dmarket_api: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Получает историю продаж предмета за указанный период.

    Args:
        item_name: Название предмета (market hash name)
        game: Код игры (csgo, dota2, rust, tf2)
        period: Период истории (1h, 12h, 24h, 7d, 30d)
        use_cache: Использовать ли кешированные данные
        dmarket_api: Экземпляр DMarketAPI или None для создания нового

    Returns:
        Список продаж, каждая продажа представлена словарем с ключами:
        - price: цена продажи в USD
        - timestamp: время продажи (unix timestamp)
        - market_hash_name: название предмета

    """
    # Проверяем валидность периода
    if period not in CACHE_TTL:
        period = "24h"

    # Пытаемся загрузить из кеша, если требуется
    if use_cache:
        cached_data = _load_from_cache(item_name, game, period)
        if cached_data:
            logger.info(f"Загружена история продаж {item_name} ({game}) из кеша")
            return cached_data

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
        logger.info(
            f"Получение истории продаж для {item_name} ({game}) за период {period}",
        )

        # Ожидаем, если нужно (ограничение API)
        await rate_limiter.wait_if_needed("market_history")

        # Получаем данные о продажах
        sales_data = await dmarket_api.get_item_price_history(
            title=item_name,
            game=game,
            period=period,
        )

        if not sales_data or not isinstance(sales_data, list):
            logger.warning(f"Не удалось получить историю продаж для {item_name}")
            return []

        # Форматируем результаты
        sales_history = []
        for sale in sales_data:
            # Проверяем наличие необходимых полей
            if "date" not in sale or "price" not in sale:
                continue

            # Добавляем запись о продаже
            sales_history.append(
                {
                    "price": float(sale["price"]) / 100,  # Цены хранятся в центах
                    "timestamp": sale["date"],
                    "market_hash_name": item_name,
                },
            )

        # Сортируем по времени (от новых к старым)
        sales_history.sort(key=operator.itemgetter("timestamp"), reverse=True)

        # Сохраняем в кеш
        if use_cache:
            _save_to_cache(item_name, game, period, sales_history)

        return sales_history

    except Exception as e:
        logger.exception(f"Ошибка при получении истории продаж: {e}")
        return []
    finally:
        if close_client and hasattr(dmarket_api, "_close_client"):
            try:
                await dmarket_api._close_client()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии клиента API: {e}")


async def detect_price_anomalies(
    item_name: str,
    game: str = "csgo",
    period: str = "7d",
    threshold_percent: float = 20.0,
    dmarket_api: DMarketAPI | None = None,
) -> dict[str, Any]:
    """Выявляет аномалии в ценах продаж предмета.

    Args:
        item_name: Название предмета (market hash name)
        game: Код игры (csgo, dota2, rust, tf2)
        period: Период анализа (1h, 12h, 24h, 7d, 30d)
        threshold_percent: Пороговый процент отклонения для аномалии
        dmarket_api: Экземпляр DMarketAPI или None для создания нового

    Returns:
        Словарь с результатами анализа:
        - anomalies: список аномальных продаж
        - average_price: средняя цена за период
        - median_price: медианная цена за период
        - min_price: минимальная цена за период
        - max_price: максимальная цена за период
        - num_sales: количество продаж за период

    """
    # Получаем историю продаж
    sales_history = await get_item_sales_history(
        item_name=item_name,
        game=game,
        period=period,
        dmarket_api=dmarket_api,
    )

    if not sales_history:
        return {
            "anomalies": [],
            "average_price": 0,
            "median_price": 0,
            "min_price": 0,
            "max_price": 0,
            "num_sales": 0,
        }

    # Получаем цены
    prices = [sale["price"] for sale in sales_history]

    # Рассчитываем статистику
    avg_price = sum(prices) / len(prices)
    median_price = _calculate_median(prices)
    min_price = min(prices)
    max_price = max(prices)

    # Выявляем аномалии
    anomalies = []

    for sale in sales_history:
        price = sale["price"]

        # Рассчитываем отклонение от медианы
        deviation_percent = abs((price - median_price) / median_price * 100)

        # Если отклонение превышает порог, считаем продажу аномальной
        if deviation_percent >= threshold_percent:
            # Добавляем информацию об аномалии
            anomaly = sale.copy()
            anomaly["deviation_percent"] = deviation_percent
            anomaly["is_high"] = price > median_price
            anomaly["date"] = datetime.fromtimestamp(sale["timestamp"]).strftime(
                "%Y-%m-%d %H:%M:%S",
            )

            anomalies.append(anomaly)

    # Сортируем аномалии по размеру отклонения (по убыванию)
    anomalies.sort(key=operator.itemgetter("deviation_percent"), reverse=True)

    return {
        "anomalies": anomalies,
        "average_price": avg_price,
        "median_price": median_price,
        "min_price": min_price,
        "max_price": max_price,
        "num_sales": len(sales_history),
    }


async def calculate_price_trend(
    item_name: str,
    game: str = "csgo",
    period: str = "7d",
    dmarket_api: DMarketAPI | None = None,
) -> dict[str, Any]:
    """Рассчитывает тренд цены предмета за указанный период.

    Args:
        item_name: Название предмета (market hash name)
        game: Код игры (csgo, dota2, rust, tf2)
        period: Период анализа (1h, 12h, 24h, 7d, 30d)
        dmarket_api: Экземпляр DMarketAPI или None для создания нового

    Returns:
        Словарь с информацией о тренде:
        - trend: направление тренда ("up", "down", "stable")
        - change_percent: процент изменения цены
        - start_price: цена в начале периода
        - end_price: цена в конце периода
        - volatility: волатильность цены (стандартное отклонение)

    """
    # Получаем историю продаж
    sales_history = await get_item_sales_history(
        item_name=item_name,
        game=game,
        period=period,
        dmarket_api=dmarket_api,
    )

    if not sales_history or len(sales_history) < 2:
        return {
            "trend": "unknown",
            "change_percent": 0,
            "start_price": 0,
            "end_price": 0,
            "volatility": 0,
        }

    # Сортируем по времени (от старых к новым)
    sales_history.sort(key=operator.itemgetter("timestamp"))

    # Получаем цены в начале и конце периода
    start_price = sales_history[0]["price"]
    end_price = sales_history[-1]["price"]

    # Рассчитываем изменение цены
    price_change = end_price - start_price
    change_percent = (price_change / start_price) * 100 if start_price > 0 else 0

    # Определяем направление тренда
    trend = "stable" if abs(change_percent) < 5 else "up" if change_percent > 0 else "down"

    # Рассчитываем волатильность (стандартное отклонение цен)
    prices = [sale["price"] for sale in sales_history]
    volatility = _calculate_std_dev(prices)

    return {
        "trend": trend,
        "change_percent": change_percent,
        "start_price": start_price,
        "end_price": end_price,
        "volatility": volatility,
        "num_sales": len(sales_history),
        "period": period,
    }


async def get_market_trend_overview(
    game: str = "csgo",
    item_count: int = 50,
    min_price: float = 1.0,
    max_price: float = 500.0,
    period: str = "7d",
    dmarket_api: DMarketAPI | None = None,
) -> dict[str, Any]:
    """Получает обзор трендов рынка для наиболее популярных предметов.

    Args:
        game: Код игры (csgo, dota2, rust, tf2)
        item_count: Количество анализируемых предметов
        min_price: Минимальная цена предмета (USD)
        max_price: Максимальная цена предмета (USD)
        period: Период анализа (1h, 12h, 24h, 7d, 30d)
        dmarket_api: Экземпляр DMarketAPI или None для создания нового

    Returns:
        Словарь с обзором трендов рынка:
        - market_trend: общий тренд рынка ("up", "down", "stable")
        - avg_change_percent: средний процент изменения цен
        - up_trending_items: список предметов с растущим трендом
        - down_trending_items: список предметов с падающим трендом
        - stable_items: список предметов со стабильным трендом

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
        logger.info(f"Получение обзора трендов рынка для {game} за период {period}")

        # Получаем популярные предметы
        await rate_limiter.wait_if_needed("market")

        popular_items = await dmarket_api.get_market_items(
            game=game,
            limit=item_count,
            min_price=min_price * 100,  # в центах
            max_price=max_price * 100,  # в центах
            sort_by="popularity",
        )

        if not popular_items or "items" not in popular_items:
            logger.warning(f"Не удалось получить популярные предметы для {game}")
            return {
                "market_trend": "unknown",
                "avg_change_percent": 0,
                "up_trending_items": [],
                "down_trending_items": [],
                "stable_items": [],
            }

        # Анализируем тренды для каждого предмета
        up_trending = []
        down_trending = []
        stable_items = []
        all_changes = []

        for item in popular_items.get("items", []):
            market_hash_name = item.get("title", "")
            if not market_hash_name:
                continue

            # Получаем тренд для предмета
            trend_info = await calculate_price_trend(
                item_name=market_hash_name,
                game=game,
                period=period,
                dmarket_api=dmarket_api,
            )

            # Дополняем информацию о предмете
            trend_info["market_hash_name"] = market_hash_name
            trend_info["image_url"] = item.get("imageUrl", "")
            trend_info["current_price"] = _extract_price_from_item(item)

            # Распределяем по категориям
            all_changes.append(trend_info["change_percent"])

            if trend_info["trend"] == "up":
                up_trending.append(trend_info)
            elif trend_info["trend"] == "down":
                down_trending.append(trend_info)
            else:
                stable_items.append(trend_info)

        # Сортируем списки по проценту изменения
        up_trending.sort(key=operator.itemgetter("change_percent"), reverse=True)
        down_trending.sort(key=operator.itemgetter("change_percent"))

        # Определяем общий тренд рынка
        avg_change = sum(all_changes) / len(all_changes) if all_changes else 0

        market_trend = "stable" if abs(avg_change) < 3 else "up" if avg_change > 0 else "down"

        return {
            "market_trend": market_trend,
            "avg_change_percent": avg_change,
            "up_trending_items": up_trending[:10],  # Топ-10 растущих
            "down_trending_items": down_trending[:10],  # Топ-10 падающих
            "stable_items": stable_items[:10],  # Топ-10 стабильных
            "timestamp": int(time.time()),
            "game": game,
            "period": period,
        }

    except Exception as e:
        logger.exception(f"Ошибка при получении обзора трендов рынка: {e}")
        return {
            "market_trend": "unknown",
            "avg_change_percent": 0,
            "up_trending_items": [],
            "down_trending_items": [],
            "stable_items": [],
        }
    finally:
        if close_client and hasattr(dmarket_api, "_close_client"):
            try:
                await dmarket_api._close_client()
            except Exception as e:
                logger.warning(f"Ошибка при закрытии клиента API: {e}")


def _extract_price_from_item(item: dict[str, Any]) -> float:
    """Извлекает цену из информации о предмете."""
    try:
        # Сначала проверяем поле salesPrice, которое соответствует последней реальной цене продажи
        if item.get("salesPrice"):
            return float(item["salesPrice"]) / 100

        # Если нет, смотрим на минимальную цену предложения (наибольшее значение)
        if item.get("price"):
            return float(item["price"]["USD"]) / 100

        return 0
    except (KeyError, ValueError, TypeError):
        return 0


def _calculate_median(numbers: list[float]) -> float:
    """Рассчитывает медиану списка чисел."""
    if not numbers:
        return 0

    sorted_numbers = sorted(numbers)
    n = len(sorted_numbers)

    if n % 2 == 0:
        # Если четное количество элементов, берем среднее двух средних
        return (sorted_numbers[n // 2 - 1] + sorted_numbers[n // 2]) / 2
    # Если нечетное, берем средний элемент
    return sorted_numbers[n // 2]


def _calculate_std_dev(numbers: list[float]) -> float:
    """Рассчитывает стандартное отклонение списка чисел."""
    if not numbers or len(numbers) < 2:
        return 0

    # Среднее значение
    mean = sum(numbers) / len(numbers)

    # Сумма квадратов отклонений
    sum_of_squares = sum((x - mean) ** 2 for x in numbers)

    # Стандартное отклонение
    return (sum_of_squares / (len(numbers) - 1)) ** 0.5


def _get_cache_file_path(item_name: str, game: str, period: str) -> Path:
    """Возвращает путь к файлу кеша для истории продаж."""
    # Безопасное имя файла без спецсимволов
    safe_name = "".join(c if c.isalnum() else "_" for c in item_name)
    return SALES_CACHE_DIR / f"{game}_{safe_name}_{period}.json"


def _load_from_cache(item_name: str, game: str, period: str) -> list[dict[str, Any]]:
    """Загружает историю продаж из кеша, если она не устарела."""
    cache_file = _get_cache_file_path(item_name, game, period)

    try:
        # Проверяем существование файла
        if not cache_file.exists():
            return []

        # Проверяем время изменения файла
        file_age = time.time() - cache_file.stat().st_mtime
        if file_age > CACHE_TTL.get(period, 3600):
            # Кеш устарел
            return []

        # Загружаем данные из файла
        with open(cache_file, encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        logger.warning(f"Ошибка при загрузке кеша истории продаж: {e}")
        return []


def _save_to_cache(
    item_name: str,
    game: str,
    period: str,
    data: list[dict[str, Any]],
) -> None:
    """Сохраняет историю продаж в кеш."""
    cache_file = _get_cache_file_path(item_name, game, period)

    try:
        # Создаем директорию, если её нет
        cache_file.parent.mkdir(parents=True, exist_ok=True)

        # Сохраняем данные в файл
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    except Exception as e:
        logger.warning(f"Ошибка при сохранении кеша истории продаж: {e}")


# Функции для совместимости с тестами
async def get_sales_history(
    items: list[str],
    api_client: DMarketAPI | None = None,
) -> dict[str, Any]:
    """Get sales history for multiple items (for test compatibility).

    Args:
        items: List of item names
        api_client: DMarket API client instance

    Returns:
        Dictionary with LastSales and Total keys
    """
    if not items:
        return {"LastSales": [], "Total": 0}

    try:
        all_sales = []
        batch_size = 50

        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]

            if api_client:
                # Use provided API client
                response = await api_client.request(
                    method="GET",
                    endpoint="/market-api/v1/last-sales",
                    params={"Titles": batch},
                )
            else:
                # Create new API client
                async with DMarketAPI(
                    public_key=DMARKET_PUBLIC_KEY,
                    secret_key=DMARKET_SECRET_KEY,
                    api_url=DMARKET_API_URL,
                ) as api:
                    response = await api.request(
                        method="GET",
                        endpoint="/market-api/v1/last-sales",
                        params={"Titles": batch},
                    )

            if "Error" in response:
                # Return error from API response
                return {"Error": response["Error"], "LastSales": [], "Total": 0}

            if "LastSales" in response:
                all_sales.extend(response["LastSales"])

        return {"LastSales": all_sales, "Total": len(all_sales)}

    except Exception as e:
        logger.exception(f"Error getting sales history: {e}")
        return {"Error": str(e), "LastSales": [], "Total": 0}


async def analyze_sales_history(
    item_name: str,
    days: int | None = None,
    api_client: DMarketAPI | None = None,
) -> dict[str, Any]:
    """Analyze sales history for an item (for test compatibility).

    Args:
        item_name: Item name to analyze
        days: Number of days to analyze (default: 7)
        api_client: DMarket API client instance

    Returns:
        Dictionary with analysis results including:
        - item_name: Name of the item
        - has_data: Whether sales data is available
        - total_sales: Total number of sales
        - recent_sales: List of recent sales
        - average_price: Average sale price
        - sales_per_day: Average sales per day
        - price_trend: Price trend (up/down/stable)
    """
    if days is None:
        days = 7

    try:
        sales_data = await get_sales_history([item_name], api_client=api_client)

        if "Error" in sales_data:
            return {
                "item_name": item_name,
                "has_data": False,
                "total_sales": 0,
                "recent_sales": [],
                "sales_per_day": 0.0,
                "price_trend": "unknown",
                "error": sales_data["Error"],
            }

        last_sales = sales_data.get("LastSales", [])

        # Calculate sales per day
        sales_per_day = len(last_sales) / days if days > 0 else 0

        # Determine price trend
        price_trend = "stable"
        if len(last_sales) >= 2:
            # Sort by date (oldest first)
            sorted_sales = sorted(last_sales, key=lambda x: x.get("date", 0))
            first_price = sorted_sales[0].get("price", {}).get("USD", 0)
            last_price = sorted_sales[-1].get("price", {}).get("USD", 0)

            if first_price > 0:
                change_percent = ((last_price - first_price) / first_price) * 100
                if change_percent > 5:
                    price_trend = "up"
                elif change_percent < -5:
                    price_trend = "down"

        return {
            "item_name": item_name,
            "has_data": len(last_sales) > 0,
            "total_sales": len(last_sales),
            "recent_sales": last_sales[:10],
            "average_price": (
                sum(s.get("price", {}).get("USD", 0) for s in last_sales) / len(last_sales)
                if last_sales
                else 0
            ),
            "sales_per_day": sales_per_day,
            "price_trend": price_trend,
        }

    except Exception as e:
        logger.exception(f"Error analyzing sales history: {e}")
        return {
            "item_name": item_name,
            "has_data": False,
            "total_sales": 0,
            "recent_sales": [],
            "sales_per_day": 0.0,
            "price_trend": "unknown",
            "error": str(e),
        }


async def execute_api_request(
    endpoint: str,
    params: dict[str, Any] | None = None,
    api_client: DMarketAPI | None = None,
) -> dict[str, Any]:
    """Execute API request (for test compatibility).

    Args:
        endpoint: API endpoint
        params: Request parameters
        api_client: DMarket API client instance

    Returns:
        API response
    """
    try:
        if api_client:
            return await api_client.request(
                method="GET",
                endpoint=endpoint,
                params=params or {},
            )
        async with DMarketAPI(
            public_key=DMARKET_PUBLIC_KEY,
            secret_key=DMARKET_SECRET_KEY,
            api_url=DMARKET_API_URL,
        ) as api:
            return await api.request(
                method="GET",
                endpoint=endpoint,
                params=params or {},
            )
    except Exception as e:
        logger.exception(f"Error executing API request: {e}")
        return {"Error": str(e)}


async def get_arbitrage_opportunities_with_sales_history(
    min_sales_per_day: float = 1.0,
    price_trend_filter: str | None = None,
    api_client: DMarketAPI | None = None,
) -> list[dict[str, Any]]:
    """Get arbitrage opportunities filtered by sales history.

    Args:
        min_sales_per_day: Minimum sales volume per day
        price_trend_filter: Filter by price trend (up/down/stable)
        api_client: DMarket API client instance

    Returns:
        List of filtered arbitrage opportunities
    """
    from src.dmarket.arbitrage import find_arbitrage_items

    try:
        # Get arbitrage items
        arbitrage_items = await find_arbitrage_items(api_client=api_client)

        # Filter by sales history
        filtered_items = []
        for item in arbitrage_items:
            item_name = item.get("market_hash_name", "")
            analysis = await analyze_sales_history(
                item_name,
                api_client=api_client,
            )

            # Check if has data and meets criteria
            if not analysis.get("has_data", False):
                continue

            sales_per_day = analysis.get("sales_per_day", 0)
            price_trend = analysis.get("price_trend", "")

            # Apply filters
            if sales_per_day < min_sales_per_day:
                continue

            if price_trend_filter and price_trend != price_trend_filter:
                continue

            # Add analysis data to item
            item["sales_analysis"] = analysis
            filtered_items.append(item)

        return filtered_items

    except Exception as e:
        logger.exception(f"Error getting arbitrage opportunities: {e}")
        return []
