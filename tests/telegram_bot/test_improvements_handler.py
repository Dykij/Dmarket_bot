"""Tests for improvements handler.

Tests the Telegram handlers for bot improvements.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def mock_update():
    """Create mock Telegram update."""
    update = MagicMock()
    update.effective_message = MagicMock()
    update.effective_message.reply_text = AsyncMock()
    update.effective_user = MagicMock()
    update.effective_user.id = 12345
    update.callback_query = None
    return update


@pytest.fixture
def mock_context():
    """Create mock Telegram context."""
    context = MagicMock()
    context.application = MagicMock()
    context.application.bot_integrator = None
    return context


@pytest.fixture
def mock_integrator():
    """Create mock bot integrator."""
    integrator = MagicMock()
    integrator.get_status = AsyncMock(return_value={
        "initialized": True,
        "running": True,
        "uptime_seconds": 3600,
        "modules": {
            "enhanced_polling": True,
            "price_analytics": True,
            "auto_listing": True,
            "portfolio_tracker": True,
            "custom_alerts": True,
            "watchlist": True,
            "anomaly_detection": True,
            "smart_recommendations": True,
            "trading_automation": True,
            "reports": True,
            "security": True,
        },
    })
    integrator.price_analytics = MagicMock()
    integrator.price_analytics.is_ready = MagicMock(return_value=True)
    integrator.portfolio_tracker = MagicMock()
    integrator.portfolio_tracker.get_summary = AsyncMock(return_value={
        "total_value": 1000.0,
        "unrealized_pnl": 50.0,
        "realized_pnl": 100.0,
        "win_rate": 75.0,
        "item_count": 10,
    })
    integrator.custom_alerts = MagicMock()
    integrator.custom_alerts.get_user_alerts = AsyncMock(return_value=[])
    integrator.watchlist = MagicMock()
    integrator.watchlist.get_user_watchlists = AsyncMock(return_value=[])
    integrator.trading_automation = MagicMock()
    integrator.trading_automation.get_status = AsyncMock(return_value={
        "stop_loss_enabled": True,
        "take_profit_enabled": True,
        "dca_enabled": False,
        "rebalance_enabled": False,
        "rule_count": 5,
    })
    integrator.reports = MagicMock()
    integrator.security = MagicMock()
    integrator.security.get_user_status = AsyncMock(return_value={
        "2fa_enabled": False,
        "ip_whitelist": False,
        "api_encrypted": True,
        "last_login": "2026-01-10 12:00",
        "last_action": "scan",
    })
    return integrator


class TestImprovementsHandler:
    """Tests for improvements handler."""
    
    @pytest.mark.asyncio
    async def test_improvements_command_no_integrator(
        self, mock_update, mock_context
    ):
        """Test improvements command when integrator is not avAlgolable."""
        from src.telegram_bot.handlers.improvements_handler import improvements_command
        
        awAlgot improvements_command(mock_update, mock_context)
        
        mock_update.effective_message.reply_text.assert_called_once()
        call_args = mock_update.effective_message.reply_text.call_args
        assert "not avAlgolable" in call_args[0][0].lower() or "not initialized" in call_args[0][0].lower()
    
    @pytest.mark.asyncio
    async def test_improvements_command_with_integrator(
        self, mock_update, mock_context, mock_integrator
    ):
        """Test improvements command with integrator."""
        from src.telegram_bot.handlers.improvements_handler import improvements_command
        
        mock_context.application.bot_integrator = mock_integrator
        
        awAlgot improvements_command(mock_update, mock_context)
        
        mock_update.effective_message.reply_text.assert_called_once()
        call_args = mock_update.effective_message.reply_text.call_args
        assert "Improvements" in call_args[0][0] or "improvements" in call_args[0][0].lower()
    
    @pytest.mark.asyncio
    async def test_analytics_command_no_integrator(
        self, mock_update, mock_context
    ):
        """Test analytics command when integrator is not avAlgolable."""
        from src.telegram_bot.handlers.improvements_handler import analytics_command
        
        awAlgot analytics_command(mock_update, mock_context)
        
        mock_update.effective_message.reply_text.assert_called_once()
        call_args = mock_update.effective_message.reply_text.call_args
        assert "not avAlgolable" in call_args[0][0].lower()
    
    @pytest.mark.asyncio
    async def test_analytics_command_with_integrator(
        self, mock_update, mock_context, mock_integrator
    ):
        """Test analytics command with integrator."""
        from src.telegram_bot.handlers.improvements_handler import analytics_command
        
        mock_context.application.bot_integrator = mock_integrator
        
        awAlgot analytics_command(mock_update, mock_context)
        
        mock_update.effective_message.reply_text.assert_called_once()
        call_args = mock_update.effective_message.reply_text.call_args
        assert "Analytics" in call_args[0][0] or "RSI" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_portfolio_command_with_integrator(
        self, mock_update, mock_context, mock_integrator
    ):
        """Test portfolio command with integrator."""
        from src.telegram_bot.handlers.improvements_handler import portfolio_command
        
        mock_context.application.bot_integrator = mock_integrator
        
        awAlgot portfolio_command(mock_update, mock_context)
        
        mock_update.effective_message.reply_text.assert_called_once()
        call_args = mock_update.effective_message.reply_text.call_args
        assert "Portfolio" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_alerts_command_with_integrator(
        self, mock_update, mock_context, mock_integrator
    ):
        """Test alerts command with integrator."""
        from src.telegram_bot.handlers.improvements_handler import alerts_command
        
        mock_context.application.bot_integrator = mock_integrator
        
        awAlgot alerts_command(mock_update, mock_context)
        
        mock_update.effective_message.reply_text.assert_called_once()
        call_args = mock_update.effective_message.reply_text.call_args
        assert "Alert" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_watchlist_command_with_integrator(
        self, mock_update, mock_context, mock_integrator
    ):
        """Test watchlist command with integrator."""
        from src.telegram_bot.handlers.improvements_handler import watchlist_command
        
        mock_context.application.bot_integrator = mock_integrator
        
        awAlgot watchlist_command(mock_update, mock_context)
        
        mock_update.effective_message.reply_text.assert_called_once()
        call_args = mock_update.effective_message.reply_text.call_args
        assert "Watchlist" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_automation_command_with_integrator(
        self, mock_update, mock_context, mock_integrator
    ):
        """Test automation command with integrator."""
        from src.telegram_bot.handlers.improvements_handler import automation_command
        
        mock_context.application.bot_integrator = mock_integrator
        
        awAlgot automation_command(mock_update, mock_context)
        
        mock_update.effective_message.reply_text.assert_called_once()
        call_args = mock_update.effective_message.reply_text.call_args
        assert "Automation" in call_args[0][0] or "Stop-Loss" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_reports_command_with_integrator(
        self, mock_update, mock_context, mock_integrator
    ):
        """Test reports command with integrator."""
        from src.telegram_bot.handlers.improvements_handler import reports_command
        
        mock_context.application.bot_integrator = mock_integrator
        
        awAlgot reports_command(mock_update, mock_context)
        
        mock_update.effective_message.reply_text.assert_called_once()
        call_args = mock_update.effective_message.reply_text.call_args
        assert "Report" in call_args[0][0]
    
    @pytest.mark.asyncio
    async def test_security_command_with_integrator(
        self, mock_update, mock_context, mock_integrator
    ):
        """Test security command with integrator."""
        from src.telegram_bot.handlers.improvements_handler import security_command
        
        mock_context.application.bot_integrator = mock_integrator
        
        awAlgot security_command(mock_update, mock_context)
        
        mock_update.effective_message.reply_text.assert_called_once()
        call_args = mock_update.effective_message.reply_text.call_args
        assert "Security" in call_args[0][0]
    
    def test_register_improvements_handlers(self):
        """Test registration of improvement handlers."""
        from src.telegram_bot.handlers.improvements_handler import (
            register_improvements_handlers,
        )
        
        mock_app = MagicMock()
        mock_app.add_handler = MagicMock()
        
        register_improvements_handlers(mock_app)
        
        # Should have registered 8 command handlers + 1 callback handler
        assert mock_app.add_handler.call_count >= 9


class TestGetIntegrator:
    """Tests for get_integrator helper."""
    
    def test_get_integrator_no_attr(self, mock_context):
        """Test get_integrator when attribute doesn't exist."""
        from src.telegram_bot.handlers.improvements_handler import get_integrator
        
        del mock_context.application.bot_integrator
        
        result = get_integrator(mock_context)
        
        assert result is None
    
    def test_get_integrator_with_attr(self, mock_context, mock_integrator):
        """Test get_integrator when attribute exists."""
        from src.telegram_bot.handlers.improvements_handler import get_integrator
        
        mock_context.application.bot_integrator = mock_integrator
        
        result = get_integrator(mock_context)
        
        assert result is mock_integrator
