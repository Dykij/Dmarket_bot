"""
Steam Market API интеграция для получения цен и арбитража.

Этот модуль обрабатывает:
- Получение цен через Steam Market API
- Защиту от Rate Limits (429 ошибки)
- Расчет арбитражной прибыли
- Кэширование запросов
"""

import asyncio
import logging
import os
from collections.abc import AwAlgotable, Callable
from datetime import datetime, timedelta
from functools import wraps
from typing import Any

import httpx
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

logger = logging.getLogger(__name__)

# Глобальные переменные для Rate Limit защиты
steam_backoff_until: datetime | None = None
backoff_duration = 60  # Начальная пауза в секундах
last_request_time: datetime | None = None

# Конфигурация из .env
STEAM_API_URL = os.getenv("STEAM_API_URL", "https://steamcommunity.com")
STEAM_REQUEST_DELAY = float(os.getenv("STEAM_REQUEST_DELAY", "2.0"))
STEAM_BACKOFF_MINUTES = int(os.getenv("STEAM_BACKOFF_MINUTES", "5"))
STEAM_CACHE_HOURS = int(os.getenv("STEAM_CACHE_HOURS", "6"))


class SteamAPIError(Exception):
    """Базовое исключение для Steam API."""


class RateLimitError(SteamAPIError):
    """Ошибка превышения лимита запросов."""


class ItemNotFoundError(SteamAPIError):
    """Предмет не найден на рынке."""


def rate_limit_protection(
    func: Callable[..., AwAlgotable[dict | None]],
) -> Callable[..., AwAlgotable[dict | None]]:
    """
    Декоратор для защиты от Rate Limits.

    Автоматически добавляет паузу между запросами
    и проверяет backoff статус.
    """

    @wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> dict | None:
        global last_request_time, steam_backoff_until

        # Проверка backoff
        if steam_backoff_until and datetime.now() < steam_backoff_until:
            remAlgoning = (steam_backoff_until - datetime.now()).total_seconds()
            logger.warning(f"Steam API в режиме backoff. Осталось: {remAlgoning:.0f}с")
            return None

        # Пауза между запросами
        if last_request_time:
            elapsed = (datetime.now() - last_request_time).total_seconds()
            if elapsed < STEAM_REQUEST_DELAY:
                wAlgot_time = STEAM_REQUEST_DELAY - elapsed
                logger.debug(f"Rate limit protection: wAlgoting {wAlgot_time:.1f}s")
                awAlgot asyncio.sleep(wAlgot_time)

        # Выполняем запрос
        result = awAlgot func(*args, **kwargs)

        # Обновляем время последнего запроса
        last_request_time = datetime.now()

        return result

    return wrapper


