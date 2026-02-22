"""
Comprehensive tests for rate_limit_decorator module.

Tests the rate limiting decorator for Telegram bot commands including:
- Basic rate limiting functionality
- Whitelist bypass
- Custom error messages
- Callback query and message handling
- Missing rate limiter handling
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Message, Update, User
from telegram.ext import ContextTypes

from src.utils.rate_limit_decorator import rate_limit


@pytest.fixture()
def mock_user():
    """Create a mock Telegram user."""
    user = MagicMock(spec=User)
    user.id = 12345
    user.username = "testuser"
    return user


@pytest.fixture()
def mock_update(mock_user):
    """Create a mock Telegram Update."""
    update = MagicMock(spec=Update)
    update.effective_user = mock_user
    update.message = MagicMock(spec=Message)
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


@pytest.fixture()
def mock_context():
    """Create a mock Telegram context."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot_data = MagicMock()
    return context


@pytest.fixture()
def mock_rate_limiter():
    """Create a mock UserRateLimiter."""
    limiter = AsyncMock()
    limiter.is_whitelisted = AsyncMock(return_value=False)
    limiter.check_limit = AsyncMock(return_value=(True, {}))
    return limiter


class TestRateLimitDecorator:
    """Tests for rate_limit decorator basic functionality."""

    @pytest.mark.asyncio()
    async def test_decorator_allows_request_within_limit(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test that decorator allows request when within rate limit."""
        # Arrange
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter
        mock_rate_limiter.check_limit.return_value = (True, {"limit": 10, "window": 60})

        @rate_limit(action="test", cost=1)
        async def test_command(update, context):
            return "success"

        # Act
        result = await test_command(mock_update, mock_context)

        # Assert
        assert result == "success"
        mock_rate_limiter.check_limit.assert_called_once_with(12345, "test", 1)

    @pytest.mark.asyncio()
    async def test_decorator_blocks_request_when_limit_exceeded(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test that decorator blocks request when rate limit exceeded."""
        # Arrange
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter
        mock_rate_limiter.check_limit.return_value = (
            False,
            {"limit": 10, "window": 60, "retry_after": 30},
        )

        @rate_limit(action="scan", cost=1)
        async def test_command(update, context):
            return "success"

        # Act
        result = await test_command(mock_update, mock_context)

        # Assert
        assert result is None
        mock_update.message.reply_text.assert_called_once()
        call_text = mock_update.message.reply_text.call_args[0][0]
        assert "⚠️ Превышен лимит запросов!" in call_text
        assert "scan" in call_text
        assert "30 сек" in call_text

    @pytest.mark.asyncio()
    async def test_decorator_with_custom_message(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test that decorator uses custom error message when provided."""
        # Arrange
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter
        mock_rate_limiter.check_limit.return_value = (
            False,
            {"limit": 5, "retry_after": 20},
        )
        custom_msg = "🚫 Custom rate limit message!"

        @rate_limit(action="test", cost=2, message=custom_msg)
        async def test_command(update, context):
            return "success"

        # Act
        result = await test_command(mock_update, mock_context)

        # Assert
        assert result is None
        mock_update.message.reply_text.assert_called_once_with(custom_msg)


class TestRateLimitWhitelist:
    """Tests for whitelist bypass functionality."""

    @pytest.mark.asyncio()
    async def test_whitelisted_user_bypasses_rate_limit(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test that whitelisted users bypass rate limiting."""
        # Arrange
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter
        mock_rate_limiter.is_whitelisted.return_value = True

        @rate_limit(action="test", cost=1)
        async def test_command(update, context):
            return "success"

        # Act
        result = await test_command(mock_update, mock_context)

        # Assert
        assert result == "success"
        mock_rate_limiter.is_whitelisted.assert_called_once_with(12345)
        mock_rate_limiter.check_limit.assert_not_called()

    @pytest.mark.asyncio()
    async def test_non_whitelisted_user_checks_limit(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test that non-whitelisted users go through rate limit check."""
        # Arrange
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter
        mock_rate_limiter.is_whitelisted.return_value = False
        mock_rate_limiter.check_limit.return_value = (True, {})

        @rate_limit(action="test", cost=1)
        async def test_command(update, context):
            return "success"

        # Act
        result = await test_command(mock_update, mock_context)

        # Assert
        assert result == "success"
        mock_rate_limiter.is_whitelisted.assert_called_once_with(12345)
        mock_rate_limiter.check_limit.assert_called_once()


class TestRateLimitCallbackQuery:
    """Tests for callback query handling."""

    @pytest.mark.asyncio()
    async def test_decorator_handles_callback_query_limit_exceeded(
        self, mock_user, mock_context, mock_rate_limiter
    ):
        """Test that decorator handles callback query when limit exceeded."""
        # Arrange
        callback_query = MagicMock(spec=CallbackQuery)
        callback_query.from_user = mock_user
        callback_query.answer = AsyncMock()

        update = MagicMock(spec=Update)
        update.effective_user = mock_user
        update.message = None
        update.callback_query = callback_query

        mock_context.bot_data.user_rate_limiter = mock_rate_limiter
        mock_rate_limiter.check_limit.return_value = (
            False,
            {"limit": 10, "window": 60, "retry_after": 15},
        )

        @rate_limit(action="callback", cost=1)
        async def test_command(update, context):
            return "success"

        # Act
        result = await test_command(update, mock_context)

        # Assert
        assert result is None
        callback_query.answer.assert_called_once()
        call_args = callback_query.answer.call_args
        assert "⚠️ Превышен лимит запросов!" in call_args[0][0]
        assert call_args[1]["show_alert"] is True


class TestRateLimitEdgeCases:
    """Tests for edge cases and error handling."""

    @pytest.mark.asyncio()
    async def test_decorator_without_effective_user(self, mock_context):
        """Test that decorator passes through when no effective user."""
        # Arrange
        update = MagicMock(spec=Update)
        update.effective_user = None

        @rate_limit(action="test", cost=1)
        async def test_command(update, context):
            return "success"

        # Act
        result = await test_command(update, mock_context)

        # Assert
        assert result == "success"

    @pytest.mark.asyncio()
    async def test_decorator_without_rate_limiter(self, mock_update, mock_context):
        """Test that decorator passes through when rate limiter not found."""
        # Arrange
        mock_context.bot_data.user_rate_limiter = None

        @rate_limit(action="test", cost=1)
        async def test_command(update, context):
            return "success"

        # Act
        with patch("src.utils.rate_limit_decorator.logger") as mock_logger:
            result = await test_command(mock_update, mock_context)

        # Assert
        assert result == "success"
        mock_logger.warning.assert_called_once_with(
            "rate_limiter_not_found", user_id=12345
        )

    @pytest.mark.asyncio()
    async def test_decorator_with_default_action(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test that decorator uses default action when not specified."""
        # Arrange
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter
        mock_rate_limiter.check_limit.return_value = (True, {})

        @rate_limit()  # No parameters
        async def test_command(update, context):
            return "success"

        # Act
        result = await test_command(mock_update, mock_context)

        # Assert
        assert result == "success"
        mock_rate_limiter.check_limit.assert_called_once_with(12345, "default", 1)

    @pytest.mark.asyncio()
    async def test_decorator_with_custom_cost(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test that decorator uses custom cost parameter."""
        # Arrange
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter
        mock_rate_limiter.check_limit.return_value = (True, {})

        @rate_limit(action="expensive", cost=5)
        async def test_command(update, context):
            return "success"

        # Act
        result = await test_command(mock_update, mock_context)

        # Assert
        assert result == "success"
        mock_rate_limiter.check_limit.assert_called_once_with(12345, "expensive", 5)
