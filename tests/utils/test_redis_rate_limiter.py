"""Tests for Redis sliding window rate limiter.

Based on SkillsMP recommendations for testing Redis functionality.
"""

from unittest.mock import AsyncMock

import pytest

from src.utils.redis_rate_limiter import (
    RateLimitPresets,
    SlidingWindowRateLimiter,
    get_sliding_window_limiter,
)


class TestSlidingWindowRateLimiter:
    """Tests for SlidingWindowRateLimiter class."""

    @pytest.fixture
    def mock_redis(self):
        """Create mock Redis client."""
        mock = AsyncMock()
        mock.script_load = AsyncMock(return_value="test_sha")
        mock.evalsha = AsyncMock(return_value=[1, 99])  # allowed, remaining
        mock.zremrangebyscore = AsyncMock()
        mock.zcard = AsyncMock(return_value=5)
        mock.delete = AsyncMock()
        mock.close = AsyncMock()
        return mock

    @pytest.fixture
    def rate_limiter(self, mock_redis):
        """Create rate limiter with mock Redis."""
        limiter = SlidingWindowRateLimiter(
            redis_client=mock_redis,
            prefix="test:ratelimit:",
            default_limit=100,
            default_window=60,
        )
        return limiter

    @pytest.mark.asyncio
    async def test_is_allowed_success(self, rate_limiter, mock_redis):
        """Test that request is allowed when under limit."""
        # Arrange
        identifier = "user:123:api"

        # Act
        result = await rate_limiter.is_allowed(identifier)

        # Assert
        assert result is True
        mock_redis.evalsha.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_allowed_rate_limit_exceeded(self, rate_limiter, mock_redis):
        """Test that request is blocked when over limit."""
        # Arrange
        mock_redis.evalsha = AsyncMock(return_value=[0, 5.0])  # not allowed, retry after
        identifier = "user:456:api"

        # Act
        result = await rate_limiter.is_allowed(identifier)

        # Assert
        assert result is False

    @pytest.mark.asyncio
    async def test_check_and_increment_allowed(self, rate_limiter, mock_redis):
        """Test check_and_increment when allowed."""
        # Arrange
        identifier = "user:123:api"

        # Act
        is_allowed, remaining, retry_after = await rate_limiter.check_and_increment(
            identifier
        )

        # Assert
        assert is_allowed is True
        assert remaining == 99
        assert retry_after == 0.0

    @pytest.mark.asyncio
    async def test_check_and_increment_exceeded(self, rate_limiter, mock_redis):
        """Test check_and_increment when rate limit exceeded."""
        # Arrange
        mock_redis.evalsha = AsyncMock(return_value=[0, 30.0])
        identifier = "user:456:api"

        # Act
        is_allowed, remaining, retry_after = await rate_limiter.check_and_increment(
            identifier
        )

        # Assert
        assert is_allowed is False
        assert remaining == 0
        assert retry_after == 30.0

    @pytest.mark.asyncio
    async def test_get_current_usage(self, rate_limiter, mock_redis):
        """Test getting current usage count."""
        # Arrange
        identifier = "user:123:api"

        # Act
        usage = await rate_limiter.get_current_usage(identifier)

        # Assert
        assert usage == 5
        mock_redis.zcard.assert_called_once()

    @pytest.mark.asyncio
    async def test_reset(self, rate_limiter, mock_redis):
        """Test resetting rate limit counter."""
        # Arrange
        identifier = "user:123:api"

        # Act
        result = await rate_limiter.reset(identifier)

        # Assert
        assert result is True
        mock_redis.delete.assert_called_once()

    @pytest.mark.asyncio
    async def test_close(self, rate_limiter, mock_redis):
        """Test closing connection."""
        # Act
        await rate_limiter.close()

        # Assert
        mock_redis.close.assert_called_once()
        assert rate_limiter._client is None

    def test_make_key(self, rate_limiter):
        """Test key generation with prefix."""
        # Act
        key = rate_limiter._make_key("user:123:api")

        # Assert
        assert key == "test:ratelimit:user:123:api"

    @pytest.mark.asyncio
    async def test_custom_limit_and_window(self, rate_limiter, mock_redis):
        """Test with custom limit and window."""
        # Arrange
        identifier = "user:123:api"

        # Act
        await rate_limiter.is_allowed(identifier, limit=50, window=30)

        # Assert
        call_args = mock_redis.evalsha.call_args
        assert call_args is not None
        # Check that custom limit and window were passed
        assert 50 in call_args[0] or 50 in call_args.args
        assert 30 in call_args[0] or 30 in call_args.args

    @pytest.mark.asyncio
    async def test_fail_open_on_redis_error(self, rate_limiter, mock_redis):
        """Test that requests are allowed when Redis fails."""
        # Arrange
        mock_redis.evalsha = AsyncMock(side_effect=Exception("Redis error"))
        identifier = "user:123:api"

        # Act
        result = await rate_limiter.is_allowed(identifier)

        # Assert - fail open, allow request
        assert result is True


class TestRateLimitPresets:
    """Tests for RateLimitPresets class."""

    def test_dmarket_market_preset(self):
        """Test DMarket market preset."""
        assert RateLimitPresets.DMARKET_MARKET["limit"] == 30
        assert RateLimitPresets.DMARKET_MARKET["window"] == 60

    def test_waxpeer_preset(self):
        """Test Waxpeer preset."""
        assert RateLimitPresets.WAXPEER_API["limit"] == 60
        assert RateLimitPresets.WAXPEER_API["window"] == 60

    def test_telegram_presets(self):
        """Test Telegram presets."""
        assert RateLimitPresets.TELEGRAM_USER["limit"] == 30
        assert RateLimitPresets.TELEGRAM_GROUP["limit"] == 20


class TestGetSlidingWindowLimiter:
    """Tests for get_sliding_window_limiter function."""

    def test_singleton_creation(self):
        """Test singleton is created."""
        from src.utils import redis_rate_limiter as module

        # Reset singleton
        module._rate_limiter = None

        # Act
        limiter1 = get_sliding_window_limiter(redis_url="redis://localhost:6379")
        limiter2 = get_sliding_window_limiter()

        # Assert
        assert limiter1 is limiter2
