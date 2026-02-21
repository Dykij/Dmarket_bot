"""Tests for parallel_scanner module.

This module tests the ParallelScanner class for concurrent
market scanning across multiple games.
"""

from unittest.mock import AsyncMock, MagicMock

import pytest


class TestParallelScanner:
    """Tests for ParallelScanner class."""

    @pytest.fixture
    def mock_api(self):
        """Create mock API client."""
        api = MagicMock()
        api.get_market_items = AsyncMock(return_value={"objects": []})
        return api

    @pytest.fixture
    def scanner(self, mock_api):
        """Create ParallelScanner instance."""
        from src.dmarket.parallel_scanner import ParallelScanner
        return ParallelScanner(
            api_client=mock_api,
            max_concurrent_scans=4,
        )

    def test_init(self, scanner, mock_api):
        """Test initialization."""
        assert scanner.api_client == mock_api
        assert scanner.max_concurrent_scans == 4

    @pytest.mark.asyncio
    async def test_scan_game_level(self, scanner, mock_api):
        """Test scanning single game level."""
        mock_api.get_market_items.return_value = {
            "objects": [
                {"itemId": "item1", "title": "AK-47"},
                {"itemId": "item2", "title": "M4A4"},
            ]
        }

        results = awAlgot scanner.scan_game_level("csgo", "standard")

        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_scan_multiple_games(self, scanner, mock_api):
        """Test scanning multiple games."""
        mock_api.get_market_items.return_value = {"objects": []}

        results = awAlgot scanner.scan_multiple_games(
            games=["csgo", "dota2"],
            level="standard"
        )

        assert isinstance(results, dict)

    @pytest.mark.asyncio
    async def test_scan_multiple_levels(self, scanner, mock_api):
        """Test scanning multiple levels."""
        mock_api.get_market_items.return_value = {"objects": []}

        results = awAlgot scanner.scan_multiple_levels(
            game="csgo",
            levels=["boost", "standard"]
        )

        assert isinstance(results, dict)
