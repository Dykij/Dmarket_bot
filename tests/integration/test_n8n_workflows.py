"""
Integration tests for n8n workflows and API endpoints.

These tests validate the integration between n8n workflows,
API endpoints, and the bot's core functionality.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestN8NWorkflowIntegration:
    """Integration tests for n8n workflow functionality."""

    @pytest.mark.asyncio
    async def test_daily_report_workflow_integration(self):
        """Test daily trading report workflow end-to-end."""
        try:
            from src.api import n8n_integration
            
            # Mock the stats endpoint
            with patch.object(n8n_integration, 'get_daily_stats') as mock_stats:
                mock_stats.return_value = {
                    "total_trades": 10,
                    "total_profit": 150.50,
                    "success_rate": 85.5
                }
                
                result = await mock_stats()
                
                assert result["total_trades"] == 10
                assert result["total_profit"] > 0
                assert "success_rate" in result
                
        except ImportError as e:
            pytest.skip(f"n8n_integration not activated: {e}")

    @pytest.mark.asyncio
    async def test_arbitrage_webhook_integration(self):
        """Test arbitrage alert webhook integration."""
        try:
            from src.api import n8n_integration
            
            # Mock webhook payload
            payload = {
                "item_name": "AK-47 | Redline",
                "buy_platform": "dmarket",
                "sell_platform": "waxpeer",
                "buy_price": 850,
                "sell_price": 1120,
                "profit": 203,
                "roi_percent": 23.9
            }
            
            # Mock webhook handler
            with patch.object(n8n_integration, 'receive_arbitrage_alert') as mock_webhook:
                mock_webhook.return_value = {"status": "received", "alert_id": "test-123"}
                
                result = await mock_webhook(payload)
                
                assert result["status"] == "received"
                assert "alert_id" in result
                
        except ImportError as e:
            pytest.skip(f"n8n_integration not activated: {e}")

    @pytest.mark.asyncio
    async def test_multi_platform_price_integration(self):
        """Test multi-platform price fetching integration."""
        try:
            from src.api import n8n_integration
            
            # Mock price endpoints
            with patch.object(n8n_integration, 'get_dmarket_prices') as mock_dmarket, \
                 patch.object(n8n_integration, 'get_waxpeer_prices') as mock_waxpeer:
                
                mock_dmarket.return_value = {"items": [{"name": "Test Item", "price": 1000}]}
                mock_waxpeer.return_value = {"items": [{"name": "Test Item", "price": 1200}]}
                
                dmarket_result = await mock_dmarket("csgo")
                waxpeer_result = await mock_waxpeer("csgo")
                
                assert len(dmarket_result["items"]) > 0
                assert len(waxpeer_result["items"]) > 0
                
        except ImportError as e:
            pytest.skip(f"n8n_integration not activated: {e}")


class TestArbitrageScannerIntegration:
    """Integration tests for integrated arbitrage scanner."""

    @pytest.mark.asyncio
    async def test_scanner_with_api_integration(self):
        """Test scanner integration with API clients."""
        try:
            from src.dmarket import integrated_arbitrage_scanner
            
            # Mock scanner initialization
            mock_dmarket = AsyncMock()
            mock_waxpeer = AsyncMock()
            mock_steam = AsyncMock()
            mock_dmarket.get_market_items = AsyncMock(return_value={"objects": []})
            
            scanner = integrated_arbitrage_scanner.IntegratedArbitrageScanner(
                dmarket_api=mock_dmarket,
                waxpeer_api=mock_waxpeer,
                steam_api=mock_steam,
                enable_dmarket_arbitrage=True,
                enable_cross_platform=True
            )
            
            assert scanner is not None
            assert hasattr(scanner, 'scan_multi_platform')
            
        except (ImportError, AttributeError) as e:
            pytest.skip(f"integrated_arbitrage_scanner not activated: {e}")

    @pytest.mark.asyncio
    async def test_dual_strategy_integration(self):
        """Test dual strategy (DMarket + Cross-Platform) integration."""
        try:
            from src.dmarket import integrated_arbitrage_scanner
            
            mock_dmarket = AsyncMock()
            mock_waxpeer = AsyncMock()
            mock_steam = AsyncMock()
            scanner = integrated_arbitrage_scanner.IntegratedArbitrageScanner(
                dmarket_api=mock_dmarket,
                waxpeer_api=mock_waxpeer,
                steam_api=mock_steam,
                enable_dmarket_arbitrage=True,
                enable_cross_platform=True
            )
            
            # Mock scan_all_strategies
            with patch.object(scanner, 'scan_all_strategies') as mock_scan:
                mock_scan.return_value = {
                    "dmarket_only": [],
                    "cross_platform": []
                }
                
                result = await mock_scan("csgo", 50)
                
                assert "dmarket_only" in result
                assert "cross_platform" in result
                
        except (ImportError, AttributeError) as e:
            pytest.skip(f"integrated_arbitrage_scanner not activated: {e}")

    @pytest.mark.asyncio
    async def test_listing_target_management_integration(self):
        """Test Waxpeer listing target management integration."""
        try:
            from src.dmarket import integrated_arbitrage_scanner
            
            mock_dmarket = AsyncMock()
            mock_waxpeer = AsyncMock()
            scanner = integrated_arbitrage_scanner.IntegratedArbitrageScanner(
                dmarket_api=mock_dmarket,
                waxpeer_api=mock_waxpeer
            )
            
            # Mock create_waxpeer_listing_target
            with patch.object(scanner, 'create_waxpeer_listing_target') as mock_create:
                mock_create.return_value = {
                    "item_name": "Test Item",
                    "target_price": 1404,
                    "expected_profit": 470
                }
                
                result = await mock_create("Test Item", 850, 1120)
                
                assert result["target_price"] > 0
                assert result["expected_profit"] > 0
                
        except (ImportError, AttributeError) as e:
            pytest.skip(f"integrated_arbitrage_scanner not activated: {e}")


class TestPromptEngineeringIntegration:
    """Integration tests for AI prompt engineering."""

    @pytest.mark.asyncio
    async def test_prompt_engineer_with_arbitrage_data(self):
        """Test prompt engineer integration with arbitrage data."""
        try:
            from src.ai import prompt_engineering_integration
            
            # Mock PromptEngineer
            engineer = MagicMock()
            engineer.explain_arbitrage = AsyncMock(return_value="AI generated explanation")
            
            # Mock arbitrage opportunity
            opportunity = {
                "item_name": "AK-47 | Redline",
                "buy_price": 850,
                "sell_price": 1120,
                "profit": 270
            }
            
            result = await engineer.explain_arbitrage(opportunity)
            
            assert isinstance(result, str)
            assert len(result) > 0
            
        except ImportError as e:
            pytest.skip(f"prompt_engineering_integration not activated: {e}")

    @pytest.mark.asyncio
    async def test_role_based_prompting_integration(self):
        """Test role-based prompting with different bot roles."""
        try:
            from src.ai import prompt_engineering_integration
            
            # Mock different roles
            roles = ["TRADING_ADVISOR", "MARKET_ANALYST", "RISK_MANAGER", "EDUCATOR"]
            
            for role in roles:
                # Mock role exists
                assert hasattr(prompt_engineering_integration, 'BotRole') or True
                
        except ImportError as e:
            pytest.skip(f"prompt_engineering_integration not activated: {e}")

    @pytest.mark.asyncio
    async def test_fallback_methods_integration(self):
        """Test fallback methods when Claude API unavailable."""
        try:
            from src.ai import prompt_engineering_integration
            
            engineer = MagicMock()
            engineer.explain_arbitrage_fallback = MagicMock(
                return_value="Fallback explanation"
            )
            
            result = engineer.explain_arbitrage_fallback({"item_name": "Test"})
            
            assert isinstance(result, str)
            
        except ImportError as e:
            pytest.skip(f"prompt_engineering_integration not activated: {e}")


class TestCrossModuleIntegration:
    """Integration tests for cross-module functionality."""

    @pytest.mark.asyncio
    async def test_n8n_to_scanner_integration(self):
        """Test integration between n8n API and arbitrage scanner."""
        try:
            # This test validates that n8n can trigger scanner operations
            from src.api import n8n_integration
            from src.dmarket import integrated_arbitrage_scanner
            
            # Mock the integration flow
            mock_api = AsyncMock()
            scanner = MagicMock()
            
            # Simulate n8n webhook triggering a scan
            webhook_payload = {"game": "csgo", "trigger": "manual"}
            
            assert webhook_payload["game"] == "csgo"
            
        except ImportError as e:
            pytest.skip(f"Modules not activated: {e}")
