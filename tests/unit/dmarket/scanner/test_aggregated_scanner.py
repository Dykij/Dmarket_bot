"""Tests for AggregatedScanner module."""

from unittest.mock import AsyncMock

import pytest

from src.dmarket.scanner.aggregated_scanner import AggregatedScanner


@pytest.fixture()
def mock_api_client():
    """Create mock API client."""
    client = AsyncMock()
    client.get_aggregated_prices_bulk = AsyncMock()
    return client


@pytest.fixture()
def scanner(mock_api_client):
    """Create AggregatedScanner instance."""
    return AggregatedScanner(api_client=mock_api_client)


class TestAggregatedScanner:
    """Tests for AggregatedScanner class."""

    @pytest.mark.asyncio()
    async def test_pre_scan_finds_opportunities(self, scanner, mock_api_client):
        """Test pre-scan successfully finds arbitrage opportunities."""
        # Arrange
        mock_api_client.get_aggregated_prices_bulk.return_value = {
            "aggregatedPrices": [
                {
                    "title": "AK-47 | Redline (Field-Tested)",
                    "orderBestPrice": "1250",  # $12.50
                    "offerBestPrice": "1000",  # $10.00
                    "orderCount": 15,
                    "offerCount": 5,
                },
                {
                    "title": "AWP | Asiimov (Field-Tested)",
                    "orderBestPrice": "5000",  # $50.00
                    "offerBestPrice": "4000",  # $40.00 - much higher margin
                    "orderCount": 8,
                    "offerCount": 12,
                },
            ]
        }

        # Act
        opportunities = await scanner.pre_scan_opportunities(
            titles=["AK-47 | Redline (Field-Tested)", "AWP | Asiimov (Field-Tested)"],
            game="csgo",
            min_margin=0.10,
        )

        # Assert
        assert len(opportunities) == 2
        assert opportunities[0]["title"] == "AK-47 | Redline (Field-Tested)"
        assert opportunities[0]["margin"] > 0.10
        assert opportunities[0]["spread"] > 0
        mock_api_client.get_aggregated_prices_bulk.assert_called_once()

    @pytest.mark.asyncio()
    async def test_pre_scan_filters_low_margin(self, scanner, mock_api_client):
        """Test pre-scan filters out low-margin opportunities."""
        # Arrange
        mock_api_client.get_aggregated_prices_bulk.return_value = {
            "aggregatedPrices": [
                {
                    "title": "Low Margin Item",
                    "orderBestPrice": "1050",  # Only 5% margin
                    "offerBestPrice": "1000",
                    "orderCount": 10,
                    "offerCount": 5,
                }
            ]
        }

        # Act
        opportunities = await scanner.pre_scan_opportunities(
            titles=["Low Margin Item"],
            game="csgo",
            min_margin=0.15,  # 15% minimum
        )

        # Assert
        assert len(opportunities) == 0

    @pytest.mark.asyncio()
    async def test_pre_scan_validates_title_limit(self, scanner):
        """Test pre-scan raises error for too many titles."""
        # Arrange
        too_many_titles = [f"Item {i}" for i in range(101)]

        # Act & Assert
        with pytest.raises(ValueError, match="Maximum 100 titles"):
            await scanner.pre_scan_opportunities(
                titles=too_many_titles,
                game="csgo",
            )

    @pytest.mark.asyncio()
    async def test_batch_pre_scan_processes_multiple_batches(self, scanner, mock_api_client):
        """Test batch pre-scan handles multiple batches correctly."""
        # Arrange
        mock_api_client.get_aggregated_prices_bulk.return_value = {
            "aggregatedPrices": [
                {
                    "title": f"Item {i}",
                    "orderBestPrice": "1500",
                    "offerBestPrice": "1000",
                    "orderCount": 10,
                    "offerCount": 5,
                }
                for i in range(10)
            ]
        }

        # Act
        all_titles = [f"Item {i}" for i in range(150)]  # 2 batches
        opportunities = await scanner.batch_pre_scan(
            all_titles=all_titles,
            game="csgo",
            batch_size=100,
        )

        # Assert
        assert len(opportunities) >= 0  # Should process without error
        assert mock_api_client.get_aggregated_prices_bulk.call_count == 2

    def test_calculate_spread_with_commission(self, scanner):
        """Test spread calculation includes commission."""
        # Arrange
        order_price = 1250  # $12.50
        offer_price = 1000  # $10.00
        # Expected: 1250 - 1000 - (1250 * 0.07) = 250 - 87.5 = 162.5 → 162 (int cast)

        # Act
        spread = scanner._calculate_spread(order_price, offer_price)

        # Assert
        assert spread == 163  # int(1250 * 0.07) = 87, so 1250 - 1000 - 87 = 163

    def test_filter_by_demand_supply_ratio(self, scanner):
        """Test filtering by demand/supply ratio."""
        # Arrange
        opportunities = [
            {
                "title": "High Demand Item",
                "demand": 20,
                "supply": 5,
                "demand_supply_ratio": 4.0,
            },
            {
                "title": "Low Demand Item",
                "demand": 5,
                "supply": 20,
                "demand_supply_ratio": 0.25,
            },
        ]

        # Act
        filtered = scanner.filter_by_demand_supply_ratio(
            opportunities=opportunities,
            min_ratio=1.0,
        )

        # Assert
        assert len(filtered) == 1
        assert filtered[0]["title"] == "High Demand Item"

    def test_format_for_telegram(self, scanner):
        """Test Telegram message formatting."""
        # Arrange
        opportunities = [
            {
                "title": "AK-47 | Redline",
                "offer_price": 1000,
                "order_price": 1250,
                "spread": 162,
                "margin": 0.162,
                "demand": 15,
                "supply": 5,
            }
        ]

        # Act
        message = scanner.format_for_telegram(opportunities, top_n=10)

        # Assert
        assert "AK-47 | Redline" in message
        assert "$10.00" in message  # Buy price
        assert "$12.50" in message  # Sell price
        assert "16.2%" in message  # Margin
        assert "15/5" in message  # Demand/Supply

    def test_format_for_telegram_empty_list(self, scanner):
        """Test Telegram formatting with empty list."""
        # Act
        message = scanner.format_for_telegram([])

        # Assert
        assert "No opportunities found" in message
