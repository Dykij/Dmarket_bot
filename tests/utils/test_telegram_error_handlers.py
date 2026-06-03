"""Tests for telegram_error_handlers module.

Comprehensive tests for error boundary decorator and BaseHandler class.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.exceptions import (
    APIError,
    AuthenticationError,
    RateLimitError,
    ValidationError,
)
from src.utils.telegram_error_handlers import BaseHandler, telegram_error_boundary


class TestTelegramErrorBoundary:
    """Tests for telegram_error_boundary decorator."""

    @pytest.fixture()
    def mock_update(self) -> MagicMock:
        """Create mock Telegram update."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.effective_user.username = "testuser"
        update.message = MagicMock()
        update.message.text = "/testcommand"
        update.message.reply_text = AsyncMock()
        update.callback_query = None
        return update

    @pytest.fixture()
    def mock_context(self) -> MagicMock:
        """Create mock Telegram context."""
        return MagicMock()

    @pytest.mark.asyncio()
    async def test_successful_handler_execution(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test successful handler execution."""

        @telegram_error_boundary()
        async def test_handler(update, context):
            return "success"

        with (
            patch("src.utils.telegram_error_handlers.set_user_context"),
            patch("src.utils.telegram_error_handlers.add_breadcrumb"),
        ):
            result = await test_handler(mock_update, mock_context)
            assert result == "success"

    @pytest.mark.asyncio()
    async def test_validation_error_handling(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test ValidationError handling."""

        @telegram_error_boundary()
        async def test_handler(update, context):
            raise ValidationError("Invalid input")

        with (
            patch("src.utils.telegram_error_handlers.set_user_context"),
            patch("src.utils.telegram_error_handlers.add_breadcrumb"),
        ):
            await test_handler(mock_update, mock_context)
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "валидации" in call_args.lower() or "validation" in call_args.lower()

    @pytest.mark.asyncio()
    async def test_authentication_error_handling(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test AuthenticationError handling."""

        @telegram_error_boundary()
        async def test_handler(update, context):
            raise AuthenticationError("Invalid API key")

        with (
            patch("src.utils.telegram_error_handlers.set_user_context"),
            patch("src.utils.telegram_error_handlers.add_breadcrumb"),
            patch(
                "src.utils.telegram_error_handlers.capture_exception"
            ) as mock_capture,
        ):
            await test_handler(mock_update, mock_context)
            mock_update.message.reply_text.assert_called_once()
            mock_capture.assert_called_once()

    @pytest.mark.asyncio()
    async def test_rate_limit_error_handling(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test RateLimitError handling."""
        error = RateLimitError("Too many requests")
        error.retry_after = 120

        @telegram_error_boundary()
        async def test_handler(update, context):
            raise error

        with (
            patch("src.utils.telegram_error_handlers.set_user_context"),
            patch("src.utils.telegram_error_handlers.add_breadcrumb"),
        ):
            await test_handler(mock_update, mock_context)
            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "лимит" in call_args.lower() or "limit" in call_args.lower()

    @pytest.mark.asyncio()
    async def test_api_error_handling(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test APIError handling."""
        error = APIError("API request failed")
        error.status_code = 500

        @telegram_error_boundary()
        async def test_handler(update, context):
            raise error

        with (
            patch("src.utils.telegram_error_handlers.set_user_context"),
            patch("src.utils.telegram_error_handlers.add_breadcrumb"),
            patch(
                "src.utils.telegram_error_handlers.capture_exception"
            ) as mock_capture,
        ):
            await test_handler(mock_update, mock_context)
            mock_update.message.reply_text.assert_called_once()
            mock_capture.assert_called_once()

    @pytest.mark.asyncio()
    async def test_unexpected_error_handling(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test unexpected error handling."""

        @telegram_error_boundary(user_friendly_message="Custom error message")
        async def test_handler(update, context):
            raise ValueError("Unexpected error")

        with (
            patch("src.utils.telegram_error_handlers.set_user_context"),
            patch("src.utils.telegram_error_handlers.add_breadcrumb"),
            patch(
                "src.utils.telegram_error_handlers.capture_exception"
            ) as mock_capture,
        ):
            await test_handler(mock_update, mock_context)
            mock_update.message.reply_text.assert_called_once_with(
                "Custom error message"
            )
            mock_capture.assert_called_once()

    @pytest.mark.asyncio()
    async def test_callback_query_error_handling(self, mock_context: MagicMock) -> None:
        """Test error handling for callback queries."""
        mock_update = MagicMock()
        mock_update.effective_user = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.effective_user.username = "testuser"
        mock_update.message = None
        mock_update.callback_query = MagicMock()
        mock_update.callback_query.data = "test_callback"
        mock_update.callback_query.answer = AsyncMock()

        @telegram_error_boundary()
        async def test_handler(update, context):
            raise ValidationError("Invalid callback")

        with (
            patch("src.utils.telegram_error_handlers.set_user_context"),
            patch("src.utils.telegram_error_handlers.add_breadcrumb"),
        ):
            await test_handler(mock_update, mock_context)
            mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_no_effective_user(self, mock_context: MagicMock) -> None:
        """Test handling when no effective user."""
        mock_update = MagicMock()
        mock_update.effective_user = None
        mock_update.message = MagicMock()
        mock_update.message.text = "/test"
        mock_update.message.reply_text = AsyncMock()
        mock_update.callback_query = None

        @telegram_error_boundary()
        async def test_handler(update, context):
            return "success"

        with (
            patch("src.utils.telegram_error_handlers.set_user_context"),
            patch("src.utils.telegram_error_handlers.add_breadcrumb"),
        ):
            result = await test_handler(mock_update, mock_context)
            assert result == "success"

    @pytest.mark.asyncio()
    async def test_log_context_disabled(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test with logging context disabled."""

        @telegram_error_boundary(log_context=False)
        async def test_handler(update, context):
            return "success"

        with (
            patch("src.utils.telegram_error_handlers.set_user_context"),
            patch("src.utils.telegram_error_handlers.add_breadcrumb"),
            patch("src.utils.telegram_error_handlers.logger") as mock_logger,
        ):
            result = await test_handler(mock_update, mock_context)
            assert result == "success"
            # Logger should not be called for info logs when log_context=False
            info_calls = list(mock_logger.info.call_args_list)
            assert len(info_calls) == 0


class TestBaseHandler:
    """Tests for BaseHandler class."""

    @pytest.fixture()
    def handler(self) -> BaseHandler:
        """Create BaseHandler instance."""
        return BaseHandler()

    @pytest.fixture()
    def mock_update(self) -> MagicMock:
        """Create mock Telegram update."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        update.callback_query = None
        return update

    def test_init_default_logger(self) -> None:
        """Test BaseHandler initialization with default logger."""
        handler = BaseHandler()
        assert handler.logger is not None

    def test_init_custom_logger(self) -> None:
        """Test BaseHandler initialization with custom logger name."""
        handler = BaseHandler(logger_name="custom_logger")
        assert handler.logger.name == "custom_logger"

    @pytest.mark.asyncio()
    async def test_handle_error_with_message(
        self, handler: BaseHandler, mock_update: MagicMock
    ) -> None:
        """Test handle_error with message update."""
        error = ValueError("Test error")

        with patch("src.utils.telegram_error_handlers.capture_exception"):
            await handler.handle_error(mock_update, error, "Custom error message")

        mock_update.message.reply_text.assert_called_once_with("Custom error message")

    @pytest.mark.asyncio()
    async def test_handle_error_with_callback(self, handler: BaseHandler) -> None:
        """Test handle_error with callback query update."""
        mock_update = MagicMock()
        mock_update.effective_user = MagicMock()
        mock_update.effective_user.id = 12345
        mock_update.message = None
        mock_update.callback_query = MagicMock()
        mock_update.callback_query.answer = AsyncMock()

        error = ValueError("Test error")

        with patch("src.utils.telegram_error_handlers.capture_exception"):
            await handler.handle_error(mock_update, error)

        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_handle_error_no_effective_user(self, handler: BaseHandler) -> None:
        """Test handle_error when no effective user."""
        mock_update = MagicMock()
        mock_update.effective_user = None
        mock_update.message = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_update.callback_query = None

        error = ValueError("Test error")

        with patch("src.utils.telegram_error_handlers.capture_exception"):
            await handler.handle_error(mock_update, error)

        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_validate_user_valid(
        self, handler: BaseHandler, mock_update: MagicMock
    ) -> None:
        """Test validate_user with valid user."""
        result = await handler.validate_user(mock_update)
        assert result is True

    @pytest.mark.asyncio()
    async def test_validate_user_no_user(self, handler: BaseHandler) -> None:
        """Test validate_user with no effective user."""
        mock_update = MagicMock()
        mock_update.effective_user = None

        result = await handler.validate_user(mock_update)
        assert result is False

    @pytest.mark.asyncio()
    async def test_safe_reply_with_message(
        self, handler: BaseHandler, mock_update: MagicMock
    ) -> None:
        """Test safe_reply with message update."""
        await handler.safe_reply(mock_update, "Test message")
        mock_update.message.reply_text.assert_called_once_with("Test message")

    @pytest.mark.asyncio()
    async def test_safe_reply_with_callback(self, handler: BaseHandler) -> None:
        """Test safe_reply with callback query update."""
        mock_update = MagicMock()
        mock_update.message = None
        mock_update.callback_query = MagicMock()
        mock_update.callback_query.message = MagicMock()
        mock_update.callback_query.message.reply_text = AsyncMock()
        mock_update.callback_query.answer = AsyncMock()

        await handler.safe_reply(mock_update, "Test message")

        mock_update.callback_query.message.reply_text.assert_called_once_with(
            "Test message"
        )
        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_safe_reply_with_kwargs(
        self, handler: BaseHandler, mock_update: MagicMock
    ) -> None:
        """Test safe_reply with additional kwargs."""
        await handler.safe_reply(mock_update, "Test message", parse_mode="HTML")
        mock_update.message.reply_text.assert_called_once_with(
            "Test message", parse_mode="HTML"
        )

    @pytest.mark.asyncio()
    async def test_safe_reply_exception_handling(
        self, handler: BaseHandler, mock_update: MagicMock
    ) -> None:
        """Test safe_reply handles exceptions gracefully."""
        mock_update.message.reply_text = AsyncMock(side_effect=Exception("Send failed"))

        # Should not raise exception
        await handler.safe_reply(mock_update, "Test message")


class TestErrorBoundaryWithAdditionalArgs:
    """Tests for error boundary with additional arguments."""

    @pytest.fixture()
    def mock_update(self) -> MagicMock:
        """Create mock Telegram update."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 12345
        update.effective_user.username = "testuser"
        update.message = MagicMock()
        update.message.text = "/test"
        update.message.reply_text = AsyncMock()
        update.callback_query = None
        return update

    @pytest.fixture()
    def mock_context(self) -> MagicMock:
        """Create mock Telegram context."""
        return MagicMock()

    @pytest.mark.asyncio()
    async def test_handler_with_args(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test handler with additional positional arguments."""

        @telegram_error_boundary()
        async def test_handler(update, context, extra_arg):
            return extra_arg

        with (
            patch("src.utils.telegram_error_handlers.set_user_context"),
            patch("src.utils.telegram_error_handlers.add_breadcrumb"),
        ):
            result = await test_handler(mock_update, mock_context, "extra_value")
            assert result == "extra_value"

    @pytest.mark.asyncio()
    async def test_handler_with_kwargs(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test handler with keyword arguments."""

        @telegram_error_boundary()
        async def test_handler(update, context, **kwargs):
            return kwargs.get("key")

        with (
            patch("src.utils.telegram_error_handlers.set_user_context"),
            patch("src.utils.telegram_error_handlers.add_breadcrumb"),
        ):
            result = await test_handler(mock_update, mock_context, key="value")
            assert result == "value"

    @pytest.mark.asyncio()
    async def test_handler_preserves_function_name(
        self, mock_update: MagicMock, mock_context: MagicMock
    ) -> None:
        """Test that decorator preserves function name."""

        @telegram_error_boundary()
        async def my_custom_handler(update, context):
            return "success"

        assert my_custom_handler.__name__ == "my_custom_handler"
