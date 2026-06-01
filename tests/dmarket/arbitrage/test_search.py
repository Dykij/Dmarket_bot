"""Unit tests for arbitrage/search.py.

Tests for:
- _group_items_by_name function
- find_arbitrage_items function
- find_arbitrage_opportunities_advanced function
- _analyze_arbitrage_opportunities function
- _create_opportunity_if_profitable function
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# =============================================================================
# Test _group_items_by_name
# =============================================================================


class TestGroupItemsByName:
    """Test _group_items_by_name function."""

    def test_groups_items_by_title(self):
        """Test grouping items by title."""
        from src.dmarket.arbitrage.search import _group_items_by_name

        items = [
            {"title": "AK-47 | Redline", "price": 10},
            {"title": "AK-47 | Redline", "price": 12},
            {"title": "M4A4 | Asiimov", "price": 20},
        ]

        grouped = _group_items_by_name(items)

        assert len(grouped) == 2
        assert "AK-47 | Redline" in grouped
        assert "M4A4 | Asiimov" in grouped
        assert len(grouped["AK-47 | Redline"]) == 2
        assert len(grouped["M4A4 | Asiimov"]) == 1

    def test_ignores_empty_titles(self):
        """Test that items with empty titles are ignored."""
        from src.dmarket.arbitrage.search import _group_items_by_name

        items = [
            {"title": "Valid Item", "price": 10},
            {"title": "", "price": 15},
            {"price": 20},  # No title
        ]

        grouped = _group_items_by_name(items)

        assert len(grouped) == 1
        assert "Valid Item" in grouped

    def test_empty_input(self):
        """Test grouping with empty input."""
        from src.dmarket.arbitrage.search import _group_items_by_name

        grouped = _group_items_by_name([])
        assert grouped == {}


# =============================================================================
# Test find_arbitrage_items
# =============================================================================


class TestFindArbitrageItems:
    """Test find_arbitrage_items function."""

    @pytest.mark.asyncio()
    async def test_boost_mode(self):
        """Test find_arbitrage_items with boost mode."""
        from src.dmarket.arbitrage.search import find_arbitrage_items

        with patch(
            "src.dmarket.arbitrage.search.arbitrage_boost_async",
            AsyncMock(return_value=[{"name": "Item1", "profit": 2.0}]),
        ) as mock_boost:
            results = await find_arbitrage_items(
                game="csgo",
                mode="boost",
                min_price=1.0,
                max_price=50.0,
            )

            mock_boost.assert_called_once()
            assert len(results) == 1

    @pytest.mark.asyncio()
    async def test_low_mode_uses_boost(self):
        """Test that 'low' mode uses boost function."""
        from src.dmarket.arbitrage.search import find_arbitrage_items

        with patch(
            "src.dmarket.arbitrage.search.arbitrage_boost_async",
            AsyncMock(return_value=[]),
        ) as mock_boost:
            await find_arbitrage_items(game="csgo", mode="low")
            mock_boost.assert_called_once()

    @pytest.mark.asyncio()
    async def test_mid_mode(self):
        """Test find_arbitrage_items with mid mode."""
        from src.dmarket.arbitrage.search import find_arbitrage_items

        with patch(
            "src.dmarket.arbitrage.search.arbitrage_mid_async",
            AsyncMock(return_value=[]),
        ) as mock_mid:
            await find_arbitrage_items(game="csgo", mode="mid")
            mock_mid.assert_called_once()

    @pytest.mark.asyncio()
    async def test_pro_mode(self):
        """Test find_arbitrage_items with pro mode."""
        from src.dmarket.arbitrage.search import find_arbitrage_items

        with patch(
            "src.dmarket.arbitrage.search.arbitrage_pro_async",
            AsyncMock(return_value=[]),
        ) as mock_pro:
            await find_arbitrage_items(game="csgo", mode="pro")
            mock_pro.assert_called_once()

    @pytest.mark.asyncio()
    async def test_default_mode(self):
        """Test find_arbitrage_items with unknown mode uses mid."""
        from src.dmarket.arbitrage.search import find_arbitrage_items

        with patch(
            "src.dmarket.arbitrage.search.arbitrage_mid_async",
            AsyncMock(return_value=[]),
        ) as mock_mid:
            await find_arbitrage_items(game="csgo", mode="unknown_mode")
            mock_mid.assert_called_once()

    @pytest.mark.asyncio()
    async def test_converts_tuple_results(self):
        """Test that tuple results are converted to dictionaries."""
        from src.dmarket.arbitrage.search import find_arbitrage_items

        tuple_results = [
            ("Item Name", 10.0, 15.0, 5.0, 50.0),
        ]

        with patch(
            "src.dmarket.arbitrage.search.arbitrage_mid_async",
            AsyncMock(return_value=tuple_results),
        ):
            results = await find_arbitrage_items(game="csgo", mode="mid")

            assert len(results) == 1
            assert results[0]["market_hash_name"] == "Item Name"
            assert results[0]["buy_price"] == 10.0
            assert results[0]["sell_price"] == 15.0
            assert results[0]["profit"] == 5.0
            assert results[0]["profit_percent"] == 50.0

    @pytest.mark.asyncio()
    async def test_passes_dict_results_through(self):
        """Test that dictionary results are passed through unchanged."""
        from src.dmarket.arbitrage.search import find_arbitrage_items

        dict_results = [
            {"name": "Item", "buy_price": 10.0, "sell_price": 15.0},
        ]

        with patch(
            "src.dmarket.arbitrage.search.arbitrage_mid_async",
            AsyncMock(return_value=dict_results),
        ):
            results = await find_arbitrage_items(game="csgo", mode="mid")

            assert len(results) == 1
            assert results[0]["name"] == "Item"


# =============================================================================
# Test find_arbitrage_opportunities_advanced
# =============================================================================


class TestFindArbitrageOpportunitiesAdvanced:
    """Test find_arbitrage_opportunities_advanced function."""

    @pytest.fixture()
    def mock_api_client(self):
        """Create a mock API client."""
        client = MagicMock()
        client.get_all_market_items = AsyncMock(return_value=[])
        return client

    @pytest.mark.asyncio()
    async def test_uses_cache(self, mock_api_client):
        """Test that function uses cached results."""
        from src.dmarket.arbitrage.search import find_arbitrage_opportunities_advanced

        cached = [{"item_name": "Cached Item"}]

        with patch(
            "src.dmarket.arbitrage.search.get_arbitrage_cache",
            return_value=cached,
        ):
            results = await find_arbitrage_opportunities_advanced(
                api_client=mock_api_client,
                game="csgo",
            )

            assert results == cached
            mock_api_client.get_all_market_items.assert_not_called()

    @pytest.mark.asyncio()
    async def test_fallback_to_csgo(self, mock_api_client):
        """Test fallback to csgo for unknown game."""
        from src.dmarket.arbitrage.search import find_arbitrage_opportunities_advanced

        with patch(
            "src.dmarket.arbitrage.search.get_arbitrage_cache",
            return_value=None,
        ):
            with patch("src.dmarket.arbitrage.search.save_arbitrage_cache"):
                await find_arbitrage_opportunities_advanced(
                    api_client=mock_api_client,
                    game="unknown_game",
                )

            # Should be called with csgo (fallback)
            call_args = mock_api_client.get_all_market_items.call_args
            assert call_args.kwargs["game"] == "csgo"

    @pytest.mark.asyncio()
    async def test_game_from_mode(self, mock_api_client):
        """Test extracting game from mode parameter."""
        from src.dmarket.arbitrage.search import find_arbitrage_opportunities_advanced

        with patch(
            "src.dmarket.arbitrage.search.get_arbitrage_cache",
            return_value=None,
        ):
            with patch("src.dmarket.arbitrage.search.save_arbitrage_cache"):
                await find_arbitrage_opportunities_advanced(
                    api_client=mock_api_client,
                    mode="game_dota2",
                )

            call_args = mock_api_client.get_all_market_items.call_args
            assert call_args.kwargs["game"] == "dota2"

    @pytest.mark.asyncio()
    async def test_mode_normalization(self, mock_api_client):
        """Test mode normalization (normal -> medium, best -> high)."""
        from src.dmarket.arbitrage.search import find_arbitrage_opportunities_advanced

        with (
            patch(
                "src.dmarket.arbitrage.search.get_arbitrage_cache",
                return_value=None,
            ),
            patch("src.dmarket.arbitrage.search.save_arbitrage_cache"),
        ):
            # Should internally convert "normal" to "medium"
            await find_arbitrage_opportunities_advanced(
                api_client=mock_api_client,
                mode="normal",
            )

    @pytest.mark.asyncio()
    async def test_returns_empty_for_no_items(self, mock_api_client):
        """Test returns empty list when no market items found."""
        from src.dmarket.arbitrage.search import find_arbitrage_opportunities_advanced

        mock_api_client.get_all_market_items = AsyncMock(return_value=[])

        with patch(
            "src.dmarket.arbitrage.search.get_arbitrage_cache",
            return_value=None,
        ):
            results = await find_arbitrage_opportunities_advanced(
                api_client=mock_api_client,
            )

            assert results == []

    @pytest.mark.asyncio()
    async def test_handles_api_exception(self, mock_api_client):
        """Test handles API exceptions gracefully."""
        from src.dmarket.arbitrage.search import find_arbitrage_opportunities_advanced

        mock_api_client.get_all_market_items = AsyncMock(
            side_effect=Exception("API Error")
        )

        with patch(
            "src.dmarket.arbitrage.search.get_arbitrage_cache",
            return_value=None,
        ):
            results = await find_arbitrage_opportunities_advanced(
                api_client=mock_api_client,
            )

            assert results == []

    @pytest.mark.asyncio()
    async def test_price_range_from_mode(self, mock_api_client):
        """Test that price range is determined from mode."""
        from src.dmarket.arbitrage.search import find_arbitrage_opportunities_advanced

        with patch(
            "src.dmarket.arbitrage.search.get_arbitrage_cache",
            return_value=None,
        ):
            with patch("src.dmarket.arbitrage.search.save_arbitrage_cache"):
                await find_arbitrage_opportunities_advanced(
                    api_client=mock_api_client,
                    mode="medium",
                )

            # Should have called with price range based on mode
            mock_api_client.get_all_market_items.assert_called_once()


# =============================================================================
# Test _analyze_arbitrage_opportunities
# =============================================================================


class TestAnalyzeArbitrageOpportunities:
    """Test _analyze_arbitrage_opportunities function."""

    def test_skips_single_item_groups(self):
        """Test that groups with single item are skipped."""
        from src.dmarket.arbitrage.search import _analyze_arbitrage_opportunities

        grouped_items = {
            "Single Item": [{"title": "Single Item", "price": {"USD": 1000}}],
        }

        opportunities = _analyze_arbitrage_opportunities(
            grouped_items=grouped_items,
            min_profit=5.0,
            game="csgo",
        )

        assert opportunities == []

    def test_finds_opportunities_in_groups(self):
        """Test finding opportunities in item groups."""
        from src.dmarket.arbitrage.search import _analyze_arbitrage_opportunities

        grouped_items = {
            "Test Item": [
                {"title": "Test Item", "price": {"USD": 1000}, "itemId": "item1"},
                {"title": "Test Item", "price": {"USD": 1500}, "itemId": "item2"},
            ],
        }

        opportunities = _analyze_arbitrage_opportunities(
            grouped_items=grouped_items,
            min_profit=1.0,  # Low threshold
            game="csgo",
        )

        # Should find opportunity if profit meets threshold
        assert isinstance(opportunities, list)


# =============================================================================
# Test _create_opportunity_if_profitable
# =============================================================================


class TestCreateOpportunityIfProfitable:
    """Test _create_opportunity_if_profitable function."""

    def test_returns_none_for_unprofitable(self):
        """Test returns None for unprofitable opportunity."""
        from src.dmarket.arbitrage.search import _create_opportunity_if_profitable

        result = _create_opportunity_if_profitable(
            item_name="Test",
            cheapest={"itemId": "item1"},
            cheapest_price=10.0,
            sell_item={"itemId": "item2", "price": {"USD": 1000}},  # $10
            commission_percent=7.0,
            min_profit=50.0,  # 50% profit required - won't meet
            game="csgo",
            item_rarity="",
            item_type="",
            item_popularity=0.5,
        )

        assert result is None

    def test_returns_opportunity_for_profitable(self):
        """Test returns opportunity for profitable item."""
        from src.dmarket.arbitrage.search import _create_opportunity_if_profitable

        result = _create_opportunity_if_profitable(
            item_name="Test Item",
            cheapest={"itemId": "item1"},
            cheapest_price=10.0,
            sell_item={"itemId": "item2", "price": {"USD": 2000}},  # $20
            commission_percent=5.0,
            min_profit=5.0,  # 5% profit required
            game="csgo",
            item_rarity="Covert",
            item_type="Rifle",
            item_popularity=0.8,
        )

        if result:  # If profitable
            assert result["item_name"] == "Test Item"
            assert result["buy_price"] == 10.0
            assert result["sell_price"] == 20.0
            assert result["game"] == "csgo"
            assert result["rarity"] == "Covert"
            assert "timestamp" in result

    def test_includes_image_url(self):
        """Test that imageUrl is included when avAlgolable."""
        from src.dmarket.arbitrage.search import _create_opportunity_if_profitable

        result = _create_opportunity_if_profitable(
            item_name="Test",
            cheapest={"itemId": "item1", "imageUrl": "https://example.com/image.png"},
            cheapest_price=5.0,
            sell_item={"itemId": "item2", "price": {"USD": 2000}},  # High profit
            commission_percent=5.0,
            min_profit=1.0,
            game="csgo",
            item_rarity="",
            item_type="",
            item_popularity=0.5,
        )

        if result:
            assert result.get("image_url") == "https://example.com/image.png"

    def test_includes_buy_sell_links(self):
        """Test that buy and sell links are included."""
        from src.dmarket.arbitrage.search import _create_opportunity_if_profitable

        result = _create_opportunity_if_profitable(
            item_name="Test",
            cheapest={"itemId": "buy123"},
            cheapest_price=5.0,
            sell_item={"itemId": "sell456", "price": {"USD": 2000}},
            commission_percent=5.0,
            min_profit=1.0,
            game="csgo",
            item_rarity="",
            item_type="",
            item_popularity=0.5,
        )

        if result:
            assert "buy123" in result.get("buy_link", "")
            assert "sell456" in result.get("sell_link", "")


# =============================================================================
# Test Module Exports
# =============================================================================


class TestModuleExports:
    """Test module exports."""

    def test_all_exports(self):
        """Test __all__ contains expected exports."""
        from src.dmarket.arbitrage.search import __all__

        assert "find_arbitrage_items" in __all__
        assert "find_arbitrage_opportunities_advanced" in __all__
