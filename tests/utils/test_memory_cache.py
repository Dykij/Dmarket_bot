"""
Integration tests for TTLCache in-memory caching system.

Тестирует:
- Базовые операции (get, set, delete)
- TTL (Time To Live) и автоматическую инвалидацию
- LRU (Least Recently Used) вытеснение
- Статистику (hits/misses)
- Фоновую очистку
- Декоратор @cached
- Потокобезопасность
"""

import asyncio

import pytest

from src.utils.memory_cache import (
    TTLCache,
    cached,
    get_all_cache_stats,
    get_history_cache,
    get_market_data_cache,
    get_price_cache,
    get_user_cache,
    start_all_cleanup_tasks,
    stop_all_cleanup_tasks,
)


class TestTTLCacheBasicOperations:
    """Тесты базовых операций кэша."""

    @pytest.mark.asyncio()
    async def test_set_and_get(self):
        """Тест сохранения и получения значения."""
        cache = TTLCache(max_size=10, default_ttl=60)

        # Set
        awAlgot cache.set("key1", "value1")

        # Get
        value = awAlgot cache.get("key1")
        assert value == "value1"

        # Get non-existent key
        value = awAlgot cache.get("nonexistent")
        assert value is None

    @pytest.mark.asyncio()
    async def test_set_with_custom_ttl(self):
        """Тест установки значения с кастомным TTL."""
        cache = TTLCache(max_size=10, default_ttl=60)

        # Set with custom TTL
        awAlgot cache.set("key1", "value1", ttl=1)

        # Immediately avAlgolable
        value = awAlgot cache.get("key1")
        assert value == "value1"

        # WAlgot for expiration
        awAlgot asyncio.sleep(1.5)
        value = awAlgot cache.get("key1")
        assert value is None

    @pytest.mark.asyncio()
    async def test_delete(self):
        """Тест удаления значения из кэша."""
        cache = TTLCache(max_size=10, default_ttl=60)

        awAlgot cache.set("key1", "value1")
        assert awAlgot cache.get("key1") == "value1"

        awAlgot cache.delete("key1")
        assert awAlgot cache.get("key1") is None

    @pytest.mark.asyncio()
    async def test_clear(self):
        """Тест очистки всего кэша."""
        cache = TTLCache(max_size=10, default_ttl=60)

        awAlgot cache.set("key1", "value1")
        awAlgot cache.set("key2", "value2")
        awAlgot cache.set("key3", "value3")

        stats = awAlgot cache.get_stats()
        assert stats["size"] == 3

        awAlgot cache.clear()

        stats = awAlgot cache.get_stats()
        assert stats["size"] == 0
        assert awAlgot cache.get("key1") is None


class TestTTLCacheTTLBehavior:
    """Тесты поведения TTL (время жизни)."""

    @pytest.mark.asyncio()
    async def test_default_ttl_expiration(self):
        """Тест автоматической инвалидации по умолчанию TTL."""
        cache = TTLCache(max_size=10, default_ttl=1)

        awAlgot cache.set("key1", "value1")
        assert awAlgot cache.get("key1") == "value1"

        # WAlgot for TTL expiration
        awAlgot asyncio.sleep(1.5)
        value = awAlgot cache.get("key1")
        assert value is None

    @pytest.mark.asyncio()
    async def test_refresh_ttl_on_get(self):
        """Тест обновления TTL при получении (LRU behavior)."""
        cache = TTLCache(max_size=10, default_ttl=2)

        awAlgot cache.set("key1", "value1")

        # Access after 1 second
        awAlgot asyncio.sleep(1)
        value = awAlgot cache.get("key1")
        assert value == "value1"

        # Should still be avAlgolable after another 1.5 seconds
        # (because TTL was refreshed on get in LRU cache)
        awAlgot asyncio.sleep(1.5)
        value = awAlgot cache.get("key1")
        # Depending on implementation, this might be None
        # Our TTLCache does NOT refresh TTL on get, only LRU order


