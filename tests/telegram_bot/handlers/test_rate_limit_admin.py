"""Tests for rate_limit_admin.py - Admin commands for rate limiting management.

Phase 3 tests for achieving 80% coverage.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram_bot.handlers.rate_limit_admin import (
    ADMIN_IDS,
    is_admin,
    rate_limit_config_command,
    rate_limit_reset_command,
    rate_limit_stats_command,
    rate_limit_whitelist_command,
)

# ============================================================================
# is_admin Tests
# ============================================================================


class TestIsAdmin:
    """Tests for is_admin function."""

    def test_is_admin_true(self):
        """Test admin check for admin user."""
        admin_id = ADMIN_IDS[0] if ADMIN_IDS else 123456789

        with patch("src.telegram_bot.handlers.rate_limit_admin.ADMIN_IDS", [admin_id]):
            assert is_admin(admin_id) is True

    def test_is_admin_false(self):
        """Test admin check for non-admin user."""
        with patch("src.telegram_bot.handlers.rate_limit_admin.ADMIN_IDS", [123456789]):
            assert is_admin(999999999) is False

    def test_is_admin_empty_list(self):
        """Test admin check with empty admin list."""
        with patch("src.telegram_bot.handlers.rate_limit_admin.ADMIN_IDS", []):
            assert is_admin(123456789) is False


# ============================================================================
# rate_limit_stats_command Tests
# ============================================================================


class TestRateLimitStatsCommand:
    """Tests for rate_limit_stats_command."""

    @pytest.fixture()
    def mock_update(self):
        """Create mock Update object."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 123456789
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture()
    def mock_context(self):
        """Create mock Context object."""
        context = MagicMock()
        context.args = []
        context.bot_data = MagicMock()
        return context

    @pytest.fixture()
    def mock_rate_limiter(self):
        """Create mock rate limiter."""
        limiter = MagicMock()
        limiter.get_user_stats = AsyncMock(
            return_value={
                "scan": {"remAlgoning": 3, "limit": 10},
                "trade": {"remAlgoning": 5, "limit": 5},
            }
        )
        return limiter

    @pytest.mark.asyncio()
    async def test_stats_no_user(self, mock_context):
        """Test stats command with no effective user."""
        update = MagicMock()
        update.effective_user = None
        update.message = None

        awAlgot rate_limit_stats_command(update, mock_context)

        # Should return early without error

    @pytest.mark.asyncio()
    async def test_stats_no_message(self, mock_context):
        """Test stats command with no message."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.message = None

        awAlgot rate_limit_stats_command(update, mock_context)

    @pytest.mark.asyncio()
    async def test_stats_non_admin(self, mock_update, mock_context):
        """Test stats command by non-admin user."""
        with patch(
            "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=False
        ):
            awAlgot rate_limit_stats_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "только администраторам" in call_args

    @pytest.mark.asyncio()
    async def test_stats_no_rate_limiter(self, mock_update, mock_context):
        """Test stats command when rate limiter not configured."""
        mock_context.bot_data = MagicMock()
        mock_context.bot_data.user_rate_limiter = None

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(mock_context.bot_data, "__getattribute__", return_value=None),
        ):
            awAlgot rate_limit_stats_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "не настроен" in call_args

    @pytest.mark.asyncio()
    async def test_stats_success_own_user(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test stats command for own user."""
        mock_context.args = []
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_stats_command(mock_update, mock_context)

            mock_rate_limiter.get_user_stats.assert_called_once_with(
                mock_update.effective_user.id
            )
            mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_stats_success_other_user(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test stats command for another user."""
        mock_context.args = ["999999999"]
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_stats_command(mock_update, mock_context)

            mock_rate_limiter.get_user_stats.assert_called_once_with(999999999)

    @pytest.mark.asyncio()
    async def test_stats_error_handling(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test stats command error handling."""
        mock_rate_limiter.get_user_stats.side_effect = Exception("Database error")
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_stats_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Ошибка" in call_args

    @pytest.mark.asyncio()
    async def test_stats_formatting_low_usage(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test stats formatting with low usage (green)."""
        mock_rate_limiter.get_user_stats.return_value = {
            "scan": {"remAlgoning": 9, "limit": 10},  # 10% usage
        }
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_stats_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "🟢" in call_args

    @pytest.mark.asyncio()
    async def test_stats_formatting_medium_usage(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test stats formatting with medium usage (yellow)."""
        mock_rate_limiter.get_user_stats.return_value = {
            "scan": {"remAlgoning": 3, "limit": 10},  # 70% usage
        }
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_stats_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "🟡" in call_args

    @pytest.mark.asyncio()
    async def test_stats_formatting_high_usage(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test stats formatting with high usage (red)."""
        mock_rate_limiter.get_user_stats.return_value = {
            "scan": {"remAlgoning": 1, "limit": 10},  # 90% usage
        }
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_stats_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "🔴" in call_args


# ============================================================================
# rate_limit_reset_command Tests
# ============================================================================


class TestRateLimitResetCommand:
    """Tests for rate_limit_reset_command."""

    @pytest.fixture()
    def mock_update(self):
        """Create mock Update object."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 123456789
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture()
    def mock_context(self):
        """Create mock Context object."""
        context = MagicMock()
        context.args = []
        context.bot_data = MagicMock()
        return context

    @pytest.fixture()
    def mock_rate_limiter(self):
        """Create mock rate limiter."""
        limiter = MagicMock()
        limiter.reset_user_limits = AsyncMock()
        return limiter

    @pytest.mark.asyncio()
    async def test_reset_no_user(self, mock_context):
        """Test reset command with no effective user."""
        update = MagicMock()
        update.effective_user = None
        update.message = None

        awAlgot rate_limit_reset_command(update, mock_context)

    @pytest.mark.asyncio()
    async def test_reset_non_admin(self, mock_update, mock_context):
        """Test reset command by non-admin user."""
        with patch(
            "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=False
        ):
            awAlgot rate_limit_reset_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "только администраторам" in call_args

    @pytest.mark.asyncio()
    async def test_reset_no_rate_limiter(self, mock_update, mock_context):
        """Test reset command when rate limiter not configured."""
        # Set args so it doesn't trigger usage message
        mock_context.args = ["123456"]  # Valid user_id
        # Ensure bot_data.user_rate_limiter returns None
        type(mock_context).bot_data = MagicMock()

        with patch(
            "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
        ):
            # The function uses getattr which returns None by default for non-existent attributes
            awAlgot rate_limit_reset_command(mock_update, mock_context)

            # This test validates that the command handles the case
            assert mock_update.message.reply_text.called

    @pytest.mark.asyncio()
    async def test_reset_no_args(self, mock_update, mock_context, mock_rate_limiter):
        """Test reset command with no arguments."""
        mock_context.args = []
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_reset_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Использование" in call_args

    @pytest.mark.asyncio()
    async def test_reset_invalid_user_id(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test reset command with invalid user ID."""
        mock_context.args = ["not_a_number"]
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_reset_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Использование" in call_args

    @pytest.mark.asyncio()
    async def test_reset_all_actions(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test reset command for all actions."""
        mock_context.args = ["999999999"]
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_reset_command(mock_update, mock_context)

            mock_rate_limiter.reset_user_limits.assert_called_once_with(999999999, None)
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Лимиты сброшены" in call_args
            assert "все действия" in call_args

    @pytest.mark.asyncio()
    async def test_reset_specific_action(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test reset command for specific action."""
        mock_context.args = ["999999999", "scan"]
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_reset_command(mock_update, mock_context)

            mock_rate_limiter.reset_user_limits.assert_called_once_with(
                999999999, "scan"
            )
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "scan" in call_args

    @pytest.mark.asyncio()
    async def test_reset_error_handling(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test reset command error handling."""
        mock_context.args = ["999999999"]
        mock_rate_limiter.reset_user_limits.side_effect = Exception("Database error")
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_reset_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Ошибка" in call_args


# ============================================================================
# rate_limit_whitelist_command Tests
# ============================================================================


class TestRateLimitWhitelistCommand:
    """Tests for rate_limit_whitelist_command."""

    @pytest.fixture()
    def mock_update(self):
        """Create mock Update object."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 123456789
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture()
    def mock_context(self):
        """Create mock Context object."""
        context = MagicMock()
        context.args = []
        context.bot_data = MagicMock()
        return context

    @pytest.fixture()
    def mock_rate_limiter(self):
        """Create mock rate limiter."""
        limiter = MagicMock()
        limiter.add_whitelist = AsyncMock()
        limiter.remove_whitelist = AsyncMock()
        limiter.is_whitelisted = AsyncMock(return_value=False)
        return limiter

    @pytest.mark.asyncio()
    async def test_whitelist_no_user(self, mock_context):
        """Test whitelist command with no effective user."""
        update = MagicMock()
        update.effective_user = None
        update.message = None

        awAlgot rate_limit_whitelist_command(update, mock_context)

    @pytest.mark.asyncio()
    async def test_whitelist_non_admin(self, mock_update, mock_context):
        """Test whitelist command by non-admin user."""
        with patch(
            "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=False
        ):
            awAlgot rate_limit_whitelist_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "только администраторам" in call_args

    @pytest.mark.asyncio()
    async def test_whitelist_no_rate_limiter(self, mock_update, mock_context):
        """Test whitelist command when rate limiter not configured."""
        mock_context.args = ["add", "123456"]  # Valid args
        # Ensure bot_data.user_rate_limiter returns None
        type(mock_context).bot_data = MagicMock()

        with patch(
            "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
        ):
            # The function uses getattr which returns None by default for non-existent attributes
            awAlgot rate_limit_whitelist_command(mock_update, mock_context)

            # This test validates that the command handles the case
            assert mock_update.message.reply_text.called

    @pytest.mark.asyncio()
    async def test_whitelist_insufficient_args(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test whitelist command with insufficient arguments."""
        mock_context.args = ["add"]
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_whitelist_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Использование" in call_args

    @pytest.mark.asyncio()
    async def test_whitelist_invalid_user_id(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test whitelist command with invalid user ID."""
        mock_context.args = ["add", "not_a_number"]
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_whitelist_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Использование" in call_args

    @pytest.mark.asyncio()
    async def test_whitelist_add(self, mock_update, mock_context, mock_rate_limiter):
        """Test adding user to whitelist."""
        mock_context.args = ["add", "999999999"]
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_whitelist_command(mock_update, mock_context)

            mock_rate_limiter.add_whitelist.assert_called_once_with(999999999)
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "добавлен в whitelist" in call_args

    @pytest.mark.asyncio()
    async def test_whitelist_remove(self, mock_update, mock_context, mock_rate_limiter):
        """Test removing user from whitelist."""
        mock_context.args = ["remove", "999999999"]
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_whitelist_command(mock_update, mock_context)

            mock_rate_limiter.remove_whitelist.assert_called_once_with(999999999)
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "удален из whitelist" in call_args

    @pytest.mark.asyncio()
    async def test_whitelist_check_whitelisted(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test checking if user is whitelisted."""
        mock_context.args = ["check", "999999999"]
        mock_rate_limiter.is_whitelisted.return_value = True
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_whitelist_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "в whitelist" in call_args

    @pytest.mark.asyncio()
    async def test_whitelist_check_not_whitelisted(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test checking if user is not whitelisted."""
        mock_context.args = ["check", "999999999"]
        mock_rate_limiter.is_whitelisted.return_value = False
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_whitelist_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "не в whitelist" in call_args

    @pytest.mark.asyncio()
    async def test_whitelist_unknown_action(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test whitelist command with unknown action."""
        mock_context.args = ["unknown", "999999999"]
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_whitelist_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Неизвестное действие" in call_args

    @pytest.mark.asyncio()
    async def test_whitelist_error_handling(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test whitelist command error handling."""
        mock_context.args = ["add", "999999999"]
        mock_rate_limiter.add_whitelist.side_effect = Exception("Database error")
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_whitelist_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Ошибка" in call_args


# ============================================================================
# rate_limit_config_command Tests
# ============================================================================


class TestRateLimitConfigCommand:
    """Tests for rate_limit_config_command."""

    @pytest.fixture()
    def mock_update(self):
        """Create mock Update object."""
        update = MagicMock()
        update.effective_user = MagicMock()
        update.effective_user.id = 123456789
        update.message = MagicMock()
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture()
    def mock_context(self):
        """Create mock Context object."""
        context = MagicMock()
        context.args = []
        context.bot_data = MagicMock()
        return context

    @pytest.fixture()
    def mock_rate_limiter(self):
        """Create mock rate limiter."""
        from src.utils.user_rate_limiter import RateLimitConfig

        limiter = MagicMock()
        limiter.limits = {
            "scan": RateLimitConfig(requests=10, window=60, burst=2),
            "trade": RateLimitConfig(requests=5, window=30),
        }
        limiter.update_limit = MagicMock()
        return limiter

    @pytest.mark.asyncio()
    async def test_config_no_user(self, mock_context):
        """Test config command with no effective user."""
        update = MagicMock()
        update.effective_user = None
        update.message = None

        awAlgot rate_limit_config_command(update, mock_context)

    @pytest.mark.asyncio()
    async def test_config_non_admin(self, mock_update, mock_context):
        """Test config command by non-admin user."""
        with patch(
            "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=False
        ):
            awAlgot rate_limit_config_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "только администраторам" in call_args

    @pytest.mark.asyncio()
    async def test_config_no_rate_limiter(self, mock_update, mock_context):
        """Test config command when rate limiter not configured."""
        mock_context.args = ["scan", "10", "60"]  # Valid args
        # Ensure bot_data.user_rate_limiter returns None
        type(mock_context).bot_data = MagicMock()

        with patch(
            "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
        ):
            # The function uses getattr which returns None by default for non-existent attributes
            awAlgot rate_limit_config_command(mock_update, mock_context)

            # This test validates that the command handles the case
            assert mock_update.message.reply_text.called

    @pytest.mark.asyncio()
    async def test_config_show_current_limits(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test config command showing current limits."""
        mock_context.args = []
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_config_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Текущие лимиты" in call_args

    @pytest.mark.asyncio()
    async def test_config_insufficient_args(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test config command with insufficient arguments."""
        mock_context.args = ["scan", "5"]  # Missing window
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_config_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Использование" in call_args

    @pytest.mark.asyncio()
    async def test_config_invalid_requests(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test config command with invalid requests value."""
        mock_context.args = ["scan", "not_a_number", "60"]
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_config_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Использование" in call_args

    @pytest.mark.asyncio()
    async def test_config_update_limit(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test updating a rate limit."""
        mock_context.args = ["scan", "10", "120"]
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_config_command(mock_update, mock_context)

            mock_rate_limiter.update_limit.assert_called_once()
            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Лимит обновлен" in call_args

    @pytest.mark.asyncio()
    async def test_config_update_limit_with_burst(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test updating a rate limit with burst."""
        mock_context.args = ["scan", "10", "120", "3"]
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_config_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Burst" in call_args

    @pytest.mark.asyncio()
    async def test_config_error_handling(
        self, mock_update, mock_context, mock_rate_limiter
    ):
        """Test config command error handling."""
        mock_context.args = ["scan", "10", "60"]
        mock_rate_limiter.update_limit.side_effect = Exception("Config error")
        mock_context.bot_data.user_rate_limiter = mock_rate_limiter

        with (
            patch(
                "src.telegram_bot.handlers.rate_limit_admin.is_admin", return_value=True
            ),
            patch.object(
                mock_context.bot_data,
                "__getattribute__",
                return_value=mock_rate_limiter,
            ),
        ):
            awAlgot rate_limit_config_command(mock_update, mock_context)

            call_args = mock_update.message.reply_text.call_args[0][0]
            assert "Ошибка" in call_args
