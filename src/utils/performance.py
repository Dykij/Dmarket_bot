"""Утилиты для оптимизации производительности проекта."""

import asyncio
import functools
import logging
import time
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

# Типы для аннотаций
T = TypeVar("T")
CacheKey = str | tuple[Any, ...]
CacheValue = tuple[Any, float]  # (значение, время_создания)


class AdvancedCache:
    """Продвинутый кеш с контролем TTL и отдельными хранилищами для разных типов данных."""

    def __init__(self, default_ttl: int = 300) -> None:
        """Инициализирует кеш.

        Args:
            default_ttl: Время жизни кеша по умолчанию в секундах

        """
        self._caches: dict[str, dict[CacheKey, CacheValue]] = {}
        self._default_ttl = default_ttl
        self._ttls: dict[str, int] = {}
        self._hits = 0
        self._misses = 0

    def register_cache(self, name: str, ttl: int | None = None) -> None:
        """Регистрирует новое хранилище кеша.

        Args:
            name: Имя кеша
            ttl: Время жизни кеша в секундах, если отличается от стандартного

        """
        if name not in self._caches:
            self._caches[name] = {}
            self._ttls[name] = ttl if ttl is not None else self._default_ttl
            logger.debug(
                f"Создано новое хранилище кеша '{name}' с TTL={self._ttls[name]} сек",
            )

    def get(self, cache_name: str, key: CacheKey) -> Any | None:
        """Получает значение из кеша, если оно существует и не устарело.

        Args:
            cache_name: Имя хранилища кеша
            key: Ключ для поиска в кеше

        Returns:
            Значение из кеша или None, если кеш устарел или отсутствует

        """
        if cache_name not in self._caches:
            self.register_cache(cache_name)
            self._misses += 1
            return None

        cache_storage = self._caches[cache_name]
        if key not in cache_storage:
            self._misses += 1
            return None

        value, timestamp = cache_storage[key]
        ttl = self._ttls[cache_name]

        if time.time() - timestamp > ttl:
            # Кеш устарел
            logger.debug(
                f"Кеш '{cache_name}' для ключа {key} устарел (возраст: {time.time() - timestamp:.1f}с, TTL: {ttl}с)",
            )
            del cache_storage[key]
            self._misses += 1
            return None

        self._hits += 1
        return value

    def set(self, cache_name: str, key: CacheKey, value: Any) -> None:
        """Устанавливает значение в кеш.

        Args:
            cache_name: Имя хранилища кеша
            key: Ключ для сохранения в кеше
            value: Значение для сохранения

        """
        if cache_name not in self._caches:
            self.register_cache(cache_name)

        self._caches[cache_name][key] = (value, time.time())
        logger.debug("Сохранено в кеш '%s', ключ: %s", cache_name, key)

    def invalidate(self, cache_name: str, key: CacheKey | None = None) -> None:
        """Инвалидирует кеш (полностью или по ключу).

        Args:
            cache_name: Имя хранилища кеша
            key: Если задан - инвалидирует только этот ключ, иначе весь кеш

        """
        if cache_name not in self._caches:
            return

        if key is not None:
            if key in self._caches[cache_name]:
                del self._caches[cache_name][key]
                logger.debug("Инвалидирован ключ %s в кеше '%s'", key, cache_name)
        else:
            self._caches[cache_name].clear()
            logger.debug("Полностью очищен кеш '%s'", cache_name)

    def clear_all(self) -> None:
        """Очищает все кеши."""
        for cache_name in self._caches:
            self._caches[cache_name].clear()
        logger.info("Все кеши очищены")

    def get_stats(self) -> dict[str, Any]:
        """Возвращает статистику использования кеша.

        Returns:
            Словарь со статистикой: количество хитов, промахов, хранилищ,
            процент хитов, размеры хранилищ

        """
        total_requests = self._hits + self._misses
        hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0

        stats: dict[str, Any] = {
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate_percent": hit_rate,
            "caches": {},
        }

        for cache_name, storage in self._caches.items():
            stats["caches"][cache_name] = {
                "size": len(storage),
                "ttl": self._ttls[cache_name],
            }

        return stats


# Создаем глобальный экземпляр кеша для использования во всем проекте
global_cache = AdvancedCache()


