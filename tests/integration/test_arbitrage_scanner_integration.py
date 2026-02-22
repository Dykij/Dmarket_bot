"""Integration tests for ArbitrageScanner."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from src.dmarket.arbitrage_scanner import ArbitrageScanner

from src.dmarket.liquidity_analyzer import LiquidityAnalyzer

pytestmark = pytest.mark.asyncio


@pytest.fixture()
def mock_api_client():
    return MagicMock()


@pytest.fixture()
def mock_liquidity_analyzer():
    analyzer = MagicMock(spec=LiquidityAnalyzer)
    # Setup filter_liquid_items to return the items it receives (pass-through)
    # or a filtered list.
    analyzer.filter_liquid_items = AsyncMock()
    return analyzer


@pytest.fixture()
def scanner(mock_api_client, mock_liquidity_analyzer):
    scanner = ArbitrageScanner(api_client=mock_api_client, enable_liquidity_filter=True)
    scanner.liquidity_analyzer = mock_liquidity_analyzer
    return scanner


@pytest.mark.asyncio()
async def test_scan_game_with_liquidity_filter_enabled(
    scanner, mock_liquidity_analyzer
):
    """Test that scan_game calls liquidity_analyzer.filter_liquid_items when enabled."""

    # Mock items returned by the arbitrage functions
    mock_items = [
        {"title": "Item 1", "profit": 10.0, "price": {"amount": 1000}},
        {"title": "Item 2", "profit": 5.0, "price": {"amount": 500}},
        {"title": "Item 3", "profit": 2.0, "price": {"amount": 200}},
        {"title": "Item 4", "profit": 1.0, "price": {"amount": 100}},
    ]

    # Configure the analyzer to return a subset of items
    filtered_items = mock_items[:2]
    mock_liquidity_analyzer.filter_liquid_items.return_value = filtered_items

    # Patch the external functions used in scan_game
    with (
        patch("src.dmarket.arbitrage_scanner.arbitrage_mid_async", return_value=mock_items),
        patch("src.dmarket.arbitrage_scanner.ArbitrageTrader") as MockTrader,
    ):
        # Configure ArbitrageTrader mock to return empty list to avoid duplicates/complexity
        mock_trader_instance = MockTrader.return_value
        mock_trader_instance.find_profitable_items = AsyncMock(return_value=[])

        # Run scan_game
        results = await scanner.scan_game(game="csgo", mode="medium", max_items=10)

        # Verify results
        assert len(results) == 2
        assert results == filtered_items

        # Verify liquidity analyzer was called
        mock_liquidity_analyzer.filter_liquid_items.assert_called_once()

        # Verify the items passed to the analyzer were the ones found (sorted by profit)
        # Note: scan_game sorts items by profit descending before filtering
        # Our mock_items are already sorted by profit descending
        call_args = mock_liquidity_analyzer.filter_liquid_items.call_args
        assert len(call_args[0][0]) == 4
        assert call_args[0][0][0]["title"] == "Item 1"


@pytest.mark.asyncio()
async def test_scan_game_with_liquidity_filter_disabled(mock_api_client):
    """Test that scan_game skips liquidity analysis when disabled."""

    scanner = ArbitrageScanner(
        api_client=mock_api_client, enable_liquidity_filter=False
    )
    # Ensure analyzer is None
    scanner.liquidity_analyzer = None

    mock_items = [
        {"title": "Item 1", "profit": 10.0, "price": {"amount": 1000}},
        {"title": "Item 2", "profit": 5.0, "price": {"amount": 500}},
    ]

    with (
        patch("src.dmarket.arbitrage_scanner.arbitrage_mid_async", return_value=mock_items),
        patch("src.dmarket.arbitrage_scanner.ArbitrageTrader") as MockTrader,
    ):
        mock_trader_instance = MockTrader.return_value
        mock_trader_instance.find_profitable_items = AsyncMock(return_value=[])

        results = await scanner.scan_game(game="csgo", mode="medium", max_items=10)

        assert len(results) == 2
        assert results == mock_items

        # If we had a mock analyzer, we could assert it wasn't called,
        # but here we just check the result flow.


@pytest.mark.asyncio()
async def test_scan_game_filtering_logic(scanner, mock_liquidity_analyzer):
    """Test that scan_game correctly handles the filtering flow."""

    # Create items with mixed profits
    mock_items = [
        {"title": "High Profit", "profit": 100.0, "price": {"amount": 1000}},
        {"title": "Low Profit", "profit": 1.0, "price": {"amount": 100}},
        {"title": "Medium Profit", "profit": 50.0, "price": {"amount": 500}},
    ]

    # Expected sort order: High, Medium, Low
    sorted_items = [mock_items[0], mock_items[2], mock_items[1]]

    mock_liquidity_analyzer.filter_liquid_items.return_value = sorted_items

    with (
        patch("src.dmarket.arbitrage_scanner.arbitrage_mid_async", return_value=mock_items),
        patch("src.dmarket.arbitrage_scanner.ArbitrageTrader") as MockTrader,
    ):
        mock_trader_instance = MockTrader.return_value
        mock_trader_instance.find_profitable_items = AsyncMock(return_value=[])

        await scanner.scan_game(game="csgo", mode="medium", max_items=10)

        # Check that items passed to analyzer were sorted
        call_args = mock_liquidity_analyzer.filter_liquid_items.call_args
        passed_items = call_args[0][0]

        assert passed_items[0]["title"] == "High Profit"
        assert passed_items[1]["title"] == "Medium Profit"
        assert passed_items[2]["title"] == "Low Profit"
