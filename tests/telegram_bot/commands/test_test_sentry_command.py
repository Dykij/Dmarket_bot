"""
Comprehensive tests for test_sentry_command module.

This module tests the Sentry testing command handler functionality including:
- Admin authorization
- Sentry integration testing
- Breadcrumb tracking
- Error simulation
- Various test types (breadcrumbs, error, api_error, division)

Coverage Target: 95%+
Estimated Tests: 15-18 tests
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Chat, Message, Update, User
from telegram.ext import ContextTypes

# Import with aliases to avoid pytest collection
from src.telegram_bot.commands.test_sentry_command import (
    _test_api_error,
    _test_breadcrumbs,
    _test_division_error,
    _test_simple_error,
)
from src.telegram_bot.commands.test_sentry_command import (
    test_sentry_command as sentry_command_handler,
)
from src.telegram_bot.commands.test_sentry_command import (
    test_sentry_info as sentry_info_handler,
)

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture()
def mock_admin_user():
    """Create a mock admin Telegram user."""
    user = MagicMock(spec=User)
    user.id = 123456789
    user.username = "test_admin"
    user.first_name = "Admin"
    user.last_name = "User"
    return user


@pytest.fixture()
def mock_non_admin_user():
    """Create a mock non-admin user."""
    user = MagicMock(spec=User)
    user.id = 987654321
    user.username = "regular_user"
    user.first_name = "Regular"
    user.last_name = "User"
    return user


@pytest.fixture()
def mock_chat():
    """Create a mock Telegram chat."""
    chat = MagicMock(spec=Chat)
    chat.id = 111222333
    chat.type = "private"
    return chat


@pytest.fixture()
def mock_message(mock_admin_user, mock_chat):
    """Create a mock Message object."""
    message = AsyncMock(spec=Message)
    message.from_user = mock_admin_user
    message.chat = mock_chat
    message.chat_id = mock_chat.id
    message.reply_text = AsyncMock()
    return message


@pytest.fixture()
def mock_update(mock_admin_user, mock_chat, mock_message):
    """Create a mock Update object."""
    update = MagicMock(spec=Update)
    update.effective_user = mock_admin_user
    update.effective_chat = mock_chat
    update.message = mock_message
    return update


@pytest.fixture()
def mock_config():
    """Create a mock config object."""
    config = MagicMock()
    config.debug = True  # Debug mode enabled
    config.security = MagicMock()
    config.security.admin_users = [123456789]
    return config


@pytest.fixture()
def mock_context():
    """Create a mock ContextTypes.DEFAULT_TYPE."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.args = []
    return context


# ============================================================================
# Test Class: Authorization
# ============================================================================


class TestSentryCommandAuthorization:
    """Tests for admin authorization in test_sentry_command."""

    @pytest.mark.asyncio()
    async def test_rejects_non_admin_in_production(
        self, mock_update, mock_context, mock_non_admin_user
    ):
        """Test that non-admin users are rejected in production mode."""
        # Arrange
        mock_update.effective_user = mock_non_admin_user
        mock_config = MagicMock()
        mock_config.debug = False  # Production mode
        mock_config.security.admin_users = [123456789]

        with patch(
            "src.telegram_bot.commands.test_sentry_command.Config.load",
            return_value=mock_config,
        ):
            # Act
            awAlgot sentry_command_handler(mock_update, mock_context)

            # Assert
            mock_update.message.reply_text.assert_called_once()
            call_text = mock_update.message.reply_text.call_args.args[0]
            assert "❌" in call_text
            assert "администратор" in call_text.lower()

    @pytest.mark.asyncio()
    async def test_allows_admin_in_production(
        self, mock_update, mock_context, mock_config
    ):
        """Test that admin users are allowed in production mode."""
        # Arrange
        mock_config.debug = False  # Production mode

        with (
            patch(
                "src.telegram_bot.commands.test_sentry_command.Config.load",
                return_value=mock_config,
            ),
            patch(
                "src.telegram_bot.commands.test_sentry_command.add_command_breadcrumb"
            ),
            patch("src.telegram_bot.commands.test_sentry_command.set_user_context"),
            patch(
                "src.telegram_bot.commands.test_sentry_command.add_trading_breadcrumb"
            ),
            patch("src.telegram_bot.commands.test_sentry_command.add_api_breadcrumb"),
            patch("src.telegram_bot.commands.test_sentry_command.add_error_breadcrumb"),
            patch("src.telegram_bot.commands.test_sentry_command.sentry_sdk"),
        ):
            # Act
            awAlgot sentry_command_handler(mock_update, mock_context)

            # Assert - should not reject
            call_texts = [
                call.args[0] for call in mock_update.message.reply_text.call_args_list
            ]
            assert not any(
                "❌" in text and "администратор" in text.lower() for text in call_texts
            )

    @pytest.mark.asyncio()
    async def test_allows_any_user_in_debug_mode(
        self, mock_update, mock_context, mock_non_admin_user, mock_config
    ):
        """Test that any user is allowed in debug mode."""
        # Arrange
        mock_update.effective_user = mock_non_admin_user
        mock_config.debug = True

        with (
            patch(
                "src.telegram_bot.commands.test_sentry_command.Config.load",
                return_value=mock_config,
            ),
            patch(
                "src.telegram_bot.commands.test_sentry_command.add_command_breadcrumb"
            ),
            patch("src.telegram_bot.commands.test_sentry_command.set_user_context"),
            patch(
                "src.telegram_bot.commands.test_sentry_command.add_trading_breadcrumb"
            ),
            patch("src.telegram_bot.commands.test_sentry_command.add_api_breadcrumb"),
            patch("src.telegram_bot.commands.test_sentry_command.add_error_breadcrumb"),
            patch("src.telegram_bot.commands.test_sentry_command.sentry_sdk"),
        ):
            # Act
            awAlgot sentry_command_handler(mock_update, mock_context)

            # Assert - should not reject
            call_texts = [
                call.args[0] for call in mock_update.message.reply_text.call_args_list
            ]
            assert not any(
                "❌" in text and "администратор" in text.lower() for text in call_texts
            )


