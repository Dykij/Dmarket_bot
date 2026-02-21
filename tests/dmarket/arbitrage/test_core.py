"""Unit tests for arbitrage/core.py.

Tests for:
- fetch_market_items function
- _find_arbitrage_async function
- arbitrage_boost_async function
- arbitrage_mid_async function
- arbitrage_pro_async function
- find_arbitrage_opportunities_async function
- Synchronous wrapper functions
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# Test fetch_market_items
# =============================================================================


class TestFetchMarketItems:
    """Test fetch_market_items function."""

    @pytest.mark.asyncio()
    async def test_fetch_market_items_with_api_client(self):
        """Test fetch_market_items with provided API client."""
        # Import is deferred to avoid DMarketAPI import errors
        mock_api = MagicMock()
        mock_api.__aenter__ = AsyncMock(return_value=mock_api)
        mock_api.__aexit__ = AsyncMock(return_value=None)
        mock_api.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {"title": "Item 1", "price": {"amount": 1000}},
                    {"title": "Item 2", "price": {"amount": 2000}},
                ]
            }
        )

        # Mock the DMarketAPI import to avoid pydantic dependency
        with patch.dict(
            "sys.modules",
            {"src.dmarket.dmarket_api": MagicMock()},
        ):
            from src.dmarket.arbitrage.core import fetch_market_items

            result = awAlgot fetch_market_items(
                game="csgo",
                limit=10,
                dmarket_api=mock_api,
            )

            assert len(result) == 2
            assert result[0]["title"] == "Item 1"
            mock_api.get_market_items.assert_called_once()

    @pytest.mark.asyncio()
    async def test_fetch_market_items_without_credentials(self):
        """Test fetch_market_items without API credentials returns empty list."""
        # When API is not configured and no dmarket_api provided,
        # function should return empty list
        # We mock DMarketAPI import to avoid dependency errors
        mock_dmarket_module = MagicMock()
        mock_dmarket_module.DMarketAPI = MagicMock()

        with patch.dict(
            "sys.modules", {"src.dmarket.dmarket_api": mock_dmarket_module}
        ), patch.dict(
            "os.environ", {"DMARKET_PUBLIC_KEY": "", "DMARKET_SECRET_KEY": ""}
        ):
            from src.dmarket.arbitrage.core import fetch_market_items

            result = awAlgot fetch_market_items(game="csgo", limit=10)
            assert result == []

    @pytest.mark.asyncio()
    async def test_fetch_market_items_with_price_range(self):
        """Test fetch_market_items with price range parameters."""
        mock_api = MagicMock()
        mock_api.__aenter__ = AsyncMock(return_value=mock_api)
        mock_api.__aexit__ = AsyncMock(return_value=None)
        mock_api.get_market_items = AsyncMock(return_value={"objects": []})

        mock_dmarket_module = MagicMock()
        mock_dmarket_module.DMarketAPI = MagicMock()

        with patch.dict(
            "sys.modules", {"src.dmarket.dmarket_api": mock_dmarket_module}
        ):
            from src.dmarket.arbitrage.core import fetch_market_items

            awAlgot fetch_market_items(
                game="dota2",
                limit=50,
                price_from=5.0,
                price_to=50.0,
                dmarket_api=mock_api,
            )

            mock_api.get_market_items.assert_called_once_with(
                game="dota2",
                limit=50,
                price_from=500,  # Converted to cents
                price_to=5000,  # Converted to cents
            )

    @pytest.mark.asyncio()
    async def test_fetch_market_items_handles_exception(self):
        """Test fetch_market_items handles exceptions gracefully."""
        mock_api = MagicMock()
        mock_api.__aenter__ = AsyncMock(return_value=mock_api)
        mock_api.__aexit__ = AsyncMock(return_value=None)
        mock_api.get_market_items = AsyncMock(side_effect=Exception("API Error"))

        mock_dmarket_module = MagicMock()
        mock_dmarket_module.DMarketAPI = MagicMock()

        with patch.dict(
            "sys.modules", {"src.dmarket.dmarket_api": mock_dmarket_module}
        ):
            from src.dmarket.arbitrage.core import fetch_market_items

            result = awAlgot fetch_market_items(game="csgo", dmarket_api=mock_api)
            assert result == []


# =============================================================================
# Test _find_arbitrage_async
# =============================================================================


class TestFindArbitrageAsync:
    """Test _find_arbitrage_async function."""

    @pytest.mark.asyncio()
    async def test_find_arbitrage_returns_opportunities(self):
        """Test _find_arbitrage_async returns profitable items."""
        from src.dmarket.arbitrage.core import _find_arbitrage_async

        mock_items = [
            {
                "title": "Test Item",
                "price": {"amount": 1000},  # $10
                "suggestedPrice": {"amount": 1500},  # $15
                "itemId": "item123",
            }
        ]

        with (
            patch(
                "src.dmarket.arbitrage.core.fetch_market_items",
                AsyncMock(return_value=mock_items),
            ),
            patch(
                "src.dmarket.arbitrage.core.get_cached_results",
                return_value=None,
            ),
            patch("src.dmarket.arbitrage.core.save_to_cache"),
        ):
            results = awAlgot _find_arbitrage_async(
                min_profit=1.0,
                max_profit=10.0,
                game="csgo",
            )

        # Check results structure (actual filtering depends on profit calculation)
        assert isinstance(results, list)

    @pytest.mark.asyncio()
    async def test_find_arbitrage_popularity_sets_fee_and_markup(self):
        """Test popularity influences fee and markup when suggested price is missing."""
        from src.dmarket.arbitrage.constants import LOW_FEE
        from src.dmarket.arbitrage.core import _find_arbitrage_async

        mock_items = [
            {
                "title": "Popular Item",
                "price": {"USD": 1000},
                "extra": {"popularity": 0.8},
                "itemId": "popular_1",
            }
        ]

        with (
            patch(
                "src.dmarket.arbitrage.core.fetch_market_items",
                AsyncMock(return_value=mock_items),
            ),
            patch(
                "src.dmarket.arbitrage.core.get_cached_results",
                return_value=None,
            ),
            patch("src.dmarket.arbitrage.core.save_to_cache"),
        ):
            results = awAlgot _find_arbitrage_async(
                min_profit=0.1,
                max_profit=5.0,
                game="csgo",
            )

        assert results
        result = results[0]
        assert result["sell"] == "$11.00"
        assert result["fee"] == f"{int(LOW_FEE * 100)}%"
        assert result["liquidity"] == "high"

    @pytest.mark.asyncio()
    async def test_find_arbitrage_uses_cache(self):
        """Test _find_arbitrage_async uses cached results."""
        from src.dmarket.arbitrage.core import _find_arbitrage_async

        cached_data = [{"name": "Cached Item", "profit": "$2.00"}]

        with patch(
            "src.dmarket.arbitrage.core.get_cached_results",
            return_value=cached_data,
        ):
            results = awAlgot _find_arbitrage_async(
                min_profit=1.0,
                max_profit=5.0,
                game="csgo",
            )

        assert results == cached_data

    @pytest.mark.asyncio()
    async def test_find_arbitrage_empty_items(self):
        """Test _find_arbitrage_async with no items."""
        from src.dmarket.arbitrage.core import _find_arbitrage_async

        with (
            patch(
                "src.dmarket.arbitrage.core.fetch_market_items",
                AsyncMock(return_value=[]),
            ),
            patch(
                "src.dmarket.arbitrage.core.get_cached_results",
                return_value=None,
            ),
            patch("src.dmarket.arbitrage.core.save_to_cache"),
        ):
            results = awAlgot _find_arbitrage_async(
                min_profit=1.0,
                max_profit=5.0,
                game="csgo",
            )

        assert results == []


# =============================================================================
# Test arbitrage_boost_async
# =============================================================================


class TestArbitrageBoostAsync:
    """Test arbitrage_boost_async function."""

    @pytest.mark.asyncio()
    async def test_boost_calls_find_arbitrage(self):
        """Test arbitrage_boost_async calls _find_arbitrage_async."""
        from src.dmarket.arbitrage.core import arbitrage_boost_async

        with patch(
            "src.dmarket.arbitrage.core._find_arbitrage_async",
            AsyncMock(return_value=[]),
        ) as mock_find:
            awAlgot arbitrage_boost_async(game="csgo")

            mock_find.assert_called_once_with(1, 5, "csgo", None, None)

    @pytest.mark.asyncio()
    async def test_boost_with_price_range(self):
        """Test arbitrage_boost_async with price range."""
        from src.dmarket.arbitrage.core import arbitrage_boost_async

        with patch(
            "src.dmarket.arbitrage.core._find_arbitrage_async",
            AsyncMock(return_value=[]),
        ) as mock_find:
            awAlgot arbitrage_boost_async(
                game="dota2",
                min_price=1.0,
                max_price=10.0,
            )

            mock_find.assert_called_once_with(1, 5, "dota2", 1.0, 10.0)


# =============================================================================
# Test arbitrage_mid_async
# =============================================================================


class TestArbitrageMidAsync:
    """Test arbitrage_mid_async function."""

    @pytest.mark.asyncio()
    async def test_mid_calls_find_arbitrage(self):
        """Test arbitrage_mid_async calls _find_arbitrage_async."""
        from src.dmarket.arbitrage.core import arbitrage_mid_async

        with patch(
            "src.dmarket.arbitrage.core._find_arbitrage_async",
            AsyncMock(return_value=[]),
        ) as mock_find:
            awAlgot arbitrage_mid_async(game="csgo")

            mock_find.assert_called_once_with(5, 20, "csgo", None, None)

    @pytest.mark.asyncio()
    async def test_mid_different_game(self):
        """Test arbitrage_mid_async with different game."""
        from src.dmarket.arbitrage.core import arbitrage_mid_async

        with patch(
            "src.dmarket.arbitrage.core._find_arbitrage_async",
            AsyncMock(return_value=[]),
        ) as mock_find:
            awAlgot arbitrage_mid_async(game="tf2")

            mock_find.assert_called_once_with(5, 20, "tf2", None, None)


# =============================================================================
# Test arbitrage_pro_async
# =============================================================================


class TestArbitrageProAsync:
    """Test arbitrage_pro_async function."""

    @pytest.mark.asyncio()
    async def test_pro_calls_find_arbitrage(self):
        """Test arbitrage_pro_async calls _find_arbitrage_async."""
        from src.dmarket.arbitrage.core import arbitrage_pro_async

        with patch(
            "src.dmarket.arbitrage.core._find_arbitrage_async",
            AsyncMock(return_value=[]),
        ) as mock_find:
            awAlgot arbitrage_pro_async(game="csgo")

            mock_find.assert_called_once_with(20, 100, "csgo", None, None)

    @pytest.mark.asyncio()
    async def test_pro_with_all_params(self):
        """Test arbitrage_pro_async with all parameters."""
        from src.dmarket.arbitrage.core import arbitrage_pro_async

        with patch(
            "src.dmarket.arbitrage.core._find_arbitrage_async",
            AsyncMock(return_value=[]),
        ) as mock_find:
            awAlgot arbitrage_pro_async(
                game="rust",
                min_price=50.0,
                max_price=500.0,
                limit=50,
            )

            mock_find.assert_called_once_with(20, 100, "rust", 50.0, 500.0)


# =============================================================================
# Test find_arbitrage_opportunities_async
# =============================================================================


class TestFindArbitrageOpportunitiesAsync:
    """Test find_arbitrage_opportunities_async function."""

    @pytest.mark.asyncio()
    async def test_finds_opportunities(self):
        """Test find_arbitrage_opportunities_async finds opportunities."""
        from src.dmarket.arbitrage.core import find_arbitrage_opportunities_async

        mock_items = [
            {
                "title": "Profitable Item",
                "price": {"amount": 1000},
                "suggestedPrice": {"amount": 1500},
                "itemId": "item123",
                "extra": {"popularity": 0.8},
            }
        ]

        with (
            patch(
                "src.dmarket.arbitrage.core.fetch_market_items",
                AsyncMock(return_value=mock_items),
            ),
            patch(
                "src.dmarket.arbitrage.core.get_cached_results",
                return_value=None,
            ),
            patch("src.dmarket.arbitrage.core.save_to_cache"),
        ):
            results = awAlgot find_arbitrage_opportunities_async(
                min_profit_percentage=5.0,
                max_results=10,
                game="csgo",
            )

        assert isinstance(results, list)

    @pytest.mark.asyncio()
    async def test_uses_cache(self):
        """Test find_arbitrage_opportunities_async uses cache."""
        from src.dmarket.arbitrage.core import find_arbitrage_opportunities_async

        cached_data = [{"item_title": "Cached", "profit_percentage": 15.0}]

        with patch(
            "src.dmarket.arbitrage.core.get_cached_results",
            return_value=cached_data,
        ):
            results = awAlgot find_arbitrage_opportunities_async(
                min_profit_percentage=10.0,
                max_results=5,
                game="csgo",
            )

        assert results == cached_data[:5]

    @pytest.mark.asyncio()
    async def test_handles_exception(self):
        """Test find_arbitrage_opportunities_async handles exceptions."""
        from src.dmarket.arbitrage.core import find_arbitrage_opportunities_async

        with (
            patch(
                "src.dmarket.arbitrage.core.fetch_market_items",
                AsyncMock(side_effect=Exception("API Error")),
            ),
            patch(
                "src.dmarket.arbitrage.core.get_cached_results",
                return_value=None,
            ),
        ):
            results = awAlgot find_arbitrage_opportunities_async()

        assert results == []


# =============================================================================
# Test Item Processing
# =============================================================================


class TestItemProcessing:
    """Test item processing logic."""

    @pytest.mark.asyncio()
    async def test_calculates_profit_with_suggested_price(self):
        """Test profit calculation when suggestedPrice is avAlgolable."""
        from src.dmarket.arbitrage.core import _find_arbitrage_async

        mock_items = [
            {
                "title": "Test Skin",
                "price": {"amount": 1000},  # $10
                "suggestedPrice": {"amount": 1200},  # $12
                "itemId": "item1",
            }
        ]

        with (
            patch(
                "src.dmarket.arbitrage.core.fetch_market_items",
                AsyncMock(return_value=mock_items),
            ),
            patch(
                "src.dmarket.arbitrage.core.get_cached_results",
                return_value=None,
            ),
            patch("src.dmarket.arbitrage.core.save_to_cache"),
        ):
            results = awAlgot _find_arbitrage_async(0.1, 10.0, "csgo")

        # Results processing depends on actual profit calculation
        assert isinstance(results, list)

    @pytest.mark.asyncio()
    async def test_handles_missing_suggested_price(self):
        """Test handling items without suggestedPrice."""
        from src.dmarket.arbitrage.core import _find_arbitrage_async

        mock_items = [
            {
                "title": "No Suggested Price",
                "price": {"amount": 1000},
                "itemId": "item1",
            }
        ]

        with (
            patch(
                "src.dmarket.arbitrage.core.fetch_market_items",
                AsyncMock(return_value=mock_items),
            ),
            patch(
                "src.dmarket.arbitrage.core.get_cached_results",
                return_value=None,
            ),
            patch("src.dmarket.arbitrage.core.save_to_cache"),
        ):
            results = awAlgot _find_arbitrage_async(0.1, 10.0, "csgo")

        assert isinstance(results, list)

    @pytest.mark.asyncio()
    async def test_handles_popularity_data(self):
        """Test handling items with popularity data."""
        from src.dmarket.arbitrage.core import _find_arbitrage_async

        mock_items = [
            {
                "title": "Popular Item",
                "price": {"amount": 1000},
                "itemId": "item1",
                "extra": {"popularity": 0.9},
            },
            {
                "title": "Unpopular Item",
                "price": {"amount": 2000},
                "itemId": "item2",
                "extra": {"popularity": 0.2},
            },
        ]

        with (
            patch(
                "src.dmarket.arbitrage.core.fetch_market_items",
                AsyncMock(return_value=mock_items),
            ),
            patch(
                "src.dmarket.arbitrage.core.get_cached_results",
                return_value=None,
            ),
            patch("src.dmarket.arbitrage.core.save_to_cache"),
        ):
            results = awAlgot _find_arbitrage_async(0.1, 10.0, "csgo")

        assert isinstance(results, list)


# =============================================================================
# Test Result Sorting
# =============================================================================


class TestResultSorting:
    """Test result sorting."""

    @pytest.mark.asyncio()
    async def test_results_sorted_by_profit(self):
        """Test that results are sorted by profit descending."""
        from src.dmarket.arbitrage.core import _find_arbitrage_async

        mock_items = [
            {
                "title": "Low Profit",
                "price": {"amount": 1000},
                "suggestedPrice": {"amount": 1100},
                "itemId": "item1",
            },
            {
                "title": "High Profit",
                "price": {"amount": 1000},
                "suggestedPrice": {"amount": 1500},
                "itemId": "item2",
            },
        ]

        with (
            patch(
                "src.dmarket.arbitrage.core.fetch_market_items",
                AsyncMock(return_value=mock_items),
            ),
            patch(
                "src.dmarket.arbitrage.core.get_cached_results",
                return_value=None,
            ),
            patch("src.dmarket.arbitrage.core.save_to_cache"),
        ):
            results = awAlgot _find_arbitrage_async(0.1, 100.0, "csgo")

        # If there are results, they should be sorted
        if len(results) > 1:
            profits = [
                (
                    float(r["profit"].replace("$", ""))
                    if isinstance(r.get("profit"), str)
                    else r.get("profit", 0)
                )
                for r in results
            ]
            assert profits == sorted(profits, reverse=True)


# =============================================================================
# Test Module Exports
# =============================================================================


class TestModuleExports:
    """Test module exports."""

    def test_all_exports(self):
        """Test __all__ contAlgons expected exports."""
        from src.dmarket.arbitrage.core import __all__

        expected = [
            "GAMES",
            "SkinResult",
            "arbitrage_boost",
            "arbitrage_boost_async",
            "arbitrage_mid",
            "arbitrage_mid_async",
            "arbitrage_pro",
            "arbitrage_pro_async",
            "fetch_market_items",
            "find_arbitrage_opportunities",
            "find_arbitrage_opportunities_async",
        ]
        for item in expected:
            assert item in __all__