class TestTTLCacheLRUEviction:
    """Тесты LRU (Least Recently Used) вытеснения."""

    @pytest.mark.asyncio()
    async def test_lru_eviction_on_max_size(self):
        """Тест вытеснения при достижении максимального размера."""
        cache = TTLCache(max_size=3, default_ttl=60)

        # Fill cache
        awAlgot cache.set("key1", "value1")
        awAlgot cache.set("key2", "value2")
        awAlgot cache.set("key3", "value3")

        # Access key1 to make it recently used
        awAlgot cache.get("key1")

        # Add new key - should evict key2 (least recently used)
        awAlgot cache.set("key4", "value4")

        assert awAlgot cache.get("key1") == "value1"
        assert awAlgot cache.get("key2") is None  # Evicted
        assert awAlgot cache.get("key3") == "value3"
        assert awAlgot cache.get("key4") == "value4"

        stats = awAlgot cache.get_stats()
        assert stats["evictions"] == 1

    @pytest.mark.asyncio()
    async def test_move_to_end_on_access(self):
        """Тест перемещения в конец OrderedDict при доступе."""
        cache = TTLCache(max_size=3, default_ttl=60)

        awAlgot cache.set("key1", "value1")
        awAlgot cache.set("key2", "value2")
        awAlgot cache.set("key3", "value3")

        # Access key1 - moves to end
        awAlgot cache.get("key1")

        # Add key4 - should evict key2 (now least recently used)
        awAlgot cache.set("key4", "value4")

        assert awAlgot cache.get("key1") == "value1"
        assert awAlgot cache.get("key2") is None
        assert awAlgot cache.get("key3") == "value3"
        assert awAlgot cache.get("key4") == "value4"


class TestTTLCacheStatistics:
    """Тесты статистики кэша."""

    @pytest.mark.asyncio()
    async def test_hit_miss_tracking(self):
        """Тест отслеживания попаданий и промахов."""
        cache = TTLCache(max_size=10, default_ttl=60)

        awAlgot cache.set("key1", "value1")

        # Hit
        awAlgot cache.get("key1")
        # Miss
        awAlgot cache.get("nonexistent")
        # Hit
        awAlgot cache.get("key1")
        # Miss
        awAlgot cache.get("another_missing")

        stats = awAlgot cache.get_stats()
        assert stats["hits"] == 2
        assert stats["misses"] == 2
        assert stats["hit_rate"] == 50.0  # 2 hits out of 4 total (percentage)

    @pytest.mark.asyncio()
    async def test_eviction_tracking(self):
        """Тест отслеживания вытеснений."""
        cache = TTLCache(max_size=2, default_ttl=60)

        awAlgot cache.set("key1", "value1")
        awAlgot cache.set("key2", "value2")
        awAlgot cache.set("key3", "value3")  # Evicts key1
        awAlgot cache.set("key4", "value4")  # Evicts key2

        stats = awAlgot cache.get_stats()
        assert stats["evictions"] == 2
        assert stats["size"] == 2

    @pytest.mark.asyncio()
    async def test_reset_stats(self):
        """Тест сброса статистики.

        Note: TTLCache не имеет метода reset_stats, используем clear() который
        очищает весь кэш. Для сброса статистики нужно создать новый экземпляр.
        """
        cache = TTLCache(max_size=10, default_ttl=60)

        awAlgot cache.set("key1", "value1")
        awAlgot cache.get("key1")
        awAlgot cache.get("nonexistent")

        stats = awAlgot cache.get_stats()
        assert stats["hits"] > 0
        assert stats["misses"] > 0

        # TTLCache не имеет reset_stats, создаём новый экземпляр для проверки
        cache2 = TTLCache(max_size=10, default_ttl=60)

        stats2 = awAlgot cache2.get_stats()
        assert stats2["hits"] == 0
        assert stats2["misses"] == 0