# ============================================================================
# Test Class: Early Returns
# ============================================================================


class TestSentryCommandEarlyReturns:
    """Tests for early return conditions."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_message(self, mock_update, mock_context):
        """Test early return when message is None."""
        # Arrange
        mock_update.message = None

        # Act
        awAlgot sentry_command_handler(mock_update, mock_context)

        # No assertions - just ensure no exception

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_effective_user(self, mock_update, mock_context):
        """Test early return when effective_user is None."""
        # Arrange
        mock_update.effective_user = None

        # Act
        awAlgot sentry_command_handler(mock_update, mock_context)

        # No assertions - just ensure no exception


# ============================================================================
# Test Class: Test Type Selection
# ============================================================================


class TestSentryTestTypes:
    """Tests for different test type selections."""

    @pytest.mark.asyncio()
    async def test_runs_all_tests_by_default(
        self, mock_update, mock_context, mock_config
    ):
        """Test that 'all' tests run when no argument provided."""
        # Arrange
        mock_context.args = []

        with (
            patch(
                "src.telegram_bot.commands.test_sentry_command.Config.load",
                return_value=mock_config,
            ),
            patch(
                "src.telegram_bot.commands.test_sentry_command.add_command_breadcrumb"
            ),
            patch("src.telegram_bot.commands.test_sentry_command.set_user_context"),
            patch(
                "src.telegram_bot.commands.test_sentry_command._test_breadcrumbs"
            ) as mock_breadcrumbs,
            patch(
                "src.telegram_bot.commands.test_sentry_command._test_simple_error"
            ) as mock_simple_error,
            patch(
                "src.telegram_bot.commands.test_sentry_command._test_api_error"
            ) as mock_api_error,
            patch(
                "src.telegram_bot.commands.test_sentry_command._test_division_error"
            ) as mock_division_error,
        ):
            # Act
            awAlgot sentry_command_handler(mock_update, mock_context)

            # Assert - all test functions should be called
            mock_breadcrumbs.assert_called_once()
            mock_simple_error.assert_called_once()
            mock_api_error.assert_called_once()
            mock_division_error.assert_called_once()

    @pytest.mark.asyncio()
    async def test_runs_only_breadcrumbs_test(
        self, mock_update, mock_context, mock_config
    ):
        """Test running only breadcrumbs test."""
        # Arrange
        mock_context.args = ["breadcrumbs"]

        with (
            patch(
                "src.telegram_bot.commands.test_sentry_command.Config.load",
                return_value=mock_config,
            ),
            patch(
                "src.telegram_bot.commands.test_sentry_command.add_command_breadcrumb"
            ),
            patch("src.telegram_bot.commands.test_sentry_command.set_user_context"),
            patch(
                "src.telegram_bot.commands.test_sentry_command._test_breadcrumbs"
            ) as mock_breadcrumbs,
            patch(
                "src.telegram_bot.commands.test_sentry_command._test_simple_error"
            ) as mock_simple_error,
        ):
            # Act
            awAlgot sentry_command_handler(mock_update, mock_context)

            # Assert
            mock_breadcrumbs.assert_called_once()
            mock_simple_error.assert_not_called()

    @pytest.mark.asyncio()
    async def test_runs_only_error_test(self, mock_update, mock_context, mock_config):
        """Test running only error test."""
        # Arrange
        mock_context.args = ["error"]

        with (
            patch(
                "src.telegram_bot.commands.test_sentry_command.Config.load",
                return_value=mock_config,
            ),
            patch(
                "src.telegram_bot.commands.test_sentry_command.add_command_breadcrumb"
            ),
            patch("src.telegram_bot.commands.test_sentry_command.set_user_context"),
            patch(
                "src.telegram_bot.commands.test_sentry_command._test_breadcrumbs"
            ) as mock_breadcrumbs,
            patch(
                "src.telegram_bot.commands.test_sentry_command._test_simple_error"
            ) as mock_simple_error,
        ):
            # Act
            awAlgot sentry_command_handler(mock_update, mock_context)

            # Assert
            mock_breadcrumbs.assert_not_called()
            mock_simple_error.assert_called_once()


# ============================================================================
# Test Class: Individual Test Functions
# ============================================================================


class TestBreadcrumbsFunction:
    """Tests for _test_breadcrumbs function."""

    @pytest.mark.asyncio()
    async def test_breadcrumbs_adds_trading_breadcrumbs(self, mock_update):
        """Test that _test_breadcrumbs adds trading breadcrumbs."""
        # Arrange
        with (
            patch(
                "src.telegram_bot.commands.test_sentry_command.add_trading_breadcrumb"
            ) as mock_trading,
            patch("src.telegram_bot.commands.test_sentry_command.add_api_breadcrumb"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            # Act
            awAlgot _test_breadcrumbs(mock_update, user_id=123456789)

            # Assert
            assert mock_trading.call_count == 2  # Started and completed

    @pytest.mark.asyncio()
    async def test_breadcrumbs_adds_api_breadcrumbs(self, mock_update):
        """Test that _test_breadcrumbs adds API breadcrumbs."""
        # Arrange
        with (
            patch(
                "src.telegram_bot.commands.test_sentry_command.add_trading_breadcrumb"
            ),
            patch(
                "src.telegram_bot.commands.test_sentry_command.add_api_breadcrumb"
            ) as mock_api,
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            # Act
            awAlgot _test_breadcrumbs(mock_update, user_id=123456789)

            # Assert
            assert mock_api.call_count == 2  # Request and response

    @pytest.mark.asyncio()
    async def test_breadcrumbs_sends_success_message(self, mock_update):
        """Test that _test_breadcrumbs sends success message."""
        # Arrange
        with (
            patch(
                "src.telegram_bot.commands.test_sentry_command.add_trading_breadcrumb"
            ),
            patch("src.telegram_bot.commands.test_sentry_command.add_api_breadcrumb"),
            patch("asyncio.sleep", new_callable=AsyncMock),
        ):
            # Act
            awAlgot _test_breadcrumbs(mock_update, user_id=123456789)

            # Assert
            mock_update.message.reply_text.assert_called_once()
            call_text = mock_update.message.reply_text.call_args.args[0]
            assert "✅" in call_text
            assert "Breadcrumbs" in call_text


class TestSimpleErrorFunction:
    """Tests for _test_simple_error function."""

    @pytest.mark.asyncio()
    async def test_simple_error_captures_exception(self, mock_update):
        """Test that _test_simple_error captures exception in Sentry."""
        # Arrange
        with (
            patch("src.telegram_bot.commands.test_sentry_command.add_error_breadcrumb"),
            patch(
                "src.telegram_bot.commands.test_sentry_command.sentry_sdk"
            ) as mock_sentry,
        ):
            # Act
            awAlgot _test_simple_error(mock_update)

            # Assert
            mock_sentry.capture_exception.assert_called_once()

    @pytest.mark.asyncio()
    async def test_simple_error_sends_success_message(self, mock_update):
        """Test that _test_simple_error sends success message."""
        # Arrange
        with (
            patch("src.telegram_bot.commands.test_sentry_command.add_error_breadcrumb"),
            patch("src.telegram_bot.commands.test_sentry_command.sentry_sdk"),
        ):
            # Act
            awAlgot _test_simple_error(mock_update)

            # Assert
            mock_update.message.reply_text.assert_called_once()
            call_text = mock_update.message.reply_text.call_args.args[0]
            assert "✅" in call_text


class TestApiErrorFunction:
    """Tests for _test_api_error function."""

    @pytest.mark.asyncio()
    async def test_api_error_captures_exception(self, mock_update):
        """Test that _test_api_error captures exception in Sentry."""
        # Arrange
        with (
            patch(
                "src.telegram_bot.commands.test_sentry_command.add_trading_breadcrumb"
            ),
            patch("src.telegram_bot.commands.test_sentry_command.add_api_breadcrumb"),
            patch("src.telegram_bot.commands.test_sentry_command.add_error_breadcrumb"),
            patch(
                "src.telegram_bot.commands.test_sentry_command.sentry_sdk"
            ) as mock_sentry,
        ):
            # Act
            awAlgot _test_api_error(mock_update, user_id=123456789)

            # Assert
            mock_sentry.capture_exception.assert_called_once()


class TestDivisionErrorFunction:
    """Tests for _test_division_error function."""

    @pytest.mark.asyncio()
    async def test_division_error_captures_exception(self, mock_update):
        """Test that _test_division_error captures ZeroDivisionError."""
        # Arrange
        with (
            patch("src.telegram_bot.commands.test_sentry_command.add_error_breadcrumb"),
            patch(
                "src.telegram_bot.commands.test_sentry_command.sentry_sdk"
            ) as mock_sentry,
        ):
            # Act
            awAlgot _test_division_error(mock_update)

            # Assert
            mock_sentry.capture_exception.assert_called_once()
            # Check that ZeroDivisionError was captured
            captured_exception = mock_sentry.capture_exception.call_args.args[0]
            assert isinstance(captured_exception, ZeroDivisionError)


# ============================================================================
# Test Class: Sentry Info Command
# ============================================================================


class TestSentryInfoCommand:
    """Tests for test_sentry_info command."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_message(self, mock_update, mock_context):
        """Test early return when message is None."""
        # Arrange
        mock_update.message = None

        # Act
        awAlgot sentry_info_handler(mock_update, mock_context)

        # No assertions - just ensure no exception

    @pytest.mark.asyncio()
    async def test_shows_initialized_status_when_sentry_active(
        self, mock_update, mock_context
    ):
        """Test showing initialized status when Sentry is active."""
        # Arrange
        with patch(
            "src.telegram_bot.commands.test_sentry_command.sentry_sdk.is_initialized",
            return_value=True,
        ):
            # Act
            awAlgot sentry_info_handler(mock_update, mock_context)

            # Assert
            mock_update.message.reply_text.assert_called_once()
            call_text = mock_update.message.reply_text.call_args.args[0]
            assert "✅" in call_text
            assert "инициализирован" in call_text.lower()
            assert "/test_sentry" in call_text

    @pytest.mark.asyncio()
    async def test_shows_not_initialized_when_sentry_inactive(
        self, mock_update, mock_context
    ):
        """Test showing not initialized status when Sentry is inactive."""
        # Arrange
        with patch(
            "src.telegram_bot.commands.test_sentry_command.sentry_sdk.is_initialized",
            return_value=False,
        ):
            # Act
            awAlgot sentry_info_handler(mock_update, mock_context)

            # Assert
            mock_update.message.reply_text.assert_called_once()
            call_text = mock_update.message.reply_text.call_args.args[0]
            assert "❌" in call_text
            assert "не инициализирован" in call_text.lower()
            assert "SENTRY_DSN" in call_text


