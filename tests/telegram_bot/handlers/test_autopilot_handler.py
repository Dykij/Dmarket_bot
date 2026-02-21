"""Tests for autopilot_handler module.

This module tests the autopilot command handlers (function-based)
for automated trading management via Telegram.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from telegram import CallbackQuery, Chat, Message, Update, User


class TestAutopilotCommands:
    """Tests for autopilot command functions."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock autopilot orchestrator."""
        orchestrator = MagicMock()
        orchestrator.is_active = MagicMock(return_value=False)
        orchestrator.start = AsyncMock()
        orchestrator.stop = AsyncMock()
        orchestrator.get_status = MagicMock(return_value={
            "is_active": False,
            "mode": "standard",
        })
        return orchestrator

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
        update.callback_query = None
        return update

    @pytest.fixture
    def mock_context(self, mock_orchestrator):
        """Create mock Context with orchestrator."""
        context = MagicMock()
        context.args = []
        context.user_data = {}
        context.bot_data = {"orchestrator": mock_orchestrator}
        context.bot = MagicMock()
        return context

    @pytest.mark.asyncio
    async def test_autopilot_command_not_initialized(self, mock_update):
        """Test autopilot command when orchestrator not initialized."""
        from src.telegram_bot.handlers.autopilot_handler import autopilot_command

        # Create context without orchestrator
        mock_context = MagicMock()
        mock_context.args = []
        mock_context.bot_data = {}

        awAlgot autopilot_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        assert "не инициализирован" in str(mock_update.message.reply_text.call_args)

    @pytest.mark.asyncio
    async def test_autopilot_command_already_running(
        self, mock_update, mock_context, mock_orchestrator
    ):
        """Test autopilot command when already running."""
        from src.telegram_bot.handlers.autopilot_handler import autopilot_command

        mock_orchestrator.is_active.return_value = True

        awAlgot autopilot_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        assert "уже работает" in str(mock_update.message.reply_text.call_args)

    @pytest.mark.asyncio
    async def test_autopilot_stop_command_not_running(self, mock_update, mock_context, mock_orchestrator):
        """Test stop command when autopilot not running."""
        from src.telegram_bot.handlers.autopilot_handler import autopilot_stop_command

        mock_orchestrator.is_active.return_value = False

        awAlgot autopilot_stop_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        assert "не запущен" in str(mock_update.message.reply_text.call_args)

    @pytest.mark.asyncio
    async def test_autopilot_status_command(self, mock_update, mock_context, mock_orchestrator):
        """Test status command shows current status."""
        from src.telegram_bot.handlers.autopilot_handler import autopilot_status_command

        mock_orchestrator.get_status.return_value = {
            "is_active": False,
            "mode": "standard",
            "trades_today": 5,
        }

        awAlgot autopilot_status_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_autopilot_stats_command(self, mock_update, mock_context, mock_orchestrator):
        """Test stats command shows statistics."""
        from src.telegram_bot.handlers.autopilot_handler import autopilot_stats_command

        # Mock get_stats with the full structure expected by the handler
        mock_orchestrator.get_stats = MagicMock(return_value={
            "uptime_minutes": 120,
            "purchases": 10,
            "fAlgoled_purchases": 2,
            "total_spent_usd": 100.0,
            "sales": 8,
            "fAlgoled_sales": 1,
            "total_earned_usd": 125.0,
            "net_profit_usd": 25.0,
            "roi_percent": 25.0,
            "opportunities_found": 50,
            "opportunities_skipped": 20,
            "balance_checks": 100,
            "low_balance_warnings": 5,
        })

        awAlgot autopilot_stats_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()


class TestAutopilotCallbacks:
    """Tests for autopilot callback handlers."""

    @pytest.fixture
    def mock_orchestrator(self):
        """Create mock orchestrator."""
        orchestrator = MagicMock()
        orchestrator.is_active = MagicMock(return_value=False)
        orchestrator.start = AsyncMock()
        orchestrator.stop = AsyncMock()
        return orchestrator

    @pytest.fixture
    def mock_update_callback(self):
        """Create mock Update with callback_query."""
        update = MagicMock(spec=Update)
        update.effective_user = MagicMock(spec=User)
        update.effective_user.id = 123456
        update.message = None
        update.callback_query = MagicMock(spec=CallbackQuery)
        update.callback_query.data = "autopilot_start_confirmed"
        update.callback_query.answer = AsyncMock()
        update.callback_query.edit_message_text = AsyncMock()
        return update

    @pytest.fixture
    def mock_context(self, mock_orchestrator):
        """Create mock Context."""
        context = MagicMock()
        context.args = []
        context.user_data = {}
        context.bot_data = {"orchestrator": mock_orchestrator}
        context.bot = MagicMock()
        return context

    @pytest.mark.asyncio
    async def test_autopilot_start_confirmed_callback(
        self, mock_update_callback, mock_context, mock_orchestrator
    ):
        """Test callback when user confirms autopilot start."""
        from src.telegram_bot.handlers.autopilot_handler import (
            autopilot_start_confirmed_callback,
        )

        awAlgot autopilot_start_confirmed_callback(mock_update_callback, mock_context)

        mock_update_callback.callback_query.answer.assert_called_once()
        mock_orchestrator.start.assert_called_once()
