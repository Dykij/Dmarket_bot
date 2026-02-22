"""Tests for steam_commands module.

This module tests the Steam commands handlers for statistics
and settings management.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import Message, Update, User

from src.telegram_bot.handlers.steam_commands import (
    steam_settings_command,
    steam_stats_command,
    steam_top_command,
)


class TestSteamStatsCommand:
    """Tests for steam_stats_command."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Update."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Context."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_stats_command_success(self, mock_update, mock_context):
        """Test successful stats command."""
        with patch("src.telegram_bot.handlers.steam_commands.get_steam_enhancer") as mock_enhancer_fn:
            mock_enhancer = MagicMock()
            mock_enhancer.get_daily_stats.return_value = {
                "count": 10,
                "avg_profit": 15.5,
                "max_profit": 25.0,
                "min_profit": 8.0,
            }
            mock_enhancer_fn.return_value = mock_enhancer

            with patch("src.telegram_bot.handlers.steam_commands.get_steam_db") as mock_db_fn:
                mock_db = MagicMock()
                mock_db.get_settings.return_value = {
                    "min_profit": 10,
                    "min_volume": 5,
                    "is_paused": False,
                }
                mock_db.get_cache_stats.return_value = {
                    "total": 100,
                    "actual": 80,
                    "stale": 20,
                }
                mock_db_fn.return_value = mock_db

                await steam_stats_command(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()
                call_args = mock_update.message.reply_text.call_args
                assert "Статистика" in str(call_args)

    @pytest.mark.asyncio
    async def test_stats_command_no_findings(self, mock_update, mock_context):
        """Test stats command with no findings."""
        with patch("src.telegram_bot.handlers.steam_commands.get_steam_enhancer") as mock_enhancer_fn:
            mock_enhancer = MagicMock()
            mock_enhancer.get_daily_stats.return_value = {
                "count": 0,
                "avg_profit": 0,
                "max_profit": 0,
                "min_profit": 0,
            }
            mock_enhancer_fn.return_value = mock_enhancer

            with patch("src.telegram_bot.handlers.steam_commands.get_steam_db") as mock_db_fn:
                mock_db = MagicMock()
                mock_db.get_settings.return_value = {
                    "min_profit": 10,
                    "min_volume": 5,
                    "is_paused": False,
                }
                mock_db.get_cache_stats.return_value = {
                    "total": 0,
                    "actual": 0,
                    "stale": 0,
                }
                mock_db_fn.return_value = mock_db

                await steam_stats_command(mock_update, mock_context)

                mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_stats_command_error(self, mock_update, mock_context):
        """Test stats command with error."""
        with patch("src.telegram_bot.handlers.steam_commands.get_steam_enhancer") as mock_enhancer_fn:
            mock_enhancer_fn.side_effect = Exception("Database error")

            await steam_stats_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "Ошибка" in str(call_args)

    @pytest.mark.asyncio
    async def test_stats_command_no_message(self, mock_update, mock_context):
        """Test stats command without message."""
        mock_update.message = None

        await steam_stats_command(mock_update, mock_context)

        # Should return early without error


class TestSteamTopCommand:
    """Tests for steam_top_command."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Update."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Context."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_top_command_success(self, mock_update, mock_context):
        """Test successful top command."""
        with patch("src.telegram_bot.handlers.steam_commands.get_steam_enhancer") as mock_enhancer_fn:
            mock_enhancer = MagicMock()
            mock_enhancer.get_top_items.return_value = [
                {"name": "AK-47 | Redline", "profit": 25.0},
                {"name": "M4A4 | Howl", "profit": 20.0},
            ]
            mock_enhancer_fn.return_value = mock_enhancer

            await steam_top_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_top_command_empty(self, mock_update, mock_context):
        """Test top command with empty results."""
        with patch("src.telegram_bot.handlers.steam_commands.get_steam_enhancer") as mock_enhancer_fn:
            mock_enhancer = MagicMock()
            mock_enhancer.get_top_items.return_value = []
            mock_enhancer_fn.return_value = mock_enhancer

            await steam_top_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()


class TestSteamSettingsCommand:
    """Tests for steam_settings_command."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Update."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Context."""
        return MagicMock()

    @pytest.mark.asyncio
    async def test_settings_command(self, mock_update, mock_context):
        """Test settings command."""
        with patch("src.telegram_bot.handlers.steam_commands.get_steam_db") as mock_db_fn:
            mock_db = MagicMock()
            mock_db.get_settings.return_value = {
                "min_profit": 10,
                "min_volume": 5,
                "is_paused": False,
            }
            mock_db_fn.return_value = mock_db

            await steam_settings_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_settings_command_paused(self, mock_update, mock_context):
        """Test settings command when paused."""
        with patch("src.telegram_bot.handlers.steam_commands.get_steam_db") as mock_db_fn:
            mock_db = MagicMock()
            mock_db.get_settings.return_value = {
                "min_profit": 10,
                "min_volume": 5,
                "is_paused": True,
            }
            mock_db_fn.return_value = mock_db

            await steam_settings_command(mock_update, mock_context)

            mock_update.message.reply_text.assert_called_once()
            call_args = mock_update.message.reply_text.call_args
            assert "Пауза" in str(call_args) or "paused" in str(call_args).lower()
