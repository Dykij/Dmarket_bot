"""
In-Memory Cache с TTL для оптимизации частых запросов.

Модуль предоставляет легковесный асинхронный кэш с временем жизни (TTL)
для кэширования результатов API запросов, цен, истории и других данных.
"""

import asyncio
import logging
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, ParamSpec, TypeVar, cast

logger = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


class TTLCache:
    """
    Асинхронный in-memory кэш с TTL и LRU вытеснением.

    Features:
    - TTL (Time To Live) для автоматической инвалидации
    - LRU (Least Recently Used) вытеснение при превышении размера
    - Async-safe операции
    - Статистика использования (hits/misses)
    - Автоматическая очистка устаревших записей
    """

    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        Инициализация кэша.

        Args:
            max_size: Максимальное количество элементов в кэше
            default_ttl: TTL по умолчанию в секундах
        """
        self._cache: OrderedDict[str, dict[str, Any]] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = asyncio.Lock()

        # Статистика
        self._hits = 0
        self._misses = 0
        self._evictions = 0

        # Фоновая задача очистки
        self._cleanup_task: asyncio.Task[None] | None = None

    async def start_cleanup(self, interval: int = 60) -> None:
        """
        Запустить фоновую задачу очистки устаревших записей.

        Args:
            interval: Интервал очистки в секундах
        """
        if self._cleanup_task and not self._cleanup_task.done():
            return

        async def cleanup_loop() -> None:
            while True:
                try:
                    await asyncio.sleep(interval)
                    await self._cleanup_expired()
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    logger.error("Error in cache cleanup: %s", e, exc_info=True)

        self._cleanup_task = asyncio.create_task(cleanup_loop())

    async def stop_cleanup(self) -> None:
        """Остановить фоновую задачу очистки."""
        if self._cleanup_task and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

    async def get(self, key: str) -> Any | None:
        """
        Получить значение из кэша.

        Args:
            key: Ключ

        Returns:
            Значение или None если не найдено или устарело
        """
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]
            expires_at = entry["expires_at"]

            # Проверка TTL
            if time.time() > expires_at:
                del self._cache[key]
                self._misses += 1
                return None

            # LRU: переместить в конец (самый свежий)
            self._cache.move_to_end(key)
            self._hits += 1

            return entry["value"]

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """
        Сохранить значение в кэше.

        Args:
            key: Ключ
            value: Значение
            ttl: TTL в секундах (или default_ttl если None)
        """
        async with self._lock:
            ttl = ttl or self._default_ttl
            expires_at = time.time() + ttl

            # Если ключ уже есть, обновить
            if key in self._cache:
                self._cache.move_to_end(key)
            # Если кэш полон, удалить самый старый (LRU)
            elif len(self._cache) >= self._max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._evictions += 1

            self._cache[key] = {
                "value": value,
                "expires_at": expires_at,
                "created_at": time.time(),
            }

    async def delete(self, key: str) -> bool:
        """
        Удалить ключ из кэша.

        Args:
            key: Ключ

        Returns:
            True если ключ был удален, False если не найден
        """
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    async def clear(self) -> None:
        """Очистить весь кэш."""
        async with self._lock:
            self._cache.clear()
            logger.info("Cache cleared")

    async def _cleanup_expired(self) -> None:
        """Очистить устаревшие записи."""
        async with self._lock:
            current_time = time.time()
            expired_keys = [
                key for key, entry in self._cache.items() if current_time > entry["expires_at"]
            ]

            for key in expired_keys:
                del self._cache[key]

            if expired_keys:
                logger.debug("Cleaned up %s expired cache entries", len(expired_keys))

    async def get_stats(self) -> dict[str, Any]:
        """
        Получить статистику использования кэша.

        Returns:
            Словарь со статистикой
        """
        async with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

            return {
                "size": len(self._cache),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_rate": round(hit_rate, 2),
                "total_requests": total_requests,
            }


# Глобальные экземпляры кэша для разных категорий данных
_price_cache = TTLCache(max_size=5000, default_ttl=30)  # 30 сек для цен
_market_data_cache = TTLCache(max_size=2000, default_ttl=60)  # 1 мин для маркет данных
_history_cache = TTLCache(max_size=1000, default_ttl=300)  # 5 мин для истории
_user_cache = TTLCache(max_size=500, default_ttl=600)  # 10 мин для пользователей


def cached(
    cache: TTLCache | None = None,
    ttl: int | None = None,
    key_prefix: str = "",
) -> Callable[[Callable[P, Awaitable[T]]], Callable[P, Awaitable[T]]]:
    """
    Декоратор для кэширования результатов асинхронных функций.

    Args:
        cache: Экземпляр TTLCache (по умолчанию _market_data_cache)
        ttl: TTL в секундах (по умолчанию из кэша)
        key_prefix: Префикс для ключей кэша

    Example:
        @cached(cache=_price_cache, ttl=30, key_prefix="item_price")
        async def get_item_price(item_id: str) -> float:
            return await api.get_price(item_id)
    """
    cache_instance = cache or _market_data_cache

    def decorator(func: Callable[P, Awaitable[T]]) -> Callable[P, Awaitable[T]]:
        @wraps(func)
        async def wrapper(*args: P.args, **kwargs: P.kwargs) -> T:
            # Создать ключ кэша из имени функции и аргументов
            cache_key = _make_cache_key(key_prefix or func.__name__, args, kwargs)

            # Попытка получить из кэша
            cached_value = await cache_instance.get(cache_key)
            if cached_value is not None:
                logger.debug("Cache HIT: %s", cache_key)
                return cast("T", cached_value)

            # Вызвать функцию и сохранить результат
            logger.debug("Cache MISS: %s", cache_key)
            result = await func(*args, **kwargs)
            await cache_instance.set(cache_key, result, ttl=ttl)

            return result

        return wrapper

    return decorator


def _make_cache_key(prefix: str, args: tuple[Any, ...], kwargs: dict[str, Any]) -> str:
    """
    Создать ключ кэша из префикса и аргументов.

    Args:
        prefix: Префикс ключа
        args: Позиционные аргументы
        kwargs: Именованные аргументы

    Returns:
        Строка-ключ для кэша
    """
    # Пропустить self/cls
    args_to_use = args[1:] if args and hasattr(args[0], "__dict__") else args

    key_parts = [prefix]

    # Добавить позиционные аргументы
    for arg in args_to_use:
        key_parts.append(str(arg))

    # Добавить именованные аргументы (сортированные для консистентности)
    for k, v in sorted(kwargs.items()):
        key_parts.append(f"{k}={v}")

    return ":".join(key_parts)


async def get_price_cache() -> TTLCache:
    """Получить глобальный кэш цен."""
    return _price_cache


async def get_market_data_cache() -> TTLCache:
    """Получить глобальный кэш маркет данных."""
    return _market_data_cache


async def get_history_cache() -> TTLCache:
    """Получить глобальный кэш истории."""
    return _history_cache


async def get_user_cache() -> TTLCache:
    """Получить глобальный кэш пользователей."""
    return _user_cache


async def start_all_cleanup_tasks() -> None:
    """Запустить фоновую очистку для всех кэшей."""
    await _price_cache.start_cleanup(interval=30)
    await _market_data_cache.start_cleanup(interval=60)
    await _history_cache.start_cleanup(interval=120)
    await _user_cache.start_cleanup(interval=300)
    logger.info("All cache cleanup tasks started")


async def stop_all_cleanup_tasks() -> None:
    """Остановить фоновую очистку для всех кэшей."""
    await _price_cache.stop_cleanup()
    await _market_data_cache.stop_cleanup()
    await _history_cache.stop_cleanup()
    await _user_cache.stop_cleanup()
    logger.info("All cache cleanup tasks stopped")


async def get_all_cache_stats() -> dict[str, dict[str, Any]]:
    """
    Получить статистику всех кэшей.

    Returns:
        Словарь со статистикой каждого кэша
    """
    return {
        "price_cache": await _price_cache.get_stats(),
        "market_data_cache": await _market_data_cache.get_stats(),
        "history_cache": await _history_cache.get_stats(),
        "user_cache": await _user_cache.get_stats(),
    }


async def clear_all_caches() -> None:
    """
    Очистить все глобальные кэши.

    Полезно для тестирования и сброса состояния кэшей.
    """
    await _price_cache.clear()
    await _market_data_cache.clear()
    await _history_cache.clear()
    await _user_cache.clear()
    logger.info("All caches cleared")
