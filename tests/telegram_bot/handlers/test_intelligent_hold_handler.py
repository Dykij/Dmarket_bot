"""Tests for intelligent_hold_handler module.

This module tests the intelligent hold command functions
for holding strategy recommendations via Telegram.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Chat, Message, Update, User


class TestIntelligentHoldCommands:
    """Tests for intelligent hold command functions."""

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
    async def test_hold_command(self, mock_update, mock_context):
        """Test /hold command."""
        from src.telegram_bot.handlers.intelligent_hold_handler import hold_command

        await hold_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