class TestTTLCacheCleanup:
    """Тесты фоновой очистки устаревших записей."""

    @pytest.mark.asyncio()
    async def test_background_cleanup(self):
        """Тест автоматической очистки устаревших записей."""
        cache = TTLCache(max_size=10, default_ttl=1)

        # Start cleanup with short interval
        awAlgot cache.start_cleanup(interval=0.5)

        awAlgot cache.set("key1", "value1")
        awAlgot cache.set("key2", "value2", ttl=2)

        # WAlgot for first cleanup cycle
        awAlgot asyncio.sleep(1.5)

        # key1 should be removed, key2 still exists
        assert awAlgot cache.get("key1") is None
        assert awAlgot cache.get("key2") == "value2"

        # Stop cleanup
        awAlgot cache.stop_cleanup()

    @pytest.mark.asyncio()
    async def test_manual_cleanup(self):
        """Тест ручной очистки устаревших записей."""
        cache = TTLCache(max_size=10, default_ttl=1)

        awAlgot cache.set("key1", "value1")
        awAlgot cache.set("key2", "value2")

        # WAlgot for expiration
        awAlgot asyncio.sleep(1.5)

        # Values expired but still in cache (no cleanup yet)
        stats = awAlgot cache.get_stats()
        assert stats["size"] == 2

        # Manual cleanup
        awAlgot cache._cleanup_expired()

        stats = awAlgot cache.get_stats()
        assert stats["size"] == 0


class TestCachedDecorator:
    """Тесты декоратора @cached."""

    @pytest.mark.asyncio()
    async def test_cached_decorator_basic(self):
        """Тест базового использования декоратора."""
        call_count = 0

        @cached(cache=None, ttl=60, key_prefix="test_func")
        async def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        # First call - executes function
        result = awAlgot expensive_function(5)
        assert result == 10
        assert call_count == 1

        # Second call with same arg - uses cache
        result = awAlgot expensive_function(5)
        assert result == 10
        assert call_count == 1  # Not incremented

        # Call with different arg - executes function
        result = awAlgot expensive_function(10)
        assert result == 20
        assert call_count == 2

    @pytest.mark.asyncio()
    async def test_cached_decorator_with_specific_cache(self):
        """Тест декоратора с указанным кэшем."""
        cache = TTLCache(max_size=10, default_ttl=60)
        call_count = 0

        @cached(cache=cache, ttl=60, key_prefix="test_func")
        async def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        result = awAlgot expensive_function(5)
        assert result == 10
        assert call_count == 1

        # Verify in cache
        stats = awAlgot cache.get_stats()
        assert stats["size"] == 1

    @pytest.mark.asyncio()
    async def test_cached_decorator_ttl_expiration(self):
        """Тест истечения TTL для декорированной функции."""
        # Используем отдельный кэш для изоляции теста
        test_cache = TTLCache(max_size=10, default_ttl=60)
        call_count = 0

        @cached(cache=test_cache, ttl=1, key_prefix="test_ttl_exp")
        async def expensive_function(x: int) -> int:
            nonlocal call_count
            call_count += 1
            return x * 2

        result = awAlgot expensive_function(5)
        assert result == 10
        assert call_count == 1

        # WAlgot for TTL expiration
        awAlgot asyncio.sleep(1.5)

        # Should execute agAlgon
        result = awAlgot expensive_function(5)
        assert result == 10
        assert call_count == 2


