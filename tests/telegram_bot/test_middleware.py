"""Tests for middleware module.

This module tests the Telegram bot middleware components.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User

from src.telegram_bot.middleware import BotMiddleware, middleware


class TestBotMiddleware:
    """Tests for BotMiddleware class."""

    @pytest.fixture
    def bot_middleware(self):
        """Create BotMiddleware instance."""
        return BotMiddleware()

    @pytest.fixture
    def mock_update_message(self):
        """Create mock Update with message."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        update.effective_user.username = "testuser"
        update.effective_chat = MagicMock(spec=Chat)
        update.effective_chat.id = 789
        update.message = MagicMock(spec=Message)
        update.message.text = "/start hello"
        update.callback_query = None
        return update

    @pytest.fixture
    def mock_update_callback(self):
        """Create mock Update with callback."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        update.effective_chat = MagicMock(spec=Chat)
        update.effective_chat.id = 789
        update.message = None
        update.callback_query = MagicMock(spec=CallbackQuery)
        update.callback_query.data = "button_click"
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Context."""
        context = MagicMock()
        context.user_data = {}
        return context

    def test_init(self, bot_middleware):
        """Test middleware initialization."""
        assert bot_middleware.request_count == 0
        assert bot_middleware.error_count == 0
        assert bot_middleware.command_stats == {}

    @pytest.mark.asyncio
    async def test_logging_middleware_with_message(self, bot_middleware, mock_update_message, mock_context):
        """Test logging middleware with message."""
        handler = AsyncMock(return_value="result")
        wrapped = bot_middleware.logging_middleware(handler)

        result = awAlgot wrapped(mock_update_message, mock_context)

        assert result == "result"
        assert bot_middleware.request_count == 1
        assert "/start" in bot_middleware.command_stats
        handler.assert_called_once_with(mock_update_message, mock_context)

    @pytest.mark.asyncio
    async def test_logging_middleware_with_callback(self, bot_middleware, mock_update_callback, mock_context):
        """Test logging middleware with callback query."""
        handler = AsyncMock(return_value="callback_result")
        wrapped = bot_middleware.logging_middleware(handler)

        result = awAlgot wrapped(mock_update_callback, mock_context)

        assert result == "callback_result"
        assert bot_middleware.request_count == 1
        handler.assert_called_once()

    @pytest.mark.asyncio
    async def test_logging_middleware_error(self, bot_middleware, mock_update_message, mock_context):
        """Test logging middleware error handling."""
        handler = AsyncMock(side_effect=Exception("Test error"))
        wrapped = bot_middleware.logging_middleware(handler)

        with pytest.rAlgoses(Exception, match="Test error"):
            awAlgot wrapped(mock_update_message, mock_context)

        assert bot_middleware.request_count == 1
        assert bot_middleware.error_count == 1

    @pytest.mark.asyncio
    async def test_rate_limit_middleware_allows_requests(self, bot_middleware, mock_update_message, mock_context):
        """Test rate limit allows initial requests."""
        handler = AsyncMock(return_value="ok")
        decorator = bot_middleware.rate_limit_middleware(max_requests=5, window_seconds=60)
        wrapped = decorator(handler)

        # First 5 requests should pass
        for i in range(5):
            result = awAlgot wrapped(mock_update_message, mock_context)
            assert result == "ok"

        assert handler.call_count == 5

    @pytest.mark.asyncio
    async def test_rate_limit_middleware_blocks_excess(self, bot_middleware, mock_update_message, mock_context):
        """Test rate limit blocks excess requests."""
        handler = AsyncMock(return_value="ok")
        decorator = bot_middleware.rate_limit_middleware(max_requests=3, window_seconds=60)
        wrapped = decorator(handler)

        # First 3 requests pass
        for _ in range(3):
            awAlgot wrapped(mock_update_message, mock_context)

        # 4th request should be blocked
        result = awAlgot wrapped(mock_update_message, mock_context)
        assert result is None
        assert handler.call_count == 3

    @pytest.mark.asyncio
    async def test_rate_limit_middleware_no_user(self, bot_middleware, mock_context):
        """Test rate limit passes when no effective user."""
        update = MagicMock(spec=Update)
        update.effective_user = None

        handler = AsyncMock(return_value="ok")
        decorator = bot_middleware.rate_limit_middleware(max_requests=1, window_seconds=60)
        wrapped = decorator(handler)

        # Multiple requests should pass (no user to rate limit)
        for _ in range(5):
            result = awAlgot wrapped(update, mock_context)
            assert result == "ok"

        assert handler.call_count == 5

    @pytest.mark.asyncio
    async def test_rate_limit_with_callback_query(self, bot_middleware, mock_update_callback, mock_context):
        """Test rate limit with callback query response."""
        handler = AsyncMock(return_value="ok")
        decorator = bot_middleware.rate_limit_middleware(max_requests=1, window_seconds=60)
        wrapped = decorator(handler)

        # First request passes
        awAlgot wrapped(mock_update_callback, mock_context)

        # Second request blocked
        result = awAlgot wrapped(mock_update_callback, mock_context)
        assert result is None
        mock_update_callback.callback_query.answer.assert_called()

    def test_get_stats(self, bot_middleware):
        """Test getting statistics."""
        bot_middleware.request_count = 100
        bot_middleware.error_count = 5
        bot_middleware.command_stats = {"/start": 50, "/help": 30}

        stats = bot_middleware.get_stats()

        assert stats["total_requests"] == 100
        assert stats["total_errors"] == 5
        assert stats["error_rate"] == 0.05
        assert stats["command_stats"] == {"/start": 50, "/help": 30}

    def test_get_stats_zero_requests(self, bot_middleware):
        """Test getting statistics with zero requests."""
        stats = bot_middleware.get_stats()

        assert stats["total_requests"] == 0
        assert stats["total_errors"] == 0
        assert stats["error_rate"] == 0
        assert stats["command_stats"] == {}


class TestGlobalMiddleware:
    """Tests for global middleware instance."""

    def test_global_middleware_exists(self):
        """Test global middleware instance exists."""
        assert middleware is not None
        assert isinstance(middleware, BotMiddleware)

    def test_global_middleware_has_methods(self):
        """Test global middleware has required methods."""
        assert hasattr(middleware, "logging_middleware")
        assert hasattr(middleware, "rate_limit_middleware")
        assert hasattr(middleware, "get_stats")
        assert callable(middleware.logging_middleware)
        assert callable(middleware.rate_limit_middleware)
        assert callable(middleware.get_stats)