def cached(
    cache_name: str,
    key_function: Callable[..., CacheKey] | None = None,
    ttl: int | None = None,
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Декоратор для кеширования результатов функций.

    Args:
        cache_name: Имя хранилища кеша
        key_function: Функция для генерации ключа кеша на основе аргументов
        ttl: Время жизни кеша в секундах

    Returns:
        Декорированная функция с кешированием результатов

    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                # Генерируем ключ кеша
                if key_function is not None:
                    cache_key = key_function(*args, **kwargs)
                else:
                    # По умолчанию используем аргументы как ключ
                    cache_key = (args, tuple(sorted(kwargs.items())))

                # Регистрируем кеш при необходимости
                if ttl is not None and cache_name not in global_cache._ttls:
                    global_cache.register_cache(cache_name, ttl)

                # Проверяем кеш
                cached_result = global_cache.get(cache_name, cache_key)
                if cached_result is not None:
                    logger.debug("Возвращен результат из кеша для %s", func.__name__)
                    return cached_result  # type: ignore[no-any-return]

                # Выполняем функцию и кешируем результат
                result = await func(*args, **kwargs)
                global_cache.set(cache_name, cache_key, result)
                return result  # type: ignore[no-any-return]

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Генерируем ключ кеша
            if key_function is not None:
                cache_key = key_function(*args, **kwargs)
            else:
                # По умолчанию используем аргументы как ключ
                cache_key = (args, tuple(sorted(kwargs.items())))

            # Регистрируем кеш при необходимости
            if ttl is not None and cache_name not in global_cache._ttls:
                global_cache.register_cache(cache_name, ttl)

            # Проверяем кеш
            cached_result = global_cache.get(cache_name, cache_key)
            if cached_result is not None:
                logger.debug(f"Возвращен результат из кеша для {func.__name__}")
                return cached_result  # type: ignore[no-any-return]

            # Выполняем функцию и кешируем результат
            result = func(*args, **kwargs)
            global_cache.set(cache_name, cache_key, result)
            return result

        return wrapper

    return decorator


def profile_performance(func: Callable[..., T]) -> Callable[..., T]:  # noqa: UP047
    """Декоратор для профилирования производительности функций.

    Args:
        func: Функция для профилирования

    Returns:
        Декорированная функция с профилированием

    """
    if asyncio.iscoroutinefunction(func):

        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> T:
            start_time = time.time()
            try:
                return await func(*args, **kwargs)  # type: ignore[no-any-return]
            finally:
                execution_time = time.time() - start_time
                logger.info(
                    "Время выполнения %s: %.4f сек",
                    func.__name__,
                    execution_time,
                )

        return async_wrapper  # type: ignore[return-value]

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> T:
        start_time = time.time()
        try:
            return func(*args, **kwargs)
        finally:
            execution_time = time.time() - start_time
            logger.info(
                "Время выполнения %s: %.4f сек",
                func.__name__,
                execution_time,
            )

    return wrapper


class AsyncBatch:
    """Класс для выполнения и группировки асинхронных операций пакетами.

    Помогает оптимизировать исполнение множества асинхронных задач путем
    их группировки в пакеты с ограниченным количеством одновременных операций.
    """

    def __init__(self, max_concurrent: int = 5, delay_between_batches: float = 0.1) -> None:
        """Инициализирует объект для пакетного исполнения.

        Args:
            max_concurrent: Максимальное количество одновременных операций
            delay_between_batches: Задержка между группами операций в секундах

        """
        self.max_concurrent = max_concurrent
        self.delay = delay_between_batches
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def execute(self, tasks: list[Any]) -> list[Any]:
        """Выполняет список асинхронных задач с ограничением по параллельности.

        Args:
            tasks: Список корутин для выполнения

        Returns:
            Список результатов выполнения задач в том же порядке

        """

        async def _wrapped_task(task: Any) -> Any:
            async with self._semaphore:
                return await task

        # Оборачиваем задачи для обработки через семафор
        wrapped_tasks = [_wrapped_task(task) for task in tasks]

        # Выполняем задачи и возвращаем результаты
        return await asyncio.gather(*wrapped_tasks)
