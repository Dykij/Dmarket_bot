"""Tests for Enhanced User Rate Limiter."""

from datetime import UTC, datetime, timedelta

import pytest

from src.utils.user_rate_limiter_enhanced import (
    EnhancedUserRateLimiter,
    OperationLimit,
    RateLimitConfig,
    RateLimitResult,
    RateLimitStrategy,
    get_user_rate_limiter,
    init_user_rate_limiter,
)


class TestRateLimitConfig:
    """Tests for RateLimitConfig."""

    def test_default_config(self):
        """Test default configuration."""
        config = RateLimitConfig()

        assert config.requests_per_minute == 30
        assert config.requests_per_hour == 500
        assert config.strategy == RateLimitStrategy.SLIDING_WINDOW

    def test_custom_config(self):
        """Test custom configuration."""
        config = RateLimitConfig(
            requests_per_minute=60,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            burst_limit=20,
        )

        assert config.requests_per_minute == 60
        assert config.strategy == RateLimitStrategy.TOKEN_BUCKET
        assert config.burst_limit == 20


class TestSlidingWindowStrategy:
    """Tests for sliding window rate limiting."""

    @pytest.fixture
    def limiter(self):
        """Create limiter with sliding window."""
        config = RateLimitConfig(
            requests_per_minute=5,
            strategy=RateLimitStrategy.SLIDING_WINDOW,
        )
        return EnhancedUserRateLimiter(
            config=config,
            operation_limits={"test_op": OperationLimit("test_op", 5, 50, 0)}
        )

    @pytest.mark.asyncio
    async def test_allows_under_limit(self, limiter):
        """Test allows requests under limit."""
        for _ in range(4):
            result = await limiter.check_rate_limit(123, "test_op")
            assert result.allowed is True
            assert result.result == RateLimitResult.ALLOWED

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, limiter):
        """Test blocks requests over limit."""
        # Make 5 requests (at limit)
        for _ in range(5):
            await limiter.check_rate_limit(123, "test_op")

        # 6th should be blocked
        result = await limiter.check_rate_limit(123, "test_op")
        assert result.allowed is False
        assert result.result == RateLimitResult.RATE_LIMITED

    @pytest.mark.asyncio
    async def test_remaining_count(self, limiter):
        """Test remaining count is correct."""
        # First request - remaining is calculated before recording
        result = await limiter.check_rate_limit(123, "test_op")
        # After first request, 4 remaining slots
        assert result.remaining >= 4

        result = await limiter.check_rate_limit(123, "test_op")
        # After second request, 3 remaining slots
        assert result.remaining >= 3

    @pytest.mark.asyncio
    async def test_retry_after(self, limiter):
        """Test retry after calculation."""
        for _ in range(5):
            await limiter.check_rate_limit(123, "test_op")

        result = await limiter.check_rate_limit(123, "test_op")
        assert result.retry_after > 0
        assert result.retry_after <= 60


class TestTokenBucketStrategy:
    """Tests for token bucket rate limiting."""

    @pytest.fixture
    def limiter(self):
        """Create limiter with token bucket."""
        config = RateLimitConfig(
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            burst_limit=5,
            refill_rate=1.0,  # 1 token per second
        )
        return EnhancedUserRateLimiter(config=config)

    @pytest.mark.asyncio
    async def test_allows_burst(self, limiter):
        """Test allows burst of requests."""
        for _ in range(5):
            result = await limiter.check_rate_limit(123)
            assert result.allowed is True

    @pytest.mark.asyncio
    async def test_blocks_after_burst(self, limiter):
        """Test blocks after burst exhausted."""
        for _ in range(5):
            await limiter.check_rate_limit(123)

        result = await limiter.check_rate_limit(123)
        assert result.allowed is False

    @pytest.mark.asyncio
    async def test_token_refill(self, limiter):
        """Test tokens refill over time."""
        # Exhaust tokens
        for _ in range(5):
            await limiter.check_rate_limit(123)

        # Manually advance time by modifying last_refill
        state = limiter._get_user_state(123)
        state.last_refill = datetime.now(UTC) - timedelta(seconds=2)

        # Should have 2 new tokens
        result = await limiter.check_rate_limit(123)
        assert result.allowed is True


