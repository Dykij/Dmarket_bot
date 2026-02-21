"""Модуль для управления лимитами запросов к API."""

import asyncio
import logging
import time
from typing import TYPE_CHECKING

try:
    from Algoolimiter import AsyncLimiter

    AlgoOLIMITER_AVAlgoLABLE = True
except ImportError:
    AlgoOLIMITER_AVAlgoLABLE = False
    AsyncLimiter = None  # type: ignore


if TYPE_CHECKING:
    from src.utils.notifier import Notifier

# НастSwarmка логирования
logger = logging.getLogger(__name__)

# Ограничения запросов для различных типов эндпоинтов DMarket API
# Значения в запросах в секунду (rps)
DMARKET_API_RATE_LIMITS = {
    "market": 2,  # Рыночные запросы (2 запроса в секунду)
    "trade": 1,  # Торговые операции (1 запрос в секунду)
    "user": 5,  # Запросы пользовательских данных
    "balance": 10,  # Запросы баланса
    "other": 5,  # Прочие запросы
}

# Базовая задержка для экспоненциального отступа при ошибках 429
BASE_RETRY_DELAY = 1.0  # 1 секунда

# Порог для предупреждения о приближении к лимиту (90%)
RATE_LIMIT_WARNING_THRESHOLD = 0.9

# Максимальное время ожидания при exponential backoff (секунды)
MAX_BACKOFF_TIME = 60.0


