"""Тесты для модуля performance.

Проверяет утилиты оптимизации производительности.
"""

import time

from src.utils.performance import AdvancedCache


class TestAdvancedCache:
    """Тесты класса AdvancedCache."""

    def test_cache_initialization(self):
        """Тест инициализации кеша."""
        cache = AdvancedCache(default_ttl=300)
        assert cache._default_ttl == 300
        assert cache._hits == 0
        assert cache._misses == 0
        assert len(cache._caches) == 0

    def test_cache_initialization_default_ttl(self):
        """Тест инициализации с TTL по умолчанию."""
        cache = AdvancedCache()
        assert cache._default_ttl == 300

    def test_cache_initialization_custom_ttl(self):
        """Тест инициализации с custom TTL."""
        cache = AdvancedCache(default_ttl=600)
        assert cache._default_ttl == 600

    def test_register_cache(self):
        """Тест регистрации нового хранилища кеша."""
        cache = AdvancedCache()
        cache.register_cache("test_cache")
        assert "test_cache" in cache._caches
        assert cache._ttls["test_cache"] == 300

    def test_register_cache_with_custom_ttl(self):
        """Тест регистрации кеша с custom TTL."""
        cache = AdvancedCache()
        cache.register_cache("test_cache", ttl=600)
        assert cache._ttls["test_cache"] == 600

    def test_register_cache_idempotent(self):
        """Тест что повторная регистрация не меняет кеш."""
        cache = AdvancedCache()
        cache.register_cache("test_cache", ttl=100)
        cache.set("test_cache", "key1", "value1")

        # Регистрируем повторно
        cache.register_cache("test_cache", ttl=200)

        # TTL не должен измениться
        assert cache._ttls["test_cache"] == 100
        assert cache.get("test_cache", "key1") == "value1"

    def test_set_and_get_value(self):
        """Тест сохранения и получения значения."""
        cache = AdvancedCache()
        cache.set("test_cache", "key1", "value1")
        result = cache.get("test_cache", "key1")
        assert result == "value1"

    def test_get_nonexistent_key(self):
        """Тест получения несуществующего ключа."""
        cache = AdvancedCache()
        result = cache.get("test_cache", "nonexistent")
        assert result is None
        assert cache._misses == 1

    def test_get_from_nonexistent_cache(self):
        """Тест получения из несуществующего кеша."""
        cache = AdvancedCache()
        result = cache.get("nonexistent_cache", "key1")
        assert result is None
        assert "nonexistent_cache" in cache._caches  # Автоматически создается

    def test_cache_hit_counter(self):
        """Тест счетчика попаданий в кеш."""
        cache = AdvancedCache()
        cache.set("test_cache", "key1", "value1")
        cache.get("test_cache", "key1")
        cache.get("test_cache", "key1")
        assert cache._hits == 2

    def test_cache_miss_counter(self):
        """Тест счетчика промахов кеша."""
        cache = AdvancedCache()
        cache.get("test_cache", "key1")
        cache.get("test_cache", "key2")
        assert cache._misses == 2

    def test_cache_expiration(self):
        """Тест истечения срока действия кеша."""
        cache = AdvancedCache(default_ttl=1)
        cache.set("test_cache", "key1", "value1")

        # Ждем истечения TTL
        time.sleep(1.1)

        result = cache.get("test_cache", "key1")
        assert result is None
        assert cache._misses == 1

    def test_cache_not_expired(self):
        """Тест что кеш не истекает раньше времени."""
        cache = AdvancedCache(default_ttl=5)
        cache.set("test_cache", "key1", "value1")

        # Получаем сразу
        result = cache.get("test_cache", "key1")
        assert result == "value1"
        assert cache._hits == 1

    def test_multiple_caches(self):
        """Тест работы с несколькими хранилищами."""
        cache = AdvancedCache()
        cache.set("cache1", "key1", "value1")
        cache.set("cache2", "key2", "value2")

        assert cache.get("cache1", "key1") == "value1"
        assert cache.get("cache2", "key2") == "value2"

    def test_same_key_different_caches(self):
        """Тест одинаковых ключей в разных хранилищах."""
        cache = AdvancedCache()
        cache.set("cache1", "key", "value1")
        cache.set("cache2", "key", "value2")

        assert cache.get("cache1", "key") == "value1"
        assert cache.get("cache2", "key") == "value2"

    def test_overwrite_value(self):
        """Тест перезаписи значения."""
        cache = AdvancedCache()
        cache.set("test_cache", "key1", "value1")
        cache.set("test_cache", "key1", "value2")

        result = cache.get("test_cache", "key1")
        assert result == "value2"

    def test_cache_with_tuple_key(self):
        """Тест использования tuple в качестве ключа."""
        cache = AdvancedCache()
        cache.set("test_cache", ("key1", "key2"), "value")
        result = cache.get("test_cache", ("key1", "key2"))
        assert result == "value"

    def test_cache_with_complex_value(self):
        """Тест сохранения сложных объектов."""
        cache = AdvancedCache()
        complex_value = {"nested": {"data": [1, 2, 3]}}
        cache.set("test_cache", "key1", complex_value)
        result = cache.get("test_cache", "key1")
        assert result == complex_value

    def test_cache_with_none_value(self):
        """Тест сохранения None."""
        cache = AdvancedCache()
        cache.set("test_cache", "key1", None)
        result = cache.get("test_cache", "key1")
        assert result is None
        assert cache._hits == 1  # Должно быть попадание

    def test_expired_cache_removed(self):
        """Тест что истекший кеш удаляется."""
        cache = AdvancedCache(default_ttl=1)
        cache.set("test_cache", "key1", "value1")

        time.sleep(1.1)
        cache.get("test_cache", "key1")

        # Проверяем что ключ удален
        assert "key1" not in cache._caches["test_cache"]

    def test_different_ttls_for_different_caches(self):
        """Тест разных TTL для разных хранилищ."""
        cache = AdvancedCache()
        cache.register_cache("short_ttl", ttl=1)
        cache.register_cache("long_ttl", ttl=10)

        cache.set("short_ttl", "key", "value1")
        cache.set("long_ttl", "key", "value2")

        time.sleep(1.1)

        assert cache.get("short_ttl", "key") is None
        assert cache.get("long_ttl", "key") == "value2"

    def test_cache_statistics(self):
        """Тест статистики кеша."""
        cache = AdvancedCache()

        # 3 промаха
        cache.get("test_cache", "key1")
        cache.get("test_cache", "key2")
        cache.get("test_cache", "key3")

        # Добавляем значения
        cache.set("test_cache", "key1", "value1")
        cache.set("test_cache", "key2", "value2")

        # 2 попадания
        cache.get("test_cache", "key1")
        cache.get("test_cache", "key2")

        # 1 промах
        cache.get("test_cache", "key3")

        assert cache._hits == 2
        assert cache._misses == 4

    def test_empty_string_key(self):
        """Тест использования пустой строки в качестве ключа."""
        cache = AdvancedCache()
        cache.set("test_cache", "", "empty_key_value")
        result = cache.get("test_cache", "")
        assert result == "empty_key_value"

    def test_numeric_key(self):
        """Тест использования числового ключа."""
        cache = AdvancedCache()
        cache.set("test_cache", 123, "numeric_key")
        result = cache.get("test_cache", 123)
        assert result == "numeric_key"

    def test_boolean_value(self):
        """Тест сохранения boolean значений."""
        cache = AdvancedCache()
        cache.set("test_cache", "true_key", True)
        cache.set("test_cache", "false_key", False)

        assert cache.get("test_cache", "true_key") is True
        assert cache.get("test_cache", "false_key") is False

    def test_zero_ttl(self):
        """Тест с нулевым TTL (мгновенное истечение)."""
        cache = AdvancedCache(default_ttl=0)
        cache.set("test_cache", "key1", "value1")

        # Даже минимальная задержка должна привести к истечению
        time.sleep(0.01)
        result = cache.get("test_cache", "key1")
        assert result is None

    def test_very_long_ttl(self):
        """Тест с очень длинным TTL."""
        cache = AdvancedCache(default_ttl=86400)  # 1 день
        cache.set("test_cache", "key1", "value1")
        result = cache.get("test_cache", "key1")
        assert result == "value1"

    def test_cache_name_with_special_characters(self):
        """Тест имени кеша со спецсимволами."""
        cache = AdvancedCache()
        cache.set("cache-with-dash_and_underscore.123", "key", "value")
        result = cache.get("cache-with-dash_and_underscore.123", "key")
        assert result == "value"

    def test_large_number_of_keys(self):
        """Тест с большим количеством ключей."""
        cache = AdvancedCache()

        # Добавляем 1000 ключей
        for i in range(1000):
            cache.set("test_cache", f"key_{i}", f"value_{i}")

        # Проверяем несколько случайных
        assert cache.get("test_cache", "key_0") == "value_0"
        assert cache.get("test_cache", "key_500") == "value_500"
        assert cache.get("test_cache", "key_999") == "value_999"

    def test_cache_update_resets_timestamp(self):
        """Тест что обновление значения сбрасывает timestamp."""
        cache = AdvancedCache(default_ttl=2)
        cache.set("test_cache", "key1", "value1")

        time.sleep(1)

        # Обновляем значение
        cache.set("test_cache", "key1", "value2")

        # Ждем еще 1 секунду (в сумме 2, но обновление было 1 сек назад)
        time.sleep(1)

        # Значение должно быть доступно
        result = cache.get("test_cache", "key1")
        assert result == "value2"

    def test_invalidate_specific_key(self):
        """Тест инвалидации конкретного ключа."""
        cache = AdvancedCache()
        cache.set("test_cache", "key1", "value1")
        cache.set("test_cache", "key2", "value2")

        cache.invalidate("test_cache", "key1")

        assert cache.get("test_cache", "key1") is None
        assert cache.get("test_cache", "key2") == "value2"

    def test_invalidate_entire_cache(self):
        """Тест инвалидации всего кеша."""
        cache = AdvancedCache()
        cache.set("test_cache", "key1", "value1")
        cache.set("test_cache", "key2", "value2")

        cache.invalidate("test_cache")

        assert cache.get("test_cache", "key1") is None
        assert cache.get("test_cache", "key2") is None

    def test_invalidate_nonexistent_cache(self):
        """Инвалидация несуществующего кеша не должна вызывать ошибку."""
        cache = AdvancedCache()
        # Не должно вызывать исключение
        cache.invalidate("nonexistent_cache")
        cache.invalidate("nonexistent_cache", "some_key")

    def test_clear_all(self):
        """Тест очистки всех кешей."""
        cache = AdvancedCache()
        cache.set("cache1", "key1", "value1")
        cache.set("cache2", "key2", "value2")

        cache.clear_all()

        assert cache.get("cache1", "key1") is None
        assert cache.get("cache2", "key2") is None

    def test_get_stats_empty(self):
        """Тест статистики пустого кеша."""
        cache = AdvancedCache()
        cache._hits = 0
        cache._misses = 0
        stats = cache.get_stats()

        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["hit_rate_percent"] == 0
        assert stats["caches"] == {}

    def test_get_stats_with_data(self):
        """Тест статистики с данными."""
        cache = AdvancedCache()
        cache._hits = 0
        cache._misses = 0
        cache.set("test_cache", "key1", "value1")

        # Hit
        cache.get("test_cache", "key1")
        # Miss
        cache.get("test_cache", "nonexistent")

        stats = cache.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate_percent"] == 50.0
        assert "test_cache" in stats["caches"]
        assert stats["caches"]["test_cache"]["size"] == 1

    def test_hit_rate_calculation(self):
        """Тест расчета hit rate."""
        cache = AdvancedCache()
        cache._hits = 0
        cache._misses = 0
        cache.set("test_cache", "key1", "value1")

        # 4 hits
        for _ in range(4):
            cache.get("test_cache", "key1")

        # 1 miss
        cache.get("test_cache", "nonexistent")

        stats = cache.get_stats()
        assert stats["hit_rate_percent"] == 80.0  # 4/(4+1) = 80%


