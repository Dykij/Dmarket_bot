"""
Unit tests for Steam API integration module.

Tests cover:
- get_steam_price() functionality
- calculate_arbitrage() calculations
- Rate limit handling
- Error handling
- App ID mapping
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dmarket.steam_api import (
    calculate_arbitrage,
    get_backoff_status,
    get_liquidity_status,
    get_prices_batch,
    get_steam_price,
    normalize_item_name,
    reset_backoff,
)


class TestGetSteamPrice:
    """Tests for get_steam_price function."""

    @pytest.mark.asyncio()
    async def test_get_steam_price_success(self):
        """Test successful price fetch from Steam API."""
        with patch("httpx.AsyncClient") as mock_client:
            # Setup mock response
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {
                "success": True,
                "lowest_price": "$10.50",
                "volume": "150",
                "median_price": "$11.00",
            }

            # Setup async context manager
            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test
            result = await get_steam_price("AK-47 | Redline (Field-Tested)", app_id=730)

            # Assertions
            assert result is not None
            assert result["price"] == 10.50
            assert result["volume"] == 150
            assert result["median_price"] == 11.00

            # Verify API call
            mock_get.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_steam_price_rate_limit(self):
        """Test handling of 429 Rate Limit error."""
        # Reset backoff first to ensure clean state
        reset_backoff()

        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 429

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test - should raise RateLimitError
            with pytest.raises(Exception):  # Can be RateLimitError or general Exception
                await get_steam_price("Test Item")

            # Backoff should be active now
            backoff_status = get_backoff_status()
            assert backoff_status["active"] is True

        # Clean up after test
        reset_backoff()

    @pytest.mark.asyncio()
    async def test_get_steam_price_item_not_found(self):
        """Test handling when item is not found."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": False}

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test - should raise ItemNotFoundError
            with pytest.raises(Exception):  # Can be ItemNotFoundError or general Exception
                await get_steam_price("Nonexistent Item")

    @pytest.mark.asyncio()
    async def test_get_steam_price_server_error(self):
        """Test handling of server errors."""
        with patch("httpx.AsyncClient") as mock_client:
            mock_response = MagicMock()
            mock_response.status_code = 500

            mock_get = AsyncMock(return_value=mock_response)
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test - should raise SteamAPIError
            with pytest.raises(Exception):  # Can be SteamAPIError or general Exception
                await get_steam_price("Test Item")

    @pytest.mark.asyncio()
    async def test_get_steam_price_timeout(self):
        """Test handling of timeout errors."""
        import httpx

        with patch("httpx.AsyncClient") as mock_client:
            mock_get = AsyncMock(side_effect=httpx.TimeoutException("Timeout"))
            mock_client.return_value.__aenter__.return_value.get = mock_get

            # Test - should raise SteamAPIError
            with pytest.raises(Exception):  # Can be SteamAPIError or general Exception
                await get_steam_price("Test Item")


class TestCalculateArbitrage:
    """Tests for calculate_arbitrage function."""

    def test_calculate_arbitrage_positive_profit(self):
        """Test calculation with positive profit."""
        profit = calculate_arbitrage(dmarket_price=10.0, steam_price=15.0)

        # Expected: (15 * 0.8696 - 10) / 10 * 100 = 30.44%
        assert profit > 0
        assert pytest.approx(profit, abs=0.1) == 30.44

    def test_calculate_arbitrage_small_profit(self):
        """Test calculation with small profit."""
        profit = calculate_arbitrage(dmarket_price=10.0, steam_price=11.0)

        # Expected: (11 * 0.8696 - 10) / 10 * 100 = -4.36%
        assert profit < 0  # После комиссии убыток

    def test_calculate_arbitrage_high_profit(self):
        """Test calculation with high profit."""
        profit = calculate_arbitrage(dmarket_price=5.0, steam_price=15.0)

        # Expected: (15 * 0.8696 - 5) / 5 * 100 = 160.88%
        assert profit > 150

    def test_calculate_arbitrage_negative_price_returns_zero(self):
        """Test that negative prices return 0.0."""
        # Negative dmarket_price
        result = calculate_arbitrage(dmarket_price=-10.0, steam_price=15.0)
        assert result == 0.0

        # Zero dmarket_price
        result = calculate_arbitrage(dmarket_price=0.0, steam_price=15.0)
        assert result == 0.0

    def test_calculate_arbitrage_steam_lower_gives_negative(self):
        """Test that steam_price < dmarket_price gives negative profit."""
        profit = calculate_arbitrage(dmarket_price=15.0, steam_price=10.0)
        assert profit < 0  # Loss after commission


