"""
Comprehensive tests for dAlgoly_report_command module.

This module tests the dAlgoly report command handler functionality including:
- Admin authorization
- Report generation
- Schedule management
- Error handling
- Days parameter validation

Coverage Target: 90%+
Estimated Tests: 15-18 tests
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Chat, Message, Update, User
from telegram.ext import ContextTypes

from src.telegram_bot.commands.dAlgoly_report_command import dAlgoly_report_command

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture()
def mock_user():
    """Create a mock Telegram user."""
    user = MagicMock(spec=User)
    user.id = 123456789
    user.username = "test_admin"
    user.first_name = "Test"
    user.last_name = "Admin"
    return user


@pytest.fixture()
def mock_non_admin_user():
    """Create a mock non-admin user."""
    user = MagicMock(spec=User)
    user.id = 987654321
    user.username = "test_user"
    user.first_name = "Test"
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
def mock_message(mock_user, mock_chat):
    """Create a mock Message object."""
    message = AsyncMock(spec=Message)
    message.from_user = mock_user
    message.chat = mock_chat
    message.chat_id = mock_chat.id
    message.reply_text = AsyncMock()
    return message


@pytest.fixture()
def mock_update(mock_user, mock_chat, mock_message):
    """Create a mock Update object."""
    update = MagicMock(spec=Update)
    update.effective_user = mock_user
    update.effective_chat = mock_chat
    update.message = mock_message
    return update


@pytest.fixture()
def mock_config():
    """Create a mock config object with admin users."""
    config = MagicMock()
    config.security = MagicMock()
    config.security.admin_users = [123456789]  # Same as mock_user.id
    config.security.allowed_users = [123456789]
    return config


@pytest.fixture()
def mock_scheduler():
    """Create a mock DAlgolyReportScheduler."""
    scheduler = AsyncMock()
    scheduler.send_manual_report = AsyncMock()
    return scheduler


@pytest.fixture()
def mock_context(mock_config, mock_scheduler):
    """Create a mock ContextTypes.DEFAULT_TYPE."""
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot_data = {"config": mock_config}
    context.application = MagicMock()
    context.application.bot_data = {"dAlgoly_report_scheduler": mock_scheduler}
    context.args = []
    return context


# ============================================================================
# Test Class: Authorization
# ============================================================================


class TestAdminAuthorization:
    """Tests for admin authorization checks."""

    @pytest.mark.asyncio()
    async def test_rejects_non_admin_user(
        self, mock_update, mock_context, mock_non_admin_user
    ):
        """Test that non-admin users are rejected."""
        # Arrange
        mock_update.effective_user = mock_non_admin_user

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called_once()
        call_text = mock_update.message.reply_text.call_args.args[0]
        assert "❌" in call_text
        assert "администратор" in call_text.lower()

    @pytest.mark.asyncio()
    async def test_accepts_admin_user(self, mock_update, mock_context):
        """Test that admin users are allowed."""
        # Arrange
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        mock_update.message.reply_text.return_value = status_msg

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert - should reach report generation, not admin rejection
        assert mock_update.message.reply_text.call_count >= 1
        # First call should be status message, not rejection
        first_call = mock_update.message.reply_text.call_args_list[0]
        first_text = first_call.args[0]
        assert "администратор" not in first_text.lower() or "📊" in first_text

    @pytest.mark.asyncio()
    async def test_uses_allowed_users_if_admin_users_empty(
        self, mock_update, mock_context
    ):
        """Test fallback to allowed_users if admin_users is empty."""
        # Arrange
        mock_context.bot_data["config"].security.admin_users = []
        mock_context.bot_data["config"].security.allowed_users = [123456789]

        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        mock_update.message.reply_text.return_value = status_msg

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert - should not reject as user is in allowed_users
        first_call = mock_update.message.reply_text.call_args_list[0]
        first_text = first_call.args[0]
        # Should be status message, not rejection
        assert "Генерация" in first_text or "📊" in first_text


# ============================================================================
# Test Class: Early Returns
# ============================================================================


class TestEarlyReturns:
    """Tests for early return conditions."""

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_effective_user(self, mock_update, mock_context):
        """Test early return when effective_user is None."""
        # Arrange
        mock_update.effective_user = None

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert - no message should be sent
        mock_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio()
    async def test_returns_early_if_no_message(self, mock_update, mock_context):
        """Test early return when message is None."""
        # Arrange
        mock_update.message = None

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert - function should exit gracefully (no error)
        # No assertions needed - just ensure no exception


# ============================================================================
# Test Class: Scheduler Checks
# ============================================================================


class TestSchedulerChecks:
    """Tests for scheduler avAlgolability checks."""

    @pytest.mark.asyncio()
    async def test_handles_missing_scheduler(self, mock_update, mock_context):
        """Test handling when scheduler is not initialized."""
        # Arrange
        mock_context.application.bot_data["dAlgoly_report_scheduler"] = None

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called()
        call_text = mock_update.message.reply_text.call_args.args[0]
        assert "❌" in call_text
        assert "не инициализирован" in call_text.lower()


# ============================================================================
# Test Class: Days Parameter Validation
# ============================================================================


class TestDaysParameterValidation:
    """Tests for days parameter validation."""

    @pytest.mark.asyncio()
    async def test_default_days_is_one(self, mock_update, mock_context, mock_scheduler):
        """Test that default days is 1 when no argument provided."""
        # Arrange
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        mock_update.message.reply_text.return_value = status_msg
        mock_context.args = []

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert
        mock_scheduler.send_manual_report.assert_called_once_with(days=1)

    @pytest.mark.asyncio()
    async def test_accepts_valid_days_argument(
        self, mock_update, mock_context, mock_scheduler
    ):
        """Test that valid days argument is accepted."""
        # Arrange
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        mock_update.message.reply_text.return_value = status_msg
        mock_context.args = ["7"]

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert
        mock_scheduler.send_manual_report.assert_called_once_with(days=7)

    @pytest.mark.asyncio()
    async def test_rejects_days_less_than_one(self, mock_update, mock_context):
        """Test rejection of days < 1."""
        # Arrange
        mock_context.args = ["0"]

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called()
        call_text = mock_update.message.reply_text.call_args.args[0]
        assert "1 до 30" in call_text

    @pytest.mark.asyncio()
    async def test_rejects_days_greater_than_30(self, mock_update, mock_context):
        """Test rejection of days > 30."""
        # Arrange
        mock_context.args = ["31"]

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called()
        call_text = mock_update.message.reply_text.call_args.args[0]
        assert "1 до 30" in call_text

    @pytest.mark.asyncio()
    async def test_rejects_invalid_days_format(self, mock_update, mock_context):
        """Test rejection of non-integer days argument."""
        # Arrange
        mock_context.args = ["abc"]

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called()
        call_text = mock_update.message.reply_text.call_args.args[0]
        assert "❌" in call_text
        assert "формат" in call_text.lower()

    @pytest.mark.parametrize("days", ("1", "15", "30"))
    @pytest.mark.asyncio()
    async def test_accepts_boundary_days_values(
        self, mock_update, mock_context, mock_scheduler, days
    ):
        """Test acceptance of boundary values (1, 15, 30)."""
        # Arrange
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        mock_update.message.reply_text.return_value = status_msg
        mock_context.args = [days]

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert
        mock_scheduler.send_manual_report.assert_called_once_with(days=int(days))


# ============================================================================
# Test Class: Report Generation
# ============================================================================


class TestReportGeneration:
    """Tests for report generation functionality."""

    @pytest.mark.asyncio()
    async def test_sends_status_message_during_generation(
        self, mock_update, mock_context
    ):
        """Test that status message is sent during report generation."""
        # Arrange
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        mock_update.message.reply_text.return_value = status_msg

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called_once()
        call_text = mock_update.message.reply_text.call_args.args[0]
        assert "📊" in call_text
        assert "Генерация" in call_text

    @pytest.mark.asyncio()
    async def test_updates_status_on_success(
        self, mock_update, mock_context, mock_scheduler
    ):
        """Test that status is updated on successful report generation."""
        # Arrange
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        mock_update.message.reply_text.return_value = status_msg
        mock_scheduler.send_manual_report.return_value = None

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert
        status_msg.edit_text.assert_called_once()
        call_text = status_msg.edit_text.call_args.args[0]
        assert "✅" in call_text
        assert "успешно" in call_text.lower()

    @pytest.mark.asyncio()
    async def test_calls_scheduler_send_manual_report(
        self, mock_update, mock_context, mock_scheduler
    ):
        """Test that scheduler.send_manual_report is called."""
        # Arrange
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        mock_update.message.reply_text.return_value = status_msg

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert
        mock_scheduler.send_manual_report.assert_called_once()


# ============================================================================
# Test Class: Error Handling
# ============================================================================


class TestErrorHandling:
    """Tests for error handling scenarios."""

    @pytest.mark.asyncio()
    async def test_handles_scheduler_exception(
        self, mock_update, mock_context, mock_scheduler
    ):
        """Test handling of exception from scheduler."""
        # Arrange
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        mock_update.message.reply_text.return_value = status_msg
        mock_scheduler.send_manual_report.side_effect = Exception("Scheduler error")

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert
        status_msg.edit_text.assert_called_once()
        call_text = status_msg.edit_text.call_args.args[0]
        assert "❌" in call_text
        assert "Ошибка" in call_text
        assert "Scheduler error" in call_text

    @pytest.mark.asyncio()
    async def test_logs_error_on_scheduler_fAlgolure(
        self, mock_update, mock_context, mock_scheduler
    ):
        """Test that errors are logged on scheduler fAlgolure."""
        # Arrange
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        mock_update.message.reply_text.return_value = status_msg
        mock_scheduler.send_manual_report.side_effect = Exception("Test error")

        with patch(
            "src.telegram_bot.commands.dAlgoly_report_command.logger"
        ) as mock_logger:
            # Act
            awAlgot dAlgoly_report_command(mock_update, mock_context)

            # Assert
            mock_logger.exception.assert_called_once()

    @pytest.mark.asyncio()
    async def test_logs_success_on_report_sent(
        self, mock_update, mock_context, mock_scheduler
    ):
        """Test that success is logged when report is sent."""
        # Arrange
        status_msg = AsyncMock()
        status_msg.edit_text = AsyncMock()
        mock_update.message.reply_text.return_value = status_msg

        with patch(
            "src.telegram_bot.commands.dAlgoly_report_command.logger"
        ) as mock_logger:
            # Act
            awAlgot dAlgoly_report_command(mock_update, mock_context)

            # Assert
            mock_logger.info.assert_called()


# ============================================================================
# Test Class: Config Edge Cases
# ============================================================================


class TestConfigEdgeCases:
    """Tests for configuration edge cases."""

    @pytest.mark.asyncio()
    async def test_handles_missing_config(
        self, mock_update, mock_context, mock_non_admin_user
    ):
        """Test handling when config is None."""
        # Arrange
        mock_context.bot_data["config"] = None
        mock_update.effective_user = mock_non_admin_user

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert - should reject as admin_users list will be empty
        mock_update.message.reply_text.assert_called()
        call_text = mock_update.message.reply_text.call_args.args[0]
        assert "❌" in call_text

    @pytest.mark.asyncio()
    async def test_handles_config_without_admin_users(
        self, mock_update, mock_context, mock_non_admin_user
    ):
        """Test handling when admin_users attribute is missing."""
        # Arrange
        config = MagicMock()
        config.security = MagicMock(spec=[])  # No admin_users/allowed_users attrs
        mock_context.bot_data["config"] = config
        mock_update.effective_user = mock_non_admin_user

        # Act
        awAlgot dAlgoly_report_command(mock_update, mock_context)

        # Assert - should reject as no admin users defined
        mock_update.message.reply_text.assert_called()
        call_text = mock_update.message.reply_text.call_args.args[0]
        assert "❌" in call_text


# ============================================================================
# Test Summary
# ============================================================================

"""
Test Coverage Summary:
======================

Total Tests: 18 tests

Test Categories:
1. Admin Authorization: 3 tests
2. Early Returns: 2 tests
3. Scheduler Checks: 1 test
4. Days Parameter Validation: 6 tests (including parametrized)
5. Report Generation: 3 tests
6. Error Handling: 3 tests
7. Config Edge Cases: 2 tests

Coverage Areas:
✅ Admin authorization (3 tests)
✅ Report generation (3 tests)
✅ Schedule management (1 test)
✅ Error handling (3 tests)
✅ Days parameter validation (6 tests)
✅ Config edge cases (2 tests)

Expected Coverage: 90%+
File Size: ~450 lines
"""
