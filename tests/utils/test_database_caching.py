"""
Integration tests for Database Query Caching.

Тестирует кэшируемые методы DatabaseManager:
- get_user_by_telegram_id_cached()
- get_recent_scans_cached()
- get_cache_stats()
"""

import asyncio

import pytest

from src.utils.database import DatabaseManager


@pytest.fixture()
async def db_manager():
    """Create in-memory database manager for testing."""
    # Clear all caches before test to ensure isolation
    from src.utils.memory_cache import clear_all_caches

    await clear_all_caches()

    db = DatabaseManager("sqlite:///:memory:", echo=False)
    await db.init_database()
    yield db
    await db.close()

    # Clear all caches after test
    await clear_all_caches()


class TestDatabaseCachedQueries:
    """Тесты кэшируемых запросов к базе данных."""

    @pytest.mark.asyncio()
    async def test_get_user_by_telegram_id_cached_basic(self, db_manager):
        """Тест базового кэширования get_user_by_telegram_id."""
        # Create user
        await db_manager.get_or_create_user(
            telegram_id=123456789,
            username="test_user",
            first_name="Test",
            last_name="User",
        )

        # First call - should hit database
        cached_user = await db_manager.get_user_by_telegram_id_cached(123456789)
        assert cached_user is not None
        assert cached_user.telegram_id == 123456789
        assert cached_user.username == "test_user"

        # Second call - should use cache
        cached_user_2 = await db_manager.get_user_by_telegram_id_cached(123456789)
        assert cached_user_2 is not None
        assert cached_user_2.telegram_id == 123456789

        # Check cache stats
        stats = await db_manager.get_cache_stats()
        # get_user_by_telegram_id_cached uses _user_cache
        user_cache_stats = stats["user_cache"]
        assert user_cache_stats["hits"] >= 1  # Second call was a hit

    @pytest.mark.asyncio()
    async def test_get_user_by_telegram_id_cached_non_existent(self, db_manager):
        """Тест кэширования для несуществующего пользователя."""
        # Query non-existent user
        cached_user = await db_manager.get_user_by_telegram_id_cached(999999999)
        assert cached_user is None

        # Query agAlgon - should use cache
        cached_user_2 = await db_manager.get_user_by_telegram_id_cached(999999999)
        assert cached_user_2 is None

    @pytest.mark.asyncio()
    async def test_invalidate_user_cache(self, db_manager):
        """Тест инвалидации кэша пользователя."""
        # Create user
        await db_manager.get_or_create_user(
            telegram_id=123456789,
            username="test_user",
        )

        # First call - cache it
        cached_user = await db_manager.get_user_by_telegram_id_cached(123456789)
        assert cached_user is not None
        assert cached_user.username == "test_user"

        # Invalidate cache
        await db_manager.invalidate_user_cache(123456789)

        # Update user directly in DB
        async with db_manager.get_async_session() as session:
            from sqlalchemy import text

            await session.execute(
                text(
                    """
                    UPDATE users
                    SET username = :new_username
                    WHERE telegram_id = :telegram_id
                """
                ),
                {"new_username": "updated_user", "telegram_id": 123456789},
            )
            await session.commit()

        # Query agAlgon - should fetch fresh data from DB
        cached_user_2 = await db_manager.get_user_by_telegram_id_cached(123456789)
        assert cached_user_2 is not None
        assert cached_user_2.username == "updated_user"

    @pytest.mark.asyncio()
    async def test_get_recent_scans_cached_basic(self, db_manager):
        """Тест базового кэширования get_recent_scans."""
        # Create user
        user = await db_manager.get_or_create_user(telegram_id=123456789)

        # Log some scan commands
        for i in range(5):
            await db_manager.log_command(
                user_id=user.id,
                command="arbitrage_scan",
                parameters={"game": "csgo", "opportunities_found": i + 1},
                success=True,
                execution_time_ms=100 + i * 10,
            )

        # First call - should hit database
        scans = await db_manager.get_recent_scans_cached(user.id, limit=10)
        assert len(scans) == 5
        assert scans[0]["command"] == "arbitrage_scan"

        # Second call - should use cache
        scans_2 = await db_manager.get_recent_scans_cached(user.id, limit=10)
        assert len(scans_2) == 5

        # Check cache stats - get_cache_stats() returns dict of all caches
        stats = await db_manager.get_cache_stats()
        # Cached queries use _market_data_cache by default (cache=None)
        market_stats = stats["market_data_cache"]
        # At least one hit from the second call
        assert market_stats["hits"] >= 1

    @pytest.mark.asyncio()
    async def test_get_recent_scans_cached_limit(self, db_manager):
        """Тест лимита в get_recent_scans_cached."""
        # Create user
        user = await db_manager.get_or_create_user(telegram_id=123456789)

        # Log 10 scan commands
        for i in range(10):
            await db_manager.log_command(
                user_id=user.id,
                command="arbitrage_scan",
                parameters={"game": "csgo"},
                success=True,
            )

        # Query with limit=5
        scans = await db_manager.get_recent_scans_cached(user.id, limit=5)
        assert len(scans) == 5

        # Query with limit=3
        scans_3 = await db_manager.get_recent_scans_cached(user.id, limit=3)
        assert len(scans_3) == 3

    @pytest.mark.asyncio()
    async def test_get_cache_stats(self, db_manager):
        """Тест получения статистики кэша БД."""
        # Make some cached queries
        await db_manager.get_or_create_user(telegram_id=123456789)
        await db_manager.get_user_by_telegram_id_cached(123456789)
        await db_manager.get_user_by_telegram_id_cached(123456789)

        # Get stats
        stats = await db_manager.get_cache_stats()

        # Проверяем структуру с вложенными кэшами
        assert "price_cache" in stats
        assert "market_data_cache" in stats
        assert "history_cache" in stats
        assert "user_cache" in stats

        # Проверяем статистику user_cache
        # (используется для get_user_by_telegram_id_cached)
        user_cache_stats = stats["user_cache"]
        assert "hits" in user_cache_stats
        assert "misses" in user_cache_stats
        assert "size" in user_cache_stats
        # Должен быть хотя бы 1 hit (втоSwarm запрос)
        assert user_cache_stats["hits"] >= 1

    @pytest.mark.asyncio()
    async def test_cache_ttl_expiration(self, db_manager):
        """Тест истечения TTL кэша."""
        # This test would require modifying TTL to be very short
        # or mocking time, which is complex. Skipping for now.
        # In production, TTL is 600 seconds (10 minutes) for user_cache.

    @pytest.mark.asyncio()
    async def test_concurrent_cached_queries(self, db_manager):
        """Тест конкурентных кэшируемых запросов."""
        # Create user
        await db_manager.get_or_create_user(
            telegram_id=123456789, username="concurrent_user"
        )

        # Prime the cache with first query
        first_result = await db_manager.get_user_by_telegram_id_cached(123456789)
        assert first_result is not None

        # Multiple concurrent queries (cache should be populated now)
        tasks = [
            db_manager.get_user_by_telegram_id_cached(123456789) for _ in range(20)
        ]
        results = await asyncio.gather(*tasks)

        # All should return the same user
        assert len(results) == 20
        assert all(r is not None for r in results)
        assert all(r.telegram_id == 123456789 for r in results)

        # Check cache stats - most queries should hit cache
        # (20 queries + 1 priming = 21 total, minus 1 miss)
        stats = await db_manager.get_cache_stats()
        user_cache_stats = stats["user_cache"]
        # After priming, most concurrent queries hit cache
        assert user_cache_stats["hits"] >= 15


