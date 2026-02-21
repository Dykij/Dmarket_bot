"""Fallback Cache - кэширование с fallback на устаревшие данные при сбоях.

Этот модуль обеспечивает:
1. Кэширование API ответов с настраиваемым TTL
2. Fallback на устаревшие (stale) данные при сбоях API
3. Многоуровневое кэширование (memory → Redis)
4. Graceful degradation при недоступности внешних сервисов
5. Метрики hit/miss для мониторинга

Ключевая идея: Лучше вернуть устаревшие данные, чем ошибку.

Использование:
    >>> cache = FallbackCache(ttl=300, stale_ttl=3600)
    >>>
    >>> # Получить данные с fallback
    >>> data, is_stale = await cache.get_or_fetch(
    ...     key="market_items_csgo",
    ...     fetch_func=lambda: api.get_items("csgo"),
    ... )
    >>> if is_stale:
    ...     logger.warning("Using stale data")

Created: January 2026
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any, TypeVar

import structlog

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from redis.asyncio import Redis

logger = structlog.get_logger(__name__)

T = TypeVar("T")


class CacheStatus(StrEnum):
    """Статус результата из кэша."""

    HIT = "hit"  # Свежие данные из кэша
    STALE = "stale"  # Устаревшие данные из кэша
    MISS = "miss"  # Данные из источника
    ERROR = "error"  # Ошибка при получении


@dataclass
class CacheEntry:
    """Запись в кэше.

    Attributes:
        data: Кэшированные данные
        created_at: Время создания записи
        expires_at: Время истечения TTL (свежие данные)
        stale_expires_at: Время истечения stale TTL (устаревшие данные)
        hit_count: Количество обращений к этой записи
        source: Откуда были получены данные
    """

    data: Any
    created_at: datetime
    expires_at: datetime
    stale_expires_at: datetime
    hit_count: int = 0
    source: str = "api"

    def is_fresh(self) -> bool:
        """Проверить, свежи ли данные."""
        return datetime.now(UTC) < self.expires_at

    def is_stale_valid(self) -> bool:
        """Проверить, можно ли использовать устаревшие данные."""
        return datetime.now(UTC) < self.stale_expires_at

    def age_seconds(self) -> float:
        """Возраст записи в секундах."""
        return (datetime.now(UTC) - self.created_at).total_seconds()

    def to_dict(self) -> dict[str, Any]:
        """Сериализовать в словарь."""
        return {
            "data": self.data,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "stale_expires_at": self.stale_expires_at.isoformat(),
            "hit_count": self.hit_count,
            "source": self.source,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CacheEntry:
        """Десериализовать из словаря."""
        return cls(
            data=data["data"],
            created_at=datetime.fromisoformat(data["created_at"]),
            expires_at=datetime.fromisoformat(data["expires_at"]),
            stale_expires_at=datetime.fromisoformat(data["stale_expires_at"]),
            hit_count=data.get("hit_count", 0),
            source=data.get("source", "redis"),
        )


@dataclass
class CacheStats:
    """Статистика кэша.

    Attributes:
        hits: Количество попаданий (свежие данные)
        stale_hits: Количество использований устаревших данных
        misses: Количество промахов (данные из источника)
        errors: Количество ошибок
        evictions: Количество вытесненных записей
    """

    hits: int = 0
    stale_hits: int = 0
    misses: int = 0
    errors: int = 0
    evictions: int = 0

    def record_hit(self) -> None:
        """Записать попадание."""
        self.hits += 1

    def record_stale_hit(self) -> None:
        """Записать использование устаревших данных."""
        self.stale_hits += 1

    def record_miss(self) -> None:
        """Записать промах."""
        self.misses += 1

    def record_error(self) -> None:
        """Записать ошибку."""
        self.errors += 1

    def record_eviction(self) -> None:
        """Записать вытеснение."""
        self.evictions += 1

    @property
    def total_requests(self) -> int:
        """Общее количество запросов."""
        return self.hits + self.stale_hits + self.misses + self.errors

    @property
    def hit_rate(self) -> float:
        """Процент попаданий (0-100)."""
        if self.total_requests == 0:
            return 0.0
        return (self.hits + self.stale_hits) / self.total_requests * 100

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "hits": self.hits,
            "stale_hits": self.stale_hits,
            "misses": self.misses,
            "errors": self.errors,
            "evictions": self.evictions,
            "total_requests": self.total_requests,
            "hit_rate": round(self.hit_rate, 2),
        }


class FallbackCache:
    """Кэш с fallback на устаревшие данные при сбоях.

    Двухуровневая система TTL:
    - ttl: Время жизни "свежих" данных (по умолчанию 5 минут)
    - stale_ttl: Время жизни "устаревших" данных (по умолчанию 1 час)

    При запросе:
    1. Если данные свежие → вернуть из кэша (HIT)
    2. Если данные устаревшие:
       - Попробовать обновить из источника
       - При ошибке → вернуть устаревшие (STALE)
    3. Если данных нет → получить из источника (MISS)
    """

    def __init__(
        self,
        ttl: int = 300,  # 5 минут
        stale_ttl: int = 3600,  # 1 час
        max_size: int = 1000,
        redis_client: Redis | None = None,
        namespace: str = "fallback_cache",
    ) -> None:
        """Инициализация кэша.

        Args:
            ttl: Время жизни свежих данных в секундах
            stale_ttl: Время жизни устаревших данных в секундах
            max_size: Максимальный размер in-memory кэша
            redis_client: Redis клиент (опционально)
            namespace: Namespace для Redis ключей
        """
        self._ttl = timedelta(seconds=ttl)
        self._stale_ttl = timedelta(seconds=stale_ttl)
        self._max_size = max_size
        self._redis = redis_client
        self._namespace = namespace

        self._cache: dict[str, CacheEntry] = {}
        self._stats = CacheStats()
        self._lock = asyncio.Lock()

        logger.info(
            "fallback_cache_initialized",
            ttl_seconds=ttl,
            stale_ttl_seconds=stale_ttl,
            max_size=max_size,
            redis_enabled=redis_client is not None,
        )

    async def get_or_fetch(
        self,
        key: str,
        fetch_func: Callable[[], Awaitable[T]],
        ttl: int | None = None,
        stale_ttl: int | None = None,
    ) -> tuple[T, CacheStatus]:
        """Получить данные из кэша или источника с fallback.

        Args:
            key: Ключ кэша
            fetch_func: Асинхронная функция для получения данных
            ttl: Опционально переопределить TTL для этого запроса
            stale_ttl: Опционально переопределить stale TTL

        Returns:
            Tuple (данные, статус)
            Статус: HIT (свежие), STALE (устаревшие), MISS (из источника)

        Example:
            >>> data, status = await cache.get_or_fetch(
            ...     "market_csgo",
            ...     lambda: api.get_market_items("csgo"),
            ... )
            >>> print(f"Status: {status}")  # HIT, STALE, or MISS
        """
        effective_ttl = timedelta(seconds=ttl) if ttl else self._ttl
        effective_stale_ttl = (
            timedelta(seconds=stale_ttl) if stale_ttl else self._stale_ttl
        )

        # 1. Проверить in-memory кэш
        entry = self._cache.get(key)

        if entry:
            if entry.is_fresh():
                # Свежие данные → вернуть сразу
                entry.hit_count += 1
                self._stats.record_hit()
                self._track_metrics("hit", key)
                logger.debug(
                    "cache_hit",
                    key=key,
                    age_seconds=entry.age_seconds(),
                )
                return entry.data, CacheStatus.HIT

            if entry.is_stale_valid():
                # Устаревшие данные → попробовать обновить
                try:
                    data = await fetch_func()
                    await self._store(key, data, effective_ttl, effective_stale_ttl)
                    self._stats.record_miss()
                    self._track_metrics("refresh", key)
                    logger.debug(
                        "cache_refreshed",
                        key=key,
                        old_age_seconds=entry.age_seconds(),
                    )
                    return data, CacheStatus.MISS

                except Exception as e:
                    # Ошибка при обновлении → вернуть устаревшие
                    entry.hit_count += 1
                    self._stats.record_stale_hit()
                    self._track_metrics("stale", key)
                    logger.warning(
                        "cache_stale_fallback",
                        key=key,
                        error=str(e),
                        age_seconds=entry.age_seconds(),
                    )
                    return entry.data, CacheStatus.STALE

        # 2. Проверить Redis если настроен
        if self._redis:
            redis_entry = await self._get_from_redis(key)
            if redis_entry:
                if redis_entry.is_fresh():
                    # Свежие данные из Redis
                    self._cache[key] = redis_entry  # Сохранить в memory
                    self._stats.record_hit()
                    self._track_metrics("redis_hit", key)
                    return redis_entry.data, CacheStatus.HIT

                if redis_entry.is_stale_valid():
                    # Устаревшие данные из Redis
                    try:
                        data = await fetch_func()
                        await self._store(key, data, effective_ttl, effective_stale_ttl)
                        self._stats.record_miss()
                        return data, CacheStatus.MISS
                    except Exception as e:
                        self._cache[key] = redis_entry
                        self._stats.record_stale_hit()
                        self._track_metrics("redis_stale", key)
                        logger.warning(
                            "cache_redis_stale_fallback",
                            key=key,
                            error=str(e),
                        )
                        return redis_entry.data, CacheStatus.STALE

        # 3. Нет данных в кэше → получить из источника
        try:
            data = await fetch_func()
            await self._store(key, data, effective_ttl, effective_stale_ttl)
            self._stats.record_miss()
            self._track_metrics("miss", key)
            logger.debug("cache_miss", key=key)
            return data, CacheStatus.MISS

        except Exception as e:
            self._stats.record_error()
            self._track_metrics("error", key)
            logger.exception(
                "cache_fetch_error",
                key=key,
                error=str(e),
            )
            raise

    async def _store(
        self,
        key: str,
        data: Any,
        ttl: timedelta,
        stale_ttl: timedelta,
    ) -> None:
        """Сохранить данные в кэш.

        Args:
            key: Ключ кэша
            data: Данные для сохранения
            ttl: Время жизни свежих данных
            stale_ttl: Время жизни устаревших данных
        """
        now = datetime.now(UTC)
        entry = CacheEntry(
            data=data,
            created_at=now,
            expires_at=now + ttl,
            stale_expires_at=now + stale_ttl,
            source="api",
        )

        async with self._lock:
            # Проверить размер и вытеснить старые записи
            if len(self._cache) >= self._max_size:
                await self._evict_oldest()

            self._cache[key] = entry

        # Сохранить в Redis если настроен
        if self._redis:
            await self._store_to_redis(key, entry)

    async def _evict_oldest(self) -> None:
        """Вытеснить самые старые записи."""
        if not self._cache:
            return

        # Сортировать по времени создания
        sorted_entries = sorted(
            self._cache.items(),
            key=lambda x: x[1].created_at,
        )

        # Удалить 10% самых старых
        evict_count = max(1, len(sorted_entries) // 10)

        for key, _ in sorted_entries[:evict_count]:
            del self._cache[key]
            self._stats.record_eviction()

        logger.info(
            "cache_eviction",
            evicted_count=evict_count,
            remaining_count=len(self._cache),
        )

    async def _get_from_redis(self, key: str) -> CacheEntry | None:
        """Получить запись из Redis.

        Args:
            key: Ключ кэша

        Returns:
            CacheEntry или None
        """
        if not self._redis:
            return None

        try:
            redis_key = f"{self._namespace}:{key}"
            data = await self._redis.get(redis_key)
            if data:
                entry_dict = json.loads(data)
                return CacheEntry.from_dict(entry_dict)
        except Exception as e:
            logger.warning(
                "cache_redis_get_error",
                key=key,
                error=str(e),
            )

        return None

    async def _store_to_redis(self, key: str, entry: CacheEntry) -> None:
        """Сохранить запись в Redis.

        Args:
            key: Ключ кэша
            entry: Запись для сохранения
        """
        if not self._redis:
            return

        try:
            redis_key = f"{self._namespace}:{key}"
            # TTL в Redis = stale_ttl (чтобы данные жили дольше)
            expire_seconds = int(
                (entry.stale_expires_at - datetime.now(UTC)).total_seconds()
            )
            if expire_seconds > 0:
                await self._redis.setex(
                    redis_key,
                    expire_seconds,
                    json.dumps(entry.to_dict()),
                )
        except Exception as e:
            logger.warning(
                "cache_redis_store_error",
                key=key,
                error=str(e),
            )

    async def invalidate(self, key: str) -> bool:
        """Инвалидировать запись в кэше.

        Args:
            key: Ключ для инвалидации

        Returns:
            True если запись была удалена
        """
        deleted = False

        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                deleted = True

        if self._redis:
            try:
                redis_key = f"{self._namespace}:{key}"
                await self._redis.delete(redis_key)
            except Exception as e:
                logger.warning(
                    "cache_redis_invalidate_error",
                    key=key,
                    error=str(e),
                )

        if deleted:
            logger.debug("cache_invalidated", key=key)

        return deleted

    async def invalidate_pattern(self, pattern: str) -> int:
        """Инвалидировать записи по паттерну.

        Args:
            pattern: Паттерн для поиска ключей (например, "market_*")

        Returns:
            Количество удалённых записей
        """
        count = 0

        async with self._lock:
            keys_to_delete = [k for k in self._cache if self._match_pattern(k, pattern)]
            for key in keys_to_delete:
                del self._cache[key]
                count += 1

        logger.info(
            "cache_pattern_invalidated",
            pattern=pattern,
            count=count,
        )
        return count

    @staticmethod
    def _match_pattern(key: str, pattern: str) -> bool:
        """Проверить соответствие ключа паттерну.

        Args:
            key: Ключ для проверки
            pattern: Паттерн (поддерживает * в конце)

        Returns:
            True если соответствует
        """
        if pattern.endswith("*"):
            return key.startswith(pattern[:-1])
        return key == pattern

    async def clear(self) -> int:
        """Очистить весь кэш.

        Returns:
            Количество удалённых записей
        """
        async with self._lock:
            count = len(self._cache)
            self._cache.clear()

        if self._redis:
            try:
                # Удалить все ключи с нашим namespace
                async for key in self._redis.scan_iter(f"{self._namespace}:*"):
                    await self._redis.delete(key)
            except Exception as e:
                logger.warning(
                    "cache_redis_clear_error",
                    error=str(e),
                )

        logger.warning("cache_cleared", count=count)
        return count

    def get_stats(self) -> dict[str, Any]:
        """Получить статистику кэша.

        Returns:
            Словарь со статистикой
        """
        stats = self._stats.to_dict()
        stats["cache_size"] = len(self._cache)
        stats["max_size"] = self._max_size
        stats["ttl_seconds"] = self._ttl.total_seconds()
        stats["stale_ttl_seconds"] = self._stale_ttl.total_seconds()
        stats["redis_enabled"] = self._redis is not None
        return stats

    def _track_metrics(self, action: str, key: str) -> None:
        """Обновить Prometheus метрики.

        Args:
            action: Тип действия (hit, miss, stale, error)
            key: Ключ кэша (для labels)
        """
        try:
            from src.utils.prometheus_metrics import (
                CACHE_OPERATIONS,
                CACHE_SIZE,
            )

            # Извлечь category из ключа (например, "market_csgo" → "market")
            category = key.split("_", maxsplit=1)[0] if "_" in key else key

            CACHE_OPERATIONS.labels(
                cache="fallback",
                action=action,
                category=category,
            ).inc()

            CACHE_SIZE.labels(cache="fallback").set(len(self._cache))
        except ImportError:
            pass  # Prometheus not available

    @staticmethod
    def make_key(*args: Any, **kwargs: Any) -> str:
        """Создать ключ кэша из аргументов.

        Удобная утилита для создания уникальных ключей.

        Args:
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы

        Returns:
            Строковый ключ

        Example:
            >>> key = FallbackCache.make_key("market", "csgo", min_price=10)
            >>> # "market_csgo_min_price_10"
        """
        parts = [str(a) for a in args]
        parts.extend(f"{k}_{v}" for k, v in sorted(kwargs.items()))
        return "_".join(parts)

    @staticmethod
    def make_hash_key(*args: Any, **kwargs: Any) -> str:
        """Создать хэшированный ключ (для длинных аргументов).

        Args:
            *args: Позиционные аргументы
            **kwargs: Именованные аргументы

        Returns:
            Короткий хэшированный ключ

        Example:
            >>> key = FallbackCache.make_hash_key(long_query, filters={...})
            >>> # "query_a1b2c3d4"
        """
        data = str(args) + str(sorted(kwargs.items()))
        # Using SHA256 for secure hashing (truncated for short keys)
        hash_value = hashlib.sha256(data.encode()).hexdigest()[:8]
        prefix = str(args[0])[:10] if args else "cache"
        return f"{prefix}_{hash_value}"


# Глобальный экземпляр кэша
_cache_instance: FallbackCache | None = None


def get_fallback_cache() -> FallbackCache:
    """Получить глобальный экземпляр FallbackCache.

    Returns:
        FallbackCache
    """
    global _cache_instance
    if _cache_instance is None:
        _cache_instance = FallbackCache()
    return _cache_instance


def set_fallback_cache(cache: FallbackCache) -> None:
    """Установить глобальный экземпляр FallbackCache.

    Args:
        cache: Экземпляр FallbackCache
    """
    global _cache_instance
    _cache_instance = cache


# Декоратор для автоматического кэширования
def cached(
    ttl: int = 300,
    stale_ttl: int = 3600,
    key_prefix: str = "",
) -> Any:
    """Декоратор для кэширования результатов функции.

    Args:
        ttl: Время жизни свежих данных
        stale_ttl: Время жизни устаревших данных
        key_prefix: Префикс для ключа кэша

    Returns:
        Декорированная функция

    Example:
        >>> @cached(ttl=60, key_prefix="market")
        ... async def get_market_items(game: str) -> list:
        ...     return await api.get_items(game)
    """

    def decorator(func: Any) -> Any:
        import functools

        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            cache = get_fallback_cache()

            # Создать ключ
            if key_prefix:
                key = FallbackCache.make_key(key_prefix, *args, **kwargs)
            else:
                key = FallbackCache.make_key(func.__name__, *args, **kwargs)

            # Получить из кэша или вызвать функцию
            data, _status = await cache.get_or_fetch(
                key=key,
                fetch_func=lambda: func(*args, **kwargs),
                ttl=ttl,
                stale_ttl=stale_ttl,
            )

            return data

        return wrapper

    return decorator


__all__ = [
    "CacheEntry",
    "CacheStats",
    "CacheStatus",
    "FallbackCache",
    "cached",
    "get_fallback_cache",
    "set_fallback_cache",
]
