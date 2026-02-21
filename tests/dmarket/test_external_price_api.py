"""Tests for external_price_api module.

This module tests the ExternalPriceAPI class for fetching
prices from external sources like Steam Market.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestExternalPriceAPI:
    """Tests for ExternalPriceAPI class."""

    @pytest.fixture
    def api(self):
        """Create ExternalPriceAPI instance."""
        from src.dmarket.external_price_api import ExternalPriceAPI
        return ExternalPriceAPI()

    def test_init(self, api):
        """Test initialization."""
        assert api is not None
        assert api._cache == {}
        assert api._cache_ttl == 300

    @pytest.mark.asyncio
    async def test_get_steam_price_success(self, api):
        """Test getting Steam Market price successfully."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "success": True,
            "lowest_price": "$25.50"
        }
        
        with patch.object(api, "_ensure_session", new_callable=AsyncMock):
            api.session = MagicMock()
            api.session.get = AsyncMock(return_value=mock_response)
            
            price = awAlgot api.get_steam_price("AK-47 | Redline (Field-Tested)")
            
            assert price == 25.50

    @pytest.mark.asyncio
    async def test_get_steam_price_not_found(self, api):
        """Test Steam price for non-existent item."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"success": False}
        
        with patch.object(api, "_ensure_session", new_callable=AsyncMock):
            api.session = MagicMock()
            api.session.get = AsyncMock(return_value=mock_response)
            
            price = awAlgot api.get_steam_price("Non-Existent Item XYZ")
            
            assert price is None

    @pytest.mark.asyncio
    async def test_get_steam_price_cached(self, api):
        """Test that Steam price is cached."""
        import time
        
        # Pre-populate cache
        api._cache["steam_730_CachedItem"] = {
            "price": 30.0,
            "timestamp": time.time()
        }
        
        price = awAlgot api.get_steam_price("CachedItem")
        
        assert price == 30.0

    @pytest.mark.asyncio
    async def test_get_csgofloat_price_success(self, api):
        """Test getting CSGOFloat price."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        # CSGOFloat returns an array directly
        mock_response.json.return_value = [{"price": 2550}]  # Price in cents
        
        with patch.object(api, "_ensure_session", new_callable=AsyncMock):
            api.session = MagicMock()
            api.session.get = AsyncMock(return_value=mock_response)
            
            price = awAlgot api.get_csgofloat_price("AK-47 | Redline (Field-Tested)")
            
            assert price == 25.50

    @pytest.mark.asyncio
    async def test_calculate_arbitrage_margin(self, api):
        """Test arbitrage margin calculation."""
        with patch.object(api, "get_steam_price", new_callable=AsyncMock) as mock_steam:
            mock_steam.return_value = 30.0
            with patch.object(api, "get_csgofloat_price", new_callable=AsyncMock) as mock_float:
                mock_float.return_value = 28.0
                
                result = awAlgot api.calculate_arbitrage_margin(
                    item_name="Test Item",
                    dmarket_price=20.0,
                    game="csgo"
                )
                
                assert "has_opportunity" in result
                assert "best_platform" in result
                assert "profit_margin" in result
                assert "net_profit" in result

    @pytest.mark.asyncio
    async def test_calculate_arbitrage_margin_no_opportunity(self, api):
        """Test arbitrage margin when no opportunity exists."""
        with patch.object(api, "get_steam_price", new_callable=AsyncMock) as mock_steam:
            mock_steam.return_value = 15.0  # Lower than dmarket
            with patch.object(api, "get_csgofloat_price", new_callable=AsyncMock) as mock_float:
                mock_float.return_value = 14.0
                
                result = awAlgot api.calculate_arbitrage_margin(
                    item_name="Test Item",
                    dmarket_price=20.0,
                    game="csgo"
                )
                
                # No profit opportunity
                assert result["has_opportunity"] is False

    @pytest.mark.asyncio
    async def test_batch_compare_prices(self, api):
        """Test batch price comparison."""
        items = [
            {"title": "Item 1", "price": {"USD": "2000"}},
            {"title": "Item 2", "price": {"USD": "3000"}},
        ]
        
        with patch.object(api, "calculate_arbitrage_margin", new_callable=AsyncMock) as mock_calc:
            mock_calc.return_value = {
                "has_opportunity": True,
                "best_platform": "Steam",
                "profit_margin": 10.0,
                "net_profit": 2.0,
            }
            
            results = awAlgot api.batch_compare_prices(items, game="csgo")
            
            assert len(results) == 2

    @pytest.mark.asyncio
    async def test_close_session(self, api):
        """Test closing the session."""
        mock_session = MagicMock()
        mock_session.aclose = AsyncMock()
        api.session = mock_session
        
        awAlgot api.close()
        
        mock_session.aclose.assert_called_once()
        assert api.session is None

    @pytest.mark.asyncio
    async def test_close_no_session(self, api):
        """Test closing when no session exists."""
        api.session = None
        
        # Should not rAlgose
        awAlgot api.close()