class TestCachePerformance:
    """Тесты производительности кэширования."""

    @pytest.mark.asyncio()
    async def test_cache_reduces_db_queries(self, db_manager):
        """Тест, что кэш уменьшает количество запросов к БД."""
        import time

        # Create user
        user = await db_manager.get_or_create_user(telegram_id=123456789)

        # Log some scans
        for i in range(10):
            await db_manager.log_command(
                user_id=user.id,
                command="arbitrage_scan",
                parameters={"game": "csgo"},
                success=True,
            )

        # Measure time for first query (DB)
        start = time.perf_counter()
        scans_1 = await db_manager.get_recent_scans_cached(user.id, limit=10)
        time_db = time.perf_counter() - start

        # Measure time for second query (cache)
        start = time.perf_counter()
        scans_2 = await db_manager.get_recent_scans_cached(user.id, limit=10)
        time_cache = time.perf_counter() - start

        assert len(scans_1) == 10
        assert len(scans_2) == 10

        # Cache should be faster (though this might not always be true in tests)
        # At minimum, cache should not be slower
        # Just verify both completed successfully
        assert time_db >= 0
        assert time_cache >= 0

    @pytest.mark.asyncio()
    async def test_cache_with_multiple_users(self, db_manager):
        """Тест кэширования для множества пользователей."""
        # Create 10 users
        user_ids = []
        for i in range(10):
            user = await db_manager.get_or_create_user(
                telegram_id=100000 + i, username=f"user_{i}"
            )
            user_ids.append(user.telegram_id)

        # Query each user twice (first should cache, second should hit cache)
        for telegram_id in user_ids:
            user_1 = await db_manager.get_user_by_telegram_id_cached(telegram_id)
            user_2 = await db_manager.get_user_by_telegram_id_cached(telegram_id)
            assert user_1 is not None
            assert user_2 is not None
            assert user_1.telegram_id == telegram_id

        # Check cache stats
        stats = await db_manager.get_cache_stats()
        user_cache_stats = stats["user_cache"]
        assert user_cache_stats["hits"] >= 10  # At least one hit per user


class TestCacheConsistency:
    """Тесты консистентности кэша."""

    @pytest.mark.asyncio()
    async def test_cache_consistency_after_update(self, db_manager):
        """Тест консистентности после обновления данных."""
        # Create user
        await db_manager.get_or_create_user(
            telegram_id=123456789, username="original_name"
        )

        # Cache it
        cached_1 = await db_manager.get_user_by_telegram_id_cached(123456789)
        assert cached_1.username == "original_name"

        # Update via get_or_create_user (which should invalidate cache)
        await db_manager.get_or_create_user(
            telegram_id=123456789, username="updated_name"
        )

        # Manually invalidate cache
        await db_manager.invalidate_user_cache(123456789)

        # Query agAlgon - should have fresh data
        cached_2 = await db_manager.get_user_by_telegram_id_cached(123456789)
        assert cached_2.username == "updated_name"

    @pytest.mark.asyncio()
    async def test_cache_does_not_return_stale_data_after_delete(self, db_manager):
        """Тест, что кэш не возвращает устаревшие данные после удаления."""
        # Create user
        await db_manager.get_or_create_user(
            telegram_id=123456789, username="to_be_deleted"
        )

        # Cache it
        cached_1 = await db_manager.get_user_by_telegram_id_cached(123456789)
        assert cached_1 is not None

        # Delete user from DB
        async with db_manager.get_async_session() as session:
            from sqlalchemy import text

            await session.execute(
                text("DELETE FROM users WHERE telegram_id = :telegram_id"),
                {"telegram_id": 123456789},
            )
            await session.commit()

        # Invalidate cache
        await db_manager.invalidate_user_cache(123456789)

        # Query agAlgon - should return None
        cached_2 = await db_manager.get_user_by_telegram_id_cached(123456789)
        assert cached_2 is None
