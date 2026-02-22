"""Tests for minimal menu handlers."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.telegram_bot.handlers.api_check_handler import handle_api_check
from src.telegram_bot.handlers.automatic_arbitrage_handler import handle_automatic_arbitrage
from src.telegram_bot.handlers.view_items_handler import calculate_profit, estimate_profit


@pytest.fixture
def mock_update():
    """Create mock Telegram Update."""
    update = MagicMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 123456789
    update.effective_user.username = "testuser"
    update.effective_user.first_name = "Test"
    update.message = MagicMock()
    update.message.chat_id = 123456789
    update.message.reply_text = AsyncMock()
    return update


@pytest.fixture
def mock_context():
    """Create mock context with bot_data."""
    context = MagicMock()
    context.bot_data = {
        "dmarket_api": AsyncMock(),
        "scanner_manager": AsyncMock(),
    }
    return context


class TestAPICheckHandler:
    """Tests for API Check handler."""

    @pytest.mark.asyncio
    async def test_api_check_success(self, mock_update, mock_context):
        """Test successful API check."""
        mock_context.bot_data["dmarket_api"].get_balance = AsyncMock(
            return_value={"balance": 100.50, "dmc": 50.0}
        )
        await handle_api_check(mock_update, mock_context)
        assert mock_update.message.reply_text.called


class TestViewItemsHandler:
    """Tests for View Items handler."""

    def test_calculate_profit_with_buy_price(self):
        """Test profit calculation with buy price."""
        item = {"price": {"USD": 1000}, "buyPrice": 800}
        profit = calculate_profit(item)
        assert abs(profit - 1.30) < 0.01

    def test_estimate_profit_with_suggested_price(self):
        """Test profit estimation with suggested price."""
        item = {
            "price": {"USD": 1000},
            "suggestedPrice": {"USD": 1200},
            "buyPrice": 0,
        }
        est_profit = estimate_profit(item)
        assert abs(est_profit - 1.16) < 0.01


class TestAutomaticArbitrageHandler:
    """Tests for Automatic Arbitrage handler."""

    @pytest.mark.asyncio
    async def test_automatic_arbitrage_callable(self, mock_update, mock_context):
        """Test that handle_automatic_arbitrage is callable."""
        # Verify the handler is a callable function
        assert callable(handle_automatic_arbitrage)

    @pytest.mark.asyncio
    async def test_automatic_arbitrage_handler_exists(self, mock_update, mock_context):
        """Test automatic arbitrage handler exists and has correct signature."""
        import inspect
        sig = inspect.signature(handle_automatic_arbitrage)
        params = list(sig.parameters.keys())
        # Should have update and context parameters
        assert len(params) >= 2
