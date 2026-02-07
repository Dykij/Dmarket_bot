"""Base DMarket API client logic."""

import asyncio
import hashlib
import hmac
import logging
import time
import traceback
from typing import Any, TYPE_CHECKING
import httpx
import nacl.signing
from src.utils import json_utils as json
from src.utils.api_circuit_breaker import call_with_circuit_breaker
from src.utils.rate_limiter import DMarketRateLimiter, RateLimiter
from src.utils.sentry_breadcrumbs import add_api_breadcrumb

if TYPE_CHECKING:
    from src.telegram_bot.notifier import Notifier

logger = logging.getLogger(__name__)

CACHE_TTL = {
    "short": 30,
    "medium": 300,
    "long": 1800,
}

api_cache: dict[str, Any] = {}

GAME_MAP: dict[str, str] = {
    "csgo": "a8db",
    "cs2": "a8db",
    "dota2": "9a92",
    "rust": "rust",
    "tf2": "tf2",
}

class BaseDMarketClient:
    """Core logic for DMarket API communication."""

    BASE_URL = "https://api.dmarket.com"

    # Баланс и аккаунт
    ENDPOINT_BALANCE = "/account/v1/balance"
    ENDPOINT_BALANCE_LEGACY = "/api/v1/account/balance"
    ENDPOINT_ACCOUNT_DETAILS = "/api/v1/account/details"
    ENDPOINT_ACCOUNT_OFFERS = "/api/v1/account/offers"

    # Маркет
    ENDPOINT_MARKET_ITEMS = "/exchange/v1/market/items"
    ENDPOINT_MARKET_PRICE_AGGREGATED = "/exchange/v1/market/aggregated-prices"
    ENDPOINT_MARKET_META = "/exchange/v1/market/meta"

    # Пользователь
    ENDPOINT_USER_INVENTORY = "/inventory/v1/user/items"
    ENDPOINT_USER_OFFERS = "/marketplace-api/v1/user-offers"
    ENDPOINT_USER_TARGETS = "/main/v2/user-targets"

    # Операции
    ENDPOINT_PURCHASE = "/exchange/v1/market/items/buy"
    ENDPOINT_SELL = "/exchange/v1/user/inventory/sell"
    ENDPOINT_SELL_CREATE = "/marketplace-api/v1/user-offers/create"
    ENDPOINT_OFFER_EDIT = "/exchange/v1/user-offers/edit"
    ENDPOINT_OFFER_DELETE = "/exchange/v1/user-offers/delete"

    # Статистика и аналитика
    ENDPOINT_SALES_HISTORY = "/account/v1/sales-history"
    ENDPOINT_ITEM_PRICE_HISTORY = "/exchange/v1/market/price-history"
    ENDPOINT_LAST_SALES = "/trade-aggregator/v1/last-sales"

    # Новые эндпоинты 2024/2025
    ENDPOINT_MARKET_BEST_OFFERS = "/exchange/v1/market/best-offers"
    ENDPOINT_MARKET_SEARCH = "/exchange/v1/market/search"
    ENDPOINT_AGGREGATED_PRICES_POST = "/marketplace-api/v1/aggregated-prices"
    ENDPOINT_TARGETS_BY_TITLE = "/marketplace-api/v1/targets-by-title"
    ENDPOINT_DEPOSIT_ASSETS = "/marketplace-api/v1/deposit-assets"
    ENDPOINT_DEPOSIT_STATUS = "/marketplace-api/v1/deposit-status"
    ENDPOINT_WITHDRAW_ASSETS = "/exchange/v1/withdraw-assets"
    ENDPOINT_INVENTORY_SYNC = "/marketplace-api/v1/user-inventory/sync"
    ENDPOINT_GAMES_LIST = "/game/v1/games"

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
        notifier: Any = None,
    ) -> None:
        self.public_key = public_key
        self._public_key = public_key

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
        self.notifier = notifier
        self.retry_codes = retry_codes or [429, 500, 502, 503, 504]

        self.pool_limits = pool_limits or httpx.Limits(
            max_connections=100,
            max_keepalive_connections=30,
            keepalive_expiry=60.0,
        )

        self._client: httpx.AsyncClient | None = None
        self._http2_enabled = True
        self._client_ref_count = 0
        self._client_lock = asyncio.Lock()
        self.rate_limiter = DMarketRateLimiter()
        self._signing_key = None

        from concurrent.futures import ThreadPoolExecutor
        self._signing_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="hmac_signer")

    def _prepare_signing_key(self) -> None:
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

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            try:
                self._client = httpx.AsyncClient(
                    timeout=self.connection_timeout,
                    limits=self.pool_limits,
                    http2=self._http2_enabled,
                    follow_redirects=True,
                    verify=True,
                )
            except ImportError:
                self._http2_enabled = False
                self._client = httpx.AsyncClient(
                    timeout=self.connection_timeout,
                    limits=self.pool_limits,
                    http2=False,
                    follow_redirects=True,
                    verify=True,
                )
        return self._client

    async def _close_client(self) -> None:
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    def _generate_signature(self, method: str, path: str, body: str = "") -> dict[str, str]:
        if not self.public_key or not self.secret_key:
            return {"Content-Type": "application/json"}
        try:
            timestamp = str(int(time.time()))
            string_to_sign = f"{method.upper()}{path}{body}{timestamp}"
            if self._signing_key is None:
                self._prepare_signing_key()
            if self._signing_key:
                signed = self._signing_key.sign(string_to_sign.encode("utf-8"))
                signature = signed.signature.hex()
                return {
                    "X-Api-Key": self.public_key,
                    "X-Request-Sign": f"dmar ed25519 {signature}",
                    "X-Sign-Date": timestamp,
                    "Content-Type": "application/json",
                }
            return self._generate_signature_hmac(method, path, body)
        except Exception as e:
            logger.exception(f"Error generating signature: {e}")
            return self._generate_signature_hmac(method, path, body)

    def _generate_signature_hmac(self, method: str, path: str, body: str = "") -> dict[str, str]:
        timestamp = str(int(time.time()))
        string_to_sign = timestamp + method + path
        if body: string_to_sign += body
        signature = hmac.new(self.secret_key, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
        return {"X-Api-Key": self.public_key, "X-Request-Sign": signature, "X-Sign-Date": timestamp, "Content-Type": "application/json"}

    async def _generate_signature_async(self, method: str, path: str, body: str = "") -> dict[str, str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self._signing_executor, self._generate_signature, method, path, body)

    def _generate_headers(self, method: str, target: str, body: str = "") -> dict[str, str]:
        return self._generate_signature(method, target, body)

    def _get_cache_key(self, method: str, path: str, params: dict[str, Any] | None = None, data: dict[str, Any] | None = None) -> str:
        key_parts = [method, path]
        if params:
            sorted_params = sorted((str(k), str(v)) for k, v in params.items())
            key_parts.append(str(sorted_params))
        if data:
            try:
                data_str = json.dumps(data, sort_keys=True)
                key_parts.append(hashlib.sha256(data_str.encode()).hexdigest())
            except (TypeError, ValueError):
                key_parts.append(str(data))
        return hashlib.sha256("|".join(key_parts).encode()).hexdigest()

    def _is_cacheable(self, method: str, path: str) -> tuple[bool, str]:
        if method.upper() != "GET": return (False, "")
        if any(e in path for e in ["/meta", "/aggregated"]): return (True, "medium")
        if any(e in path for e in ["/market/", "/items", "/inventory"]): return (True, "short")
        if any(e in path for e in ["/balance", "/account/"]): return (True, "short")
        return (False, "")

    def _get_from_cache(self, cache_key: str) -> dict[str, Any] | None:
        if not self.enable_cache: return None
        entry = api_cache.get(cache_key)
        if not entry: return None
        data, expire = entry
        if time.time() < expire: return data
        api_cache.pop(cache_key, None)
        return None

    def _save_to_cache(self, cache_key: str, data: dict[str, Any], ttl_type: str) -> None:
        if not self.enable_cache: return
        ttl = CACHE_TTL.get(ttl_type, 30)
        api_cache[cache_key] = (data, time.time() + ttl)

    def _prepare_sorted_params(self, params: dict[str, Any] | None) -> list[tuple[str, Any]]:
        return sorted(params.items()) if params else []

    def _build_path_for_signature(self, method: str, path: str, params_items: list[tuple[str, Any]]) -> str:
        if method.upper() != "GET" or not params_items: return path
        from urllib.parse import urlencode
        qs = urlencode(params_items)
        return f"{path}?{qs}" if qs else path

    async def _execute_single_http_request(self, client: httpx.AsyncClient, method: str, url: str, params: list[tuple[str, Any]] | None, data: dict[str, Any] | None, headers: dict[str, str]) -> httpx.Response:
        m = method.upper()
        if m == "GET": return await call_with_circuit_breaker(client.get, url, params=params, headers=headers)
        if m == "POST": return await call_with_circuit_breaker(client.post, url, json=data, headers=headers)
        if m == "PUT": return await call_with_circuit_breaker(client.put, url, json=data, headers=headers)
        if m == "DELETE": return await call_with_circuit_breaker(client.delete, url, headers=headers)
        if m == "PATCH": return await call_with_circuit_breaker(client.patch, url, json=data, headers=headers)
        raise ValueError(f"Unsupported method: {method}")

    def _parse_json_response(self, response: httpx.Response, path: str) -> dict[str, Any]:
        if response.status_code == 204: return {"status": "success", "code": 204}
        try: return response.json()
        except: return {"error": "invalid_json", "status_code": response.status_code}

    def _calculate_retry_delay(self, status_code: int, retries: int, current_delay: float, response: httpx.Response | None = None) -> float:
        if status_code == 429:
            ra = response.headers.get("Retry-After") if response else None
            if ra: return float(ra)
            return min(current_delay * 2, 30)
        return 1.0 + retries * 0.5

    def _parse_http_error_response(self, response: httpx.Response) -> dict[str, Any]:
        try: return response.json()
        except: return {"error": "Non-JSON response", "status_code": response.status_code}

    async def _request(self, method: str, path: str, params: dict[str, Any] | None = None, data: dict[str, Any] | None = None, force_refresh: bool = False) -> dict[str, Any]:
        try:
            from src.utils.prometheus_metrics import dmarket_requests_total
            dmarket_requests_total.labels(endpoint=path, method=method.upper()).inc()
        except:
            pass

        client = await self._get_client()
        url = f"{self.api_url}{path}"
        params_items = self._prepare_sorted_params(params)
        body_json = json.dumps(data) if data and method.upper() in {"POST", "PUT", "PATCH"} else ""
        path_for_signature = self._build_path_for_signature(method, path, params_items)
        headers = self._generate_signature(method.upper(), path_for_signature, body_json)
        await self.rate_limiter.acquire(path)

        retries = 0
        retry_delay = 1.0
        while retries <= self.max_retries:
            try:
                response = await self._execute_single_http_request(client, method, url, params_items, data, headers)
                
                # Smart Rate Limiter Integration
                if self.rate_limiter and hasattr(self.rate_limiter, "update_from_headers"):
                    self.rate_limiter.update_from_headers(response.headers, path)

                response.raise_for_status()
                return self._parse_json_response(response, path)
            except Exception as e:
                retries += 1
                if retries > self.max_retries: return {"error": str(e), "code": "REQUEST_FAILED"}
                await asyncio.sleep(retry_delay)
                retry_delay *= 2
        return {}


# Alias for backward compatibility
DMarketAPIClient = BaseDMarketClient