import asyncio
from unittest.mock import patch

import pytest

from src.utils.performance import (
    AsyncBatch,
    cached,
    global_cache,
    profile_performance,
)


class TestCachedDecorator:
    """Тесты для декоратора cached."""

    def setup_method(self):
        """Сброс глобального кеша перед каждым тестом."""
        global_cache.clear_all()
        global_cache._hits = 0
        global_cache._misses = 0

    def test_cached_sync_function(self):
        """Тест кеширования синхронной функции."""
        call_count = 0

        @cached("sync_cache")
        def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # Первый вызов
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1

        # ВтоSwarm вызов - из кеша
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Функция не вызвана повторно

    @pytest.mark.asyncio()
    async def test_cached_async_function(self):
        """Тест кеширования асинхронной функции."""
        call_count = 0

        @cached("async_cache")
        async def async_expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 3

        # Первый вызов
        result1 = await async_expensive_function(5)
        assert result1 == 15
        assert call_count == 1

        # ВтоSwarm вызов - из кеша
        result2 = await async_expensive_function(5)
        assert result2 == 15
        assert call_count == 1

    def test_cached_different_args(self):
        """Тест кеширования с разными аргументами."""
        call_count = 0

        @cached("args_cache")
        def func(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        func(1)  # call_count = 1
        func(2)  # call_count = 2
        func(1)  # из кеша, call_count = 2
        func(2)  # из кеша, call_count = 2

        assert call_count == 2

    def test_cached_custom_key_function(self):
        """Тест с кастомной функцией генерации ключа."""

        @cached("custom_key_cache", key_function=lambda x, y: f"{x}-{y}")
        def func(x: int, y: int) -> int:
            return x + y

        result1 = func(1, 2)
        result2 = func(1, 2)

        assert result1 == result2 == 3

    def test_cached_with_kwargs(self):
        """Тест кеширования с kwargs."""
        call_count = 0

        @cached("kwargs_cache")
        def func(x: int, multiplier: int = 2) -> int:
            nonlocal call_count
            call_count += 1
            return x * multiplier

        func(5, multiplier=3)
        func(5, multiplier=3)  # из кеша
        func(5, multiplier=4)  # другой ключ

        assert call_count == 2

    def test_cached_preserves_function_name(self):
        """Декоратор должен сохранять имя функции."""

        @cached("name_cache")
        def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"


class TestProfilePerformanceDecorator:
    """Тесты для декоратора profile_performance."""

    def test_profile_sync_function(self):
        """Тест профилирования синхронной функции."""

        @profile_performance
        def sync_func(x: int) -> int:
            return x * 2

        result = sync_func(5)
        assert result == 10

    @pytest.mark.asyncio()
    async def test_profile_async_function(self):
        """Тест профилирования асинхронной функции."""

        @profile_performance
        async def async_func(x: int) -> int:
            await asyncio.sleep(0.01)
            return x * 2

        result = await async_func(5)
        assert result == 10

    def test_profile_logs_execution_time(self):
        """Тест логирования времени выполнения."""
        with patch("src.utils.performance.logger") as mock_logger:

            @profile_performance
            def func() -> str:
                time.sleep(0.01)
                return "done"

            result = func()

            assert result == "done"
            mock_logger.info.assert_called()

    @pytest.mark.asyncio()
    async def test_profile_async_logs_execution_time(self):
        """Тест логирования времени выполнения async функции."""
        with patch("src.utils.performance.logger") as mock_logger:

            @profile_performance
            async def async_func() -> str:
                await asyncio.sleep(0.01)
                return "done"

            result = await async_func()

            assert result == "done"
            mock_logger.info.assert_called()

    def test_profile_preserves_function_name(self):
        """Декоратор должен сохранять имя функции."""

        @profile_performance
        def my_function() -> None:
            pass

        assert my_function.__name__ == "my_function"

    def test_profile_exception_handling(self):
        """Тест обработки исключений при профилировании."""

        @profile_performance
        def func_with_error() -> None:
            raise ValueError("Test error")

        with pytest.raises(ValueError, match="Test error"):
            func_with_error()


class TestAsyncBatch:
    """Тесты для класса AsyncBatch."""

    @pytest.mark.asyncio()
    async def test_init_default_values(self):
        """Тест инициализации с дефолтными значениями."""
        batch = AsyncBatch()
        assert batch.max_concurrent == 5
        assert batch.delay == 0.1

    @pytest.mark.asyncio()
    async def test_init_custom_values(self):
        """Тест инициализации с кастомными значениями."""
        batch = AsyncBatch(max_concurrent=10, delay_between_batches=0.5)
        assert batch.max_concurrent == 10
        assert batch.delay == 0.5

    @pytest.mark.asyncio()
    async def test_execute_single_task(self):
        """Тест выполнения одной задачи."""
        batch = AsyncBatch()

        async def task() -> int:
            return 42

        results = await batch.execute([task()])
        assert results == [42]

    @pytest.mark.asyncio()
    async def test_execute_multiple_tasks(self):
        """Тест выполнения нескольких задач."""
        batch = AsyncBatch(max_concurrent=5)

        async def task(x: int) -> int:
            return x * 2

        tasks = [task(i) for i in range(5)]
        results = await batch.execute(tasks)

        assert results == [0, 2, 4, 6, 8]

    @pytest.mark.asyncio()
    async def test_execute_preserves_order(self):
        """Результаты должны сохранять порядок задач."""
        batch = AsyncBatch(max_concurrent=3)

        async def task(x: int) -> int:
            await asyncio.sleep(0.01 * (10 - x))  # Разное время выполнения
            return x

        tasks = [task(i) for i in range(5)]
        results = await batch.execute(tasks)

        assert results == [0, 1, 2, 3, 4]

    @pytest.mark.asyncio()
    async def test_execute_empty_list(self):
        """Тест выполнения пустого списка задач."""
        batch = AsyncBatch()
        results = await batch.execute([])
        assert results == []

    @pytest.mark.asyncio()
    async def test_execute_respects_concurrency_limit(self):
        """Тест соблюдения лимита параллельности."""
        batch = AsyncBatch(max_concurrent=2)
        concurrent_count = 0
        max_concurrent_observed = 0

        async def task(x: int) -> int:
            nonlocal concurrent_count, max_concurrent_observed
            concurrent_count += 1
            max_concurrent_observed = max(max_concurrent_observed, concurrent_count)
            await asyncio.sleep(0.05)
            concurrent_count -= 1
            return x

        tasks = [task(i) for i in range(6)]
        await batch.execute(tasks)

        assert max_concurrent_observed <= 2

    @pytest.mark.asyncio()
    async def test_execute_with_exception(self):
        """Тест обработки исключений в задачах."""
        batch = AsyncBatch()

        async def failing_task() -> None:
            raise ValueError("Task failed")

        async def success_task() -> int:
            return 42

        # gather с return_exceptions=False вызовет исключение
        with pytest.raises(ValueError):
            await batch.execute([success_task(), failing_task()])


class TestGlobalCache:
    """Тесты для глобального экземпляра кеша."""

    def setup_method(self):
        """Сброс глобального кеша."""
        global_cache.clear_all()

    def test_global_cache_exists(self):
        """Глобальный кеш должен существовать."""
        assert global_cache is not None
        assert isinstance(global_cache, AdvancedCache)

    def test_global_cache_shared(self):
        """Глобальный кеш должен быть общим."""
        global_cache.set("shared_cache", "key1", "value1")

        # Импортируем снова и проверяем
        from src.utils.performance import global_cache as another_ref

        assert another_ref.get("shared_cache", "key1") == "value1"

    def test_global_cache_default_ttl(self):
        """Глобальный кеш должен иметь дефолтный TTL."""
        assert global_cache._default_ttl == 300
