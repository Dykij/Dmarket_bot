"""Тесты для Fallback Cache.

Тестирование функциональности:
- Кэширование с TTL
- Fallback на устаревшие данные при ошибках
- Статистика hit/miss/stale
- Инвалидация кэша
"""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from src.utils.fallback_cache import (
    CacheEntry,
    CacheStats,
    CacheStatus,
    FallbackCache,
    cached,
)


class TestCacheEntry:
    """Тесты для CacheEntry."""

    def test_is_fresh(self):
        """Тест проверки свежести данных."""
        now = datetime.now(UTC)
        entry = CacheEntry(
            data={"test": "data"},
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            stale_expires_at=now + timedelta(hours=1),
        )

        assert entry.is_fresh() is True

    def test_is_stale(self):
        """Тест проверки устаревших данных."""
        now = datetime.now(UTC)
        entry = CacheEntry(
            data={"test": "data"},
            created_at=now - timedelta(minutes=10),
            expires_at=now - timedelta(minutes=5),  # Истёк
            stale_expires_at=now + timedelta(minutes=50),  # Ещё валиден
        )

        assert entry.is_fresh() is False
        assert entry.is_stale_valid() is True

    def test_expired(self):
        """Тест полностью истёкших данных."""
        now = datetime.now(UTC)
        entry = CacheEntry(
            data={"test": "data"},
            created_at=now - timedelta(hours=2),
            expires_at=now - timedelta(hours=1),
            stale_expires_at=now - timedelta(minutes=30),  # Тоже истёк
        )

        assert entry.is_fresh() is False
        assert entry.is_stale_valid() is False

    def test_age_seconds(self):
        """Тест расчёта возраста записи."""
        now = datetime.now(UTC)
        entry = CacheEntry(
            data={"test": "data"},
            created_at=now - timedelta(seconds=30),
            expires_at=now + timedelta(minutes=5),
            stale_expires_at=now + timedelta(hours=1),
        )

        age = entry.age_seconds()
        assert 29 <= age <= 31  # Допускаем небольшую погрешность

    def test_to_dict_and_from_dict(self):
        """Тест сериализации и десериализации."""
        now = datetime.now(UTC)
        entry = CacheEntry(
            data={"test": "data", "nested": {"key": "value"}},
            created_at=now,
            expires_at=now + timedelta(minutes=5),
            stale_expires_at=now + timedelta(hours=1),
            hit_count=10,
            source="api",
        )

        data = entry.to_dict()
        restored = CacheEntry.from_dict(data)

        assert restored.data == entry.data
        assert restored.hit_count == entry.hit_count
        assert restored.source == entry.source


class TestCacheStats:
    """Тесты для CacheStats."""

    def test_record_operations(self):
        """Тест записи операций."""
        stats = CacheStats()

        stats.record_hit()
        stats.record_hit()
        stats.record_miss()
        stats.record_stale_hit()
        stats.record_error()

        assert stats.hits == 2
        assert stats.misses == 1
        assert stats.stale_hits == 1
        assert stats.errors == 1

    def test_hit_rate(self):
        """Тест расчёта hit rate."""
        stats = CacheStats()

        # 8 hits + 2 stale = 10 из 15 = 66.67%
        for _ in range(8):
            stats.record_hit()
        for _ in range(2):
            stats.record_stale_hit()
        for _ in range(5):
            stats.record_miss()

        assert stats.total_requests == 15
        assert stats.hit_rate == pytest.approx(66.67, rel=0.01)

    def test_hit_rate_zero_requests(self):
        """Тест hit rate при нуле запросов."""
        stats = CacheStats()
        assert stats.hit_rate == 0.0


