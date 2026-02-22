"""Unit tests for resume_command.py.

Tests for the /resume command that resumes bot operations after pause.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.telegram_bot.commands.resume_command import resume_command

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def mock_update():
    """Create a mock Telegram Update object."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123456789
    return update


@pytest.fixture()
def mock_context():
    """Create a mock Telegram Context object."""
    context = MagicMock()
    context.bot_data = {}
    return context


@pytest.fixture()
def mock_state_manager():
    """Create a mock StateManager object."""
    state_manager = MagicMock()
    state_manager.is_paused = True
    state_manager.consecutive_errors = 5
    state_manager.resume_operations = MagicMock()
    return state_manager


@pytest.fixture()
def mock_config_with_admins():
    """Create a mock Config object with admin users."""
    config = MagicMock()
    config.security = MagicMock()
    config.security.admin_users = [123456789, 987654321]
    return config


# ============================================================================
# Test: Command Returns Early - No Message/User
# ============================================================================


class TestResumeCommandEarlyReturn:
    """Tests for resume command returning early on missing data."""

    @pytest.mark.asyncio()
    async def test_resume_command_returns_early_if_no_message(self, mock_context):
        """Test that command returns early if message is None."""
        # Arrange
        update = MagicMock()
        update.message = None
        update.effective_user = MagicMock()

        # Act
        result = await resume_command(update, mock_context)

        # Assert
        assert result is None

    @pytest.mark.asyncio()
    async def test_resume_command_returns_early_if_no_user(self, mock_context):
        """Test that command returns early if effective_user is None."""
        # Arrange
        update = MagicMock()
        update.message = MagicMock()
        update.effective_user = None

        # Act
        result = await resume_command(update, mock_context)

        # Assert
        assert result is None


# ============================================================================
# Test: State Manager Not AvAlgolable
# ============================================================================


class TestStateManagerNotAvAlgolable:
    """Tests for resume command when state manager is missing."""

    @pytest.mark.asyncio()
    async def test_resume_command_handles_missing_state_manager(
        self, mock_update, mock_context
    ):
        """Test that command handles missing state manager gracefully."""
        # Arrange
        mock_context.bot_data = {}  # No state_manager

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "недоступна" in call_args or "❌" in call_args

    @pytest.mark.asyncio()
    async def test_resume_command_handles_none_state_manager(
        self, mock_update, mock_context
    ):
        """Test that command handles None state manager."""
        # Arrange
        mock_context.bot_data = {"state_manager": None}

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "недоступна" in call_args


# ============================================================================
# Test: Bot Not Paused
# ============================================================================


class TestBotNotPaused:
    """Tests for resume command when bot is not paused."""

    @pytest.mark.asyncio()
    async def test_resume_command_shows_info_when_not_paused(
        self, mock_update, mock_context, mock_state_manager
    ):
        """Test that command shows info when bot is not paused."""
        # Arrange
        mock_state_manager.is_paused = False
        mock_state_manager.consecutive_errors = 2
        mock_context.bot_data = {"state_manager": mock_state_manager}

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "не находится на паузе" in call_args or "ℹ️" in call_args

    @pytest.mark.asyncio()
    async def test_resume_command_shows_error_count_when_not_paused(
        self, mock_update, mock_context, mock_state_manager
    ):
        """Test that command shows error count when bot is not paused."""
        # Arrange
        mock_state_manager.is_paused = False
        mock_state_manager.consecutive_errors = 3
        mock_context.bot_data = {"state_manager": mock_state_manager}

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "3" in call_args or "ошибок" in call_args


# ============================================================================
# Test: Admin Authorization
# ============================================================================


class TestAdminAuthorization:
    """Tests for admin authorization in resume command."""

    @pytest.mark.asyncio()
    async def test_resume_command_rejects_non_admin_user(
        self, mock_update, mock_context, mock_state_manager, mock_config_with_admins
    ):
        """Test that non-admin users are rejected."""
        # Arrange
        mock_state_manager.is_paused = True
        mock_context.bot_data = {
            "state_manager": mock_state_manager,
            "config": mock_config_with_admins,
        }
        mock_update.effective_user.id = 111111111  # Not in admin list

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "администратор" in call_args.lower() or "⛔" in call_args

    @pytest.mark.asyncio()
    async def test_resume_command_accepts_admin_user(
        self, mock_update, mock_context, mock_state_manager, mock_config_with_admins
    ):
        """Test that admin users can resume operations."""
        # Arrange
        mock_state_manager.is_paused = True
        mock_context.bot_data = {
            "state_manager": mock_state_manager,
            "config": mock_config_with_admins,
        }
        mock_update.effective_user.id = 123456789  # In admin list

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_state_manager.resume_operations.assert_called_once()
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "возобновлена" in call_args or "✅" in call_args


