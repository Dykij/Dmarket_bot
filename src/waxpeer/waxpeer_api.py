"""
Waxpeer API Client.

Асинхронный клиент для работы с Waxpeer P2P API.
Поддерживает листинг, репрайсинг и управление продажами CS2 скинов.

API Documentation: https://docs.waxpeer.com/
Цены в API указаны в милах (mils): 1 USD = 1000 mils

Пример использования:
    ```python
    async with WaxpeerAPI(api_key="your_key") as api:
        balance = await api.get_balance()
        print(f"Баланс: ${balance.wallet}")

        # Получить цены для арбитража
        prices = await api.get_items_list(["AK-47 | Redline (Field-Tested)"])

        # Выставить предмет на продажу
        await api.list_single_item("12345", price_usd=10.50)
    ```
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

# Константы API
MILS_PER_USD = 1000  # 1 USD = 1000 mils
WAXPEER_COMMISSION = Decimal("0.06")  # 6% комиссия на продажу


class WaxpeerGame(StrEnum):
    """Поддерживаемые игры на Waxpeer."""

    CS2 = "cs2"
    CSGO = "csgo"  # Legacy support
    DOTA2 = "dota2"
    TF2 = "tf2"
    RUST = "rust"


class ListingStatus(StrEnum):
    """Статусы листинга на Waxpeer."""

    ACTIVE = "active"
    SOLD = "sold"
    CANCELLED = "cancelled"
    PENDING = "pending"


@dataclass
class WaxpeerItem:
    """Представление предмета на Waxpeer."""

    item_id: str
    name: str
    price: Decimal  # В долларах
    price_mils: int  # В милах (1 доллар = 1000 мил)
    game: WaxpeerGame
    steam_price: Decimal | None = None
    float_value: float | None = None
    status: ListingStatus = ListingStatus.PENDING
    listed_at: datetime | None = None
    count: int = 0  # Количество в продаже (ликвидность)


@dataclass
class WaxpeerBalance:
    """Баланс пользователя на Waxpeer."""

    wallet: Decimal  # В долларах
    wallet_mils: int  # В милах
    available_for_withdrawal: Decimal
    pending: Decimal = Decimal(0)
    can_trade: bool = False


@dataclass
class WaxpeerPriceInfo:
    """Информация о цене предмета на Waxpeer."""

    name: str
    price_mils: int  # Минимальная цена в милах
    price_usd: Decimal  # Минимальная цена в USD
    count: int  # Количество в продаже (ликвидность)
    steam_price_mils: int | None = None
    avg_price_mils: int | None = None

    @property
    def is_liquid(self) -> bool:
        """Предмет считается ликвидным если в продаже >= 5 штук."""
        return self.count >= 5


class WaxpeerAPIError(Exception):
    """Базовое исключение для ошибок Waxpeer API."""

    def __init__(self, message: str, error_code: str | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code


class WaxpeerRateLimitError(WaxpeerAPIError):
    """Превышен лимит запросов к API."""


class WaxpeerAuthError(WaxpeerAPIError):
    """Ошибка аутентификации API."""


class WaxpeerAPI:  # noqa: PLR0904
    """
    Асинхронный клиент для Waxpeer API.

    Поддерживает:
    - Получение баланса и статуса пользователя
    - Листинг предметов на продажу
    - Автоматический репрайсинг
    - Снятие предметов с продажи
    - Получение истории продаж

    Rate Limits (согласно документации Waxpeer):
    - GET запросы: 60 в минуту
    - POST запросы: 30 в минуту
    - Специальные эндпоинты (list-items-steam): 10 в минуту

    Пример использования:
        ```python
        async with WaxpeerAPI(api_key="your_key") as api:
            balance = await api.get_balance()
            print(f"Баланс: ${balance.wallet}")
        ```
    """

    BASE_URL = "https://api.waxpeer.com/v1"

    # Rate limits per minute (from Waxpeer documentation)
    RATE_LIMITS = {
        "default_get": 60,      # GET requests per minute
        "default_post": 30,     # POST requests per minute
        "list_items": 10,       # List items per minute (expensive operation)
        "prices": 30,           # Price queries per minute
    }

    def __init__(
        self,
        api_key: str,
        timeout: float = 10.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        respect_rate_limits: bool = True,
    ) -> None:
        """
        Инициализация клиента.

        Args:
            api_key: API ключ от Waxpeer
            timeout: Таймаут запросов в секундах
            max_retries: Максимальное количество повторных попыток
            retry_delay: Задержка между повторными попытками
            respect_rate_limits: Автоматически соблюдать rate limits
        """
        self.api_key = api_key
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.respect_rate_limits = respect_rate_limits
        self._client: httpx.AsyncClient | None = None

        # Request tracking for rate limiting
        self._request_timestamps: dict[str, list[float]] = {
            "get": [],
            "post": [],
            "list_items": [],
        }
        self._rate_limit_lock = asyncio.Lock()

    async def __aenter__(self) -> "WaxpeerAPI":
        """Создание HTTP клиента при входе в контекст."""
        self._client = httpx.AsyncClient(
            timeout=self.timeout,
            headers={"Accept": "application/json", "api-key": self.api_key},
        )
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Закрытие HTTP клиента при выходе из контекста."""
        if self._client:
            await self._client.aclose()
            self._client = None

    @property
    def client(self) -> httpx.AsyncClient:
        """Получение HTTP клиента."""
        if self._client is None:
            raise RuntimeError(
                "WaxpeerAPI must be used as async context manager: "
                "async with WaxpeerAPI(...) as api:"
            )
        return self._client

    async def _request(
        self,
        method: str,
        endpoint: str,
        params: dict[str, Any] | None = None,
        json_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Выполнение запроса к API с обработкой ошибок и повторами.

        Args:
            method: HTTP метод (GET, POST, etc.)
            endpoint: Эндпоинт API (без базового URL)
            params: Query параметры
            json_data: JSON тело запроса

        Returns:
            Ответ API в виде словаря

        Raises:
            WaxpeerAPIError: При ошибке API
            WaxpeerRateLimitError: При превышении лимита запросов
            WaxpeerAuthError: При ошибке аутентификации
        """
        url = f"{self.BASE_URL}/{endpoint}"

        # Добавляем API ключ в параметры
        if params is None:
            params = {}
        params["api"] = self.api_key

        last_error: Exception | None = None

        for attempt in range(self.max_retries):
            try:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json_data,
                )

                # Проверка статуса
                if response.status_code == 429:
                    raise WaxpeerRateLimitError("Rate limit exceeded")

                if response.status_code == 401:
                    raise WaxpeerAuthError("Invalid API key")

                if response.status_code == 403:
                    raise WaxpeerAuthError("Access denied")

                response.raise_for_status()
                data = response.json()

                # Проверка успешности ответа
                if not data.get("success", True):
                    error_msg = data.get("msg", "Unknown error")
                    raise WaxpeerAPIError(error_msg)

                logger.debug(
                    "waxpeer_request_success",
                    endpoint=endpoint,
                    attempt=attempt + 1,
                )
                return data

            except httpx.TimeoutException:
                last_error = WaxpeerAPIError("Request timeout")
                logger.warning(
                    "waxpeer_request_timeout",
                    endpoint=endpoint,
                    attempt=attempt + 1,
                )

            except httpx.HTTPStatusError as e:
                last_error = WaxpeerAPIError(f"HTTP error: {e.response.status_code}")
                logger.warning(
                    "waxpeer_http_error",
                    endpoint=endpoint,
                    status_code=e.response.status_code,
                    attempt=attempt + 1,
                )

            except (WaxpeerAuthError, WaxpeerRateLimitError):
                # Не повторяем при ошибках аутентификации или rate limit
                raise

            # Ожидание перед повтором
            if attempt < self.max_retries - 1:
                await asyncio.sleep(self.retry_delay * (attempt + 1))

        raise last_error or WaxpeerAPIError("Max retries exceeded")

    # === User & Balance ===

    async def get_user(self) -> dict[str, Any]:
        """
        Получение информации о пользователе.

        API: GET /user

        Returns:
            Словарь с данными пользователя:
            - id: Steam ID
            - name: Имя пользователя
            - wallet: Баланс в милах
            - can_trade: Готов ли к торговле
            - tradelink: Steam Trade Link
        """
        data = await self._request("GET", "user")
        return data.get("user", {})

    async def get_balance(self) -> WaxpeerBalance:
        """
        Получение баланса пользователя.

        Returns:
            Объект WaxpeerBalance с данными о балансе
        """
        user_data = await self.get_user()
        wallet_mils = user_data.get("wallet", 0)
        can_trade = user_data.get("can_trade", False)

        return WaxpeerBalance(
            wallet=Decimal(str(wallet_mils)) / Decimal(str(MILS_PER_USD)),
            wallet_mils=wallet_mils,
            available_for_withdrawal=Decimal(str(wallet_mils)) / Decimal(str(MILS_PER_USD)),
            can_trade=can_trade,
        )

    # === Item Listing ===

    async def get_my_items(self) -> list[WaxpeerItem]:
        """
        Получение списка своих выставленных предметов.

        Returns:
            Список объектов WaxpeerItem
        """
        data = await self._request("GET", "my-items")
        items = []

        for item_data in data.get("items", []):
            items.append(
                WaxpeerItem(
                    item_id=str(item_data.get("item_id", "")),
                    name=item_data.get("name", ""),
                    price_mils=item_data.get("price", 0),
                    price=Decimal(str(item_data.get("price", 0) / 1000)),
                    game=WaxpeerGame.CS2,
                    float_value=item_data.get("float", None),
                    status=ListingStatus.ACTIVE,
                )
            )

        return items

    async def list_items(
        self, items: list[dict[str, Any]], game: WaxpeerGame = WaxpeerGame.CS2
    ) -> dict[str, Any]:
        """
        Выставление предметов на продажу.

        Args:
            items: Список предметов для листинга
                   Каждый элемент: {"item_id": str, "price": int (в милах)}
            game: Игра (по умолчанию CS2)

        Returns:
            Ответ API с результатом листинга
        """
        payload = {
            "items": [
                {
                    "item_id": item["item_id"],
                    "price": item["price"],  # В милах
                    "game": game.value,
                }
                for item in items
            ]
        }

        data = await self._request("POST", "list-items-steam", json_data=payload)
        logger.info(
            "waxpeer_items_listed",
            count=len(items),
            game=game.value,
        )
        return data

    async def list_single_item(
        self,
        item_id: str,
        price_usd: Decimal | float,
        game: WaxpeerGame = WaxpeerGame.CS2,
    ) -> dict[str, Any]:
        """
        Выставление одного предмета на продажу.

        Args:
            item_id: ID предмета (asset_id из Steam)
            price_usd: Цена в долларах
            game: Игра

        Returns:
            Ответ API
        """
        price_mils = int(Decimal(str(price_usd)) * 1000)
        return await self.list_items(
            [{"item_id": item_id, "price": price_mils}],
            game=game,
        )

    async def edit_item_price(self, item_id: str, new_price_usd: Decimal | float) -> dict[str, Any]:
        """
        Изменение цены выставленного предмета.

        Args:
            item_id: ID предмета на Waxpeer
            new_price_usd: Новая цена в долларах

        Returns:
            Ответ API
        """
        new_price_mils = int(Decimal(str(new_price_usd)) * 1000)

        payload = {"items": [{"item_id": item_id, "price": new_price_mils}]}

        data = await self._request("POST", "edit-items", json_data=payload)
        logger.info(
            "waxpeer_price_updated",
            item_id=item_id,
            new_price=new_price_usd,
        )
        return data

    async def remove_items(self, item_ids: list[str]) -> dict[str, Any]:
        """
        Снятие предметов с продажи.

        Args:
            item_ids: Список ID предметов для снятия

        Returns:
            Ответ API
        """
        data = await self._request(
            "POST",
            "remove-items",
            json_data={"items": item_ids},
        )
        logger.info("waxpeer_items_removed", count=len(item_ids))
        return data

    async def remove_all_items(self) -> dict[str, Any]:
        """
        Снятие всех предметов с продажи.

        API: POST /remove-all

        Returns:
            Ответ API с количеством снятых предметов
        """
        data = await self._request("POST", "remove-all")
        logger.info("waxpeer_all_items_removed")
        return data

    # === Market Data ===

    async def get_market_prices(
        self,
        item_names: list[str],
        game: WaxpeerGame = WaxpeerGame.CS2,
    ) -> dict[str, Any]:
        """
        Получение рыночных цен для списка предметов.

        API: GET /get-items-list

        Args:
            item_names: Список названий предметов
            game: Игра (по умолчанию CS2)

        Returns:
            Словарь с ценами:
            {
                "success": true,
                "items": [
                    {"name": "...", "price": 12500, "count": 156, ...}
                ]
            }
        """
        # Waxpeer принимает названия через запятую
        names_param = ",".join(item_names)
        return await self._request(
            "GET",
            "get-items-list",
            params={
                "names": names_param,
                "game": game.value,
            },
        )

    async def get_items_list(
        self,
        names: list[str],
        game: WaxpeerGame = WaxpeerGame.CS2,
    ) -> dict[str, Any]:
        """
        Получение списка предметов по именам.

        API: GET /get-items-list
        Used by CrossPlatformArbitrageScanner for price comparison.

        Args:
            names: Список названий предметов
            game: Игра (по умолчанию CS2)

        Returns:
            Словарь с ценами и данными о ликвидности
        """
        return await self.get_market_prices(names, game)

    async def get_item_price_info(self, item_name: str) -> WaxpeerPriceInfo | None:
        """
        Получение полной информации о цене предмета.

        Args:
            item_name: Название предмета

        Returns:
            WaxpeerPriceInfo или None если предмет не найден
        """
        data = await self.get_market_prices([item_name])
        items = data.get("items", [])

        if not items:
            return None

        item = items[0]
        price_mils = item.get("price", 0)

        return WaxpeerPriceInfo(
            name=item.get("name", item_name),
            price_mils=price_mils,
            price_usd=Decimal(str(price_mils)) / Decimal(str(MILS_PER_USD)),
            count=item.get("count", 0),
            steam_price_mils=item.get("steam_price"),
            avg_price_mils=item.get("avg_price"),
        )

    async def get_item_price(self, item_name: str) -> Decimal | None:
        """
        Получение минимальной цены для одного предмета.

        Args:
            item_name: Название предмета

        Returns:
            Минимальная цена в долларах или None если нет предложений
        """
        info = await self.get_item_price_info(item_name)
        return info.price_usd if info else None

    async def get_bulk_prices(
        self, game: WaxpeerGame = WaxpeerGame.CS2
    ) -> dict[str, dict[str, Any]]:
        """
        Массовое получение всех цен для игры.

        API: GET /prices
        Более эффективно чем get_items_list для большого количества предметов.

        Args:
            game: Игра (по умолчанию CS2)

        Returns:
            Словарь {item_name: {"price": int, "count": int}}
        """
        data = await self._request(
            "GET",
            "prices",
            params={"game": game.value},
        )
        return data.get("items", {})

    # === Steam Inventory ===

    async def fetch_inventory(
        self,
        game: WaxpeerGame = WaxpeerGame.CS2,
    ) -> list[dict[str, Any]]:
        """
        Массовое получение инвентаря Steam (Bulk Fetch).
        API: GET /inventory/fetch

        Более эффективно чем постраничный get_my_inventory.

        Args:
            game: Игра

        Returns:
            Список предметов из инвентаря Steam
        """
        data = await self._request(
            "GET",
            "inventory/fetch",
            params={
                "game": game.value,
            },
        )
        return data.get("items", [])

    async def get_my_inventory(
        self,
        game: WaxpeerGame = WaxpeerGame.CS2,
        skip: int = 0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Получение инвентаря Steam для листинга.

        API: GET /get-my-inventory

        Args:
            game: Игра
            skip: Пропустить N предметов
            limit: Максимум предметов

        Returns:
            Список предметов из инвентаря Steam
        """
        data = await self._request(
            "GET",
            "get-my-inventory",
            params={
                "game": game.value,
                "skip": skip,
                "limit": limit,
            },
        )
        return data.get("items", [])

    async def check_tradelink(self, tradelink: str) -> dict[str, Any]:
        """
        Проверка валидности Trade Link.

        API: GET /check-tradelink

        Args:
            tradelink: Steam Trade Link для проверки

        Returns:
            {"success": bool, "valid": bool, "steam_id": str}
        """
        return await self._request(
            "GET",
            "check-tradelink",
            params={"tradelink": tradelink},
        )

    # === Trading History ===

    async def get_history(self, skip: int = 0, limit: int = 100) -> list[dict[str, Any]]:
        """
        Получение истории торговли.

        API: GET /history

        Args:
            skip: Сколько записей пропустить
            limit: Максимальное количество записей

        Returns:
            Список сделок
        """
        data = await self._request(
            "GET",
            "history",
            params={"skip": skip, "limit": limit},
        )
        return data.get("history", [])

    async def get_recent_sales(self, limit: int = 50) -> list[dict[str, Any]]:
        """
        Получение последних продаж.

        Args:
            limit: Количество продаж

        Returns:
            Список продаж
        """
        history = await self.get_history(limit=limit)
        return [h for h in history if h.get("status") == "sold"]

    # === Status Check ===

    async def check_online_status(self) -> bool:
        """
        Проверка онлайн-статуса (нужен для P2P торговли).

        Returns:
            True если пользователь онлайн и готов к торговле
        """
        user = await self.get_user()
        return user.get("can_trade", False)

    async def get_trade_link(self) -> str | None:
        """
        Получение Trade Link пользователя.

        Returns:
            Trade Link или None
        """
        user = await self.get_user()
        return user.get("tradelink")