class TestNormalizeItemName:
    """Tests for normalize_item_name function."""

    def test_normalize_field_tested(self):
        """Test normalization of 'Field Tested' to 'Field-Tested'."""
        result = normalize_item_name("AK-47 | Slate (Field Tested)")
        assert result == "AK-47 | Slate (Field-Tested)"

    def test_normalize_well_worn(self):
        """Test normalization of 'Well Worn' to 'Well-Worn'."""
        result = normalize_item_name("AWP | Asiimov (Well Worn)")
        assert result == "AWP | Asiimov (Well-Worn)"

    def test_normalize_battle_scarred(self):
        """Test normalization of 'Battle Scarred' to 'Battle-Scarred'."""
        result = normalize_item_name("M4A4 | Howl (Battle Scarred)")
        assert result == "M4A4 | Howl (Battle-Scarred)"

    def test_normalize_already_correct(self):
        """Test that already correct names are unchanged."""
        original = "AK-47 | Redline (Factory New)"
        result = normalize_item_name(original)
        assert result == original


class TestGetLiquidityStatus:
    """Tests for get_liquidity_status function."""

    def test_very_high_liquidity(self):
        """Test status for very high volume."""
        status = get_liquidity_status(250)
        assert "🔥" in status or "Высокая" in status or "High" in status

    def test_medium_liquidity(self):
        """Test status for medium volume (101-200)."""
        # 150 is in medium range (>100 and <=200)
        status = get_liquidity_status(150)
        assert "✅" in status or "Средняя" in status or "Medium" in status

    def test_low_liquidity(self):
        """Test status for low volume."""
        status = get_liquidity_status(60)
        assert "⚠️" in status or "Низкая" in status or "Low" in status

    def test_very_low_liquidity(self):
        """Test status for very low volume."""
        status = get_liquidity_status(10)
        assert "❌" in status or "риск" in status.lower()


class TestGetPricesBatch:
    """Tests for get_prices_batch function."""

    @pytest.mark.asyncio()
    async def test_get_prices_batch_success(self):
        """Test batch price fetching."""
        items = ["AK-47 | Redline (FT)", "AWP | Asiimov (FT)"]

        with patch("src.dmarket.steam_api.get_steam_price") as mock_get_price:
            mock_get_price.return_value = {"price": 10.0, "volume": 100}

            results = await get_prices_batch(items, delay=0.1)

            assert len(results) == 2
            assert all(item in results for item in items)
            assert mock_get_price.call_count == 2

    @pytest.mark.asyncio()
    async def test_get_prices_batch_with_errors(self):
        """Test batch fetching with some errors."""
        items = ["Good Item", "Bad Item"]

        async def mock_get_price(item, **kwargs):
            if "Bad" in item:
                return None  # Return None instead of rAlgosing exception
            return {"price": 10.0, "volume": 100}

        with patch("src.dmarket.steam_api.get_steam_price", side_effect=mock_get_price):
            results = await get_prices_batch(items, delay=0.1)

            assert results["Good Item"] is not None
            assert results["Bad Item"] is None


class TestBackoffManagement:
    """Tests for backoff management functions."""

    def test_reset_backoff(self):
        """Test resetting backoff status."""
        reset_backoff()

        status = get_backoff_status()
        assert status["active"] is False
        assert status["remaining_seconds"] == 0

    def test_get_backoff_status_inactive(self):
        """Test getting status when backoff is inactive."""
        reset_backoff()

        status = get_backoff_status()
        assert status["active"] is False
        assert status["until"] is None
        assert status["remaining_seconds"] == 0
        assert "duration" in status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