# ============================================================================
# Test: Successful Resume
# ============================================================================


class TestSuccessfulResume:
    """Tests for successful resume operation."""

    @pytest.mark.asyncio()
    async def test_resume_command_calls_resume_operations(
        self, mock_update, mock_context, mock_state_manager
    ):
        """Test that resume_operations is called on state manager."""
        # Arrange
        mock_state_manager.is_paused = True
        mock_context.bot_data = {"state_manager": mock_state_manager}

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_state_manager.resume_operations.assert_called_once()

    @pytest.mark.asyncio()
    async def test_resume_command_shows_success_message(
        self, mock_update, mock_context, mock_state_manager
    ):
        """Test that success message is shown after resume."""
        # Arrange
        mock_state_manager.is_paused = True
        mock_state_manager.consecutive_errors = 10
        mock_context.bot_data = {"state_manager": mock_state_manager}

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "✅" in call_args or "возобновлена" in call_args

    @pytest.mark.asyncio()
    async def test_resume_command_shows_reset_error_count(
        self, mock_update, mock_context, mock_state_manager
    ):
        """Test that the number of reset errors is shown."""
        # Arrange
        mock_state_manager.is_paused = True
        mock_state_manager.consecutive_errors = 7
        mock_context.bot_data = {"state_manager": mock_state_manager}

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "7" in call_args or "ошибок" in call_args


# ============================================================================
# Test: Config Without Admin Users
# ============================================================================


class TestConfigWithoutAdminUsers:
    """Tests for config without admin user restrictions."""

    @pytest.mark.asyncio()
    async def test_resume_command_allows_any_user_without_admin_config(
        self, mock_update, mock_context, mock_state_manager
    ):
        """Test that any user can resume when no admin config exists."""
        # Arrange
        mock_state_manager.is_paused = True
        mock_context.bot_data = {"state_manager": mock_state_manager}
        # No config = no admin restrictions

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_state_manager.resume_operations.assert_called_once()

    @pytest.mark.asyncio()
    async def test_resume_command_allows_user_when_admin_list_empty(
        self, mock_update, mock_context, mock_state_manager
    ):
        """Test that any user can resume when admin list is empty."""
        # Arrange
        mock_state_manager.is_paused = True
        config = MagicMock()
        config.security = MagicMock()
        config.security.admin_users = []  # Empty admin list
        mock_context.bot_data = {
            "state_manager": mock_state_manager,
            "config": config,
        }

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_state_manager.resume_operations.assert_called_once()

    @pytest.mark.asyncio()
    async def test_resume_command_allows_user_when_no_security_attr(
        self, mock_update, mock_context, mock_state_manager
    ):
        """Test that any user can resume when security attr is missing."""
        # Arrange
        mock_state_manager.is_paused = True
        config = MagicMock()
        # Configure security to not have admin_users attribute
        del config.security.admin_users
        mock_context.bot_data = {
            "state_manager": mock_state_manager,
            "config": config,
        }

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_state_manager.resume_operations.assert_called_once()


# ============================================================================
# Test: Edge Cases
# ============================================================================


class TestEdgeCases:
    """Tests for edge cases in resume command."""

    @pytest.mark.asyncio()
    async def test_resume_command_with_zero_consecutive_errors(
        self, mock_update, mock_context, mock_state_manager
    ):
        """Test resume when consecutive errors is 0."""
        # Arrange
        mock_state_manager.is_paused = True
        mock_state_manager.consecutive_errors = 0
        mock_context.bot_data = {"state_manager": mock_state_manager}

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_state_manager.resume_operations.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "0" in call_args or "Сброшено" in call_args

    @pytest.mark.asyncio()
    async def test_resume_command_with_large_error_count(
        self, mock_update, mock_context, mock_state_manager
    ):
        """Test resume when consecutive errors is very large."""
        # Arrange
        mock_state_manager.is_paused = True
        mock_state_manager.consecutive_errors = 1000
        mock_context.bot_data = {"state_manager": mock_state_manager}

        # Act
        await resume_command(mock_update, mock_context)

        # Assert
        mock_state_manager.resume_operations.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "1000" in call_args