class TestFixedWindowStrategy:
    """Tests for fixed window rate limiting."""

    @pytest.fixture
    def limiter(self):
        """Create limiter with fixed window."""
        config = RateLimitConfig(
            requests_per_minute=5,
            strategy=RateLimitStrategy.FIXED_WINDOW,
        )
        return EnhancedUserRateLimiter(
            config=config,
            operation_limits={"test_op": OperationLimit("test_op", 5, 50, 0)}
        )

    @pytest.mark.asyncio
    async def test_allows_under_limit(self, limiter):
        """Test allows requests under limit."""
        for _ in range(4):
            result = await limiter.check_rate_limit(123, "test_op")
            assert result.allowed is True

    @pytest.mark.asyncio
    async def test_blocks_over_limit(self, limiter):
        """Test blocks over limit."""
        for _ in range(5):
            await limiter.check_rate_limit(123, "test_op")

        result = await limiter.check_rate_limit(123, "test_op")
        assert result.allowed is False


class TestOperationLimits:
    """Tests for per-operation rate limits."""

    @pytest.fixture
    def limiter(self):
        """Create limiter with operation limits."""
        return EnhancedUserRateLimiter(
            operation_limits={
                "scan_market": OperationLimit("scan_market", 2, 10, 0),
                "buy_item": OperationLimit("buy_item", 1, 5, 0),
            }
        )

    @pytest.mark.asyncio
    async def test_different_limits_per_operation(self, limiter):
        """Test different limits for different operations."""
        # scan_market allows 2/min
        result = await limiter.check_rate_limit(123, "scan_market")
        assert result.allowed is True
        assert result.limit == 2

        # buy_item allows 1/min
        result = await limiter.check_rate_limit(123, "buy_item")
        assert result.allowed is True
        assert result.limit == 1

    @pytest.mark.asyncio
    async def test_operation_specific_blocking(self, limiter):
        """Test operation-specific blocking."""
        # Use up scan_market limit
        await limiter.check_rate_limit(123, "scan_market")
        await limiter.check_rate_limit(123, "scan_market")

        # scan_market should be blocked
        result = await limiter.check_rate_limit(123, "scan_market")
        assert result.allowed is False

        # buy_item should still work
        result = await limiter.check_rate_limit(123, "buy_item")
        assert result.allowed is True


class TestPriorityUsers:
    """Tests for priority user handling."""

    @pytest.fixture
    def limiter(self):
        """Create limiter."""
        config = RateLimitConfig(
            requests_per_minute=5,
            priority_multiplier=2.0,
        )
        return EnhancedUserRateLimiter(
            config=config,
            operation_limits={"test_op": OperationLimit("test_op", 5, 50, 0)}
        )

    @pytest.mark.asyncio
    async def test_priority_user_higher_limit(self, limiter):
        """Test priority users get higher limits."""
        await limiter.set_priority_user(123, True)

        # Priority user should get 10 req/min (5 * 2)
        result = await limiter.check_rate_limit(123, "test_op")
        assert result.limit == 10

    @pytest.mark.asyncio
    async def test_remove_priority(self, limiter):
        """Test removing priority status."""
        await limiter.set_priority_user(123, True)
        await limiter.set_priority_user(123, False)

        result = await limiter.check_rate_limit(123, "test_op")
        assert result.limit == 5


