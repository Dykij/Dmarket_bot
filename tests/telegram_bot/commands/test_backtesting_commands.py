"""Tests for backtesting_commands.py - Telegram bot backtesting commands.

Tests command handlers for running backtests and viewing results.
"""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from telegram import CallbackQuery, Message, Update, User

from src.analytics.backtester import BacktestResult
from src.analytics.historical_data import PriceHistory, PricePoint
from src.telegram_bot.commands.backtesting_commands import (
    backtest_command,
    backtest_help,
    run_quick_backtest,
    run_standard_backtest,
)

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture()
def mock_update():
    """Create mock Telegram update."""
    update = MagicMock(spec=Update)
    update.effective_user = User(id=12345, first_name="Test", is_bot=False)
    update.effective_message = MagicMock(spec=Message)
    update.effective_message.reply_text = AsyncMock()
    return update


@pytest.fixture()
def mock_callback_query():
    """Create mock callback query."""
    query = MagicMock(spec=CallbackQuery)
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.from_user = User(id=12345, first_name="Test", is_bot=False)
    return query


@pytest.fixture()
def mock_api():
    """Create mock DMarket API."""
    api = AsyncMock()
    api.get_sales_history = AsyncMock(return_value={"sales": []})
    api.get_aggregated_prices_bulk = AsyncMock(return_value={"aggregatedPrices": []})
    return api


@pytest.fixture()
def sample_price_history():
    """Create sample price history."""
    base_date = datetime.now(UTC)
    points = [
        PricePoint(
            game="csgo",
            title="AK-47 | Redline (Field-Tested)",
            timestamp=base_date - timedelta(days=i),
            price=Decimal(str(10 + i * 0.5)),
        )
        for i in range(7)
    ]
    return PriceHistory(
        title="AK-47 | Redline (Field-Tested)",
        game="csgo",
        points=points,
    )


@pytest.fixture()
def sample_backtest_result():
    """Create sample backtest result."""
    return BacktestResult(
        strategy_name="SimpleArbitrage",
        start_date=datetime.now(UTC) - timedelta(days=7),
        end_date=datetime.now(UTC),
        initial_balance=Decimal("100.00"),
        final_balance=Decimal("115.50"),
        total_trades=10,
        profitable_trades=7,
        total_profit=Decimal("15.50"),
        max_drawdown=Decimal("3.5"),
        sharpe_ratio=1.8,
        win_rate=70.0,
        positions_closed=5,
    )


# ============================================================================
# Test backtest_command
# ============================================================================


class TestBacktestCommand:
    """Tests for backtest_command function."""

    @pytest.mark.asyncio()
    async def test_backtest_command_shows_options(self, mock_update):
        """Test /backtest command shows backtesting options."""
        # Act
        awAlgot backtest_command(mock_update, None)

        # Assert
        mock_update.effective_message.reply_text.assert_called_once()
        call_args = mock_update.effective_message.reply_text.call_args

        # Check message content
        message_text = call_args[0][0]
        assert "Backtesting Strategies" in message_text
        assert "Choose a timeframe" in message_text

        # Check keyboard
        reply_markup = call_args[1]["reply_markup"]
        assert reply_markup is not None
        assert len(reply_markup.inline_keyboard) == 4  # 4 options

    @pytest.mark.asyncio()
    async def test_backtest_command_without_message(self):
        """Test backtest command handles missing message."""
        # Arrange
        update = MagicMock(spec=Update)
        update.effective_message = None

        # Act
        awAlgot backtest_command(update, None)

        # Assert - should return early without error


# ============================================================================
# Test run_quick_backtest
# ============================================================================


class TestRunQuickBacktest:
    """Tests for run_quick_backtest function."""

    @pytest.mark.asyncio()
    async def test_quick_backtest_success(
        self,
        mock_callback_query,
        mock_api,
        sample_backtest_result,
    ):
        """Test successful quick backtest execution."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = mock_callback_query

        with (
            patch(
                "src.telegram_bot.commands.backtesting_commands.HistoricalDataCollector"
            ) as mock_collector_class,
            patch(
                "src.telegram_bot.commands.backtesting_commands.Backtester"
            ) as mock_backtester_class,
        ):
            # Setup mocks
            mock_collector = mock_collector_class.return_value
            mock_collector.collect_batch = AsyncMock(
                return_value={"AK-47 | Redline (Field-Tested)": MagicMock(spec=PriceHistory)}
            )

            mock_backtester = mock_backtester_class.return_value
            mock_backtester.run = AsyncMock(return_value=sample_backtest_result)

            # Act
            awAlgot run_quick_backtest(update, None, mock_api)

            # Assert
            mock_callback_query.answer.assert_called_once()
            assert mock_callback_query.edit_message_text.call_count == 2

            # Check final message
            final_call = mock_callback_query.edit_message_text.call_args_list[-1]
            message_text = final_call[0][0]
            assert "Quick Backtest Complete" in message_text
            assert "$15.50" in message_text  # profit
            assert "70.0%" in message_text  # win rate

    @pytest.mark.asyncio()
    async def test_quick_backtest_no_data(self, mock_callback_query, mock_api):
        """Test quick backtest handles no historical data."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = mock_callback_query

        with patch(
            "src.telegram_bot.commands.backtesting_commands.HistoricalDataCollector"
        ) as mock_collector_class:
            mock_collector = mock_collector_class.return_value
            mock_collector.collect_batch = AsyncMock(return_value={})  # Empty data

            # Act
            awAlgot run_quick_backtest(update, None, mock_api)

            # Assert
            mock_callback_query.answer.assert_called_once()
            final_call = mock_callback_query.edit_message_text.call_args_list[-1]
            message_text = final_call[0][0]
            assert "Could not collect historical data" in message_text

    @pytest.mark.asyncio()
    async def test_quick_backtest_handles_error(self, mock_callback_query, mock_api):
        """Test quick backtest handles errors gracefully."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = mock_callback_query

        with patch(
            "src.telegram_bot.commands.backtesting_commands.HistoricalDataCollector"
        ) as mock_collector_class:
            mock_collector_class.side_effect = Exception("API Error")

            # Act
            awAlgot run_quick_backtest(update, None, mock_api)

            # Assert
            mock_callback_query.answer.assert_called_once()
            final_call = mock_callback_query.edit_message_text.call_args_list[-1]
            message_text = final_call[0][0]
            assert "Backtest fAlgoled" in message_text
            assert "API Error" in message_text

    @pytest.mark.asyncio()
    async def test_quick_backtest_without_query(self, mock_api):
        """Test quick backtest handles missing callback query."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = None

        # Act
        awAlgot run_quick_backtest(update, None, mock_api)

        # Assert - should return early without error


