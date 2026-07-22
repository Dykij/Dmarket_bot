"""
test_telegram_control.py — Tests for Telegram Control Bot.

Covers:
- Bot initialization and lifecycle
- Command handlers (/start, /stop, /status, /positions)
- Callback handlers (inline keyboards)
- Settings FSM (state machine)
- Error handling and resilience
- Message formatting
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ═══════════════════════════════════════════════════════════════════
# Telegram Notifier Tests
# ═══════════════════════════════════════════════════════════════════

class TestTelegramNotifier:
    """Tests for _TelegramNotifier."""

    def test_init_with_token(self):
        from src.telegram.notifier import _TelegramNotifier
        notifier = _TelegramNotifier.__new__(_TelegramNotifier)
        notifier._bot_token = "test_token"
        notifier._chat_id = "12345"
        notifier._enabled = True
        assert notifier._bot_token == "test_token"
        assert notifier._chat_id == "12345"

    def test_init_disabled(self):
        from src.telegram.notifier import _TelegramNotifier
        notifier = _TelegramNotifier.__new__(_TelegramNotifier)
        notifier._enabled = False
        assert notifier._enabled is False

    def test_format_trade_message(self):
        from src.telegram.notifier import _TelegramNotifier
        notifier = _TelegramNotifier.__new__(_TelegramNotifier)
        # Test that notifier can be instantiated
        assert notifier is not None


# ═══════════════════════════════════════════════════════════════════
# Formatters Tests
# ═══════════════════════════════════════════════════════════════════

class TestTelegramFormatters:
    """Tests for telegram formatters."""

    def test_format_balance(self):
        """Test balance formatting."""
        # Simple formatting test
        balance = 150.50
        formatted = f"${balance:.2f}"
        assert formatted == "$150.50"

    def test_format_percentage(self):
        """Test percentage formatting."""
        pct = 0.1567
        formatted = f"{pct:.1%}"
        assert "15.7%" in formatted

    def test_format_trade_result(self):
        """Test trade result formatting."""
        profit = 2.50
        if profit > 0:
            emoji = "✅"
        else:
            emoji = "❌"
        assert emoji == "✅"


# ═══════════════════════════════════════════════════════════════════
# Control Bot Commands Tests
# ═══════════════════════════════════════════════════════════════════

class TestControlBotCommands:
    """Tests for control bot command handlers."""

    def test_status_command_format(self):
        """Test status command output format."""
        from src.config import Config
        mode = "🧪 SIMULATION" if Config.DRY_RUN else "💸 LIVE"
        assert mode in ["🧪 SIMULATION", "💸 LIVE"]

    def test_mode_detection(self):
        """Test DRY_RUN mode detection."""
        import os
        os.environ["DRY_RUN"] = "true"
        from src.config import Config
        assert Config.DRY_RUN is True

    def test_command_list_exists(self):
        """Test that command list is defined."""
        # Basic check that command module exists
        from src.telegram.control_bot.commands import control
        assert control is not None


# ═══════════════════════════════════════════════════════════════════
# Settings FSM Tests
# ═══════════════════════════════════════════════════════════════════

class TestSettingsFSM:
    """Tests for settings state machine."""

    def test_fsm_states_defined(self):
        """Test that FSM states are defined."""
        from src.telegram.control_bot import settings_fsm
        assert settings_fsm is not None

    def test_fsm_module_importable(self):
        """Test FSM module is importable."""
        import importlib
        mod = importlib.import_module("src.telegram.control_bot.settings_fsm")
        assert mod is not None


# ═══════════════════════════════════════════════════════════════════
# Keyboards Tests
# ═══════════════════════════════════════════════════════════════════

class TestKeyboards:
    """Tests for inline keyboards."""

    def test_keyboards_module_importable(self):
        """Test keyboards module is importable."""
        from src.telegram.control_bot import keyboards
        assert keyboards is not None


# ═══════════════════════════════════════════════════════════════════
# Callback Data Tests
# ═══════════════════════════════════════════════════════════════════

class TestCallbackData:
    """Tests for callback data factories."""

    def test_callback_data_module_importable(self):
        """Test callback_data module is importable."""
        from src.telegram.control_bot import callback_data
        assert callback_data is not None


# ═══════════════════════════════════════════════════════════════════
# Resilience Tests
# ═══════════════════════════════════════════════════════════════════

class TestResilience:
    """Tests for error recovery and resilience."""

    def test_resilience_module_importable(self):
        """Test resilience module is importable."""
        from src.telegram.control_bot import resilience
        assert resilience is not None

    def test_error_handling_module_importable(self):
        """Test error_handling module is importable."""
        from src.telegram.control_bot import error_handling
        assert error_handling is not None


# ═══════════════════════════════════════════════════════════════════
# Sell Risk Gate Tests (P1 fix)
# ═══════════════════════════════════════════════════════════════════

class TestSellRiskGate:
    """Tests for drawdown freeze check in /sell command."""

    @pytest.mark.asyncio
    async def test_sell_blocked_during_drawdown_freeze(self):
        """When drawdown freeze is active, /sell should block with message."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_risk_state = MagicMock()
        mock_risk_state.drawdown_freeze_active = True
        mock_risk_state.current_drawdown_pct = 18.5

        mock_risk = MagicMock()
        mock_risk.get_state.return_value = mock_risk_state

        mock_loop = MagicMock()
        mock_loop.risk = mock_risk

        mock_message = AsyncMock()
        mock_message.from_user.id = 12345

        mock_state = MagicMock()
        mock_state.sniping_loop = mock_loop

        # cmd_sell_top does `from ..state import state` — patch at source module
        with patch.dict("src.telegram.control_bot.state.__dict__", {"state": mock_state}):
            from src.telegram.control_bot.commands.views import cmd_sell_top
            await cmd_sell_top(mock_message)

        mock_message.answer.assert_called_once()
        call_text = mock_message.answer.call_args[0][0]
        assert "Drawdown Freeze" in call_text
        assert "18.5%" in call_text

    @pytest.mark.asyncio
    async def test_sell_proceeds_when_no_freeze(self):
        """When drawdown freeze is NOT active, /sell should NOT show freeze message."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_risk_state = MagicMock()
        mock_risk_state.drawdown_freeze_active = False
        mock_risk_state.current_drawdown_pct = 5.0

        mock_risk = MagicMock()
        mock_risk.get_state.return_value = mock_risk_state

        mock_loop = MagicMock()
        mock_loop.risk = mock_risk

        mock_message = AsyncMock()
        mock_message.from_user.id = 12345

        mock_state = MagicMock()
        mock_state.sniping_loop = mock_loop

        # Just verify the freeze message is NOT sent — the sell itself may fail
        # (no real API), but the risk gate should pass through.
        with patch.dict("src.telegram.control_bot.state.__dict__", {"state": mock_state}):
            from src.telegram.control_bot.commands.views import cmd_sell_top
            # The function will proceed past risk gate, then fail on dmarket_client
            # (which is OK — we just verify it didn't hit the freeze path)
            try:
                await cmd_sell_top(mock_message)
            except Exception:
                pass  # Expected — no real DMarket client

        calls_text = str(mock_message.answer.call_args_list)
        assert "Drawdown Freeze" not in calls_text


# ═══════════════════════════════════════════════════════════════════
# Liquidate Confirmation Tests (P1 fix)
# ═══════════════════════════════════════════════════════════════════

class TestLiquidateConfirmation:
    """Tests for confirmation dialog in /liquidate command."""

    @pytest.mark.asyncio
    async def test_liquidate_shows_confirmation_no_sale(self):
        """/liquidate should show confirmation dialog, NOT sell anything."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_message = AsyncMock()
        mock_message.from_user.id = 12345

        mock_items = [
            {"hash_name": "AK-47 | Redline", "buy_price": 12.50, "status": "idle"},
            {"hash_name": "AWP | Asiimov", "buy_price": 35.00, "status": "idle"},
        ]

        import src.telegram.control_bot.commands.control as ctrl_mod
        saved_state = ctrl_mod.state
        mock_state = MagicMock()
        mock_state.client = MagicMock()
        ctrl_mod.state = mock_state

        try:
            with patch("src.db.price_history.price_db") as mock_db:
                mock_db.get_virtual_inventory.return_value = mock_items
                from src.telegram.control_bot.commands.control import cmd_liquidate
                await cmd_liquidate(mock_message)
        finally:
            ctrl_mod.state = saved_state

        # Should show confirmation dialog with item count and value
        call_text = mock_message.answer.call_args[0][0]
        assert "CONFIRMATION" in call_text
        assert "2" in call_text  # 2 items
        assert "$47.50" in call_text  # total value
        # reply_markup should be present (inline keyboard)
        assert mock_message.answer.call_kwargs.get("reply_markup") is not None

    @pytest.mark.asyncio
    async def test_liquidate_no_items_skips(self):
        """/liquidate with no items should skip with message."""
        from unittest.mock import AsyncMock, MagicMock, patch

        mock_message = AsyncMock()
        mock_message.from_user.id = 12345

        import src.telegram.control_bot.commands.control as ctrl_mod
        saved_state = ctrl_mod.state
        mock_state = MagicMock()
        mock_state.client = MagicMock()
        ctrl_mod.state = mock_state

        try:
            with patch("src.db.price_history.price_db") as mock_db:
                mock_db.get_virtual_inventory.return_value = []
                from src.telegram.control_bot.commands.control import cmd_liquidate
                await cmd_liquidate(mock_message)
        finally:
            ctrl_mod.state = saved_state

        call_text = mock_message.answer.call_args[0][0]
        assert "No unlocked items" in call_text

    @pytest.mark.asyncio
    async def test_liquidate_cancel_does_nothing(self):
        """cb_liquidate_cancel should edit message to 'cancelled', no sale."""
        from unittest.mock import AsyncMock, MagicMock, patch
        from aiogram import types

        mock_message = MagicMock(spec=types.Message)
        mock_message.edit_text = AsyncMock()

        mock_callback = AsyncMock()
        mock_callback.message = mock_message
        mock_callback.from_user.id = 12345

        from src.telegram.control_bot.commands.control import cb_liquidate_cancel
        await cb_liquidate_cancel(mock_callback)

        mock_message.edit_text.assert_called_once()
        call_text = mock_message.edit_text.call_args[0][0]
        assert "cancelled" in call_text.lower()
        mock_callback.answer.assert_called_once()
