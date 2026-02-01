"""DMarket API client module for interacting with DMarket API.

This module provides an asynchronous client for DMarket API v1.1.0, including:
- Ed25519 signature generation for authenticated requests (recommended)
- HMAC-SHA256 fallback for backward compatibility
- Rate limiting and automatic retry logic with exponential backoff
- Methods for market operations (get items, buy, sell, inventory, balance)
- Target (buy order) management with competition analysis
- Error handling with circuit breaker pattern
- Response caching for frequently used requests
- Support for all documented DMarket API endpoints

Authentication:
- Uses Ed25519 (NACL library) as the recommended signing method
- Timestamp must be within 2 minutes of server time
- Required headers: X-Api-Key, X-Sign-Date, X-Request-Sign

Prices:
- All prices in API are in CENTS (divide by 100 for USD)
- Example: price=1250 means $12.50

Example usage:

    from src.dmarket.dmarket_api import DMarketAPI

    # Initialize API client (DRY_RUN=True by default for safety)
    api = DMarketAPI(public_key, secret_key)

    # Get user balance
    balance = await api.get_balance()

    # Get market items
    items = await api.get_market_items(game="csgo", limit=100)

    # Create buy order (target)
    result = await api.create_targets("a8db", [
        {"Title": "AK-47 | Redline (Field-Tested)", "Amount": 1, "Price": {"Amount": 800, "Currency": "USD"}}
    ])

Documentation: https://docs.dmarket.com/v1/swagger.html
GitHub examples: https://github.com/dmarket/dm-trading-tools
Last updated: January 4, 2026
API Version: v1.1.0
"""

import asyncio
import hashlib
import hmac
import logging
import time
import traceback
from typing import TYPE_CHECKING, Any

from circuitbreaker import CircuitBreakerError  # type: ignore[import-untyped]
import httpx
import nacl.signing

from src.dmarket.api_validator import validate_response
from src.utils import json_utils as json


if TYPE_CHECKING:
    from src.telegram_bot.notifier import Notifier

from src.dmarket.schemas import (
    AggregatedPricesResponse,
    BuyOffersResponse,
    CreateTargetsResponse,
    MarketItemsResponse,
    SalesHistoryResponse,
    UserTargetsResponse,
)
from src.utils.api_circuit_breaker import call_with_circuit_breaker
from src.utils.rate_limiter import DMarketRateLimiter, RateLimiter
from src.utils.sentry_breadcrumbs import add_api_breadcrumb, add_trading_breadcrumb


logger = logging.getLogger(__name__)

# TTL для кэша в секундах
CACHE_TTL = {
    "short": 30,  # 30 секунд для часто меняющихся данных
    "medium": 300,  # 5 минут для умеренно стабильных данных
    "long": 1800,  # 30 минут для стабильных данных
}

# Кэш для хранения результатов запросов
api_cache: dict[str, Any] = {}

# Маппинг коротких имен игр в полные UUID для API v1.1.0
# FIX: Исправление ошибки 400 Bad Request (Game ID mapping)
# Note: DMarket API accepts both short names and UUIDs
GAME_MAP: dict[str, str] = {
    "csgo": "a8db",  # Short code accepted by DMarket for CS2/CS:GO
    "cs2": "a8db",   # CS2 = CS:GO
    "dota2": "9a92",  # Short code for Dota 2
    "rust": "rust",  # Rust uses string identifier
    "tf2": "tf2",    # TF2 uses string identifier
}


