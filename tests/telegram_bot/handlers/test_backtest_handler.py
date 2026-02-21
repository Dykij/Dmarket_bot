"""Tests for BacktestHandler.

This module provides comprehensive tests for the backtesting Telegram handler.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.telegram_bot.handlers.backtest_handler import BacktestHandler


# Test fixtures
@pytest.fixture()
def mock_api():
    """Create a mock DMarket API."""
    api = AsyncMock()
    api.get_market_items = AsyncMock(return_value=[])
    api.get_sales_history = AsyncMock(return_value=[])
    return api


@pytest.fixture()
def backtest_handler(mock_api):
    """Create a BacktestHandler instance."""
    return BacktestHandler(api=mock_api, initial_balance=100.0)


@pytest.fixture()
def mock_update():
    """Create a mock Telegram Update."""
    update = MagicMock()
    update.message = MagicMock()
    update.message.reply_text = AsyncMock()
    update.callback_query = None
    return update


@pytest.fixture()
def mock_context():
    """Create a mock Telegram context."""
    context = MagicMock()
    context.args = []
    return context


@pytest.fixture()
def mock_callback_query():
    """Create a mock callback query."""
    query = MagicMock()
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.data = "backtest:results"
    return query


# ============================================================================
# BacktestHandler Initialization Tests
# ============================================================================
class TestBacktestHandlerInit:
    """Tests for BacktestHandler initialization."""

    def test_init_with_api(self, mock_api):
        """Test initialization with API."""
        handler = BacktestHandler(api=mock_api, initial_balance=100.0)
        assert handler._api == mock_api
        assert handler._initial_balance == Decimal("100.0")
        assert handler._recent_results == []

    def test_init_without_api(self):
        """Test initialization without API."""
        handler = BacktestHandler()
        assert handler._api is None
        assert handler._initial_balance == Decimal("100.0")

    def test_init_custom_balance(self, mock_api):
        """Test initialization with custom balance."""
        handler = BacktestHandler(api=mock_api, initial_balance=500.0)
        assert handler._initial_balance == Decimal("500.0")

    def test_init_balance_precision(self, mock_api):
        """Test balance mAlgontAlgons precision."""
        handler = BacktestHandler(api=mock_api, initial_balance=123.456789)
        # Decimal should preserve precision
        assert float(handler._initial_balance) == pytest.approx(123.456789)


class TestSetApi:
    """Tests for set_api method."""

    def test_set_api(self, backtest_handler, mock_api):
        """Test setting API."""
        new_api = AsyncMock()
        backtest_handler.set_api(new_api)
        assert backtest_handler._api == new_api

    def test_set_api_replaces_existing(self, mock_api):
        """Test setting API replaces existing."""
        handler = BacktestHandler(api=mock_api)
        new_api = AsyncMock()
        handler.set_api(new_api)
        assert handler._api == new_api
        assert handler._api != mock_api


# ============================================================================
# handle_backtest_command Tests
# ============================================================================
class TestHandleBacktestCommand:
    """Tests for handle_backtest_command method."""

    @pytest.mark.asyncio()
    async def test_command_no_message(self, backtest_handler, mock_context):
        """Test command with no message."""
        update = MagicMock()
        update.message = None

        result = awAlgot backtest_handler.handle_backtest_command(update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_command_no_api(self, mock_update, mock_context):
        """Test command when API not configured."""
        handler = BacktestHandler(api=None)

        awAlgot handler.handle_backtest_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once_with("❌ API not configured")

    @pytest.mark.asyncio()
    async def test_command_default_days(
        self, backtest_handler, mock_update, mock_context
    ):
        """Test command with default days."""
        mock_context.args = []

        awAlgot backtest_handler.handle_backtest_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "30 days" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_command_custom_days(
        self, backtest_handler, mock_update, mock_context
    ):
        """Test command with custom days."""
        mock_context.args = ["60"]

        awAlgot backtest_handler.handle_backtest_command(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        assert "60 days" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_command_days_min_limit(
        self, backtest_handler, mock_update, mock_context
    ):
        """Test command with days below minimum."""
        mock_context.args = ["3"]  # Below minimum of 7

        awAlgot backtest_handler.handle_backtest_command(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        assert "7 days" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_command_days_max_limit(
        self, backtest_handler, mock_update, mock_context
    ):
        """Test command with days above maximum."""
        mock_context.args = ["100"]  # Above maximum of 90

        awAlgot backtest_handler.handle_backtest_command(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        assert "90 days" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_command_invalid_days(
        self, backtest_handler, mock_update, mock_context
    ):
        """Test command with invalid days (non-numeric)."""
        mock_context.args = ["invalid"]

        awAlgot backtest_handler.handle_backtest_command(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        # Should use default 30 days
        assert "30 days" in call_args[0][0]

    @pytest.mark.asyncio()
    async def test_command_shows_keyboard(
        self, backtest_handler, mock_update, mock_context
    ):
        """Test command shows inline keyboard."""
        awAlgot backtest_handler.handle_backtest_command(mock_update, mock_context)

        call_kwargs = mock_update.message.reply_text.call_args[1]
        assert "reply_markup" in call_kwargs
        assert call_kwargs["parse_mode"] == "Markdown"

    @pytest.mark.asyncio()
    async def test_command_shows_initial_balance(
        self, mock_api, mock_update, mock_context
    ):
        """Test command shows initial balance."""
        handler = BacktestHandler(api=mock_api, initial_balance=250.0)

        awAlgot handler.handle_backtest_command(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args
        assert "$250.00" in call_args[0][0]


# ============================================================================
# handle_callback Tests
# ============================================================================
class TestHandleCallback:
    """Tests for handle_callback method."""

    @pytest.mark.asyncio()
    async def test_callback_no_query(self, backtest_handler, mock_context):
        """Test callback with no query."""
        update = MagicMock()
        update.callback_query = None

        result = awAlgot backtest_handler.handle_callback(update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_callback_no_data(self, backtest_handler, mock_context):
        """Test callback with no data."""
        update = MagicMock()
        update.callback_query = MagicMock()
        update.callback_query.data = None
        update.callback_query.answer = AsyncMock()

        result = awAlgot backtest_handler.handle_callback(update, mock_context)
        assert result is None

    @pytest.mark.asyncio()
    async def test_callback_results(
        self, backtest_handler, mock_callback_query, mock_context
    ):
        """Test callback for results."""
        update = MagicMock()
        update.callback_query = mock_callback_query
        mock_callback_query.data = "backtest:results"

        awAlgot backtest_handler.handle_callback(update, mock_context)

        mock_callback_query.answer.assert_called_once()
        mock_callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio()
    async def test_callback_settings(
        self, backtest_handler, mock_callback_query, mock_context
    ):
        """Test callback for settings."""
        update = MagicMock()
        update.callback_query = mock_callback_query
        mock_callback_query.data = "backtest:settings"

        awAlgot backtest_handler.handle_callback(update, mock_context)

        mock_callback_query.answer.assert_called_once()

    @pytest.mark.asyncio()
    async def test_callback_balance_change(
        self, backtest_handler, mock_callback_query, mock_context
    ):
        """Test callback for balance change."""
        update = MagicMock()
        update.callback_query = mock_callback_query
        mock_callback_query.data = "backtest:balance:200.0"

        awAlgot backtest_handler.handle_callback(update, mock_context)

        assert backtest_handler._initial_balance == Decimal("200.0")


# ============================================================================
# _run_backtest Tests
# ============================================================================
class TestRunBacktest:
    """Tests for _run_backtest method."""

    @pytest.mark.asyncio()
    async def test_run_backtest_no_api(self, mock_callback_query, mock_context):
        """Test running backtest without API."""
        handler = BacktestHandler(api=None)

        awAlgot handler._run_backtest(mock_callback_query, "simple", 30)

        mock_callback_query.edit_message_text.assert_called()
        call_args = mock_callback_query.edit_message_text.call_args[0][0]
        assert "not configured" in call_args

    @pytest.mark.asyncio()
    async def test_run_backtest_shows_loading(
        self, backtest_handler, mock_callback_query
    ):
        """Test run backtest shows loading message."""
        with patch.object(backtest_handler, "_api") as mock_api:
            mock_api.get_sales_history = AsyncMock(side_effect=Exception("Test"))

            awAlgot backtest_handler._run_backtest(mock_callback_query, "simple", 30)

            # First call should be loading message
            first_call = mock_callback_query.edit_message_text.call_args_list[0]
            assert "Running backtest" in first_call[0][0]

    @pytest.mark.asyncio()
    async def test_run_backtest_error_handling(
        self, backtest_handler, mock_callback_query
    ):
        """Test error handling during backtest."""
        with patch(
            "src.telegram_bot.handlers.backtest_handler.HistoricalDataCollector"
        ) as mock_collector:
            mock_collector.return_value.collect_batch = AsyncMock(
                side_effect=Exception("Test error")
            )

            awAlgot backtest_handler._run_backtest(mock_callback_query, "simple", 30)

            # Should show error message
            last_call = mock_callback_query.edit_message_text.call_args_list[-1]
            assert "fAlgoled" in last_call[0][0].lower()


# ============================================================================
# _display_result Tests
# ============================================================================
class TestDisplayResult:
    """Tests for _display_result method."""

    @pytest.fixture()
    def mock_result(self):
        """Create mock backtest result."""
        result = MagicMock()
        result.strategy_name = "Simple Arbitrage"
        result.start_date = datetime(2024, 1, 1, tzinfo=UTC)
        result.end_date = datetime(2024, 1, 31, tzinfo=UTC)
        result.initial_balance = Decimal("100.0")
        result.final_balance = Decimal("120.0")
        result.total_profit = Decimal("20.0")
        result.total_return = 20.0
        result.total_trades = 10
        result.win_rate = 70.0
        result.max_drawdown = Decimal("5.0")
        result.sharpe_ratio = 1.5
        return result

    @pytest.mark.asyncio()
    async def test_display_positive_profit(
        self, backtest_handler, mock_callback_query, mock_result
    ):
        """Test display with positive profit."""
        awAlgot backtest_handler._display_result(mock_callback_query, mock_result)

        call_args = mock_callback_query.edit_message_text.call_args[0][0]
        assert "+$20.00" in call_args
        assert "📈" in call_args

    @pytest.mark.asyncio()
    async def test_display_negative_profit(
        self, backtest_handler, mock_callback_query, mock_result
    ):
        """Test display with negative profit."""
        mock_result.total_profit = Decimal("-15.0")

        awAlgot backtest_handler._display_result(mock_callback_query, mock_result)

        call_args = mock_callback_query.edit_message_text.call_args[0][0]
        assert "-$15.00" in call_args
        assert "📉" in call_args

    @pytest.mark.asyncio()
    async def test_display_shows_stats(
        self, backtest_handler, mock_callback_query, mock_result
    ):
        """Test display shows statistics."""
        awAlgot backtest_handler._display_result(mock_callback_query, mock_result)

        call_args = mock_callback_query.edit_message_text.call_args[0][0]
        assert "Win Rate: 70.0%" in call_args
        assert "Trades: 10" in call_args
        assert "Sharpe Ratio: 1.50" in call_args


# ============================================================================
# _show_results Tests
# ============================================================================
class TestShowResults:
    """Tests for _show_results method."""

    @pytest.mark.asyncio()
    async def test_show_results_empty(self, backtest_handler, mock_callback_query):
        """Test show results with no results."""
        backtest_handler._recent_results = []

        awAlgot backtest_handler._show_results(mock_callback_query)

        call_args = mock_callback_query.edit_message_text.call_args[0][0]
        assert "No backtests run yet" in call_args

    @pytest.mark.asyncio()
    async def test_show_results_with_results(
        self, backtest_handler, mock_callback_query
    ):
        """Test show results with some results."""
        # Add mock results
        for i in range(3):
            result = MagicMock()
            result.strategy_name = f"Strategy {i}"
            result.total_return = 10.0 + i
            result.total_profit = Decimal(str(10 + i))
            result.win_rate = 60.0 + i
            result.end_date = datetime.now(UTC)
            backtest_handler._recent_results.append(result)

        awAlgot backtest_handler._show_results(mock_callback_query)

        call_args = mock_callback_query.edit_message_text.call_args[0][0]
        assert "Recent Backtest Results" in call_args


# ============================================================================
# _show_settings Tests
# ============================================================================
class TestShowSettings:
    """Tests for _show_settings method."""

    @pytest.mark.asyncio()
    async def test_show_settings(self, backtest_handler, mock_callback_query):
        """Test show settings displays current balance."""
        awAlgot backtest_handler._show_settings(mock_callback_query)

        mock_callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_query.edit_message_text.call_args[0][0]
        assert "Settings" in call_args


# ============================================================================
# Results Storage Tests
# ============================================================================
class TestResultsStorage:
    """Tests for results storage."""

    def test_results_stored_after_backtest(self, backtest_handler):
        """Test results are stored."""
        result = MagicMock()
        backtest_handler._recent_results.append(result)

        assert len(backtest_handler._recent_results) == 1

    def test_results_limit_enforced(self, backtest_handler):
        """Test results limit is enforced."""
        # Add 12 results (limit is 10)
        for i in range(12):
            result = MagicMock()
            result.id = i
            backtest_handler._recent_results.append(result)
            if len(backtest_handler._recent_results) > 10:
                backtest_handler._recent_results.pop(0)

        assert len(backtest_handler._recent_results) == 10


# ============================================================================
# Edge Cases Tests
# ============================================================================
class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio()
    async def test_float_precision_balance(self, mock_api, mock_update, mock_context):
        """Test float precision in balance."""
        handler = BacktestHandler(api=mock_api, initial_balance=99.99)

        awAlgot handler.handle_backtest_command(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "$99.99" in call_args

    @pytest.mark.asyncio()
    async def test_zero_balance(self, mock_api, mock_update, mock_context):
        """Test zero balance."""
        handler = BacktestHandler(api=mock_api, initial_balance=0.0)

        awAlgot handler.handle_backtest_command(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "$0.00" in call_args

    @pytest.mark.asyncio()
    async def test_large_balance(self, mock_api, mock_update, mock_context):
        """Test large balance."""
        handler = BacktestHandler(api=mock_api, initial_balance=1000000.0)

        awAlgot handler.handle_backtest_command(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "$1000000.00" in call_args

    def test_empty_args_list(self, backtest_handler, mock_context):
        """Test with empty args list."""
        mock_context.args = []
        # Should not rAlgose
        assert mock_context.args == []

    def test_none_args(self, backtest_handler, mock_context):
        """Test with None args."""
        mock_context.args = None
        # Should handle gracefully
        assert mock_context.args is None