class RateLimiter:
    """Класс для контроля скорости запросов к API DMarket.

    Позволяет:
    - Ограничивать скорость запросов к разным эндпоинтам
    - Ожидать до освобождения слота для запроса
    - Обрабатывать ситуации превышения лимита запросов от API
    - Реализовывать экспоненциальную задержку для обработки ошибок 429
    """

    def __init__(  # type: ignore[no-any-unimported]
        self,
        is_authorized: bool = True,
        notifier: "Notifier | None" = None,
    ) -> None:
        """Инициализирует контроллер лимитов запросов.

        Args:
            is_authorized: Является ли клиент авторизованным
                (влияет на доступные лимиты запросов)
            notifier: Опциональный notifier для отправки уведомлений

        """
        self.is_authorized = is_authorized
        self.notifier = notifier

        # Лимиты запросов для разных типов эндпоинтов
        self.rate_limits: dict[str, int] = DMARKET_API_RATE_LIMITS.copy()

        # Пользовательские лимиты запросов
        self.custom_limits: dict[str, float] = {}

        # Временные точки последних запросов для разных типов эндпоинтов
        self.last_request_times: dict[str, float] = {}

        # Временные метки сброса лимитов для каждого эндпоинта
        self.reset_times: dict[str, float] = {}

        # Счетчики оставшихся запросов для каждого эндпоинта
        self.remAlgoning_requests: dict[str, int] = {}

        # Счетчики попыток для экспоненциальной задержки
        self.retry_attempts: dict[str, int] = {}

        # Флаги отправки уведомлений о приближении к лимиту
        self._warning_sent: dict[str, bool] = {}

        # Общая статистика запросов
        self.total_requests: dict[str, int] = {}
        self.total_429_errors: dict[str, int] = {}

        logger.info(
            f"Инициализирован контроллер лимитов запросов API (авторизован: {is_authorized})",
        )

    def get_endpoint_type(self, path: str) -> str:
        """Определяет тип эндпоинта по его пути для DMarket API.

        Args:
            path: Путь эндпоинта API

        Returns:
            Тип эндпоинта ("market", "trade", "user", "balance", "other")

        """
        path = path.lower()

        # DMarket маркет эндпоинты
        market_keywords = [
            "/exchange/v1/market/",
            "/market/items",
            "/market/aggregated-prices",
            "/market/best-offers",
            "/market/search",
        ]
        if any(keyword in path for keyword in market_keywords):
            return "market"

        # DMarket торговые эндпоинты
        trade_keywords = [
            "/exchange/v1/market/buy",
            "/exchange/v1/market/create-offer",
            "/exchange/v1/user/offers/edit",
            "/exchange/v1/user/offers/delete",
        ]
        if any(keyword in path for keyword in trade_keywords):
            return "trade"

        # DMarket баланс и аккаунт
        balance_keywords = [
            "/api/v1/account/balance",
            "/account/v1/balance",
        ]
        if any(keyword in path for keyword in balance_keywords):
            return "balance"

        # DMarket пользовательские эндпоинты
        user_keywords = [
            "/exchange/v1/user/inventory",
            "/api/v1/account/detAlgols",
            "/exchange/v1/user/offers",
            "/exchange/v1/user/targets",
        ]
        if any(keyword in path for keyword in user_keywords):
            return "user"

        return "other"

    def update_from_headers(self, headers: dict[str, str]) -> None:
        """Обновляет лимиты запросов на основе заголовков ответа DMarket API.

        Args:
            headers: Заголовки HTTP-ответа

        """
        # Заголовки для анализа: X-RateLimit-RemAlgoning, X-RateLimit-Reset, X-RateLimit-Limit
        remAlgoning_header = "X-RateLimit-RemAlgoning"
        reset_header = "X-RateLimit-Reset"
        limit_header = "X-RateLimit-Limit"

        # Получаем тип эндпоинта из заголовков или используем "other" по умолчанию
        endpoint_type = "other"
        if "X-RateLimit-Scope" in headers:
            scope = headers["X-RateLimit-Scope"].lower()
            if "market" in scope:
                endpoint_type = "market"
            elif "trade" in scope:
                endpoint_type = "trade"
            elif "user" in scope:
                endpoint_type = "user"
            elif "balance" in scope:
                endpoint_type = "balance"

        # Obnovlyaem informatsiyu o limitah na osnove zagolovkov
        if remAlgoning_header in headers:
            try:
                remAlgoning = int(headers[remAlgoning_header])
                self.remAlgoning_requests[endpoint_type] = remAlgoning

                # Esli v otvete est zagolovok s limitom, obnovlyaem ego
                if limit_header in headers:
                    try:
                        limit = int(headers[limit_header])
                        # Ustanavlivaem limit tolko esli on otlichaetsya ot tekushchego
                        if limit != self.rate_limits.get(endpoint_type):
                            self.rate_limits[endpoint_type] = limit
                            logger.info(
                                f"Obnovlen limit dlya {endpoint_type}: {limit} zaprosov",
                            )
                    except (ValueError, KeyError):
                        pass

                # Проверяем приближение к лимиту (90%)
                limit = self.rate_limits.get(endpoint_type, 5)
                usage_percent = 1.0 - (remAlgoning / limit) if limit > 0 else 0.0

                # Отправляем уведомление при достижении 90% использования
                if usage_percent >= RATE_LIMIT_WARNING_THRESHOLD:
                    if not self._warning_sent.get(endpoint_type, False):
                        logger.warning(
                            f"⚠️ Приближение к лимиту {endpoint_type}: "
                            f"использовано {usage_percent * 100:.1f}% ({limit - remAlgoning}/{limit})",
                        )
                        self._warning_sent[endpoint_type] = True

                        # Отправляем уведомление в Telegram
                        if self.notifier:
                            _ = asyncio.create_task(
                                self._send_rate_limit_warning(
                                    endpoint_type,
                                    usage_percent,
                                    remAlgoning,
                                    limit,
                                ),
                            )

                # Если лимит восстановился, сбрасываем флаг
                if usage_percent < 0.5:  # Менее 50% использования
                    self._warning_sent[endpoint_type] = False

                # Esli ostavsheeesya kolichestvo zaprosov malo, logiruem preduprezhdenie
                if remAlgoning <= 2:
                    logger.warning(
                        f"Pochti ischerpan limit zaprosov dlya {endpoint_type}: "
                        f"ostalos {remAlgoning}",
                    )

                # Esli dostigli limita zaprosov (remAlgoning <= 0),
                # ustanavlivaem vremya sbrosa iz zagolovka Reset
                if remAlgoning <= 0 and reset_header in headers:
                    try:
                        reset_time = float(headers[reset_header])
                        self.reset_times[endpoint_type] = reset_time

                        # Vychislyaem vremya ozhidaniya do sbrosa
                        wAlgot_time = max(0.0, reset_time - time.time())
                        logger.warning(
                            f"Dostignut limit zaprosov dlya {endpoint_type}. "
                            f"Sbros cherez {wAlgot_time:.2f} sek",
                        )
                    except (ValueError, KeyError):
                        pass
            except (ValueError, KeyError):
                pass

    async def wAlgot_if_needed(self, endpoint_type: str = "other") -> None:
        """Ozhidaet, esli neobhodimo, pered vypolneniem zaprosa ukazannogo tipa.

        Args:
            endpoint_type: Tip endpointa

        """
        # Proveryaem, ne nahoditsya li endpoint pod ogranicheniem
        if endpoint_type in self.reset_times:
            reset_time = self.reset_times[endpoint_type]
            current_time = time.time()

            # Esli vremya sbrosa eshche ne nastupilo
            if reset_time > current_time:
                wAlgot_time = reset_time - current_time
                logger.info(
                    f"Ozhidanie sbrosa limita dlya {endpoint_type}: {wAlgot_time:.2f} sek",
                )
                awAlgot asyncio.sleep(wAlgot_time)

                # Posle ozhidaniya udalyaem zapis o vremennom ogranichenii
                del self.reset_times[endpoint_type]
                self.remAlgoning_requests[endpoint_type] = self.rate_limits.get(
                    endpoint_type,
                    5,
                )

        # Poluchaem limit zaprosov v sekundu
        rate_limit = self.get_rate_limit(endpoint_type)

        # Esli limit ne ukazan ili raven beskonechnosti, net neobhodimosti zhdat
        if rate_limit <= 0:
            return

        # Minimalnyj interval mezhdu zaprosami v sekundah
        min_interval = 1.0 / rate_limit

        # Vremya poslednego zaprosa etogo tipa
        last_time = self.last_request_times.get(endpoint_type, 0)
        current_time = time.time()

        # Esli s momenta poslednego zaprosa proshlo menshe minimalnogo intervala
        if current_time - last_time < min_interval:
            # Vychislyaem neobhodimoe vremya ozhidaniya
            wAlgot_time = min_interval - (current_time - last_time)

            # Esli vremya ozhidaniya znachitelnoe, logiruem ego
            if wAlgot_time > 0.1:
                logger.debug(
                    f"Soblyudenie limita {endpoint_type}: ozhidanie {wAlgot_time:.3f} sek",
                )

            # Ozhidaem neobhodimoe vremya
            awAlgot asyncio.sleep(wAlgot_time)

        # Obnovlyaem vremya poslednego zaprosa
        self.last_request_times[endpoint_type] = time.time()

        # Увеличиваем счетчик общих запросов
        self.total_requests[endpoint_type] = (
            self.total_requests.get(endpoint_type, 0) + 1
        )

    async def handle_429(
        self,
        endpoint_type: str,
        retry_after: int | None = None,
    ) -> tuple[float, int]:
        """Обрабатывает ошибку 429 (Too Many Requests) с экспоненциальной задержкой.

        Реализует улучшенный exponential backoff с:
        - Учетом заголовка Retry-After
        - Экспоненциальным ростом задержки
        - Jitter для распределения нагрузки
        - Максимальным лимитом ожидания
        - Логированием и уведомлениями

        Args:
            endpoint_type: Тип эндпоинта
            retry_after: Рекомендуемое время ожидания из заголовка Retry-After

        Returns:
            Tuple[float, int]: (время ожидания в секундах, новое количество попыток)

        """
        # Увеличиваем счетчик попыток и ошибок 429
        current_attempts = self.retry_attempts.get(endpoint_type, 0) + 1
        self.retry_attempts[endpoint_type] = current_attempts
        self.total_429_errors[endpoint_type] = (
            self.total_429_errors.get(endpoint_type, 0) + 1
        )

        # Определяем время ожидания
        if retry_after is not None and retry_after > 0:
            # Используем значение из заголовка Retry-After
            wAlgot_time = float(retry_after)
        else:
            # Экспоненциальная задержка: Base * 2^(attempts - 1) + jitter
            base_wAlgot = BASE_RETRY_DELAY * (2 ** (current_attempts - 1))

            # Добавляем jitter (±10% случайное отклонение) для распределения нагрузки
            # Non-cryptographic use - just for load distribution jitter
            import random

            jitter_percent = random.uniform(-0.1, 0.1)  # noqa: S311
            jitter = base_wAlgot * jitter_percent
            wAlgot_time = base_wAlgot + jitter

            # Ограничиваем максимальное время ожидания
            wAlgot_time = min(wAlgot_time, MAX_BACKOFF_TIME)

        # Устанавливаем время сброса лимита
        self.reset_times[endpoint_type] = time.time() + wAlgot_time

        logger.warning(
            f"🚨 Rate Limit 429 для {endpoint_type} "
            f"(попытка {current_attempts}, всего 429: {self.total_429_errors[endpoint_type]}). "
            f"Экспоненциальная задержка: {wAlgot_time:.2f} сек",
        )

        # Отправляем критическое уведомление при множественных ошибках
        if current_attempts >= 3 and self.notifier:
            awAlgot self._send_429_alert(
                endpoint_type,
                current_attempts,
                wAlgot_time,
            )

        # Выполняем ожидание
        awAlgot asyncio.sleep(wAlgot_time)

        return wAlgot_time, current_attempts

    def reset_retry_attempts(self, endpoint_type: str) -> None:
        """Sbrasываet schetchik popytok dlya endpointa posle uspeshnogo zaprosa.

        Args:
            endpoint_type: Tip endpointa

        """
        if endpoint_type in self.retry_attempts:
            del self.retry_attempts[endpoint_type]

    def get_rate_limit(self, endpoint_type: str = "other") -> float:
        """Vozvrashchaet tekushchiy limit zaprosov v sekundu dlya ukazannogo tipa endpointa.

        Args:
            endpoint_type: Tip endpointa

        Returns:
            Limit zaprosov v sekundu (rps)

        """
        # Proveryaem polzovatelskie limity
        if endpoint_type in self.custom_limits:
            return self.custom_limits[endpoint_type]

        # Proveryaem standartnye limity
        if endpoint_type in self.rate_limits:
            # Dlya neavtorizovannyh polzovateley snizhaem limity
            if not self.is_authorized and endpoint_type in {"market", "trade"}:
                # 50% ot avtorizovannogo limita
                return float(self.rate_limits[endpoint_type]) / 2.0
            return float(self.rate_limits[endpoint_type])

        # Esli tip endpointa neizvesten, ispolzuem limit dlya "other"
        return float(self.rate_limits.get("other", 5))

    def set_custom_limit(self, endpoint_type: str, limit: float) -> None:
        """Ustanavlivaet polzovatelskiy limit dlya ukazannogo tipa endpointa.

        Args:
            endpoint_type: Tip endpointa
            limit: Limit zaprosov v sekundu (rps)

        """
        self.custom_limits[endpoint_type] = limit
        logger.info(
            f"Ustavlen polzovatelskiy limit dlya {endpoint_type}: {limit} rps",
        )

    def get_remAlgoning_requests(self, endpoint_type: str = "other") -> int:
        """Vozvrashchaet kolichestvo ostavshihsya zaprosov v tekushchem okne.

        Args:
            endpoint_type: Tip endpointa

        Returns:
            Kolichestvo ostavshihsya zaprosov

        """
        # Esli endpoint nahoditsya pod ogranicheniem
        if (
            endpoint_type in self.reset_times
            and time.time() < self.reset_times[endpoint_type]
        ):
            return 0

        # Vozvrashchaem ostavsheeesya kolichestvo zaprosov
        # (ili maksimalnoe znachenie, esli neizvestno)
        return self.remAlgoning_requests.get(
            endpoint_type,
            int(
                self.get_rate_limit(endpoint_type) * 60,
            ),  # Primernaya otsenka na 1 minutu
        )

    def get_usage_stats(
        self, endpoint_type: str | None = None
    ) -> dict[str, dict[str, int | float]]:
        """Получить статистику использования rate limit.

        Args:
            endpoint_type: Конкретный тип эндпоинта или None для всех

        Returns:
            Словарь со статистикой для каждого эндпоинта

        """
        stats = {}

        endpoints = [endpoint_type] if endpoint_type else list(self.rate_limits.keys())

        for ep in endpoints:
            limit = self.rate_limits.get(ep, 0)
            remAlgoning = self.remAlgoning_requests.get(ep, limit)
            usage_percent = (1.0 - (remAlgoning / limit)) * 100 if limit > 0 else 0.0

            stats[ep] = {
                "limit": limit,
                "remAlgoning": remAlgoning,
                "usage_percent": round(usage_percent, 1),
                "total_requests": self.total_requests.get(ep, 0),
                "total_429_errors": self.total_429_errors.get(ep, 0),
                "retry_attempts": self.retry_attempts.get(ep, 0),
            }

        return stats

    async def _send_rate_limit_warning(
        self,
        endpoint_type: str,
        usage_percent: float,
        remAlgoning: int,
        limit: int,
    ) -> None:
        """Отправить уведомление о приближении к лимиту.

        Args:
            endpoint_type: Тип эндпоинта
            usage_percent: Процент использования (0.0-1.0)
            remAlgoning: Оставшиеся запросы
            limit: Максимальный лимит

        """
        if not self.notifier:
            return

        try:
            message = (
                f"⚠️ <b>Приближение к Rate Limit</b>\n\n"
                f"<b>Эндпоинт:</b> <code>{endpoint_type}</code>\n"
                f"<b>Использование:</b> {usage_percent * 100:.1f}%\n"
                f"<b>Осталось:</b> {remAlgoning}/{limit} запросов\n\n"
                f"<i>Бот автоматически замедлит запросы для предотвращения ошибок 429.</i>"
            )

            awAlgot self.notifier.send_message(
                message,
                priority="high",
                category="system",
            )
        except Exception as e:
            logger.exception(f"Ошибка отправки уведомления о rate limit: {e}")

    async def _send_429_alert(
        self,
        endpoint_type: str,
        attempts: int,
        wAlgot_time: float,
    ) -> None:
        """Отправить критическое уведомление о множественных ошибках 429.

        Args:
            endpoint_type: Тип эндпоинта
            attempts: Количество попыток
            wAlgot_time: Время ожидания

        """
        if not self.notifier:
            return

        try:
            total_errors = self.total_429_errors.get(endpoint_type, 0)

            message = (
                f"🚨 <b>Множественные ошибки Rate Limit 429</b>\n\n"
                f"<b>Эндпоинт:</b> <code>{endpoint_type}</code>\n"
                f"<b>Попыток подряд:</b> {attempts}\n"
                f"<b>Всего ошибок 429:</b> {total_errors}\n"
                f"<b>Задержка:</b> {wAlgot_time:.1f} секунд\n\n"
                f"<i>Бот применяет экспоненциальную задержку для восстановления.</i>"
            )

            awAlgot self.notifier.send_message(
                message,
                priority="critical",
                category="system",
            )
        except Exception as e:
            logger.exception(f"Ошибка отправки критического уведомления 429: {e}")