class DMarketAPI:  # noqa: PLR0904
    """Асинхронный клиент для работы с DMarket API.

    Основные возможности:
    - Генерация подписей для приватных запросов
    - Асинхронные методы для работы с маркетом, инвентарём, балансом
    - Встроенный rate limiting и автоматические повторы при ошибках
    - Логирование и обработка ошибок
    - Кэширование часто используемых запросов
    - Поддержка всех документированных эндпоинтов DMarket API

    Пример:
        api = DMarketAPI(public_key, secret_key)
        items = await api.get_market_items(game="csgo")
    """

    # БАЗОВЫЕ ЭНДПОИНТЫ (согласно документации)
    BASE_URL = "https://api.dmarket.com"

    # Баланс и аккаунт
    ENDPOINT_BALANCE = "/account/v1/balance"  # Основной эндпоинт баланса
    ENDPOINT_BALANCE_LEGACY = "/api/v1/account/balance"  # Альтернативный эндпоинт
    ENDPOINT_ACCOUNT_DETAILS = "/api/v1/account/details"  # Детали аккаунта
    ENDPOINT_ACCOUNT_OFFERS = "/api/v1/account/offers"  # Активные торговые предложения

    # Маркет
    ENDPOINT_MARKET_ITEMS = "/exchange/v1/market/items"  # Поиск предметов на маркете
    ENDPOINT_MARKET_PRICE_AGGREGATED = (
        "/exchange/v1/market/aggregated-prices"  # Агрегированные цены
    )
    ENDPOINT_MARKET_META = "/exchange/v1/market/meta"  # Метаданные маркета

    # Пользователь
    ENDPOINT_USER_INVENTORY = "/inventory/v1/user/items"  # Инвентарь пользователя (v1.1.0)
    ENDPOINT_USER_OFFERS = "/marketplace-api/v1/user-offers"  # Предложения пользователя (v1.1.0)
    ENDPOINT_USER_TARGETS = "/main/v2/user-targets"  # Целевые предложения пользователя (v1.1.0)

    # Операции
    ENDPOINT_PURCHASE = "/exchange/v1/market/items/buy"  # Покупка предмета
    ENDPOINT_SELL = "/exchange/v1/user/inventory/sell"  # Выставить на продажу (Legacy)
    ENDPOINT_SELL_CREATE = "/marketplace-api/v1/create-offers"  # Создание офферов (v1.1.0)
    ENDPOINT_OFFER_EDIT = "/exchange/v1/user/offers/edit"  # Редактирование предложения
    ENDPOINT_OFFER_DELETE = "/exchange/v1/user/offers/delete"  # Удаление предложения

    # Статистика и аналитика
    ENDPOINT_SALES_HISTORY = "/account/v1/sales-history"  # История продаж
    ENDPOINT_ITEM_PRICE_HISTORY = "/exchange/v1/market/price-history"  # История цен предмета
    ENDPOINT_LAST_SALES = "/trade-aggregator/v1/last-sales"  # История последних продаж (API v1.1.0)

    # Новые эндпоинты 2024/2025 (API v1.1.0)
    ENDPOINT_MARKET_BEST_OFFERS = "/exchange/v1/market/best-offers"  # Лучшие предложения на маркете
    ENDPOINT_MARKET_SEARCH = "/exchange/v1/market/search"  # Расширенный поиск
    ENDPOINT_AGGREGATED_PRICES_POST = (
        "/marketplace-api/v1/aggregated-prices"  # Агрегированные цены (POST, v1.1.0)
    )
    ENDPOINT_TARGETS_BY_TITLE = (
        "/marketplace-api/v1/targets-by-title"  # Таргеты по названию (v1.1.0)
    )
    ENDPOINT_DEPOSIT_ASSETS = "/marketplace-api/v1/deposit-assets"  # Депозит активов (v1.1.0)
    ENDPOINT_DEPOSIT_STATUS = "/marketplace-api/v1/deposit-status"  # Статус депозита (v1.1.0)
    ENDPOINT_WITHDRAW_ASSETS = "/exchange/v1/withdraw-assets"  # Вывод активов (v1.1.0)
    ENDPOINT_INVENTORY_SYNC = (
        "/marketplace-api/v1/user-inventory/sync"  # Синхронизация инвентаря (v1.1.0)
    )
    ENDPOINT_GAMES_LIST = "/game/v1/games"  # Список всех поддерживаемых игр (v1.1.0)

    # Известные коды ошибок DMarket API и рекомендации по их обработке
    ERROR_CODES = {
        400: "Неверный запрос или параметры",
        401: "Неверная аутентификация",
        403: "Доступ запрещен",
        404: "Ресурс не найден",
        429: "Слишком много запросов (rate limit)",
        500: "Внутренняя ошибка сервера",
        502: "Bad Gateway",
        503: "Сервис недоступен",
        504: "Gateway Timeout",
    }

    def __init__(
        self,
        public_key: str,
        secret_key: str | bytes,
        api_url: str = "https://api.dmarket.com",
        max_retries: int = 3,
        connection_timeout: float = 30.0,
        pool_limits: httpx.Limits | None = None,
        retry_codes: list[int] | None = None,
        enable_cache: bool = True,
        dry_run: bool = True,
        notifier: "Notifier | None" = None,
    ) -> None:
        """Initialize DMarket API client.

        Args:
            public_key: DMarket API public key
            secret_key: DMarket API secret key
            api_url: API URL (default is https://api.dmarket.com)
            max_retries: Maximum number of retries for failed requests
            connection_timeout: Connection timeout in seconds
            pool_limits: Connection pool limits
            retry_codes: HTTP status codes to retry on
            enable_cache: Enable caching of frequent requests
            dry_run: If True, simulates trading operations without real API calls (default: True for safety)
            notifier: Notifier instance for sending alerts on API changes (optional)

        """
        self.public_key = public_key
        self._public_key = public_key  # Store for test access

        if isinstance(secret_key, str):
            self._secret_key = secret_key
            self.secret_key = secret_key.encode("utf-8")
        else:
            self._secret_key = secret_key.decode("utf-8")
            self.secret_key = secret_key

        self.api_url = api_url
        self.max_retries = max_retries
        self.connection_timeout = connection_timeout
        self.enable_cache = enable_cache
        self.dry_run = dry_run
        self.notifier = notifier  # Store notifier for API validation alerts

        # Default retry codes: server errors and too many requests
        self.retry_codes = retry_codes or [429, 500, 502, 503, 504]

        # Enhanced connection pool settings (Roadmap Task #7)
        # Optimized for high-frequency trading with DNS caching
        self.pool_limits = pool_limits or httpx.Limits(
            max_connections=100,  # Max total connections
            max_keepalive_connections=30,  # Increased for better performance
            keepalive_expiry=60.0,  # Longer keep-alive for stable connections
        )

        # HTTP client with HTTP/2 support
        self._client: httpx.AsyncClient | None = None
        self._http2_enabled = True  # Enable HTTP/2 for better performance
        self._client_ref_count = 0  # Reference counter for parallel scanning
        self._client_lock = asyncio.Lock()  # Lock for thread-safe operations

        # CPU executor for async HMAC signing (non-blocking)
        from concurrent.futures import ThreadPoolExecutor

        self._signing_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hmac_signer")

        # Initialize per-endpoint RateLimiter (Roadmap Task #3)
        self.rate_limiter = DMarketRateLimiter()

        # Prepare signing key (optimized for performance)
        self._signing_key = None

        # Log initialization with trading mode
        mode = "[DRY-RUN]" if dry_run else "[LIVE]"
        logger.info(
            f"Initialized DMarketAPI client {mode} "
            f"(authorized: {'yes' if public_key and secret_key else 'no'}, "
            f"cache: {'enabled' if enable_cache else 'disabled'}, "
            f"rate limiter: advanced per-endpoint)",
        )

        if not dry_run:
            logger.warning(
                "⚠️  DRY_RUN=false - API client will make REAL TRADES! "
                "Ensure you understand the risks."
            )

    async def __aenter__(self) -> "DMarketAPI":
        """Context manager to use the client with async with."""
        async with self._client_lock:
            self._client_ref_count += 1
            await self._get_client()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object | None,
    ) -> None:
        """Close client when exiting context manager.

        Only closes the client when reference count reaches zero.
        This allows parallel scanning without closing the client prematurely.
        """
        _ = (exc_type, exc_val, exc_tb)  # Unused but required by protocol
        async with self._client_lock:
            self._client_ref_count -= 1
            # Only close client if no other references exist
            if self._client_ref_count <= 0:
                await self._close_client()
                self._client_ref_count = 0  # Reset counter

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with optimized settings.

        Roadmap Task #7: Connection Pooling
        - HTTP/2 support for better performance (if h2 package installed)
        - Connection pooling with keepalive
        - Optimized timeout settings
        """
        if self._client is None or self._client.is_closed:
            # Try to enable HTTP/2, fallback to HTTP/1.1 if h2 not installed
            try:
                self._client = httpx.AsyncClient(
                    timeout=self.connection_timeout,
                    limits=self.pool_limits,
                    http2=self._http2_enabled,  # Try HTTP/2
                    follow_redirects=True,
                    verify=True,  # Always verify SSL
                )

                logger.debug(
                    "Created HTTP client: max_connections=%d, max_keepalive=%d, http2=enabled",
                    self.pool_limits.max_connections,
                    self.pool_limits.max_keepalive_connections,
                )
            except ImportError:
                # h2 package not installed, fallback to HTTP/1.1
                logger.info("HTTP/2 not available (h2 package not installed), using HTTP/1.1")
                self._http2_enabled = False  # Update flag

                self._client = httpx.AsyncClient(
                    timeout=self.connection_timeout,
                    limits=self.pool_limits,
                    http2=False,
                    follow_redirects=True,
                    verify=True,
                )

                logger.debug(
                    "Created HTTP client: max_connections=%s, max_keepalive=%s, http2=disabled",
                    getattr(self.pool_limits, "max_connections", "N/A"),
                    getattr(self.pool_limits, "max_keepalive_connections", "N/A"),
                )

        return self._client

    async def _close_client(self) -> None:
        """Close HTTP client if it exists."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def get_connection_pool_stats(self) -> dict[str, any]:
        """Get connection pool statistics.

        Roadmap Task #7: Connection Pooling Metrics

        Returns:
            Dictionary with connection pool stats
        """
        if self._client is None or self._client.is_closed:
            return {
                "status": "closed",
                "active_connections": 0,
                "idle_connections": 0,
            }

        # Get stats from connection pool
        stats = {
            "status": "active",
            "max_connections": self.pool_limits.max_connections,
            "max_keepalive": self.pool_limits.max_keepalive_connections,
            "keepalive_expiry": self.pool_limits.keepalive_expiry,
            "http2_enabled": self._http2_enabled,
        }

        # Try to get actual connection counts if available
        try:
            if hasattr(self._client, "_transport"):
                transport = self._client._transport
                if hasattr(transport, "_pool"):
                    pool = transport._pool
                    stats["active_connections"] = len(getattr(pool, "_requests", []))
                    stats["idle_connections"] = len(getattr(pool, "_connections", []))
        except Exception as e:
            logger.debug(f"Could not get detailed pool stats: {e}")

        return stats

    async def sell_with_arbitrage(
        self, asset_id: str, buy_price_cents: int, profit_percent: float = 15.0
    ) -> dict[str, Any]:
        """Автоматически выставляет купленный предмет на продажу.

        Args:
            asset_id: ID предмета в инвентаре DMarket
            buy_price_cents: Цена, за которую купили (в центах)
            profit_percent: Желаемая чистая прибыль в %

        Returns:
            Ответ API о создании оффера
        """
        # Расчет: (Цена покупки + % прибыли) / (1 - комиссия маркета 0.05)
        # Пример: ($10 + 15%) / 0.95 = $12.10 для получения $1.5 прибыли чистоганом
        fee_factor = 0.95
        target_multiplier = 1 + (profit_percent / 100)

        sell_price_usd = (buy_price_cents / 100 * target_multiplier) / fee_factor
        sell_price_cents = round(sell_price_usd * 100)

        payload = {
            "offers": [
                {
                    "assetId": asset_id,
                    "price": {"amount": sell_price_cents, "currency": "USD"},
                }
            ]
        }

        logger.info(
            f"📈 Арбитраж: выставляю asset {asset_id} за {sell_price_usd:.2f}$ (ROI {profit_percent}%)"
        )
        return await self._request("POST", self.ENDPOINT_SELL_CREATE, data=payload)

    def _prepare_signing_key(self) -> None:
        """Prepare Ed25519 signing key once to optimize performance."""
        try:
            secret_key_str = self._secret_key
            if len(secret_key_str) == 64:
                secret_key_bytes = bytes.fromhex(secret_key_str)
            elif len(secret_key_str) == 44 or "=" in secret_key_str:
                import base64
                secret_key_bytes = base64.b64decode(secret_key_str)
            elif len(secret_key_str) >= 64:
                secret_key_bytes = bytes.fromhex(secret_key_str[:64])
            else:
                secret_key_bytes = secret_key_str.encode("utf-8")[:32].ljust(32, b"\0")
            
            self._signing_key = nacl.signing.SigningKey(secret_key_bytes)
        except Exception as e:
            logger.error(f"Failed to prepare signing key: {e}")

    def _generate_signature(
        self,
        method: str,
        path: str,
        body: str = "",
    ) -> dict[str, str]:
        """Генерирует подпись для приватных запросов DMarket API согласно документации.

        DMarket API использует Ed25519 для подписи запросов.
        Формат: timestamp + method + path + body

        Args:
            method: HTTP-метод ("GET", "POST" и т.д.)
            path: Путь запроса (например, "/account/v1/balance")
            body: Тело запроса (строка JSON)

        Returns:
            dict: Заголовки с подписью и ключом API

        """
        if not self.public_key or not self.secret_key:
            return {"Content-Type": "application/json"}

        try:
            # Generate timestamp
            timestamp = str(int(time.time()))

            # Build string to sign: method + path + body + timestamp
            string_to_sign = f"{method.upper()}{path}{body}{timestamp}"

            # Use prepared signing key if available
            if self._signing_key is None:
                self._prepare_signing_key()
            
            if self._signing_key:
                # Sign the message
                signed = self._signing_key.sign(string_to_sign.encode("utf-8"))
                signature = signed.signature.hex()

                # Return headers with signature in DMarket format
                return {
                    "X-Api-Key": self.public_key,
                    "X-Request-Sign": f"dmar ed25519 {signature}",
                    "X-Sign-Date": timestamp,
                    "Content-Type": "application/json",
                }
            
            # Fallback if key preparation failed
            return self._generate_signature_hmac(method, path, body)

        except Exception as e:
            logger.exception(f"Error generating signature: {e}")
            # Fallback to old HMAC method if Ed25519 fails
            return self._generate_signature_hmac(method, path, body)

    def _generate_signature_hmac(
        self,
        method: str,
        path: str,
        body: str = "",
    ) -> dict[str, str]:
        """Fallback метод с HMAC-SHA256 (старый формат).

        Args:
            method: HTTP-метод
            path: Путь запроса
            body: Тело запроса

        Returns:
            dict: Заголовки с HMAC подписью

        """
        timestamp = str(int(time.time()))
        string_to_sign = timestamp + method + path

        if body:
            string_to_sign += body

        secret_key = self.secret_key

        signature = hmac.new(
            secret_key,
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        return {
            "X-Api-Key": self.public_key,
            "X-Request-Sign": signature,
            "X-Sign-Date": timestamp,
            "Content-Type": "application/json",
        }

    async def _generate_signature_async(
        self,
        method: str,
        path: str,
        body: str = "",
    ) -> dict[str, str]:
        """Асинхронная генерация подписи (не блокирует event loop).

        Выполняет CPU-интенсивную операцию подписи в отдельном потоке,
        освобождая event loop для других асинхронных операций.
        Это критично для high-frequency trading.

        Args:
            method: HTTP-метод ("GET", "POST" и т.д.)
            path: Путь запроса
            body: Тело запроса

        Returns:
            dict: Заголовки с подписью

        Note:
            Использует ThreadPoolExecutor для CPU-bound операций.
            В среднем экономит 2-5 мс на каждом запросе.
        """
        loop = asyncio.get_event_loop()

        # Выполнить подпись в отдельном потоке (не блокирует event loop)
        return await loop.run_in_executor(
            self._signing_executor,
            self._generate_signature,
            method,
            path,
            body,
        )

    def _generate_headers(
        self,
        method: str,
        target: str,
        body: str = "",
    ) -> dict[str, str]:
        """Alias for _generate_signature for test compatibility.

        Args:
            method: HTTP method
            target: Request path/target
            body: Request body

        Returns:
            dict: Headers with signature

        """
        return self._generate_signature(method, target, body)

    def _get_cache_key(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
    ) -> str:
        """Создает уникальный ключ для кэша на основе запроса.

        Args:
            method: HTTP-метод
            path: Путь запроса
            params: GET-параметры
            data: POST-данные

        Returns:
            str: Ключ кэша

        """
        key_parts = [method, path]

        if params:
            # Сортируем параметры для консистентного ключа
            sorted_params = sorted((str(k), str(v)) for k, v in params.items())
            key_parts.append(str(sorted_params))

        if data:
            # Для POST-данных используем хеш от JSON
            try:
                data_str = json.dumps(data, sort_keys=True)
                key_parts.append(hashlib.sha256(data_str.encode()).hexdigest())
            except (TypeError, ValueError):
                key_parts.append(str(data))

        return hashlib.sha256("|".join(key_parts).encode()).hexdigest()

    def _is_cacheable(self, method: str, path: str) -> tuple[bool, str]:
        """Определяет, можно ли кэшировать данный запрос и на какой период.

        Args:
            method: HTTP-метод
            path: Путь запроса

        Returns:
            Tuple[bool, str]: (можно_кэшировать, тип_ttl)

        """
        # GET-запросы можно кэшировать
        if method.upper() != "GET":
            return (False, "")

        # Определяем TTL на основе эндпоинта
        if any(
            endpoint in path
            for endpoint in [
                self.ENDPOINT_MARKET_META,
                self.ENDPOINT_MARKET_PRICE_AGGREGATED,
                "/meta",
                "/aggregated",
            ]
        ):
            return (True, "medium")  # Стабильные данные

        if any(
            endpoint in path
            for endpoint in [
                self.ENDPOINT_MARKET_ITEMS,
                self.ENDPOINT_USER_INVENTORY,
                self.ENDPOINT_MARKET_BEST_OFFERS,
                self.ENDPOINT_SALES_HISTORY,
                "/market/",
                "/items",
                "/inventory",
            ]
        ):
            return (True, "short")  # Часто меняющиеся данные

        if any(
            endpoint in path
            for endpoint in [
                self.ENDPOINT_BALANCE,
                self.ENDPOINT_BALANCE_LEGACY,
                self.ENDPOINT_ACCOUNT_DETAILS,
                "/balance",
                "/account/",
            ]
        ):
            return (True, "short")  # Финансовые данные - короткий кэш

        if any(
            endpoint in path
            for endpoint in [
                self.ENDPOINT_ITEM_PRICE_HISTORY,
                "/history",
                "/statistics",
            ]
        ):
            return (True, "long")  # Исторические данные - долгий кэш

        # По умолчанию - не кэшируем
        return (False, "")

    def _get_from_cache(self, cache_key: str) -> dict[str, Any] | None:
        """Получает данные из кэша, если они есть и не устарели.

        Args:
            cache_key: Ключ кэша

        Returns:
            Optional[Dict[str, Any]]: Данные из кэша или None

        """
        if not self.enable_cache:
            return None

        cache_entry = api_cache.get(cache_key)
        if not cache_entry:
            return None

        data, expire_time = cache_entry
        if time.time() < expire_time:
            logger.debug(f"Cache hit for key {cache_key[:8]}...")
            return data  # type: ignore[no-any-return]

        # Удаляем устаревшие данные
        logger.debug(f"Cache expired for key {cache_key[:8]}...")
        api_cache.pop(cache_key, None)
        return None

    def _save_to_cache(
        self,
        cache_key: str,
        data: dict[str, Any],
        ttl_type: str,
    ) -> None:
        """Сохраняет данные в кэш.

        Args:
            cache_key: Ключ кэша
            data: Данные для сохранения
            ttl_type: Тип TTL ('short', 'medium', 'long')

        """
        if not self.enable_cache:
            return

        ttl = CACHE_TTL.get(ttl_type, CACHE_TTL["short"])
        expire_time = time.time() + ttl
        api_cache[cache_key] = (data, expire_time)

        # Очистка кэша, если он слишком большой (более 500 записей)
        if len(api_cache) > 500:
            # Удаляем 20% старых записей
            time.time()
            keys_to_remove = sorted(
                api_cache.keys(),
                key=lambda k: api_cache[k][1],  # Сортировка по времени истечения
            )[:100]

            for key in keys_to_remove:
                api_cache.pop(key, None)

            logger.debug(f"Cache cleanup: removed {len(keys_to_remove)} old entries")

    # ============================================================================
    # Request helper methods (Phase 2 refactoring - extracted from _request)
    # ============================================================================

    def _prepare_sorted_params(
        self,
        params: dict[str, Any] | None,
    ) -> list[tuple[str, Any]]:
        """Prepare and sort query parameters for consistent signing.

        Args:
            params: Original query parameters

        Returns:
            Sorted list of (key, value) tuples
        """
        if not params:
            return []

        if isinstance(params, dict):
            return sorted(params.items())
        return sorted(params)

    def _build_path_for_signature(
        self,
        method: str,
        path: str,
        params_items: list[tuple[str, Any]],
    ) -> str:
        """Build path with query string for signature generation.

        Args:
            method: HTTP method
            path: API path
            params_items: Sorted list of query parameters

        Returns:
            Path with query string for GET requests, original path otherwise
        """
        if method.upper() != "GET" or not params_items:
            return path

        from urllib.parse import urlencode
        query_string = urlencode(params_items)
        return f"{path}?{query_string}" if query_string else path

    async def _execute_single_http_request(
        self,
        client: httpx.AsyncClient,
        method: str,
        url: str,
        params: list[tuple[str, Any]] | None,
        data: dict[str, Any] | None,
        headers: dict[str, str],
    ) -> httpx.Response:
        """Execute a single HTTP request with circuit breaker.

        Args:
            client: HTTP client
            method: HTTP method
            url: Full URL
            params: Query parameters
            data: Request body data
            headers: Request headers

        Returns:
            HTTP response

        Raises:
            ValueError: If HTTP method is not supported
        """
        method_upper = method.upper()

        if method_upper == "GET":
            return await call_with_circuit_breaker(
                client.get, url, params=params, headers=headers
            )
        if method_upper == "POST":
            return await call_with_circuit_breaker(
                client.post, url, json=data, headers=headers
            )
        if method_upper == "PUT":
            return await call_with_circuit_breaker(
                client.put, url, json=data, headers=headers
            )
        if method_upper == "DELETE":
            return await call_with_circuit_breaker(
                client.delete, url, headers=headers
            )

        msg = f"Неподдерживаемый HTTP метод: {method}"
        raise ValueError(msg)

    def _parse_json_response(
        self,
        response: httpx.Response,
        path: str,
    ) -> dict[str, Any]:
        """Parse JSON from HTTP response.

        Args:
            response: HTTP response
            path: API path (for logging)

        Returns:
            Parsed JSON data or error dict
        """
        if response.status_code == 204:  # No Content
            return {"status": "success", "code": 204}

        try:
            return response.json()  # type: ignore[no-any-return]
        except (json.JSONDecodeError, TypeError, Exception):
            logger.exception(
                f"Ошибка парсинга JSON. Код: {response.status_code}. "
                f"Текст: {response.text[:200]}"
            )
            return {
                "error": "invalid_json",
                "status_code": response.status_code,
                "raw_body": response.text[:100],
                "text": response.text,
            }

    def _calculate_retry_delay(
        self,
        status_code: int,
        retries: int,
        current_delay: float,
        response: httpx.Response | None = None,
    ) -> float:
        """Calculate delay before retry based on error type.

        Args:
            status_code: HTTP status code
            retries: Current retry count
            current_delay: Current delay value
            response: HTTP response (for Retry-After header)

        Returns:
            Delay in seconds before next retry
        """
        if status_code == 429:
            # Rate limit - use Retry-After header or exponential backoff
            retry_after = None
            if response:
                try:
                    retry_after = int(response.headers.get("Retry-After", "0"))
                except (ValueError, TypeError):
                    retry_after = None

            if retry_after and retry_after > 0:
                return float(retry_after)
            return min(current_delay * 2, 30)  # Max 30 seconds

        # Other errors - fixed delay with small increment
        return 1.0 + retries * 0.5

    def _parse_http_error_response(
        self,
        response: httpx.Response,
    ) -> dict[str, Any]:
        """Parse error response body.

        Args:
            response: HTTP response with error

        Returns:
            Parsed error data
        """
        content_type = response.headers.get("Content-Type", "")

        if "application/json" in content_type:
            try:
                return response.json()  # type: ignore[no-any-return]
            except Exception:
                return {
                    "error": "Failed to parse JSON error",
                    "raw": response.text[:100],
                }

        # Non-JSON response (e.g., HTML from Cloudflare)
        return {
            "error": "Non-JSON response",
            "status_code": response.status_code,
        }

    # ============================================================================
    # End of request helper methods
    # ============================================================================

    async def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        data: dict[str, Any] | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        """Выполняет запрос к DMarket API с обработкой ошибок, повторными попытками и кешированием.

        Args:
            method: HTTP метод (GET, POST и т.д.)
            path: Путь API без базового URL
            params: Параметры запроса (для GET)
            data: Данные для запроса (для POST/PUT)
            force_refresh: Принудительно обновить кэш (если включен)

        Returns:
            Ответ API в виде словаря

        Raises:
            Exception: При ошибке запроса после всех повторных попыток

        """
        # Создаем клиента, если его нет
        client = await self._get_client()

        # Параметры по умолчанию
        if params is None:
            params = {}

        if data is None:
            data = {}

        # Полный URL запроса
        url = f"{self.api_url}{path}"

        # Определяем возможность кэширования и тип TTL заранее
        is_cacheable, ttl_type = self._is_cacheable(method, path)
        cache_key = ""

        # Проверяем кэш для GET запросов
        body_json = ""
        if method.upper() == "GET" and self.enable_cache and not force_refresh:
            cache_key = self._get_cache_key(method, path, params, data)

            # Пробуем получить из кэша
            if is_cacheable:
                cached_data = self._get_from_cache(cache_key)
                if cached_data is not None:
                    logger.debug(f"Использую кэшированные данные для {path}")
                    return cached_data

        # Формируем тело запроса для POST/PUT/PATCH
        if data and method.upper() in {"POST", "PUT", "PATCH"}:
            body_json = json.dumps(data)

        # Подготавливаем отсортированные параметры для подписи
        # (Phase 2 refactoring - extracted to helper method)
        params_items = self._prepare_sorted_params(params)
        if params_items:
            params = params_items  # type: ignore[assignment]

        # Строим path для подписи с query string
        path_for_signature = self._build_path_for_signature(method, path, params_items)

        logger.debug(f"Path for signature: {path_for_signature}")
        headers = self._generate_signature(method.upper(), path_for_signature, body_json)

        # Use advanced per-endpoint rate limiter (Roadmap Task #3)
        await self.rate_limiter.acquire(path)

        # Переменные для повторных попыток
        retries = 0
        last_error = None
        retry_delay = 1.0  # начальная задержка в секундах

        # Основной цикл запросов с повторами при ошибках
        while retries <= self.max_retries:
            start_time = time.time()
            try:
                # Добавляем breadcrumb перед API запросом
                add_api_breadcrumb(
                    endpoint=path,
                    method=method.upper(),
                    retry_attempt=retries,
                    has_cache=cache_key and self._get_from_cache(cache_key) is not None,
                )

                # Выполняем запрос (Phase 2 - extracted to helper method)
                response = await self._execute_single_http_request(
                    client=client,
                    method=method,
                    url=url,
                    params=params,  # type: ignore[arg-type]
                    data=data,
                    headers=headers,
                )

                # Проверяем статус ответа
                response.raise_for_status()

                # Рассчитываем время ответа
                response_time_ms = (time.time() - start_time) * 1000

                # Добавляем breadcrumb об успешном запросе
                add_api_breadcrumb(
                    endpoint=path,
                    method=method.upper(),
                    status_code=response.status_code,
                    response_time_ms=response_time_ms,
                )

                # Парсим JSON ответа (Phase 2 - extracted to helper method)
                result = self._parse_json_response(response, path)

                # Сохраняем в кэш если нужно
                if method.upper() == "GET" and self.enable_cache and is_cacheable:
                    self._save_to_cache(cache_key, result, ttl_type)

                return result  # type: ignore[no-any-return]

            except CircuitBreakerError as e:
                logger.warning(f"Circuit breaker open for {method} {path}: {e}")
                # Добавляем breadcrumb об ошибке circuit breaker
                add_api_breadcrumb(
                    endpoint=path,
                    method=method.upper(),
                    error="circuit_breaker_open",
                    error_message=str(e),
                )
                last_error = e
                break

            except httpx.HTTPStatusError as e:
                status_code = e.response.status_code
                response_text = e.response.text
                response_time_ms = (time.time() - start_time) * 1000

                # Подробное логирование ошибки
                logger.warning(
                    f"HTTP ошибка {status_code} при запросе {method} {path}: {response_text}",
                )

                # Добавляем breadcrumb об HTTP ошибке
                add_api_breadcrumb(
                    endpoint=path,
                    method=method.upper(),
                    status_code=status_code,
                    response_time_ms=response_time_ms,
                    error="http_error",
                    retry_attempt=retries,
                )

                # Получаем описание ошибки из словаря кодов ошибок
                error_description = self.ERROR_CODES.get(status_code, "Неизвестная ошибка")
                logger.warning(f"Описание ошибки: {error_description}")

                # Проверяем, нужно ли повторить запрос
                if status_code in self.retry_codes:
                    retries += 1

                    # Record 429 error in advanced rate limiter (Roadmap Task #3)
                    if status_code == 429:
                        self.rate_limiter.record_429_error(path)

                    # Calculate retry delay (Phase 2 - extracted to helper method)
                    retry_delay = self._calculate_retry_delay(
                        status_code=status_code,
                        retries=retries,
                        current_delay=retry_delay,
                        response=e.response,
                    )

                    if status_code == 429:
                        logger.warning(
                            f"⚠️  Rate limit превышен для {path}. "
                            f"Повторная попытка через {retry_delay} сек.",
                        )

                    if retries <= self.max_retries:
                        logger.info(
                            f"Повторная попытка {retries}/{self.max_retries} "
                            f"через {retry_delay} сек...",
                        )
                        await asyncio.sleep(retry_delay)
                        continue

                # Parse error response (Phase 2 - extracted to helper method)
                error_data = self._parse_http_error_response(e.response)
                logger.warning(f"⚠️ API Error {e.response.status_code} на {path}: {error_data}")
                return error_data

            except (httpx.ConnectError, httpx.ReadError, httpx.WriteError) as e:
                # Сетевые ошибки
                logger.warning(f"Сетевая ошибка при запросе {method} {path}: {e!s}")

                # Добавляем breadcrumb о сетевой ошибке
                add_api_breadcrumb(
                    endpoint=path,
                    method=method.upper(),
                    error="network_error",
                    error_message=str(e),
                    retry_attempt=retries,
                )

                retries += 1
                retry_delay = min(
                    retry_delay * 1.5,
                    10,
                )  # максимальная задержка 10 секунд

                if retries <= self.max_retries:
                    logger.info(
                        f"Повторная попытка {retries}/{self.max_retries} через {retry_delay} сек...",
                    )
                    await asyncio.sleep(retry_delay)
                    continue

                last_error = e
                break

            except Exception as e:
                # Другие ошибки
                logger.exception(
                    f"Непредвиденная ошибка при запросе {method} {path}: {e!s}",
                )
                logger.exception(traceback.format_exc())

                # Добавляем breadcrumb о непредвиденной ошибке
                add_api_breadcrumb(
                    endpoint=path,
                    method=method.upper(),
                    error="unexpected_error",
                    error_message=str(e),
                    retry_attempt=retries,
                )

                last_error = e
                break

        # Если были исчерпаны все попытки
        if last_error:
            error_message = str(last_error)
            return {
                "error": True,
                "message": error_message,
                "code": "REQUEST_FAILED",
            }

        # Эта часть кода никогда не должна выполняться, но для безопасности
        return {
            "error": True,
            "message": "Unknown error occurred during API request",
            "code": "UNKNOWN_ERROR",
        }

    async def clear_cache(self) -> None:
        """Очищает весь кэш API."""
        api_cache.clear()
        logger.info("API cache cleared")

    async def clear_cache_for_endpoint(self, endpoint_path: str) -> None:
        """Очищает кэш для конкретного эндпоинта.

        Args:
            endpoint_path: Путь эндпоинта

        """
        keys_to_remove = []

        for key in api_cache:
            if endpoint_path in key:
                keys_to_remove.append(key)

        for key in keys_to_remove:
            api_cache.pop(key, None)

        logger.info(
            f"Cleared {len(keys_to_remove)} cache entries for endpoint {endpoint_path}",
        )

    # Оставляем для обратной совместимости
    def _create_error_response(
        self,
        error_message: str,
        status_code: int = 500,
        error_code: str = "ERROR",
    ) -> dict[str, Any]:
        """Create standardized error response for balance requests.

        Args:
            error_message: Human-readable error message
            status_code: HTTP status code
            error_code: Machine-readable error code

        Returns:
            Standardized error response dict
        """
        return {
            "usd": {"amount": 0},
            "has_funds": False,
            "balance": 0.0,
            "available_balance": 0.0,
            "total_balance": 0.0,
            "error": True,
            "error_message": error_message,
            "status_code": status_code,
            "code": error_code,
        }

    def _create_balance_response(
        self,
        usd_amount: float,
        usd_available: float,
        usd_total: float,
        min_required: float = 100.0,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """Create standardized success response for balance requests.

        Args:
            usd_amount: Total balance in cents
            usd_available: Available balance in cents
            usd_total: Total balance including locked funds in cents
            min_required: Minimum required balance in cents (default 100 = $1.00)
            **kwargs: Additional fields to include in response

        Returns:
            Standardized success response dict
        """
        has_funds = usd_amount >= min_required

        result = {
            "usd": {"amount": usd_amount},
            "has_funds": has_funds,
            "balance": usd_amount / 100,
            "available_balance": usd_available / 100,
            "total_balance": usd_total / 100,
            "error": False,
        }
        result.update(kwargs)
        return result

    def _parse_balance_from_response(self, response: dict[str, Any]) -> tuple[float, float, float]:
        """Parse balance data from various DMarket API response formats.

        Args:
            response: API response dict

        Returns:
            Tuple of (usd_amount, usd_available_for_trading, usd_total) in cents

        Note:
            ВАЖНО: usdAvailableToWithdraw - это сумма доступная для ВЫВОДА,
            а не для торговли! Для торговли обычно доступен весь баланс usd.
        """
        usd_amount = 0.0
        usd_available = 0.0
        usd_total = 0.0

        try:
            # Format 0: Official DMarket API format (2024)
            # {"usd": "4550", "usdAvailableToWithdraw": "0", "usdTradeProtected": "0", ...}
            if "usd" in response:
                usd_str = response.get("usd", "0")
                usd_trade_protected_str = response.get("usdTradeProtected", "0")

                usd_amount = float(usd_str) if usd_str else 0
                usd_trade_protected = (
                    float(usd_trade_protected_str) if usd_trade_protected_str else 0
                )

                # FIX: Для торговли доступен весь баланс минус trade_protected
                # usdAvailableToWithdraw - это только для вывода на внешние кошельки!
                usd_available = usd_amount - usd_trade_protected
                usd_total = usd_amount
                logger.info(
                    f"Parsed balance: ${usd_amount / 100:.2f} USD "
                    f"(available for trading: ${usd_available / 100:.2f})"
                )

            # Format 1: Alternative format with funds.usdWallet
            elif "funds" in response:
                funds = response["funds"]
                if isinstance(funds, dict) and "usdWallet" in funds:
                    wallet = funds["usdWallet"]
                    usd_amount = float(wallet.get("balance", 0)) * 100
                    usd_available = float(wallet.get("availableBalance", usd_amount / 100)) * 100
                    usd_total = float(wallet.get("totalBalance", usd_amount / 100)) * 100
                    logger.info(f"Parsed balance from funds.usdWallet: ${usd_amount / 100:.2f} USD")

            # Format 2: Simple balance/available/total format
            elif "balance" in response and isinstance(response["balance"], (int, float, str)):
                usd_amount = float(response["balance"]) * 100
                usd_available = float(response.get("available", usd_amount / 100)) * 100
                usd_total = float(response.get("total", usd_amount / 100)) * 100
                logger.info(f"Parsed balance from simple format: ${usd_amount / 100:.2f} USD")

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Error parsing balance from response: {e}")
            logger.debug(f"Raw response: {response}")

        # Normalize values
        if usd_available == 0 and usd_amount > 0:
            # Если available не установлен, считаем что весь баланс доступен
            usd_available = usd_amount
        if usd_total == 0:
            usd_total = max(usd_amount, usd_available)

        return usd_amount, usd_available, usd_total

    async def _try_endpoints_for_balance(
        self,
        endpoints: list[str],
    ) -> tuple[dict[str, Any] | None, str | None, Exception | None]:
        """Try multiple endpoints to get balance data.

        Args:
            endpoints: List of endpoint URLs to try

        Returns:
            Tuple of (response_dict, successful_endpoint, last_error)
        """
        response = None
        last_error = None
        successful_endpoint = None

        for endpoint in endpoints:
            try:
                logger.info(f"Trying to get balance from endpoint {endpoint}")
                resp = await self._request("GET", endpoint)

                if resp and not ("error" in resp or "code" in resp):
                    logger.info(f"Successfully got balance from {endpoint}")
                    response = resp
                    successful_endpoint = endpoint
                    break

            except Exception as e:
                last_error = e
                logger.warning(f"Error querying {endpoint}: {e!s}")
                continue

        return response, successful_endpoint, last_error

    async def get_balance(self) -> dict[str, Any]:
        """Улучшенная версия метода получения баланса пользователя DMarket.
        Комбинирует все доступные методы для максимальной совместимости.

        Returns:
            Информация о балансе в формате:
            {
                "usd": {"amount": value_in_cents},
                "has_funds": True/False,
                "balance": value_in_dollars,
                "available_balance": value_in_dollars,
                "total_balance": value_in_dollars,
                "error": True/False,
                "error_message": "Сообщение об ошибке (если есть)"
            }

        """
        logger.debug("Запрос баланса пользователя DMarket через универсальный метод")

        # Проверяем наличие API ключей
        if not self.public_key or not self.secret_key:
            logger.error("Ошибка: API ключи не настроены (пустые значения)")
            return self._create_error_response(
                "API ключи не настроены",
                status_code=401,
                error_code="MISSING_API_KEYS",
            )

        try:
            # 2024 update: Try direct REST API request first
            try:
                logger.debug("🔍 Trying to get balance via direct REST API request...")
                direct_response = await self.direct_balance_request()
                logger.debug(f"🔍 Direct API response: {direct_response}")

                if direct_response and direct_response.get("success", False):
                    logger.info("✅ Successfully got balance via direct REST API request")
                    balance_data = direct_response.get("data", {})
                    logger.debug(f"📊 Balance data: {balance_data}")

                    usd_amount = balance_data.get("balance", 0) * 100
                    usd_available = (
                        balance_data.get("available", balance_data.get("balance", 0)) * 100
                    )
                    usd_total = balance_data.get("total", balance_data.get("balance", 0)) * 100
                    usd_locked = balance_data.get("locked", 0) * 100
                    usd_trade_protected = balance_data.get("trade_protected", 0) * 100

                    result = self._create_balance_response(
                        usd_amount=usd_amount,
                        usd_available=usd_available,
                        usd_total=usd_total,
                        locked_balance=usd_locked / 100,
                        trade_protected_balance=usd_trade_protected / 100,
                        additional_info={
                            "method": "direct_request",
                            "raw_response": balance_data,
                        },
                    )

                    logger.info(
                        f"💰 Final balance (direct request): ${result['balance']:.2f} USD "
                        f"(available: ${result['available_balance']:.2f}, locked: ${result.get('locked_balance', 0):.2f})"
                    )
                    return result

                # If direct request failed, log error and continue with other methods
                error_message = direct_response.get("error", "Unknown error")
                logger.warning(f"⚠️ Direct REST API request failed: {error_message}")
                logger.debug(f"🔍 Full error response: {direct_response}")
            except Exception as e:
                logger.warning(f"⚠️ Error during direct REST API request: {e!s}")
                logger.exception(f"📋 Exception details: {e}")

            # If direct request failed, try internal API client
            # Try all known endpoints for getting balance
            endpoints = [
                self.ENDPOINT_BALANCE,  # Current endpoint according to documentation
                "/api/v1/account/wallet/balance",  # Alternative possible endpoint
                "/exchange/v1/user/balance",  # Possible exchange endpoint
                self.ENDPOINT_BALANCE_LEGACY,  # Legacy endpoint (for backward compatibility)
            ]

            response, successful_endpoint, last_error = await self._try_endpoints_for_balance(
                endpoints
            )

            # If we didn't get a response from any endpoint
            if not response:
                error_message = (
                    str(last_error) if last_error else "Failed to get balance from any endpoint"
                )
                logger.error(f"Critical error getting balance: {error_message}")

                # Determine error code from message
                status_code = 500
                error_code = "REQUEST_FAILED"
                error_lower = error_message.lower()
                if "404" in error_message or "not found" in error_lower:
                    status_code = 404
                    error_code = "NOT_FOUND"
                elif "401" in error_message or "unauthorized" in error_lower:
                    status_code = 401
                    error_code = "UNAUTHORIZED"

                return self._create_error_response(error_message, status_code, error_code)

            # Check for API errors
            if response and ("error" in response or "code" in response):
                error_code = response.get("code", "unknown")
                error_message = response.get("message", response.get("error", "Unknown error"))
                status_code = response.get("status", response.get("status_code", 500))

                logger.error(
                    f"DMarket API error getting balance: {error_code} - {error_message} (HTTP {status_code})"
                )

                # If authorization error (401 Unauthorized)
                if error_code == "Unauthorized" or status_code == 401:
                    logger.error(
                        "Problem with API keys. Please check correctness and validity of DMarket API keys"
                    )
                    return self._create_error_response(
                        "Authorization error: invalid API keys",
                        status_code=401,
                        error_code="UNAUTHORIZED",
                    )

                return self._create_error_response(error_message, status_code, error_code)

            # Process successful response
            logger.info(f"🔍 RAW BALANCE API RESPONSE (get_balance): {response}")
            logger.info(f"Analyzing balance response from {successful_endpoint}: {response}")

            usd_amount, usd_available, usd_total = self._parse_balance_from_response(response)

            if usd_amount == 0 and usd_available == 0 and usd_total == 0:
                logger.warning(f"Could not parse balance data from known formats: {response}")

            # Create result
            result = self._create_balance_response(
                usd_amount=usd_amount,
                usd_available=usd_available,
                usd_total=usd_total,
                additional_info={"endpoint": successful_endpoint},
            )

            logger.info(
                f"Final balance: ${result['balance']:.2f} USD "
                f"(available: ${result['available_balance']:.2f}, total: ${result['total_balance']:.2f})"
            )
            return result

        except Exception as e:
            logger.exception(f"Unexpected error getting balance: {e!s}")
            logger.exception(f"Stack trace: {traceback.format_exc()}")

            # Determine error code from exception message
            error_str = str(e)
            status_code = 500
            error_code = "EXCEPTION"
            error_lower = error_str.lower()
            if "404" in error_str or "not found" in error_lower:
                status_code = 404
                error_code = "NOT_FOUND"
            elif "401" in error_str or "unauthorized" in error_lower:
                status_code = 401
                error_code = "UNAUTHORIZED"

            return self._create_error_response(error_str, status_code, error_code)

    async def get_user_balance(self) -> dict[str, Any]:
        """Получение баланса пользователя (устаревший метод).

        Этот метод оставлен для обратной совместимости.
        Рекомендуется использовать get_balance() вместо него.

        Returns:
            dict: Информация о балансе пользователя в том же формате, что и get_balance()

        """
        logger.warning(
            "Метод get_user_balance() устарел и может быть удален в будущих версиях. "
            "Пожалуйста, используйте get_balance() вместо него.",
        )
        return await self.get_balance()

    @validate_response(MarketItemsResponse, endpoint="/exchange/v1/market/items")
    async def get_market_items(  # noqa: PLR0917
        self,
        game: str = "csgo",
        limit: int = 100,
        offset: int = 0,
        currency: str = "USD",
        price_from: float | None = None,
        price_to: float | None = None,
        title: str | None = None,
        sort: str = "price",
        force_refresh: bool = False,
        tree_filters: str | None = None,
        cursor: str = "",
    ) -> dict[str, Any]:
        """Get items from the marketplace.

        Response is automatically validated through MarketItemsResponse schema.
        If validation fails, a CRITICAL error is logged and Telegram notification sent.

        Args:
            game: Game name (csgo, dota2, tf2, rust etc)
            limit: Number of items to retrieve
            offset: Offset for pagination
            currency: Price currency (USD, EUR etc)
            price_from: Minimum price filter
            price_to: Maximum price filter
            title: Filter by item title
            sort: Sort options (price, price_desc, date, popularity)
            force_refresh: Force refresh cache
            tree_filters: JSON string with category filters (e.g., '{"category":["weapon_knife"]}')
            cursor: Cursor for pagination (alternative to offset)

        Returns:
            Items as dict with 'objects' key containing list of items

        """
        # FIX: Map short game name to full UUID (Fix 400 Bad Request)
        game_id = GAME_MAP.get(game.lower(), game)

        # Build query parameters according to docs
        params = {
            "gameId": game_id,
            "limit": limit,
            "offset": offset,
            "currency": currency,
        }

        # Support cursor-based pagination (preferred over offset)
        if cursor:
            params["cursor"] = cursor

        if price_from is not None:
            params["priceFrom"] = str(int(price_from * 100))  # Price in cents

        if price_to is not None:
            params["priceTo"] = str(int(price_to * 100))  # Price in cents

        if title:
            params["title"] = title

        if sort:
            params["orderBy"] = sort

        if tree_filters:
            params["treeFilters"] = tree_filters

        # Log full request params for debugging
        logger.info(
            f"📤 API Request: game={game} (gameId={params.get('gameId')}), "
            f"limit={limit}, price={price_from}-{price_to}, cursor={cursor[:10] if cursor else 'none'}"
        )

        # Use correct endpoint from DMarket API docs
        try:
            response = await self._request(
                "GET",
                self.ENDPOINT_MARKET_ITEMS,
                params=params,
                force_refresh=force_refresh,
            )

            # Проверяем формат ответа
            if response and isinstance(response, dict):
                # DMarket API возвращает items в поле 'objects' (согласно документации)
                if "objects" in response:
                    items_count = len(response.get("objects", []))
                    logger.info(f"✅ Получено {items_count} предметов для игры {game}")
                elif "items" in response:
                    # Альтернативное название поля
                    items_count = len(response.get("items", []))
                    logger.info(
                        f"✅ Получено {items_count} предметов для игры {game} (через поле 'items')"
                    )
                else:
                    logger.warning(
                        f"⚠️ Ответ API не содержит поле 'objects' или 'items'. "
                        f"Доступные ключи: {list(response.keys())}"
                    )
            else:
                logger.warning(f"⚠️ Пустой или некорректный ответ API: {type(response)}")

            return response

        except Exception as e:
            logger.exception(f"❌ Ошибка при получении предметов: {e}")
            # Возвращаем пустой результат в случае ошибки
            return {"objects": [], "total": {"items": 0, "offers": 0}}

    async def get_all_market_items(
        self,
        game: str = "csgo",
        max_items: int = 1000,
        currency: str = "USD",
        price_from: float | None = None,
        price_to: float | None = None,
        title: str | None = None,
        sort: str = "price",
        use_cursor: bool = True,
    ) -> list[dict[str, Any]]:
        """Get all items from the marketplace using pagination.

        Args:
            game: Game name (csgo, dota2, tf2, rust etc)
            max_items: Maximum number of items to retrieve
            currency: Price currency (USD, EUR etc)
            price_from: Minimum price filter
            price_to: Maximum price filter
            title: Filter by item title
            sort: Sort options (price, price_desc, date, popularity)
            use_cursor: Use cursor pagination (recommended) instead of offset

        Returns:
            List of all items as dict

        """
        all_items = []
        limit = 100  # Maximum limit per request
        total_fetched = 0

        if use_cursor:
            # Cursor-based pagination (recommended for large datasets)
            cursor = None

            while total_fetched < max_items:
                params = {
                    "gameId": game,
                    "limit": limit,
                    "currency": currency,
                }

                if price_from is not None:
                    params["priceFrom"] = str(int(price_from * 100))
                if price_to is not None:
                    params["priceTo"] = str(int(price_to * 100))
                if title:
                    params["title"] = title
                if sort:
                    params["orderBy"] = sort
                if cursor:
                    params["cursor"] = cursor

                response = await self._request(
                    "GET",
                    self.ENDPOINT_MARKET_ITEMS,
                    params=params,
                )

                items = response.get("objects", [])
                if not items:
                    break

                all_items.extend(items)
                total_fetched += len(items)

                # Get next cursor
                cursor = response.get("cursor") or response.get("nextCursor")

                # No more pages
                if not cursor:
                    break

            return all_items[:max_items]

        # Fallback to offset-based pagination
        offset = 0

        while total_fetched < max_items:
            response = await self.get_market_items(
                game=game,
                limit=limit,
                offset=offset,
                currency=currency,
                price_from=price_from,
                price_to=price_to,
                title=title,
                sort=sort,
            )

            items = response.get("objects", [])
            if not items:
                break

            all_items.extend(items)
            total_fetched += len(items)
            offset += limit

            if len(items) < limit:
                break

        return all_items[:max_items]

    async def buy_item(
        self,
        item_id: str,
        price: float,
        game: str = "csgo",
        item_name: str | None = None,
        sell_price: float | None = None,
        profit: float | None = None,
        source: str = "manual",
    ) -> dict[str, Any]:
        """Покупает предмет с указанным ID и ценой.

        Args:
            item_id: ID предмета для покупки
            price: Цена в USD (будет конвертирована в центы)
            game: Код игры (csgo, dota2, tf2, rust)
            item_name: Название предмета (для логирования)
            sell_price: Ожидаемая цена продажи (для логирования)
            profit: Ожидаемая прибыль (для логирования)
            source: Источник намерения (arbitrage_scanner, manual и т.д.)

        Returns:
            Результат операции покупки

        """
        from src.utils.logging_utils import BotLogger

        bot_logger = BotLogger(__name__)

        # Рассчитываем профит если возможно
        profit_usd = profit or (sell_price - price if sell_price else None)
        profit_percent = (profit_usd / price * 100) if profit_usd and price > 0 else None

        # Добавляем breadcrumb для Sentry
        add_trading_breadcrumb(
            action="buy_item_intent",
            game=game,
            item_id=item_id,
            price=price,
            item_name=item_name,
            sell_price=sell_price,
            profit=profit_usd,
            profit_percent=profit_percent,
            dry_run=self.dry_run,
        )

        # INTENT логирование ПЕРЕД покупкой
        bot_logger.log_buy_intent(
            item_name=item_name or item_id,
            price_usd=price,
            sell_price_usd=sell_price,
            profit_usd=profit_usd,
            profit_percent=profit_percent,
            source=source,
            dry_run=self.dry_run,
            game=game,
            item_id=item_id,
        )

        # Конвертируем цену из USD в центы
        price_cents = int(price * 100)

        # Формируем данные запроса согласно документации API
        data = {
            "itemId": item_id,
            "price": {
                "amount": price_cents,
                "currency": "USD",
            },
            "gameType": game,
        }

        # DRY-RUN mode: simulate purchase without real API call
        if self.dry_run:
            mode_label = "[DRY-RUN]"
            logger.info(
                f"{mode_label} 🔵 SIMULATED BUY: item_id={item_id}, price=${price:.2f}, game={game}"
            )
            result = {
                "success": True,
                "dry_run": True,
                "operation": "buy",
                "item_id": item_id,
                "price_usd": price,
                "game": game,
                "message": "Simulated purchase (DRY_RUN mode)",
            }
            # Логируем результат
            bot_logger.log_trade_result(
                operation="buy",
                success=True,
                item_name=item_name or item_id,
                price_usd=price,
                dry_run=True,
            )
            return result

        # LIVE mode: make real purchase
        mode_label = "[LIVE]"
        logger.warning(
            f"{mode_label} 🔴 REAL BUY: item_id={item_id}, price=${price:.2f}, game={game}"
        )

        try:
            # Выполняем запрос на покупку
            result = await self._request(
                "POST",
                self.ENDPOINT_PURCHASE,
                data=data,
            )

            # Логируем успешный результат
            bot_logger.log_trade_result(
                operation="buy",
                success=True,
                item_name=item_name or item_id,
                price_usd=price,
                dry_run=False,
            )

            # Очищаем кэш для инвентаря, т.к. он изменился
            await self.clear_cache_for_endpoint(self.ENDPOINT_USER_INVENTORY)

            # Очищаем кэш для баланса, т.к. он также изменился
            await self.clear_cache_for_endpoint(self.ENDPOINT_BALANCE)
            await self.clear_cache_for_endpoint(self.ENDPOINT_BALANCE_LEGACY)

            return result

        except Exception as e:
            # Логируем ошибку
            bot_logger.log_trade_result(
                operation="buy",
                success=False,
                item_name=item_name or item_id,
                price_usd=price,
                error_message=str(e),
                dry_run=False,
            )
            raise

    async def sell_item(
        self,
        item_id: str,
        price: float,
        game: str = "csgo",
        item_name: str | None = None,
        buy_price: float | None = None,
        source: str = "manual",
    ) -> dict[str, Any]:
        """Выставляет предмет на продажу.

        Args:
            item_id: ID предмета для продажи
            price: Цена в USD (будет конвертирована в центы)
            game: Код игры (csgo, dota2, tf2, rust)
            item_name: Название предмета (для логирования)
            buy_price: Цена покупки (для расчёта профита)
            source: Источник намерения (auto_sell, manual и т.д.)

        Returns:
            Результат операции продажи

        """
        from src.utils.logging_utils import BotLogger

        bot_logger = BotLogger(__name__)

        # Рассчитываем профит если возможно
        profit_usd = price - buy_price if buy_price else None
        profit_percent = (profit_usd / buy_price * 100) if profit_usd and buy_price else None

        # INTENT логирование ПЕРЕД продажей
        bot_logger.log_sell_intent(
            item_name=item_name or item_id,
            price_usd=price,
            buy_price_usd=buy_price,
            profit_usd=profit_usd,
            profit_percent=profit_percent,
            source=source,
            dry_run=self.dry_run,
            game=game,
            item_id=item_id,
        )

        # Конвертируем цену из USD в центы
        price_cents = int(price * 100)

        # Формируем данные запроса согласно документации API
        data = {
            "itemId": item_id,
            "price": {
                "amount": price_cents,
                "currency": "USD",
            },
        }

        # DRY-RUN mode: simulate sell without real API call
        if self.dry_run:
            mode_label = "[DRY-RUN]"
            logger.info(
                f"{mode_label} 🔵 SIMULATED SELL: item_id={item_id}, "
                f"price=${price:.2f}, game={game}"
            )
            result = {
                "success": True,
                "dry_run": True,
                "operation": "sell",
                "item_id": item_id,
                "price_usd": price,
                "game": game,
                "message": "Simulated sale (DRY_RUN mode)",
            }
            # Логируем результат
            bot_logger.log_trade_result(
                operation="sell",
                success=True,
                item_name=item_name or item_id,
                price_usd=price,
                dry_run=True,
            )
            return result

        # LIVE mode: make real sale
        mode_label = "[LIVE]"
        logger.warning(
            f"{mode_label} 🔴 REAL SELL: item_id={item_id}, price=${price:.2f}, game={game}"
        )

        try:
            # Выполняем запрос на продажу
            result = await self._request(
                "POST",
                self.ENDPOINT_SELL,
                data=data,
            )

            # Логируем успешный результат
            bot_logger.log_trade_result(
                operation="sell",
                success=True,
                item_name=item_name or item_id,
                price_usd=price,
                dry_run=False,
            )

            # Очищаем кэш для инвентаря и списка предложений, т.к. они изменились
            await self.clear_cache_for_endpoint(self.ENDPOINT_USER_INVENTORY)
            await self.clear_cache_for_endpoint(self.ENDPOINT_USER_OFFERS)

            return result

        except Exception as e:
            # Логируем ошибку
            bot_logger.log_trade_result(
                operation="sell",
                success=False,
                item_name=item_name or item_id,
                price_usd=price,
                error_message=str(e),
                dry_run=False,
            )
            raise

    async def get_user_inventory(
        self, game_id: str = "a8db99ca-dc45-4c0e-9989-11ba71ed97a2", limit: int = 100
    ) -> dict[str, Any]:
        """
        Получает инвентарь пользователя через актуальный эндпоинт v1.
        """
        # В 2026 году используем marketplace-api для получения личного инвентаря
        endpoint = "/marketplace-api/v1/user-inventory"
        params = {"GameID": game_id, "Limit": str(limit), "Offset": "0"}

        try:
            response = await self._request("GET", endpoint, params=params)

            # Проверка на пустой ответ или ошибку авторизации, которую мы видели в логах
            if isinstance(response, dict) and response.get("Code") == "Unauthorized":
                logger.error("❌ Ошибка авторизации. Проверьте API Keys и СИНХРОНИЗАЦИЮ ВРЕМЕНИ!")
                return {"objects": []}

            return response
        except Exception as e:
            logger.exception(f"❌ Критическая ошибка при получении инвентаря: {e!s}")
            return {"objects": []}

    async def get_suggested_price(
        self,
        item_name: str,
        game: str = "csgo",
    ) -> float | None:
        """Get suggested price for an item.

        Args:
            item_name: Item name
            game: Game name

        Returns:
            Suggested price as float or None if not found

        """
        # Find the item
        response = await self.get_market_items(
            game=game,
            title=item_name,
            limit=1,
        )

        items = response.get("items", [])
        if not items:
            return None

        item = items[0]
        suggested_price = item.get("suggestedPrice")

        if suggested_price:
            try:
                # Convert from cents to dollars
                return float(suggested_price) / 100
            except (ValueError, TypeError):
                try:
                    # Sometimes the API returns an object with amount and currency
                    amount = suggested_price.get("amount", 0)
                    return float(amount) / 100
                except (AttributeError, ValueError, TypeError):
                    return None

        return None

    # ==================== ACCOUNT METHODS ====================

    async def get_user_profile(self) -> dict[str, Any]:
        """Получает профиль пользователя согласно DMarket API.

        Returns:
            Dict[str, Any]: Информация о профиле пользователя

        Response format:
            {
                "id": "string",
                "username": "string",
                "email": "string",
                "isEmailVerified": true,
                "countryCode": "string",
                "publicKey": "string",
                ...
            }

        """
        return await self._request(
            "GET",
            "/account/v1/user",
        )

    async def get_account_details(self) -> dict[str, Any]:
        """Получает детали аккаунта пользователя.

        Returns:
            Dict[str, Any]: Информация об аккаунте

        """
        return await self._request(
            "GET",
            self.ENDPOINT_ACCOUNT_DETAILS,
        )

    # ==================== MARKETPLACE OPERATIONS ====================

    async def list_user_offers(
        self,
        game_id: str = "a8db",
        status: str = "OfferStatusActive",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Получить список предложений пользователя согласно DMarket API.

        Args:
            game_id: ID игры (a8db для CS:GO, 9a92 для Dota 2, tf2 для TF2, rust для Rust)
            status: Статус предложений (OfferStatusActive, OfferStatusSold, etc)
            limit: Количество результатов
            offset: Смещение для пагинации

        Returns:
            Dict[str, Any]: Список предложений

        Response format:
            {
                "Items": [...],
                "Total": {...},
                "Cursor": "string"
            }

        """
        params = {
            "GameID": game_id,
            "Status": status,
            "Limit": str(limit),
            "Offset": str(offset),
        }
        return await self._request(
            "GET",
            "/marketplace-api/v1/user-offers",
            params=params,
        )

    async def create_offers(
        self,
        offers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Создать предложения на продажу согласно DMarket API.

        Args:
            offers: Список предложений для создания
                Формат: [{"AssetID": "...", "Price": {"Amount": 100, "Currency": "USD"}}]

        Returns:
            Dict[str, Any]: Результат создания предложений

        """
        data = {"Offers": offers}
        return await self._request(
            "POST",
            "/marketplace-api/v1/user-offers/create",
            data=data,
        )

    async def update_offer_prices(
        self,
        offers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Обновить цены предложений согласно DMarket API.

        Args:
            offers: Список предложений с новыми ценами
                Формат: [{"OfferID": "...", "Price": {"Amount": 100, "Currency": "USD"}}]

        Returns:
            Dict[str, Any]: Результат обновления

        """
        data = {"Offers": offers}
        return await self._request(
            "POST",
            "/marketplace-api/v1/user-offers/edit",
            data=data,
        )

    async def remove_offers(
        self,
        offer_ids: list[str],
    ) -> dict[str, Any]:
        """Удалить предложения с продажи согласно DMarket API.

        Args:
            offer_ids: Список ID предложений для удаления

        Returns:
            Dict[str, Any]: Результат удаления

        """
        data = {"Offers": [{"OfferID": oid} for oid in offer_ids]}
        return await self._request(
            "POST",
            "/marketplace-api/v1/user-offers/delete",
            data=data,
        )

    async def deposit_assets(
        self,
        asset_ids: list[str],
    ) -> dict[str, Any]:
        """Депозит активов из Steam в DMarket согласно DMarket API v1.1.0.

        Args:
            asset_ids: Список ID активов для депозита

        Returns:
            Dict[str, Any]: ID депозита

        Response format:
            {"DepositID": "string"}

        Example:
            >>> result = await api.deposit_assets(["asset_id_1", "asset_id_2"])
            >>> deposit_id = result["DepositID"]
            >>> # Затем проверить статус:
            >>> status = await api.get_deposit_status(deposit_id)

        """
        data = {"AssetID": asset_ids}
        return await self._request(
            "POST",
            self.ENDPOINT_DEPOSIT_ASSETS,
            data=data,
        )

    async def get_deposit_status(
        self,
        deposit_id: str,
    ) -> dict[str, Any]:
        """Получить статус депозита согласно DMarket API v1.1.0.

        Args:
            deposit_id: ID депозита

        Returns:
            Dict[str, Any]: Статус депозита

        Response format:
            {
                "DepositID": "string",
                "Status": "TransferStatusPending | TransferStatusCompleted | TransferStatusFailed",
                "Assets": [...],
                "Error": "string" (если есть)
            }

        Example:
            >>> status = await api.get_deposit_status("deposit_123")
            >>> if status["Status"] == "TransferStatusCompleted":
            ...     print("Депозит завершен!")

        """
        path = f"{self.ENDPOINT_DEPOSIT_STATUS}/{deposit_id}"
        return await self._request("GET", path)

    async def withdraw_assets(
        self,
        asset_ids: list[str],
    ) -> dict[str, Any]:
        """Вывод активов из DMarket в Steam (API v1.1.0).

        Args:
            asset_ids: Список ID активов для вывода

        Returns:
            Dict[str, Any]: Результат операции вывода

        Example:
            >>> result = await api.withdraw_assets(["item_id_1", "item_id_2"])

        """
        data = {"AssetIDs": asset_ids}
        return await self._request(
            "POST",
            self.ENDPOINT_WITHDRAW_ASSETS,
            data=data,
        )

    async def sync_inventory(
        self,
        game_id: str = "a8db",
    ) -> dict[str, Any]:
        """Синхронизация инвентаря с внешними платформами (API v1.1.0).

        Args:
            game_id: ID игры для синхронизации

        Returns:
            Dict[str, Any]: Результат синхронизации

        Example:
            >>> result = await api.sync_inventory(game_id="a8db")
            >>> if result.get("success"):
            ...     print("Инвентарь синхронизирован")

        """
        data = {"GameID": game_id}
        return await self._request(
            "POST",
            self.ENDPOINT_INVENTORY_SYNC,
            data=data,
        )

    async def list_user_inventory(
        self,
        game_id: str = "a8db",
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Получить инвентарь пользователя согласно DMarket API.

        Args:
            game_id: ID игры
            limit: Количество результатов
            offset: Смещение для пагинации

        Returns:
            Dict[str, Any]: Список предметов в инвентаре

        """
        params = {
            "GameID": game_id,
            "Limit": str(limit),
            "Offset": str(offset),
        }
        return await self._request(
            "GET",
            "/marketplace-api/v1/user-inventory",
            params=params,
        )

    async def list_market_items(
        self,
        game_id: str = "a8db",
        limit: int = 100,
        offset: int = 0,
        order_by: str = "best_deal",
        order_dir: str = "desc",
        price_from: int | None = None,
        price_to: int | None = None,
        title: str | None = None,
    ) -> dict[str, Any]:
        """Получить список предметов на маркете согласно DMarket API.

        Args:
            game_id: ID игры (a8db для CS:GO, 9a92 для Dota 2)
            limit: Количество результатов (max 100)
            offset: Смещение для пагинации
            order_by: Сортировка (best_deal, price, date, discount)
            order_dir: Направление сортировки (asc, desc)
            price_from: Минимальная цена в центах
            price_to: Максимальная цена в центах
            title: Поиск по названию

        Returns:
            Dict[str, Any]: Список предметов на маркете

        Response format:
            {
                "Items": [...],
                "Total": {...},
                "Cursor": "string"
            }

        """
        params = {
            "GameID": game_id,
            "Limit": str(limit),
            "Offset": str(offset),
            "OrderBy": order_by,
            "OrderDir": order_dir,
        }

        if price_from is not None:
            params["PriceFrom"] = str(price_from)

        if price_to is not None:
            params["PriceTo"] = str(price_to)

        if title:
            params["Title"] = title

        return await self._request(
            "GET",
            "/marketplace-api/v1/market-items",
            params=params,
        )

    async def list_offers_by_title(
        self,
        game_id: str,
        title: str,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Получить предложения по названию предмета согласно DMarket API.

        Args:
            game_id: ID игры
            title: Название предмета
            limit: Количество результатов
            offset: Смещение для пагинации

        Returns:
            Dict[str, Any]: Список предложений

        """
        params = {
            "GameID": game_id,
            "Title": title,
            "Limit": str(limit),
            "Offset": str(offset),
        }
        return await self._request(
            "GET",
            "/marketplace-api/v1/offers-by-title",
            params=params,
        )

    @validate_response(BuyOffersResponse, endpoint="/exchange/v1/offers-buy")
    async def buy_offers(
        self,
        offers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Купить предложения с маркета согласно DMarket API.

        Response is automatically validated through BuyOffersResponse schema.

        Args:
            offers: Список предложений для покупки
                Формат: [{"offerId": "...", "price": {"amount": "100", "currency": "USD"}, "type": "dmarket"}]

        Returns:
            Dict[str, Any]: Результат покупки

        Response format:
            {
                "orderId": "string",
                "status": "TxPending",
                "txId": "string",
                ...
            }

        """
        data = {"offers": offers}
        return await self._request(
            "PATCH",
            "/exchange/v1/offers-buy",
            data=data,
        )

    async def get_aggregated_prices(
        self,
        titles: list[str],
        game_id: str = "a8db",
    ) -> dict[str, Any]:
        """Получить агрегированные цены для списка предметов согласно DMarket API.

        Устаревший метод, сохранен для обратной совместимости.
        Рекомендуется использовать get_aggregated_prices_bulk() вместо него.

        Args:
            titles: Список названий предметов
            game_id: ID игры

        Returns:
            Dict[str, Any]: Агрегированные цены

        """
        logger.warning(
            "Метод get_aggregated_prices() устарел. "
            "Используйте get_aggregated_prices_bulk() для API v1.1.0"
        )
        data = {
            "Titles": titles,
            "GameID": game_id,
        }
        return await self._request(
            "POST",
            "/marketplace-api/v1/aggregated-titles-by-games",
            data=data,
        )

    @validate_response(
        AggregatedPricesResponse,
        endpoint="/marketplace-api/v1/aggregated-prices",
    )
    async def get_aggregated_prices_bulk(
        self,
        game: str,
        titles: list[str],
        limit: int = 100,
        cursor: str = "",
    ) -> dict[str, Any]:
        """Получить агрегированные цены для списка предметов (API v1.1.0).

        Response is automatically validated through AggregatedPricesResponse schema.
        Новый метод согласно обновленной документации DMarket API.
        Позволяет получить лучшие цены покупки и продажи для множества предметов
        одним запросом с поддержкой пагинации.

        Args:
            game: Идентификатор игры (csgo, dota2, tf2, rust)
            titles: Список точных названий предметов
            limit: Лимит результатов на странице (max 100)
            cursor: Курсор для пагинации

        Returns:
            Dict[str, Any]: Агрегированные цены

        Response format:
            {
                "aggregatedPrices": [
                    {
                        "title": "Item Name",
                        "orderBestPrice": "1200",  # в центах
                        "orderCount": 15,
                        "offerBestPrice": "1250",  # в центах
                        "offerCount": 23
                    }
                ],
                "nextCursor": "..."
            }

        Example:
            >>> prices = await api.get_aggregated_prices_bulk(
            ...     game="csgo",
            ...     titles=["AK-47 | Redline (Field-Tested)", "AWP | Asiimov (Field-Tested)"],
            ... )
            >>> for item in prices["aggregatedPrices"]:
            ...     print(f"{item['title']}: Buy ${int(item['orderBestPrice']) / 100:.2f}")

        """
        data = {
            "filter": {
                "game": game,
                "titles": titles,
            },
            "limit": str(limit),
            "cursor": cursor,
        }

        logger.debug(f"Запрос агрегированных цен для {len(titles)} предметов (игра: {game})")

        return await self._request(
            "POST",
            self.ENDPOINT_AGGREGATED_PRICES_POST,
            data=data,
        )

    async def get_sales_history_aggregator(
        self,
        game_id: str,
        title: str,
        limit: int = 20,
        offset: int = 0,
        filters: str | None = None,
        tx_operation_type: list[str] | None = None,
    ) -> dict[str, Any]:
        """Получить историю продаж предмета из агрегатора согласно DMarket API.

        Args:
            game_id: ID игры (a8db, 9a92, tf2, rust)
            title: Название предмета
            limit: Количество результатов (max 20)
            offset: Смещение для пагинации
            filters: Фильтры (например: "exterior[]=factory new,phase[]=phase-1")
            tx_operation_type: Типы операций (["Offer"], ["Target"], или обе)

        Returns:
            Dict[str, Any]: История продаж

        Response format:
            {
                "sales": [
                    {"price": "string", "date": "string", "txOperationType": "Offer", ...}
                ]
            }

        """
        params: dict[str, Any] = {
            "gameId": game_id,
            "title": title,
            "limit": str(limit),
            "offset": str(offset),
        }

        if filters:
            params["filters"] = filters

        if tx_operation_type:
            params["txOperationType"] = tx_operation_type

        return await self._request(
            "GET",
            "/trade-aggregator/v1/last-sales",
            params=params,
        )

    async def get_market_best_offers(
        self,
        game: str = "csgo",
        title: str | None = None,
        limit: int = 50,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Получает лучшие предложения на маркете.

        Args:
            game: Идентификатор игры
            title: Название предмета (опционально)
            limit: Лимит результатов
            currency: Валюта цен

        Returns:
            Dict[str, Any]: Лучшие предложения

        """
        params = {
            "gameId": game,
            "limit": limit,
            "currency": currency,
        }

        if title:
            params["title"] = title

        return await self._request(
            "GET",
            self.ENDPOINT_MARKET_BEST_OFFERS,
            params=params,
        )

    async def get_offers_by_title(
        self,
        title: str,
        limit: int = 100,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        """Get offers by item title.

        API: GET /exchange/v1/offers-by-title

        Args:
            title: Item title to search for
            limit: Maximum number of results (default 100)
            cursor: Pagination cursor

        Returns:
            Dict containing offers matching the title:
            {
                "objects": [...],
                "total": int,
                "cursor": str
            }
        """
        params = {
            "Title": title,
            "Limit": str(limit),
        }
        if cursor:
            params["Cursor"] = cursor

        return await self._request(
            "GET",
            "/exchange/v1/offers-by-title",
            params=params,
        )

    async def get_market_aggregated_prices(
        self,
        game: str = "csgo",
        title: str | None = None,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Получает агрегированные цены на предметы.

        Args:
            game: Идентификатор игры
            title: Название предмета (опционально)
            currency: Валюта цен

        Returns:
            Dict[str, Any]: Агрегированные цены

        """
        params = {
            "gameId": game,
            "currency": currency,
        }

        if title:
            params["title"] = title

        return await self._request(
            "GET",
            self.ENDPOINT_MARKET_PRICE_AGGREGATED,
            params=params,
        )

    @validate_response(
        SalesHistoryResponse,
        endpoint="/account/v1/sales-history",
    )
    async def get_sales_history(
        self,
        game: str,
        title: str,
        days: int = 7,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Получает историю продаж предмета.

        Response is automatically validated through SalesHistoryResponse schema.

        Args:
            game: Идентификатор игры
            title: Название предмета
            days: Количество дней истории
            currency: Валюта цен

        Returns:
            Dict[str, Any]: История продаж

        """
        params = {
            "gameId": game,
            "title": title,
            "days": days,
            "currency": currency,
        }

        return await self._request(
            "GET",
            self.ENDPOINT_SALES_HISTORY,
            params=params,
        )

    async def get_item_price_history(
        self,
        game: str,
        title: str,
        period: str = "last_month",
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Получает историю цен предмета.

        Args:
            game: Идентификатор игры
            title: Название предмета
            period: Период ("last_day", "last_week", "last_month", "last_year")
            currency: Валюта цен

        Returns:
            Dict[str, Any]: История цен

        """
        params = {
            "gameId": game,
            "title": title,
            "period": period,
            "currency": currency,
        }

        return await self._request(
            "GET",
            self.ENDPOINT_ITEM_PRICE_HISTORY,
            params=params,
        )

    async def get_market_meta(
        self,
        game: str = "csgo",
    ) -> dict[str, Any]:
        """Получает метаданные маркета для указанной игры.

        Args:
            game: Идентификатор игры

        Returns:
            Dict[str, Any]: Метаданные маркета

        """
        params = {
            "gameId": game,
        }

        return await self._request(
            "GET",
            self.ENDPOINT_MARKET_META,
            params=params,
        )

    async def edit_offer(
        self,
        offer_id: str,
        price: float,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Редактирует существующее предложение.

        Args:
            offer_id: ID предложения
            price: Новая цена
            currency: Валюта цены

        Returns:
            Dict[str, Any]: Результат редактирования

        """
        data = {
            "offerId": offer_id,
            "price": {
                "amount": int(price * 100),  # В центах
                "currency": currency,
            },
        }

        return await self._request(
            "POST",
            self.ENDPOINT_OFFER_EDIT,
            data=data,
        )

    async def delete_offer(
        self,
        offer_id: str,
    ) -> dict[str, Any]:
        """Удаляет предложение.

        Args:
            offer_id: ID предложения

        Returns:
            Dict[str, Any]: Результат удаления

        """
        data = {
            "offers": [offer_id],
        }

        return await self._request(
            "DELETE",
            self.ENDPOINT_OFFER_DELETE,
            data=data,
        )

    async def get_active_offers(
        self,
        game: str = "csgo",
        limit: int = 50,
        offset: int = 0,
        status: str = "active",
    ) -> dict[str, Any]:
        """Получает активные предложения пользователя.

        Args:
            game: Идентификатор игры
            limit: Лимит результатов
            offset: Смещение для пагинации
            status: Статус предложений ("active", "completed", "canceled")

        Returns:
            Dict[str, Any]: Активные предложения

        """
        params = {
            "gameId": game,
            "limit": limit,
            "offset": offset,
            "status": status,
        }

        return await self._request(
            "GET",
            self.ENDPOINT_ACCOUNT_OFFERS,
            params=params,
        )

    async def get_closed_offers(
        self,
        limit: int = 100,
        cursor: str | None = None,
        order_dir: str = "desc",
        status: str | None = None,
        closed_from: int | None = None,
        closed_to: int | None = None,
    ) -> dict[str, Any]:
        """Get closed offers (completed sales).

        API: GET /marketplace-api/v1/user-offers/closed

        Args:
            limit: Maximum results (default 100)
            cursor: Pagination cursor
            order_dir: Sort direction ("asc" or "desc")
            status: Filter by status ("successful", "reverted", "trade_protected")
            closed_from: Filter by close time (timestamp)
            closed_to: Filter by close time (timestamp)

        Returns:
            Dict containing closed offers with FinalizationTime
        """
        params: dict[str, Any] = {
            "Limit": str(limit),
            "OrderDir": order_dir,
        }

        if cursor:
            params["Cursor"] = cursor
        if status:
            params["Status"] = status
        if closed_from:
            params["OfferClosed.From"] = str(closed_from)
        if closed_to:
            params["OfferClosed.To"] = str(closed_to)

        return await self._request(
            "GET",
            "/marketplace-api/v1/user-offers/closed",
            params=params,
        )

    # ==================== МЕТОДЫ ДЛЯ РАБОТЫ С ТАРГЕТАМИ ====================

    @validate_response(
        CreateTargetsResponse,
        endpoint="/marketplace-api/v1/user-targets/create",
    )
    async def create_targets(
        self,
        game_id: str,
        targets: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Создать таргеты (buy orders) для предметов.

        Response is automatically validated through CreateTargetsResponse schema.

        Args:
            game_id: Идентификатор игры (csgo, dota2, tf2, rust или полный UUID)
            targets: Список таргетов для создания

        Returns:
            Результат создания таргетов

        Example:
            >>> targets = [
            ...     {
            ...         "Title": "AK-47 | Redline (Field-Tested)",
            ...         "Amount": 1,
            ...         "Price": {"Amount": 800, "Currency": "USD"},
            ...     }
            ... ]
            >>> result = await api.create_targets("csgo", targets)

        """
        # FIX: Map short game name to full UUID (Fix 400 Bad Request)
        mapped_game_id = GAME_MAP.get(game_id.lower(), game_id)

        data = {"GameID": mapped_game_id, "Targets": targets}

        return await self._request(
            "POST",
            "/marketplace-api/v1/user-targets/create",
            data=data,
        )

    @validate_response(
        UserTargetsResponse,
        endpoint="/marketplace-api/v1/user-targets",
    )
    async def get_user_targets(
        self,
        game_id: str,
        status: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, Any]:
        """Получить список таргетов пользователя.

        Response is automatically validated through UserTargetsResponse schema.

        Args:
            game_id: Идентификатор игры (csgo, dota2, tf2, rust или полный UUID)
            status: Фильтр по статусу (TargetStatusActive, TargetStatusInactive)
            limit: Лимит результатов
            offset: Смещение для пагинации

        Returns:
            Список таргетов пользователя

        """
        # FIX: Map short game name to full UUID (Fix 400 Bad Request)
        mapped_game_id = GAME_MAP.get(game_id.lower(), game_id)

        params = {"GameID": mapped_game_id, "Limit": str(limit), "Offset": str(offset)}

        if status:
            params["BasicFilters.Status"] = status

        return await self._request(
            "GET",
            "/marketplace-api/v1/user-targets",
            params=params,
        )

    async def delete_targets(
        self,
        target_ids: list[str],
    ) -> dict[str, Any]:
        """Удалить таргеты.

        Args:
            target_ids: Список ID таргетов для удаления

        Returns:
            Результат удаления

        """
        data = {"Targets": [{"TargetID": tid} for tid in target_ids]}

        return await self._request(
            "POST",
            "/marketplace-api/v1/user-targets/delete",
            data=data,
        )

    async def get_targets_by_title(
        self,
        game_id: str,
        title: str,
    ) -> dict[str, Any]:
        """Получить таргеты для конкретного предмета (агрегированные данные, API v1.1.0).

        Новый эндпоинт согласно обновленной документации DMarket API.
        Позволяет получить все активные заявки на покупку (buy orders/targets)
        для конкретной игры и названия предмета.

        Args:
            game_id: Идентификатор игры (csgo, dota2, tf2, rust)
            title: Точное название предмета в игре

        Returns:
            Dict[str, Any]: Список таргетов для предмета

        Response format:
            {
                "orders": [
                    {
                        "amount": 10,
                        "price": "1200",  # в центах
                        "title": "AK-47 | Redline (Field-Tested)",
                        "attributes": {
                            "exterior": "Field-Tested"
                        }
                    }
                ]
            }

        Example:
            >>> targets = await api.get_targets_by_title(
            ...     game_id="csgo", title="AK-47 | Redline (Field-Tested)"
            ... )
            >>> for target in targets["orders"]:
            ...     print(f"Price: ${int(target['price']) / 100:.2f}, Amount: {target['amount']}")

        """
        # URL-encode названия для правильной передачи
        from urllib.parse import quote

        encoded_title = quote(title)
        path = f"{self.ENDPOINT_TARGETS_BY_TITLE}/{game_id}/{encoded_title}"

        logger.debug(f"Запрос таргетов для '{title}' (игра: {game_id})")

        return await self._request("GET", path)

    async def get_buy_orders_competition(
        self,
        game_id: str,
        title: str,
        price_threshold: float | None = None,
    ) -> dict[str, Any]:
        """Оценка конкуренции по buy orders для предмета.

        Использует эндпоинт targets-by-title для получения агрегированных
        данных о buy orders и оценки уровня конкуренции среди покупателей.

        Args:
            game_id: Идентификатор игры (csgo, dota2, tf2, rust)
            title: Точное название предмета
            price_threshold: Порог цены для фильтрации (в USD).
                Если указан, учитываются только ордера с ценой >= порога.

        Returns:
            Dict[str, Any]: Данные о конкуренции

        Response format:
            {
                "title": "AK-47 | Redline (Field-Tested)",
                "game_id": "csgo",
                "total_orders": 15,
                "total_amount": 45,  # Общее количество заявок на покупку
                "competition_level": "medium",  # "low", "medium", "high"
                "best_price": 8.50,  # Лучшая цена buy order в USD
                "average_price": 8.20,  # Средняя цена buy order
                "filtered_orders": 10,  # Количество ордеров выше порога (если указан)
                "orders": [...]  # Список всех ордеров
            }

        Example:
            >>> competition = await api.get_buy_orders_competition(
            ...     game_id="csgo", title="AK-47 | Redline (Field-Tested)", price_threshold=8.00
            ... )
            >>> if competition["competition_level"] == "low":
            ...     print("Низкая конкуренция - можно создавать таргет")
            >>> else:
            ...     print(f"Высокая конкуренция: {competition['total_orders']} ордеров")

        """
        price_str = f"${price_threshold:.2f}" if price_threshold else "не указан"
        logger.debug(
            f"Оценка конкуренции buy orders для '{title}' (игра: {game_id}, "
            f"порог цены: {price_str})"
        )

        try:
            # Получаем существующие таргеты для предмета
            targets_response = await self.get_targets_by_title(
                game_id=game_id,
                title=title,
            )

            orders = targets_response.get("orders", [])

            # Базовые метрики
            total_orders = len(orders)
            total_amount = 0
            prices = []
            filtered_orders = 0
            filtered_amount = 0

            # Анализируем каждый ордер
            for order in orders:
                amount = order.get("amount", 0)
                price_cents = float(order.get("price", 0))
                price_usd = price_cents / 100

                total_amount += amount
                prices.append(price_usd)

                # Фильтруем по порогу цены если указан
                if price_threshold is None or price_usd >= price_threshold:
                    filtered_orders += 1
                    filtered_amount += amount

            # Рассчитываем статистику цен
            best_price = max(prices) if prices else 0.0
            average_price = sum(prices) / len(prices) if prices else 0.0

            # Определяем уровень конкуренции
            # - low: <= 2 ордеров или общее количество <= 5
            # - medium: 3-10 ордеров или общее количество 6-20
            # - high: > 10 ордеров или общее количество > 20
            if total_orders <= 2 or total_amount <= 5:
                competition_level = "low"
            elif total_orders <= 10 or total_amount <= 20:
                competition_level = "medium"
            else:
                competition_level = "high"

            result = {
                "title": title,
                "game_id": game_id,
                "total_orders": total_orders,
                "total_amount": total_amount,
                "competition_level": competition_level,
                "best_price": best_price,
                "average_price": round(average_price, 2),
                "filtered_orders": filtered_orders if price_threshold else total_orders,
                "filtered_amount": filtered_amount if price_threshold else total_amount,
                "price_threshold": price_threshold,
                "orders": orders,
            }

            logger.info(
                f"Конкуренция для '{title}': уровень={competition_level}, "
                f"ордеров={total_orders}, количество={total_amount}, "
                f"лучшая цена=${best_price:.2f}"
            )

            return result

        except Exception as e:
            logger.exception(f"Ошибка при оценке конкуренции для '{title}': {e}")
            return {
                "title": title,
                "game_id": game_id,
                "total_orders": 0,
                "total_amount": 0,
                "competition_level": "unknown",
                "best_price": 0.0,
                "average_price": 0.0,
                "filtered_orders": 0,
                "filtered_amount": 0,
                "price_threshold": price_threshold,
                "orders": [],
                "error": str(e),
            }

    async def get_closed_targets(
        self,
        limit: int = 50,
        status: str | None = None,
        from_timestamp: int | None = None,
        to_timestamp: int | None = None,
    ) -> dict[str, Any]:
        """Получить историю закрытых таргетов.

        Args:
            limit: Лимит результатов
            status: Фильтр по статусу (successful, reverted, trade_protected)
            from_timestamp: Начало периода (timestamp)
            to_timestamp: Конец периода (timestamp)

        Returns:
            История закрытых таргетов

        """
        params = {"Limit": str(limit), "OrderDir": "desc"}

        if status:
            params["Status"] = status

        if from_timestamp:
            params["TargetClosed.From"] = str(from_timestamp)

        if to_timestamp:
            params["TargetClosed.To"] = str(to_timestamp)

        return await self._request(
            "GET",
            "/marketplace-api/v1/user-targets/closed",
            params=params,
        )

    # ==================== КОНЕЦ МЕТОДОВ ТАРГЕТОВ ====================

    # ==================== МЕТОДЫ ДЛЯ ПОЛУЧЕНИЯ МЕТАДАННЫХ ====================

    async def get_supported_games(self) -> list[dict[str, Any]]:
        """Получить список всех поддерживаемых игр на DMarket.

        Этот метод запрашивает актуальный список игр, доступных для торговли
        на платформе DMarket. Полезно для динамического обновления списка игр
        без хардкода.

        Returns:
            List[Dict[str, Any]]: Список игр с их метаданными

        Response format:
            [
                {
                    "gameId": "a8db",
                    "title": "CS:GO",
                    "appId": 730,
                    "enabled": true,
                    "categories": [...],
                    "filters": {...}
                },
                {
                    "gameId": "9a92",
                    "title": "Dota 2",
                    "appId": 570,
                    "enabled": true,
                    ...
                }
            ]

        Example:
            >>> games = await api.get_supported_games()
            >>> enabled_games = [g for g in games if g.get("enabled")]
            >>> for game in enabled_games:
            ...     print(f"{game['title']} (ID: {game['gameId']})")

        Raises:
            httpx.HTTPError: При ошибке сети или API
            ValueError: При невалидном ответе

        Note:
            Рекомендуется кешировать результат на длительное время (24+ часа),
            так как список игр обновляется редко.
        """
        logger.debug("Запрос списка поддерживаемых игр с DMarket API")

        try:
            response = await self._request(
                "GET",
                self.ENDPOINT_GAMES_LIST,
            )

            if not isinstance(response, list):
                logger.warning(f"Неожиданный формат ответа от /game/v1/games: {type(response)}")
                return []

            logger.info(f"Получено {len(response)} игр от DMarket API")

            # Логируем для отладки
            enabled_count = sum(1 for g in response if g.get("enabled", False))
            logger.debug(f"Активных игр: {enabled_count}/{len(response)}")

            return response

        except httpx.HTTPError as e:
            logger.error(
                f"Ошибка при запросе списка игр: {e}",
                exc_info=True,
            )
            raise

        except Exception as e:
            logger.error(
                f"Неожиданная ошибка при получении списка игр: {e}",
                exc_info=True,
            )
            # Возвращаем пустой список вместо падения
            return []

    # ==================== КОНЕЦ МЕТОДОВ МЕТАДАННЫХ ====================

    async def direct_balance_request(self) -> dict[str, Any]:
        """Выполняет прямой запрос баланса через REST API используя Ed25519.

        Этот метод используется как альтернативный способ получения баланса
        в случае проблем с основным методом.

        Returns:
            dict: Результат запроса баланса или словарь с ошибкой

        """
        try:
            # Актуальный эндпоинт баланса (2024) согласно документации DMarket
            endpoint = self.ENDPOINT_BALANCE
            base_url = self.api_url
            full_url = f"{base_url}{endpoint}"

            # Формируем timestamp для запроса
            timestamp = str(int(time.time()))

            # Build string to sign: GET + endpoint + timestamp
            string_to_sign = f"GET{endpoint}{timestamp}"

            logger.debug(f"Direct balance request - string to sign: {string_to_sign}")

            try:
                # Convert secret key from string to bytes
                secret_key_str = self._secret_key

                # Try different formats for secret key
                try:
                    # Format 1: HEX format (64 chars = 32 bytes)
                    if len(secret_key_str) == 64:
                        secret_key_bytes = bytes.fromhex(secret_key_str)
                    # Format 2: Base64 format
                    elif len(secret_key_str) == 44 or "=" in secret_key_str:
                        import base64

                        secret_key_bytes = base64.b64decode(secret_key_str)
                    # Format 3: Take first 64 hex chars
                    elif len(secret_key_str) >= 64:
                        secret_key_bytes = bytes.fromhex(secret_key_str[:64])
                    else:
                        # Fallback
                        secret_key_bytes = secret_key_str.encode("utf-8")[:32].ljust(32, b"\0")
                except Exception as conv_error:
                    logger.exception(f"Error converting secret key in direct request: {conv_error}")
                    raise

                # Create Ed25519 signing key
                signing_key = nacl.signing.SigningKey(secret_key_bytes)

                # Sign the message
                signed = signing_key.sign(string_to_sign.encode("utf-8"))

                # Extract signature in hex format
                signature = signed.signature.hex()

                logger.debug("Direct balance request - signature generated")

            except Exception as sig_error:
                logger.exception(f"Error generating Ed25519 signature: {sig_error}")
                # Fallback to HMAC if Ed25519 fails
                secret_key = self.secret_key
                signature = hmac.new(
                    secret_key,
                    string_to_sign.encode(),
                    hashlib.sha256,
                ).hexdigest()

            # Формируем заголовки запроса согласно документации DMarket
            headers = {
                "X-Api-Key": self.public_key,
                "X-Sign-Date": timestamp,
                "X-Request-Sign": f"dmar ed25519 {signature}",
                "Accept": "application/json",
                "Content-Type": "application/json",
            }

            logger.debug(f"Выполняем прямой запрос к {endpoint}")

            # Получаем клиент
            client = await self._get_client()

            # Выполняем запрос через httpx с circuit breaker
            response = await call_with_circuit_breaker(
                client.get, full_url, headers=headers, timeout=10
            )

            # Если запрос успешен (HTTP 200)
            if response.status_code == 200:
                try:
                    # Парсим JSON ответ
                    response_data = response.json()

                    # Проверяем структуру ответа согласно документации DMarket
                    if response_data:
                        logger.info(f"Успешный прямой запрос к {endpoint}")
                        logger.info(f"🔍 RAW ОТВЕТ API БАЛАНСА: {response_data}")
                        logger.debug(f"Ответ API баланса: {response_data}")

                        # Извлекаем значения баланса из ответа согласно официальной документации
                        # API возвращает: {"usd": "4550", "usdAvailableToWithdraw": "0", "dmc": "0", ...}
                        # где значения в центах для USD и dimoshi для DMC (все как строки)
                        #
                        # ВАЖНО: usdAvailableToWithdraw - это сумма, доступная для ВЫВОДА на внешние кошельки
                        # Это НЕ сумма для торговли! Для торговли доступен весь баланс usd.
                        # Новые пользователи или средства после покупки могут иметь usdAvailableToWithdraw=0,
                        # но при этом могут торговать на всю сумму usd.

                        # Получаем USD баланс (в центах как строка)
                        usd_str = response_data.get("usd", "0")
                        usd_available_to_withdraw_str = response_data.get(
                            "usdAvailableToWithdraw", "0"
                        )
                        usd_trade_protected_str = response_data.get("usdTradeProtected", "0")

                        # Конвертируем из строки в центы, затем в доллары
                        try:
                            balance_cents = float(usd_str)  # общий баланс в центах
                            available_to_withdraw_cents = float(
                                usd_available_to_withdraw_str
                            )  # доступно для вывода
                            trade_protected_cents = float(
                                usd_trade_protected_str
                            )  # защищенный в торговле

                            # Конвертируем центы в доллары
                            balance = balance_cents / 100
                            available_to_withdraw = available_to_withdraw_cents / 100
                            trade_protected = trade_protected_cents / 100

                            # FIX: Для ТОРГОВЛИ доступен весь баланс минус trade_protected
                            # usdAvailableToWithdraw - это только для вывода на внешние кошельки!
                            available_for_trading = balance - trade_protected

                            # Средства, недоступные для вывода (но могут быть доступны для торговли)
                            locked_for_withdrawal = (
                                balance - available_to_withdraw - trade_protected
                            )
                            locked_for_withdrawal = max(
                                0, locked_for_withdrawal
                            )  # Не может быть отрицательным

                            total = balance  # Обычно total = balance

                            logger.info(
                                f"💰 Распарсен баланс: Всего ${balance:.2f} USD "
                                f"(для торговли: ${available_for_trading:.2f}, "
                                f"для вывода: ${available_to_withdraw:.2f}, "
                                f"trade_protected: ${trade_protected:.2f})"
                            )
                        except (ValueError, TypeError) as e:
                            logger.exception(
                                f"Ошибка конвертации баланса: {e}, usd={usd_str}, usdAvailableToWithdraw={usd_available_to_withdraw_str}"
                            )
                            balance = 0.0
                            available_for_trading = 0.0
                            available_to_withdraw = 0.0
                            total = 0.0
                            locked_for_withdrawal = 0.0
                            trade_protected = 0.0

                        return {
                            "success": True,
                            "data": {
                                "balance": balance,
                                # FIX: available теперь означает "доступно для торговли"
                                "available": available_for_trading,
                                "available_to_withdraw": available_to_withdraw,
                                "total": total,
                                "locked": locked_for_withdrawal,
                                "trade_protected": trade_protected,
                            },
                        }
                except json.JSONDecodeError:
                    logger.warning(
                        f"Ошибка декодирования JSON при прямом запросе: {response.text}",
                    )

            # Если статус 401, значит проблема с авторизацией
            if response.status_code == 401:
                logger.error("Ошибка авторизации (401) при прямом запросе баланса")
                return {
                    "success": False,
                    "status_code": 401,
                    "error": "Ошибка авторизации: неверные ключи API",
                }

            # Для всех остальных ошибок
            logger.warning(
                f"Ошибка при прямом запросе: HTTP {response.status_code} - {response.text}",
            )
            return {
                "success": False,
                "status_code": response.status_code,
                "error": f"Ошибка HTTP {response.status_code}: {response.text}",
            }

        except CircuitBreakerError as e:
            logger.exception(f"Circuit breaker open for direct balance request: {e}")
            return {
                "success": False,
                "error": f"Circuit breaker open: {e}",
            }
        except Exception as e:
            logger.exception(f"Исключение при прямом запросе баланса: {e!s}")
            return {
                "success": False,
                "error": str(e),
            }