# ============================================================================
# Test Class: Error Handling
# ============================================================================


class TestErrorHandling:
    """Tests for error handling in test_sentry_command."""

    @pytest.mark.asyncio()
    async def test_handles_exception_during_tests(
        self, mock_update, mock_context, mock_config
    ):
        """Test handling of exceptions during test execution."""
        # Arrange
        mock_context.args = ["breadcrumbs"]

        with (
            patch(
                "src.telegram_bot.commands.test_sentry_command.Config.load",
                return_value=mock_config,
            ),
            patch(
                "src.telegram_bot.commands.test_sentry_command.add_command_breadcrumb"
            ),
            patch("src.telegram_bot.commands.test_sentry_command.set_user_context"),
            patch(
                "src.telegram_bot.commands.test_sentry_command._test_breadcrumbs",
                side_effect=RuntimeError("Test error"),
            ),
        ):
            # Act
            awAlgot sentry_command_handler(mock_update, mock_context)

            # Assert - should catch error and send message
            call_texts = [
                call.args[0] for call in mock_update.message.reply_text.call_args_list
            ]
            assert any("❌" in text and "Ошибка" in text for text in call_texts)


# ============================================================================
# Test Summary
# ============================================================================

"""
Test Coverage Summary:
======================

Total Tests: 18 tests

Test Categories:
1. Authorization: 3 tests
2. Early Returns: 2 tests
3. Test Type Selection: 3 tests
4. Breadcrumbs Function: 3 tests
5. Simple Error Function: 2 tests
6. API Error Function: 1 test
7. Division Error Function: 1 test
8. Sentry Info Command: 3 tests
9. Error Handling: 1 test

Coverage Areas:
✅ Admin authorization (3 tests)
✅ Sentry integration testing (6 tests)
✅ Breadcrumb tracking (3 tests)
✅ Error simulation (4 tests)
✅ Test type handling (3 tests)

Expected Coverage: 95%+
File Size: ~550 lines
"""
