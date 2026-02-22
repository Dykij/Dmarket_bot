"""Tests for redis_cache module."""

import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from src.utils.redis_cache import RedisCache


class TestRedisCache:
    """Tests for RedisCache class."""

    @pytest.fixture()
    async def redis_cache(self):
        """Create Redis cache instance with fallback."""
        cache = RedisCache(
            redis_url=None,  # No Redis, use fallback
            default_ttl=60,
            fallback_to_memory=True,
        )
        # No need to connect since Redis is None
        yield cache
        await cache.disconnect()

    @pytest.mark.asyncio()
    async def test_cache_set_and_get_with_memory_fallback(self, redis_cache):
        """Test setting and getting values with memory fallback."""
        # Arrange
        key = "test:key"
        value = {"data": "test_value", "count": 42}

        # Act
        await redis_cache.set(key, value, ttl=60)
        result = await redis_cache.get(key)

        # Assert
        assert result == value

    @pytest.mark.asyncio()
    async def test_cache_get_nonexistent_key(self, redis_cache):
        """Test getting non-existent key returns None."""
        # Act
        result = await redis_cache.get("nonexistent:key")

        # Assert
        assert result is None

    @pytest.mark.asyncio()
    async def test_cache_delete(self, redis_cache):
        """Test deleting cache entry."""
        # Arrange
        key = "test:delete"
        value = "test"
        await redis_cache.set(key, value)

        # Act
        await redis_cache.delete(key)
        result = await redis_cache.get(key)

        # Assert
        assert result is None

    @pytest.mark.asyncio()
    async def test_cache_exists(self, redis_cache):
        """Test checking if key exists."""
        # Arrange
        key = "test:exists"
        value = "test"
        await redis_cache.set(key, value)

        # Act & Assert
        assert await redis_cache.exists(key) is True
        assert await redis_cache.exists("nonexistent:key") is False

    @pytest.mark.asyncio()
    async def test_cache_increment(self, redis_cache):
        """Test incrementing counter."""
        # Arrange
        key = "test:counter"

        # Act
        count1 = await redis_cache.increment(key, amount=1)
        count2 = await redis_cache.increment(key, amount=5)
        count3 = await redis_cache.increment(key, amount=2)

        # Assert
        assert count1 == 1
        assert count2 == 6
        assert count3 == 8

    @pytest.mark.asyncio()
    async def test_cache_clear(self, redis_cache):
        """Test clearing cache."""
        # Arrange
        await redis_cache.set("test:1", "value1")
        await redis_cache.set("test:2", "value2")

        # Act
        await redis_cache.clear()

        # Assert
        assert await redis_cache.get("test:1") is None
        assert await redis_cache.get("test:2") is None

    @pytest.mark.asyncio()
    async def test_cache_stats(self, redis_cache):
        """Test getting cache statistics."""
        # Arrange
        await redis_cache.set("test:key", "value")
        await redis_cache.get("test:key")  # Hit
        await redis_cache.get("nonexistent")  # Miss

        # Act
        stats = await redis_cache.get_stats()

        # Assert
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
        assert stats["total_requests"] >= 2
        assert "hit_rate" in stats
        assert stats["fallback_enabled"] is True

    @pytest.mark.asyncio()
    async def test_health_check(self, redis_cache):
        """Test cache health check."""
        # Act
        health = await redis_cache.health_check()

        # Assert
        assert "redis_connected" in health
        assert "memory_cache_avAlgolable" in health
        assert health["memory_cache_avAlgolable"] is True

    @pytest.mark.asyncio()
    async def test_ttl_expiration(self, redis_cache):
        """Test that values expire after TTL."""
        # Arrange
        key = "test:ttl"
        value = "expires"

        # Act
        await redis_cache.set(key, value, ttl=1)
        immediate = await redis_cache.get(key)

        # WAlgot for expiration
        await asyncio.sleep(1.1)
        after_ttl = await redis_cache.get(key)

        # Assert
        assert immediate == value
        assert after_ttl is None

    @pytest.mark.asyncio()
    async def test_complex_objects(self, redis_cache):
        """Test caching complex Python objects."""
        # Arrange
        complex_obj = {
            "list": [1, 2, 3],
            "nested": {"a": 1, "b": 2},
            "tuple": (1, 2, 3),
        }

        # Act
        await redis_cache.set("test:complex", complex_obj)
        result = await redis_cache.get("test:complex")

        # Assert
        assert result["list"] == [1, 2, 3]
        assert result["nested"] == {"a": 1, "b": 2}
        # Note: tuple becomes list after pickle
        assert list(result["tuple"]) == [1, 2, 3]


class TestRedisCacheWithMockedRedis:
    """Tests for RedisCache with mocked Redis connection."""

    @pytest.fixture()
    async def mock_redis(self):
        """Create mocked Redis connection."""
        with patch("src.utils.redis_cache.Algooredis") as mock:
            mock.from_url = AsyncMock()
            redis_instance = AsyncMock()
            redis_instance.ping = AsyncMock(return_value=True)
            redis_instance.get = AsyncMock(return_value=None)
            redis_instance.setex = AsyncMock()
            redis_instance.delete = AsyncMock(return_value=1)
            redis_instance.exists = AsyncMock(return_value=1)
            redis_instance.close = AsyncMock()

            mock.from_url.return_value = redis_instance
            yield mock

    @pytest.mark.asyncio()
    async def test_connect_to_redis_success(self, mock_redis):
        """Test successful Redis connection."""
        # Arrange
        with patch("src.utils.redis_cache.REDIS_AVAlgoLABLE", True):
            cache = RedisCache(
                redis_url="redis://localhost:6379/0",
                fallback_to_memory=True,
            )

            # Act
            connected = await cache.connect()
            await cache.disconnect()

            # Assert
            assert connected is True

    @pytest.mark.asyncio()
    async def test_redis_unavAlgolable_fallback(self):
        """Test fallback to memory when Redis unavAlgolable."""
        # Arrange
        with patch("src.utils.redis_cache.REDIS_AVAlgoLABLE", False):
            cache = RedisCache(
                redis_url="redis://localhost:6379/0",
                fallback_to_memory=True,
            )

            # Act
            connected = await cache.connect()

            # Assert
            assert connected is False
            # Should still work with memory cache
            await cache.set("test", "value")
            result = await cache.get("test")
            assert result == "value"