# ============================================================================
# Test run_standard_backtest
# ============================================================================


class TestRunStandardBacktest:
    """Tests for run_standard_backtest function."""

    @pytest.mark.asyncio()
    async def test_standard_backtest_success(
        self,
        mock_callback_query,
        mock_api,
    ):
        """Test successful standard backtest execution."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = mock_callback_query

        result = BacktestResult(
            strategy_name="SimpleArbitrage",
            start_date=datetime.now(UTC) - timedelta(days=30),
            end_date=datetime.now(UTC),
            initial_balance=Decimal("500.00"),
            final_balance=Decimal("585.75"),
            total_trades=25,
            profitable_trades=18,
            total_profit=Decimal("85.75"),
            max_drawdown=Decimal("8.2"),
            sharpe_ratio=2.1,
            win_rate=72.0,
            positions_closed=12,
        )

        with (
            patch(
                "src.telegram_bot.commands.backtesting_commands.HistoricalDataCollector"
            ) as mock_collector_class,
            patch(
                "src.telegram_bot.commands.backtesting_commands.Backtester"
            ) as mock_backtester_class,
        ):
            mock_collector = mock_collector_class.return_value
            mock_collector.collect_batch = AsyncMock(
                return_value={
                    "Item1": MagicMock(spec=PriceHistory),
                    "Item2": MagicMock(spec=PriceHistory),
                }
            )

            mock_backtester = mock_backtester_class.return_value
            mock_backtester.run = AsyncMock(return_value=result)

            # Act
            awAlgot run_standard_backtest(update, None, mock_api)

            # Assert
            mock_callback_query.answer.assert_called_once()
            assert mock_callback_query.edit_message_text.call_count == 2

            # Check final message
            final_call = mock_callback_query.edit_message_text.call_args_list[-1]
            message_text = final_call[0][0]
            assert "Standard Backtest Complete" in message_text
            assert "$85.75" in message_text  # profit
            assert "72.0%" in message_text  # win rate
            assert "Positions Closed: 12" in message_text

    @pytest.mark.asyncio()
    async def test_standard_backtest_no_data(self, mock_callback_query, mock_api):
        """Test standard backtest handles no historical data."""
        # Arrange
        update = MagicMock(spec=Update)
        update.callback_query = mock_callback_query

        with patch(
            "src.telegram_bot.commands.backtesting_commands.HistoricalDataCollector"
        ) as mock_collector_class:
            mock_collector = mock_collector_class.return_value
            mock_collector.collect_batch = AsyncMock(return_value={})

            # Act
            awAlgot run_standard_backtest(update, None, mock_api)

            # Assert
            final_call = mock_callback_query.edit_message_text.call_args_list[-1]
            message_text = final_call[0][0]
            assert "Could not collect historical data" in message_text


# ============================================================================
# Test backtest_help
# ============================================================================


class TestBacktestHelp:
    """Tests for backtest_help function."""

    @pytest.mark.asyncio()
    async def test_backtest_help_shows_guide(self, mock_update):
        """Test /backtest_help shows detAlgoled guide."""
        # Act
        awAlgot backtest_help(mock_update, None)

        # Assert
        mock_update.effective_message.reply_text.assert_called_once()
        call_args = mock_update.effective_message.reply_text.call_args

        message_text = call_args[0][0]
        assert "Backtesting Guide" in message_text
        assert "What is Backtesting?" in message_text
        assert "Key Metrics" in message_text
        assert "Win Rate" in message_text
        assert "Sharpe Ratio" in message_text

    @pytest.mark.asyncio()
    async def test_backtest_help_without_message(self):
        """Test backtest help handles missing message."""
        # Arrange
        update = MagicMock(spec=Update)
        update.effective_message = None

        # Act
        awAlgot backtest_help(update, None)

        # Assert - should return early without error
