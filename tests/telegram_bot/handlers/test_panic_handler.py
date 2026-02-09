"""Tests for panic_handler module."""
from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import Message, Update, User


class TestPanicCommands:
    @pytest.fixture
    def mock_update(self):
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        update.message = MagicMock(spec=Message)
        update.message.reply_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self):
        context = MagicMock()
        context.user_data = {}
        context.bot_data = {}
        return context

    @pytest.mark.asyncio
    async def test_panic_command_import(self, mock_update, mock_context):
        from src.telegram_bot.handlers.panic_handler import panic_button_command
        assert panic_button_command is not None