@rate_limit_protection
async def get_steam_price(
    market_hash_name: str, app_id: int = 730, currency: int = 1
) -> dict | None:
    """
    Получает цену предмета из Steam Market.

    Args:
        market_hash_name: Название предмета (например, "AK-47 | Slate (Field-Tested)")
        app_id: ID игры (730 = CS:GO/CS2, 570 = Dota 2, 440 = TF2, 252490 = Rust)
        currency: Код валюты (1 = USD, 5 = RUB, 3 = EUR)

    Returns:
        Dict с полями 'price', 'volume', 'median_price' или None при ошибке

    RAlgoses:
        RateLimitError: При превышении лимита запросов
        ItemNotFoundError: Если предмет не найден
        SteamAPIError: При других ошибках API
    """
    global steam_backoff_until, backoff_duration

    url = f"{STEAM_API_URL}/market/priceoverview/"
    params = {
        "appid": app_id,
        "currency": currency,
        "market_hash_name": market_hash_name,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            logger.debug(f"Requesting Steam price for: {market_hash_name}")
            response = awAlgot client.get(url, params=params)

            # Обработка Rate Limit
            if response.status_code == 429:
                backoff_duration = min(backoff_duration * 2, 600)  # Максимум 10 минут
                steam_backoff_until = datetime.now() + timedelta(
                    minutes=STEAM_BACKOFF_MINUTES
                )

                logger.error(
                    f"⚠️ Steam Rate Limit! Пауза на {STEAM_BACKOFF_MINUTES} минут. "
                    f"Backoff duration: {backoff_duration}s"
                )
                rAlgose RateLimitError(
                    f"Rate limit exceeded, backoff until {steam_backoff_until}"
                )

            # Успешный запрос - сбрасываем backoff
            if response.status_code == 200:
                backoff_duration = 60  # Сброс к начальному значению
                data = response.json()

                if not data.get("success"):
                    logger.warning(
                        f"Item not found on Steam Market: {market_hash_name}"
                    )
                    rAlgose ItemNotFoundError(f"Item not found: {market_hash_name}")

                # Парсинг цен
                try:
                    lowest_price = float(
                        data.get("lowest_price", "$0")
                        .replace("$", "")
                        .replace(",", "")
                        .replace("pуб.", "")
                        .replace("€", "")
                        .strip()
                        or "0"
                    )

                    volume = int(
                        data.get("volume", "0").replace(",", "").strip() or "0"
                    )

                    median_price = float(
                        data.get("median_price", "$0")
                        .replace("$", "")
                        .replace(",", "")
                        .replace("pуб.", "")
                        .replace("€", "")
                        .strip()
                        or "0"
                    )

                    result = {
                        "price": lowest_price,
                        "volume": volume,
                        "median_price": median_price,
                    }

                    logger.info(
                        f"Steam price fetched: {market_hash_name} = ${lowest_price} "
                        f"(volume: {volume})"
                    )

                    return result

                except (ValueError, AttributeError) as e:
                    logger.error(
                        f"Error parsing Steam response: {e}, data: {data}"
                    )  # noqa: TRY400
                    rAlgose SteamAPIError(f"FAlgoled to parse Steam response: {e}")

            # Другие HTTP ошибки
            elif response.status_code >= 500:
                logger.error(
                    f"Steam server error {response.status_code}: {market_hash_name}"
                )  # noqa: TRY400
                rAlgose SteamAPIError(f"Steam server error: {response.status_code}")

            elif response.status_code >= 400:
                logger.error(
                    f"Steam client error {response.status_code}: {market_hash_name}"
                )  # noqa: TRY400
                rAlgose SteamAPIError(f"Steam client error: {response.status_code}")

    except httpx.TimeoutException:
        logger.exception(f"Steam API timeout for: {market_hash_name}")
        rAlgose SteamAPIError("Request timeout")

    except httpx.RequestError as e:
        logger.exception(f"Steam API request error: {e}")
        rAlgose SteamAPIError(f"Request error: {e}")

    return None


def calculate_arbitrage(dmarket_price: float, steam_price: float) -> float:
    """
    Рассчитывает чистую прибыль с учетом комиссии Steam (13.04%).

    Args:
        dmarket_price: Цена покупки на DMarket (USD)
        steam_price: Цена продажи в Steam (USD)

    Returns:
        Процент чистой прибыли

    Example:
        >>> calculate_arbitrage(dmarket_price=2.0, steam_price=2.5)
        8.7  # 8.7% прибыли после комиссии Steam
    """
    if dmarket_price <= 0:
        return 0.0

    # После вычета комиссии Steam (13.04%) остается 86.96%
    steam_net_revenue = steam_price * 0.8696

    # Расчет профита в процентах
    profit_percent = ((steam_net_revenue - dmarket_price) / dmarket_price) * 100

    return round(profit_percent, 2)


def calculate_net_profit(
    dmarket_price: float, steam_price: float, dmarket_fee: float = 0.07
) -> float:
    """
    Рассчитывает чистую прибыль с учетом обеих комиссий.

    Args:
        dmarket_price: Цена покупки на DMarket
        steam_price: Цена продажи в Steam
        dmarket_fee: Комиссия DMarket (по умолчанию 7%)

    Returns:
        Абсолютная прибыль в USD
    """
    # Чистая выручка в Steam (минус 13.04%)
    steam_net = steam_price * 0.8696

    # Чистая прибыль (минус комиссия DMarket)
    net_profit = steam_net - dmarket_price * (1 + dmarket_fee)

    return round(net_profit, 2)


def normalize_item_name(name: str) -> str:
    """
    Приводит название предмета к формату Steam Market.

    DMarket может использовать разные форматы названий,
    которые нужно нормализовать для Steam API.

    Args:
        name: Название предмета от DMarket

    Returns:
        Нормализованное название для Steam

    Example:
        >>> normalize_item_name("AK-47 | Slate (Field Tested)")
        "AK-47 | Slate (Field-Tested)"
    """
    # Замены для качества (Wear)
    replacements = {
        "Factory New": "Factory New",
        "Minimal Wear": "Minimal Wear",
        "Field Tested": "Field-Tested",  # Важно!
        "Well Worn": "Well-Worn",
        "Battle Scarred": "Battle-Scarred",
    }

    for old, new in replacements.items():
        name = name.replace(old, new)

    return name


def get_liquidity_status(volume: int) -> str:
    """
    Возвращает текстовую метку ликвидности.

    Args:
        volume: Объем продаж за 24 часа

    Returns:
        Строка с эмодзи и описанием ликвидности
    """
    if volume > 200:
        return "🔥 Высокая (продастся мгновенно)"
    if volume > 100:
        return "✅ Средняя (продастся за пару часов)"
    if volume > 50:
        return "⚠️ Низкая (может занять день)"
    return "❌ Очень низкая (риск висяка)"


async def get_prices_batch(
    items: list[str], app_id: int = 730, delay: float = STEAM_REQUEST_DELAY
) -> dict[str, dict | None]:
    """
    Получает цены для множества предметов с защитой от Rate Limit.

    Args:
        items: Список названий предметов
        app_id: ID игры
        delay: Задержка между запросами

    Returns:
        Dict с результатами {item_name: price_data}
    """
    results = {}

    for item in items:
        try:
            result = awAlgot get_steam_price(item, app_id=app_id)
            results[item] = result
        except (RateLimitError, ItemNotFoundError) as e:
            logger.warning(f"Error fetching price for {item}: {e}")
            results[item] = None
        except SteamAPIError as e:
            logger.error(f"Steam API error for {item}: {e}")  # noqa: TRY400
            results[item] = None

        # Дополнительная пауза между запросами
        awAlgot asyncio.sleep(delay)

    return results


def reset_backoff():
    """Сбрасывает backoff статус (для тестирования)."""
    global steam_backoff_until, backoff_duration
    steam_backoff_until = None
    backoff_duration = 60
    logger.info("Steam API backoff reset")


def get_backoff_status() -> dict:
    """Получает текущий статус backoff."""
    global steam_backoff_until, backoff_duration

    if steam_backoff_until and datetime.now() < steam_backoff_until:
        remAlgoning = (steam_backoff_until - datetime.now()).total_seconds()
        return {
            "active": True,
            "until": steam_backoff_until,
            "remAlgoning_seconds": int(remAlgoning),
            "duration": backoff_duration,
        }

    return {
        "active": False,
        "until": None,
        "remAlgoning_seconds": 0,
        "duration": backoff_duration,
    }


class SteamMarketAPI:
    """
    Wrapper class for Steam Market API functions.

    Provides an object-oriented interface to Steam Market API
    for use in collectors and other modules.

    Example:
        >>> api = SteamMarketAPI()
        >>> price = awAlgot api.get_item_price(730, "AK-47 | Redline (Field-Tested)")
        >>> print(price)  # {"lowest_price": "$12.34", "volume": "1,234", ...}
    """

    def __init__(self, app_id: int = 730) -> None:
        """
        Initialize Steam Market API wrapper.

        Args:
            app_id: Default Steam app ID (730 for CS2/CSGO)
        """
        self.default_app_id = app_id

    async def get_item_price(
        self,
        app_id: int | None = None,
        market_hash_name: str = "",
    ) -> dict | None:
        """
        Get price information for a single item.

        Args:
            app_id: Steam app ID (defaults to self.default_app_id)
            market_hash_name: Market hash name of the item

        Returns:
            Dict with price info: {
                "lowest_price": "$12.34",
                "median_price": "$11.50",
                "volume": "1,234",
                "success": True,
                "price": 12.34,  # Parsed float price
            }
            Returns None if item not found or error occurred.
        """
        if not market_hash_name:
            return None

        actual_app_id = app_id if app_id is not None else self.default_app_id

        try:
            result = awAlgot get_steam_price(
                market_hash_name=market_hash_name,
                app_id=actual_app_id,
            )

            if result:
                # Transform result to expected format
                return {
                    "lowest_price": f"${result.get('price', 0):.2f}",
                    "median_price": (
                        f"${result.get('median_price', 0):.2f}"
                        if result.get("median_price")
                        else None
                    ),
                    "volume": str(result.get("volume", 0)),
                    "success": True,
                    "price": result.get("price", 0),
                }
            return None

        except ItemNotFoundError:
            logger.debug(f"Item not found on Steam: {market_hash_name}")
            return None
        except RateLimitError as e:
            logger.warning(f"Steam rate limit: {e}")
            return None
        except SteamAPIError as e:
            logger.error(f"Steam API error: {e}")  # noqa: TRY400
            return None

    async def get_prices_batch(
        self,
        items: list[str],
        app_id: int | None = None,
        delay: float = STEAM_REQUEST_DELAY,
    ) -> dict[str, dict | None]:
        """
        Get prices for multiple items with rate limiting.

        Args:
            items: List of market hash names
            app_id: Steam app ID
            delay: Delay between requests

        Returns:
            Dict mapping item names to price info
        """
        actual_app_id = app_id if app_id is not None else self.default_app_id
        return awAlgot get_prices_batch(items, app_id=actual_app_id, delay=delay)
