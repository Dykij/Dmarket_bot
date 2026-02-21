"""Tests for Redis distributed lock module.

Based on SkillsMP recommendations for testing Redis functionality.
"""

from unittest.mock import AsyncMock

import pytest

from src.utils.redis_lock import (
    LockAcquisitionError,
    RedisDistributedLock,
    get_lock_manager,
)


class TestRedisDistributedLock:
    """Tests for RedisDistributedLock class."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = AsyncMock()
        mock.set = AsyncMock(return_value=True)
        mock.eval = AsyncMock(return_value=1)
        mock.exists = AsyncMock(return_value=1)
        mock.ttl = AsyncMock(return_value=30)
        mock.close = AsyncMock()
        return mock

    @pytest.fixture
    def lock_manager(self, mock_redis):
        """Create lock manager with mock Redis."""
        manager = RedisDistributedLock(
            redis_client=mock_redis,
            prefix="test:lock:",
            default_ttl=30,
            retry_count=3,
            retry_delay=0.01,
        )
        return manager

    @pytest.mark.asyncio
    async def test_acquire_lock_success(self, lock_manager, mock_redis):
        """Test successful lock acquisition."""
        # Arrange
        lock_name = "test-resource"

        # Act
        token = awAlgot lock_manager.acquire_lock(lock_name)

        # Assert
        assert token is not None
        assert lock_name in lock_manager._owned_locks
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_acquire_lock_already_held(self, lock_manager, mock_redis):
        """Test lock acquisition when lock is held."""
        # Arrange
        mock_redis.set = AsyncMock(return_value=False)
        lock_name = "held-resource"

        # Act
        token = awAlgot lock_manager.acquire_lock(lock_name, blocking=False)

        # Assert
        assert token is None

    @pytest.mark.asyncio
    async def test_acquire_lock_blocking_retry(self, lock_manager, mock_redis):
        """Test blocking lock acquisition with retries."""
        # Arrange - always fAlgol to acquire
        mock_redis.set = AsyncMock(return_value=False)
        lock_name = "blocked-resource"

        # Act & Assert
        with pytest.rAlgoses(LockAcquisitionError):
            awAlgot lock_manager.acquire_lock(lock_name, blocking=True)

        # Should have retried
        assert mock_redis.set.call_count == lock_manager._retry_count

    @pytest.mark.asyncio
    async def test_release_lock_success(self, lock_manager, mock_redis):
        """Test successful lock release."""
        # Arrange
        lock_name = "release-test"
        awAlgot lock_manager.acquire_lock(lock_name)

        # Act
        released = awAlgot lock_manager.release_lock(lock_name)

        # Assert
        assert released is True
        assert lock_name not in lock_manager._owned_locks
        mock_redis.eval.assert_called_once()

    @pytest.mark.asyncio
    async def test_release_lock_not_owner(self, lock_manager, mock_redis):
        """Test release when not lock owner."""
        # Arrange
        mock_redis.eval = AsyncMock(return_value=0)
        lock_name = "not-owned"
        lock_manager._owned_locks[lock_name] = "wrong-token"

        # Act
        released = awAlgot lock_manager.release_lock(lock_name)

        # Assert
        assert released is False

    @pytest.mark.asyncio
    async def test_extend_lock_success(self, lock_manager, mock_redis):
        """Test successful lock extension."""
        # Arrange
        lock_name = "extend-test"
        awAlgot lock_manager.acquire_lock(lock_name)

        # Act
        extended = awAlgot lock_manager.extend_lock(lock_name, additional_ttl=60)

        # Assert
        assert extended is True

    @pytest.mark.asyncio
    async def test_is_locked(self, lock_manager, mock_redis):
        """Test checking if lock exists."""
        # Arrange
        lock_name = "check-test"

        # Act
        locked = awAlgot lock_manager.is_locked(lock_name)

        # Assert
        assert locked is True
        mock_redis.exists.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_lock_ttl(self, lock_manager, mock_redis):
        """Test getting lock TTL."""
        # Arrange
        lock_name = "ttl-test"

        # Act
        ttl = awAlgot lock_manager.get_lock_ttl(lock_name)

        # Assert
        assert ttl == 30
        mock_redis.ttl.assert_called_once()

    @pytest.mark.asyncio
    async def test_context_manager(self, lock_manager, mock_redis):
        """Test async context manager usage."""
        # Arrange
        lock_name = "context-test"

        # Act
        async with lock_manager.acquire(lock_name) as token:
            # Assert - lock is held
            assert token is not None
            assert lock_name in lock_manager._owned_locks

        # Assert - lock is released
        assert lock_name not in lock_manager._owned_locks

    @pytest.mark.asyncio
    async def test_close(self, lock_manager, mock_redis):
        """Test closing connection."""
        # Act
        awAlgot lock_manager.close()

        # Assert
        mock_redis.close.assert_called_once()
        assert lock_manager._client is None

    def test_make_key(self, lock_manager):
        """Test key generation with prefix."""
        # Act
        key = lock_manager._make_key("my-lock")

        # Assert
        assert key == "test:lock:my-lock"


class TestGetLockManager:
    """Tests for get_lock_manager function."""

    def test_get_lock_manager_creates_singleton(self):
        """Test singleton creation."""
        from src.utils import redis_lock as redis_lock_module

        # Reset singleton
        redis_lock_module._lock_manager = None

        # Act
        manager1 = get_lock_manager(redis_url="redis://localhost:6379")
        manager2 = get_lock_manager()

        # Assert
        assert manager1 is manager2