class TestFallbackCache:
    """Тесты для FallbackCache."""

    @pytest.fixture
    def cache(self):
        """Фикстура для создания кэша."""
        return FallbackCache(ttl=60, stale_ttl=3600, max_size=100)

    @pytest.mark.asyncio
    async def test_get_or_fetch_miss(self, cache):
        """Тест получения данных при промахе кэша."""
        fetch_called = False

        async def fetch_data():
            nonlocal fetch_called
            fetch_called = True
            return {"key": "value"}

        data, status = await cache.get_or_fetch("test_key", fetch_data)

        assert fetch_called is True
        assert data == {"key": "value"}
        assert status == CacheStatus.MISS

    @pytest.mark.asyncio
    async def test_get_or_fetch_hit(self, cache):
        """Тест получения данных из кэша (hit)."""
        fetch_count = 0

        async def fetch_data():
            nonlocal fetch_count
            fetch_count += 1
            return {"key": "value"}

        # Первый вызов - miss
        await cache.get_or_fetch("test_key", fetch_data)
        assert fetch_count == 1

        # Второй вызов - hit
        data, status = await cache.get_or_fetch("test_key", fetch_data)

        assert fetch_count == 1  # Fetch не вызван
        assert data == {"key": "value"}
        assert status == CacheStatus.HIT

    @pytest.mark.asyncio
    async def test_stale_fallback_on_error(self):
        """Тест fallback на устаревшие данные при ошибке."""
        # Создаём кэш с очень коротким TTL
        cache = FallbackCache(ttl=1, stale_ttl=3600, max_size=100)
        call_count = 0

        async def fetch_data():
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                raise ConnectionError("API unavailable")
            return {"key": "value"}

        # Первый вызов - успешный
        data1, status1 = await cache.get_or_fetch("test_key", fetch_data)
        assert status1 == CacheStatus.MISS
        assert data1 == {"key": "value"}

        # Ждём истечения TTL (1 секунда + немного)
        await asyncio.sleep(1.1)

        # Второй вызов - ошибка, но есть stale данные
        data2, status2 = await cache.get_or_fetch("test_key", fetch_data)

        assert status2 == CacheStatus.STALE
        assert data2 == {"key": "value"}

    @pytest.mark.asyncio
    async def test_invalidate(self, cache):
        """Тест инвалидации кэша."""

        async def fetch_data():
            return {"key": "value"}

        await cache.get_or_fetch("test_key", fetch_data)
        assert cache._cache.get("test_key") is not None

        deleted = await cache.invalidate("test_key")

        assert deleted is True
        assert cache._cache.get("test_key") is None

    @pytest.mark.asyncio
    async def test_invalidate_pattern(self, cache):
        """Тест инвалидации по паттерну."""

        async def fetch_data(key):
            return {"key": key}

        await cache.get_or_fetch("market_csgo", lambda: fetch_data("csgo"))
        await cache.get_or_fetch("market_dota2", lambda: fetch_data("dota2"))
        await cache.get_or_fetch("user_123", lambda: fetch_data("user"))

        count = await cache.invalidate_pattern("market_*")

        assert count == 2
        assert "user_123" in cache._cache

    @pytest.mark.asyncio
    async def test_clear(self, cache):
        """Тест очистки кэша."""

        async def fetch_data(i):
            return {"index": i}

        for i in range(5):
            await cache.get_or_fetch(f"key_{i}", lambda i=i: fetch_data(i))

        count = await cache.clear()

        assert count == 5
        assert len(cache._cache) == 0

    @pytest.mark.asyncio
    async def test_stats(self, cache):
        """Тест статистики кэша."""

        async def fetch_data():
            return {"key": "value"}

        # Miss
        await cache.get_or_fetch("key1", fetch_data)

        # Hit
        await cache.get_or_fetch("key1", fetch_data)

        stats = cache.get_stats()

        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["cache_size"] == 1
        assert stats["hit_rate"] == 50.0

    @pytest.mark.asyncio
    async def test_max_size_eviction(self):
        """Тест вытеснения при превышении размера."""
        cache = FallbackCache(ttl=60, stale_ttl=3600, max_size=5)

        async def fetch_data(i):
            return {"index": i}

        # Добавляем 10 записей в кэш размером 5
        for i in range(10):
            await cache.get_or_fetch(f"key_{i}", lambda i=i: fetch_data(i))

        # Размер не должен превышать max_size
        assert len(cache._cache) <= 5

    def test_make_key(self):
        """Тест создания ключа."""
        key = FallbackCache.make_key("market", "csgo", min_price=10, max_price=100)

        assert "market" in key
        assert "csgo" in key
        assert "min_price_10" in key
        assert "max_price_100" in key

    def test_make_hash_key(self):
        """Тест создания хэшированного ключа."""
        key = FallbackCache.make_hash_key("long_query_data", filters={"a": 1, "b": 2})

        assert key.startswith("long_query")
        assert len(key) < 30  # Короткий ключ


class TestCachedDecorator:
    """Тесты для декоратора @cached."""

    @pytest.mark.asyncio
    async def test_cached_decorator(self):
        """Тест декоратора кэширования."""
        call_count = 0

        @cached(ttl=60, key_prefix="test")
        async def fetch_data(item_id: str) -> dict:
            nonlocal call_count
            call_count += 1
            return {"item_id": item_id}

        # Первый вызов
        result1 = await fetch_data("123")
        assert call_count == 1

        # Второй вызов (из кэша)
        result2 = await fetch_data("123")
        assert call_count == 1  # Не увеличился

        assert result1 == result2

    @pytest.mark.asyncio
    async def test_cached_decorator_different_args(self):
        """Тест декоратора с разными аргументами."""
        call_count = 0

        @cached(ttl=60)
        async def fetch_data(item_id: str) -> dict:
            nonlocal call_count
            call_count += 1
            return {"item_id": item_id}

        await fetch_data("123")
        await fetch_data("456")

        assert call_count == 2  # Разные аргументы = разные ключи