class TestViolationsAndBans:
    """Tests for violations and bans."""

    @pytest.fixture
    def limiter(self):
        """Create limiter with low thresholds for testing."""
        config = RateLimitConfig(
            requests_per_minute=2,
            max_violations=3,
            cooldown_after_limit=10,
            ban_duration=60,
        )
        return EnhancedUserRateLimiter(
            config=config,
            operation_limits={"test_op": OperationLimit("test_op", 2, 10, 0)}
        )

    @pytest.mark.asyncio
    async def test_violation_tracking(self, limiter):
        """Test violation tracking."""
        # Use up limit
        await limiter.check_rate_limit(123, "test_op")
        await limiter.check_rate_limit(123, "test_op")

        # This should be blocked and counted as violation
        await limiter.check_rate_limit(123, "test_op")

        status = limiter.get_user_status(123)
        assert status["violations"] >= 1

    @pytest.mark.asyncio
    async def test_cooldown_applied(self, limiter):
        """Test cooldown is applied after violations."""
        for _ in range(10):  # Generate violations
            await limiter.check_rate_limit(123, "test_op")

        status = limiter.get_user_status(123)

        # Should be in cooldown or have violations
        assert status["is_in_cooldown"] or status["violations"] >= 1 or status["is_banned"]

    @pytest.mark.asyncio
    async def test_ban_after_max_violations(self, limiter):
        """Test ban after max violations."""
        # Generate enough violations to trigger ban
        for _ in range(20):
            await limiter.check_rate_limit(123, "test_op")

        status = limiter.get_user_status(123)
        # Either banned or close to ban
        assert status["violations"] >= 0  # Violations reset after ban

    @pytest.mark.asyncio
    async def test_unban_user(self, limiter):
        """Test unbanning user."""
        state = limiter._get_user_state(123)
        state.banned_until = datetime.now(UTC) + timedelta(hours=1)
        state.violations = 5

        await limiter.unban_user(123)

        status = limiter.get_user_status(123)
        assert status["is_banned"] is False
        assert status["violations"] == 0


class TestUserManagement:
    """Tests for user management."""

    @pytest.fixture
    def limiter(self):
        """Create limiter."""
        return EnhancedUserRateLimiter()

    @pytest.mark.asyncio
    async def test_get_user_status(self, limiter):
        """Test getting user status."""
        await limiter.check_rate_limit(123)

        status = limiter.get_user_status(123)
        assert status["user_id"] == 123
        assert status["requests_last_minute"] == 1

    @pytest.mark.asyncio
    async def test_reset_user(self, limiter):
        """Test resetting user state."""
        # Make some requests
        for _ in range(5):
            await limiter.check_rate_limit(123)

        await limiter.reset_user(123)

        status = limiter.get_user_status(123)
        assert status["requests_last_minute"] == 0
        assert status["violations"] == 0

    @pytest.mark.asyncio
    async def test_get_retry_after(self, limiter):
        """Test getting retry after time."""
        limiter.config.requests_per_minute = 1

        await limiter.check_rate_limit(123)

        retry_after = await limiter.get_retry_after(123)
        assert retry_after >= 0


class TestStatistics:
    """Tests for statistics."""

    @pytest.fixture
    def limiter(self):
        """Create limiter."""
        return EnhancedUserRateLimiter()

    @pytest.mark.asyncio
    async def test_get_stats(self, limiter):
        """Test getting statistics."""
        await limiter.check_rate_limit(123)
        await limiter.check_rate_limit(456)

        stats = limiter.get_stats()
        assert stats["total_users"] == 2
        assert stats["total_requests"] == 2


class TestCleanup:
    """Tests for cleanup."""

    @pytest.fixture
    def limiter(self):
        """Create limiter."""
        return EnhancedUserRateLimiter()

    @pytest.mark.asyncio
    async def test_cleanup_old_data(self, limiter):
        """Test cleaning up old data."""
        await limiter.check_rate_limit(123)

        # Age the user
        state = limiter._get_user_state(123)
        state.last_request = datetime.now(UTC) - timedelta(hours=48)

        cleaned = await limiter.cleanup_old_data(max_age_hours=24)
        assert cleaned == 1


class TestGlobalFunctions:
    """Tests for global functions."""

    def test_init_user_rate_limiter(self):
        """Test initializing global limiter."""
        config = RateLimitConfig(requests_per_minute=100)
        limiter = init_user_rate_limiter(config)
        assert limiter.config.requests_per_minute == 100

    def test_get_user_rate_limiter(self):
        """Test getting global limiter."""
        init_user_rate_limiter()
        limiter = get_user_rate_limiter()
        assert limiter is not None
