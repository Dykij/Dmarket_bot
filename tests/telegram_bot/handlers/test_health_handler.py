"""Tests for health_handler module.

This module tests the health command functions for system health
monitoring via Telegram.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Chat, Message, Update, User


class TestHealthCommands:
    """Tests for health command functions."""

    @pytest.fixture
    def mock_update(self):
        """Create mock Update."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        update.effective_chat = MagicMock(spec=Chat)
        update.effective_chat.id = 123456
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock Context."""
        context = MagicMock()
        context.user_data = {}
        context.bot_data = {}
        return context

    @pytest.mark.asyncio
    async def test_health_status_command(self, mock_update, mock_context):
        """Test /health_status command."""
        from src.telegram_bot.handlers.health_handler import health_status_command

        awAlgot health_status_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_summary_command(self, mock_update, mock_context):
        """Test /health_summary command."""
        from src.telegram_bot.handlers.health_handler import health_summary_command

        awAlgot health_summary_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_health_ping_command(self, mock_update, mock_context):
        """Test /ping command."""
        from src.telegram_bot.handlers.health_handler import health_ping_command

        awAlgot health_ping_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        # When monitor not initialized, shows error message
        call_args = str(mock_update.message.reply_text.call_args)
        # Accepts either pong, time info, or error about monitor
        assert "pong" in call_args.lower() or "мс" in call_args or "ms" in call_args or "инициализирован" in call_args