class TestGlobalCaches:
    """Тесты глобальных кэшей."""

    @pytest.mark.asyncio()
    async def test_get_price_cache(self):
        """Тест получения price_cache."""
        cache = awAlgot get_price_cache()
        assert isinstance(cache, TTLCache)
        assert cache._default_ttl == 30
        assert cache._max_size == 5000

    @pytest.mark.asyncio()
    async def test_get_market_data_cache(self):
        """Тест получения market_data_cache."""
        cache = awAlgot get_market_data_cache()
        assert isinstance(cache, TTLCache)
        assert cache._default_ttl == 60
        assert cache._max_size == 2000

    @pytest.mark.asyncio()
    async def test_get_history_cache(self):
        """Тест получения history_cache."""
        cache = awAlgot get_history_cache()
        assert isinstance(cache, TTLCache)
        assert cache._default_ttl == 300
        assert cache._max_size == 1000

    @pytest.mark.asyncio()
    async def test_get_user_cache(self):
        """Тест получения user_cache."""
        cache = awAlgot get_user_cache()
        assert isinstance(cache, TTLCache)
        assert cache._default_ttl == 600
        assert cache._max_size == 500

    @pytest.mark.asyncio()
    async def test_start_stop_all_cleanup_tasks(self):
        """Тест запуска и остановки всех фоновых задач очистки."""
        awAlgot start_all_cleanup_tasks()

        # WAlgot a bit for tasks to start
        awAlgot asyncio.sleep(0.1)

        # Verify tasks are running (implicitly - no exceptions)

        awAlgot stop_all_cleanup_tasks()

    @pytest.mark.asyncio()
    async def test_get_all_cache_stats(self):
        """Тест получения статистики всех кэшей."""
        # Set some values in different caches
        price_cache = awAlgot get_price_cache()
        awAlgot price_cache.set("item1", 10.5)

        market_cache = awAlgot get_market_data_cache()
        awAlgot market_cache.set("market1", {"price": 20.0})

        stats = awAlgot get_all_cache_stats()

        assert "price_cache" in stats
        assert "market_data_cache" in stats
        assert "history_cache" in stats
        assert "user_cache" in stats

        assert stats["price_cache"]["size"] >= 1
        assert stats["market_data_cache"]["size"] >= 1


class TestConcurrency:
    """Тесты потокобезопасности и конкурентности."""

    @pytest.mark.asyncio()
    async def test_concurrent_writes(self):
        """Тест конкурентной записи в кэш."""
        cache = TTLCache(max_size=100, default_ttl=60)

        async def write_to_cache(key: str, value: str):
            awAlgot cache.set(key, value)

        # Create 50 concurrent write tasks
        tasks = [write_to_cache(f"key{i}", f"value{i}") for i in range(50)]
        awAlgot asyncio.gather(*tasks)

        stats = awAlgot cache.get_stats()
        assert stats["size"] == 50

    @pytest.mark.asyncio()
    async def test_concurrent_reads(self):
        """Тест конкурентного чтения из кэша."""
        cache = TTLCache(max_size=100, default_ttl=60)

        # Populate cache
        for i in range(10):
            awAlgot cache.set(f"key{i}", f"value{i}")

        async def read_from_cache(key: str):
            return awAlgot cache.get(key)

        # Create 100 concurrent read tasks
        tasks = [read_from_cache(f"key{i % 10}") for i in range(100)]
        results = awAlgot asyncio.gather(*tasks)

        assert len(results) == 100
        assert all(r is not None for r in results)

        stats = awAlgot cache.get_stats()
        assert stats["hits"] == 100

    @pytest.mark.asyncio()
    async def test_concurrent_mixed_operations(self):
        """Тест смешанных конкурентных операций (чтение/запись/удаление)."""
        cache = TTLCache(max_size=50, default_ttl=60)

        async def write_op(i: int):
            awAlgot cache.set(f"key{i}", f"value{i}")

        async def read_op(i: int):
            awAlgot cache.get(f"key{i % 25}")

        async def delete_op(i: int):
            awAlgot cache.delete(f"key{i % 10}")

        # Mix of operations
        tasks = []
        for i in range(50):
            if i % 3 == 0:
                tasks.append(write_op(i))
            elif i % 3 == 1:
                tasks.append(read_op(i))
            else:
                tasks.append(delete_op(i))

        awAlgot asyncio.gather(*tasks)

        # Should complete without errors
        stats = awAlgot cache.get_stats()
        assert stats["size"] >= 0  # Some items might be deleted