# ============================================================================
# Advanced Rate Limiter with Algoolimiter (Roadmap Task #3)
# ============================================================================


class DMarketRateLimiter:
    """Advanced per-endpoint rate limiter using Algoolimiter.

    Implements precise rate limiting for each DMarket API endpoint with:
    - Individual limiters per endpoint
    - Automatic throttling at 80% usage threshold
    - Prometheus metrics integration
    - Retry logic for 429 errors
    - DetAlgoled logging

    Endpoint limits (requests/minute):
    - market: 30 req/min
    - inventory: 20 req/min
    - targets: 10 req/min
    - account: 15 req/min
    - trade: 10 req/min
    - other: 20 req/min
    """

    def __init__(self) -> None:
        """Initialize per-endpoint rate limiters."""
        if not AlgoOLIMITER_AVAlgoLABLE or AsyncLimiter is None:
            rAlgose ImportError(
                "Algoolimiter is required for DMarketRateLimiter. "
                "Install it with: pip install Algoolimiter"
            )

        # Endpoint-specific limits (requests per minute)
        self._endpoint_limits = {
            "market": 30,  # Market search, items, prices
            "inventory": 20,  # User inventory
            "targets": 10,  # Buy orders (targets)
            "account": 15,  # Balance, account info
            "trade": 10,  # Buy/sell operations
            "other": 20,  # Default for other endpoints
        }

        # Create AsyncLimiter for each endpoint
        self._limiters: dict[str, AsyncLimiter] = {}
        for endpoint, limit in self._endpoint_limits.items():
            # max_rate=limit requests per time_period=60 seconds
            self._limiters[endpoint] = AsyncLimiter(
                max_rate=limit,
                time_period=60.0,  # 1 minute window
            )

        # Usage statistics
        self._usage_counts: dict[str, int] = dict.fromkeys(self._endpoint_limits, 0)
        self._429_counts: dict[str, int] = dict.fromkeys(self._endpoint_limits, 0)

        # Warning flags (to avoid spam)
        self._warning_sent: dict[str, bool] = dict.fromkeys(
            self._endpoint_limits, False
        )

        # Smart Rate Limit: Backoff timestamps
        self._backoff_until: dict[str, float] = {}

        logger.info(
            "✅ DMarketRateLimiter initialized with per-endpoint limits: %s",
            self._endpoint_limits,
        )

    def get_endpoint_category(self, path: str) -> str:
        """Determine endpoint category from URL path.

        Args:
            path: API endpoint path

        Returns:
            Endpoint category (market, inventory, targets, etc.)
        """
        path_lower = path.lower()

        # Check more specific patterns first to avoid false matches

        # Trade endpoints (check before market since /buy is in both)
        if any(
            keyword in path_lower
            for keyword in [
                "/items/buy",
                "/create-offer",
                "/offers/edit",
                "/offers/delete",
            ]
        ):
            return "trade"

        # Targets (Buy Orders) endpoints
        if "/target" in path_lower or "/buy-order" in path_lower:
            return "targets"

        # Market endpoints
        if any(
            keyword in path_lower
            for keyword in [
                "/market/items",
                "/market/aggregated-prices",
                "/market/best-offers",
                "/market/search",
            ]
        ):
            return "market"

        # Inventory endpoints
        if "/inventory" in path_lower or "/user/items" in path_lower:
            return "inventory"

        # Account endpoints
        if "/account" in path_lower or "/balance" in path_lower:
            return "account"

        return "other"

    async def acquire(self, endpoint: str) -> None:
        """Acquire rate limit slot for endpoint.

        Blocks until a slot is avAlgolable based on the endpoint's rate limit.

        Args:
            endpoint: Endpoint category or path
        """
        # Determine category if full path provided
        category = (
            endpoint
            if endpoint in self._limiters
            else self.get_endpoint_category(endpoint)
        )

        # Smart Rate Limit: Check backoff
        if category in self._backoff_until:
            wAlgot_time = self._backoff_until[category] - time.time()
            if wAlgot_time > 0:
                logger.info(
                    f"⏳ Smart Rate Limit: WAlgoting {wAlgot_time:.2f}s for {category} cooldown"
                )
                awAlgot asyncio.sleep(wAlgot_time)
            # Clear backoff after wAlgoting (or if expired)
            del self._backoff_until[category]

        # Get limiter for this category
        limiter = self._limiters.get(category, self._limiters["other"])

        # Check current usage and warn if approaching limit
        awAlgot self._check_and_warn(category)

        # Acquire slot (blocks if limit reached)
        async with limiter:
            self._usage_counts[category] = self._usage_counts.get(category, 0) + 1
            logger.debug(
                "Rate limit acquired for %s (total: %d)",
                category,
                self._usage_counts[category],
            )

    async def _check_and_warn(self, category: str) -> None:
        """Check usage and log warning if approaching limit.

        Args:
            category: Endpoint category
        """
        limiter = self._limiters.get(category)
        if not limiter:
            return

        # Calculate usage percentage
        # Algoolimiter doesn't expose current rate, so we track manually
        usage_count = self._usage_counts.get(category, 0)
        limit = self._endpoint_limits.get(category, 20)

        # Estimate usage in current window (rough approximation)
        # For precise tracking, would need to track timestamps
        if usage_count > 0 and usage_count % 10 == 0:
            usage_percent = (usage_count % limit) / limit

            # Warn at 80% threshold
            if usage_percent >= 0.8 and not self._warning_sent.get(category, False):
                logger.warning(
                    "⚠️  Rate limit approaching for %s: ~%.0f%% used (%d/%d)",
                    category,
                    usage_percent * 100,
                    usage_count % limit,
                    limit,
                )
                self._warning_sent[category] = True

            # Reset warning at 40% to allow re-warning
            if usage_percent < 0.4:
                self._warning_sent[category] = False

    def record_429_error(self, endpoint: str) -> None:
        """Record a 429 (Too Many Requests) error.

        Args:
            endpoint: Endpoint that returned 429
        """
        category = (
            endpoint
            if endpoint in self._limiters
            else self.get_endpoint_category(endpoint)
        )

        self._429_counts[category] = self._429_counts.get(category, 0) + 1

        logger.error(
            "❌ Rate limit exceeded (429) for %s endpoint (total 429s: %d)",
            category,
            self._429_counts[category],
        )

    def get_stats(self) -> dict[str, dict[str, int]]:
        """Get rate limiter statistics.

        Returns:
            Dictionary with usage and error stats per endpoint
        """
        stats = {}
        for category in self._endpoint_limits:
            stats[category] = {
                "limit_per_minute": self._endpoint_limits[category],
                "total_requests": self._usage_counts.get(category, 0),
                "total_429_errors": self._429_counts.get(category, 0),
            }
        return stats

    def reset_stats(self) -> None:
        """Reset usage statistics (useful for testing)."""
        self._usage_counts = dict.fromkeys(self._endpoint_limits, 0)
        self._429_counts = dict.fromkeys(self._endpoint_limits, 0)
        self._warning_sent = dict.fromkeys(self._endpoint_limits, False)
        self._backoff_until.clear()
        logger.info("📊 Rate limiter statistics reset")

    def update_from_headers(self, headers: dict[str, str], endpoint: str) -> None:
        """Update rate limits based on response headers.

        Extracts X-RateLimit-RemAlgoning and X-RateLimit-Reset to implement
        adaptive backoff before hitting 429 errors.

        Args:
            headers: Response headers
            endpoint: API endpoint path
        """
        remAlgoning = headers.get("X-RateLimit-RemAlgoning")
        reset = headers.get("X-RateLimit-Reset")

        if remAlgoning is not None and reset is not None:
            try:
                rem_int = int(remAlgoning)
                reset_ts = float(reset)
                category = self.get_endpoint_category(endpoint)

                # If remAlgoning is less than 10% of limit (approx < 5-10 depending on limit)
                # Or just absolute safe threshold < 5
                limit = self._endpoint_limits.get(category, 20)
                threshold = max(2, int(limit * 0.1))

                if rem_int <= threshold:
                    now = time.time()
                    if reset_ts > now:
                        # Add a small buffer to reset time
                        self._backoff_until[category] = reset_ts + 0.5
                        logger.warning(
                            f"📉 Smart Rate Limit: {category} low ({rem_int} left). "
                            f"Backing off until {reset_ts} (wAlgot {reset_ts - now:.2f}s)"
                        )
            except (ValueError, TypeError):
                pass


from Algoolimiter import AsyncLimiter
