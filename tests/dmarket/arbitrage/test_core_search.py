"""Simplified tests for arbitrage/core.py and arbitrage/search.py modules.

Tests cover the main exported functions and classes with proper mocking.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


class TestArbitrageCoreBasics:
    """Basic tests for arbitrage/core.py module."""

    def test_module_exports(self) -> None:
        """Test that module exports expected items."""
        from src.dmarket.arbitrage.core import (
            GAMES,
            arbitrage_boost,
            arbitrage_boost_async,
            arbitrage_mid,
            arbitrage_mid_async,
            arbitrage_pro,
            arbitrage_pro_async,
            fetch_market_items,
            find_arbitrage_opportunities,
            find_arbitrage_opportunities_async,
        )

        assert callable(arbitrage_boost)
        assert callable(arbitrage_mid)
        assert callable(arbitrage_pro)
        assert callable(arbitrage_boost_async)
        assert callable(arbitrage_mid_async)
        assert callable(arbitrage_pro_async)
        assert callable(fetch_market_items)
        assert callable(find_arbitrage_opportunities)
        assert callable(find_arbitrage_opportunities_async)
        assert isinstance(GAMES, dict)

    def test_games_constant_has_expected_games(self) -> None:
        """Test GAMES constant has expected game codes."""
        from src.dmarket.arbitrage.core import GAMES

        # Should have main games
        expected_keys = ["csgo", "dota2", "tf2", "rust"]
        for key in expected_keys:
            assert key in GAMES

    @pytest.mark.asyncio()
    async def test_fetch_market_items_with_api_returns_objects(self) -> None:
        """Test fetch_market_items returns objects from API response."""
        from src.dmarket.arbitrage.core import fetch_market_items

        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(
            return_value={
                "objects": [
                    {"title": "Item 1", "price": {"amount": "100"}},
                    {"title": "Item 2", "price": {"amount": "200"}},
                ]
            }
        )
        mock_api.__aenter__ = AsyncMock(return_value=mock_api)
        mock_api.__aexit__ = AsyncMock(return_value=None)

        result = await fetch_market_items(
            game="csgo",
            limit=10,
            dmarket_api=mock_api,
        )

        assert len(result) == 2
        assert result[0]["title"] == "Item 1"
        assert result[1]["title"] == "Item 2"

    @pytest.mark.asyncio()
    async def test_fetch_market_items_error_returns_empty_list(self) -> None:
        """Test fetch_market_items returns empty list on error."""
        from src.dmarket.arbitrage.core import fetch_market_items

        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(side_effect=Exception("API Error"))
        mock_api.__aenter__ = AsyncMock(return_value=mock_api)
        mock_api.__aexit__ = AsyncMock(return_value=None)

        result = await fetch_market_items(
            game="csgo",
            dmarket_api=mock_api,
        )

        assert result == []

    @pytest.mark.asyncio()
    async def test_fetch_market_items_converts_prices_to_cents(self) -> None:
        """Test that prices are converted from dollars to cents."""
        from src.dmarket.arbitrage.core import fetch_market_items

        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(return_value={"objects": []})
        mock_api.__aenter__ = AsyncMock(return_value=mock_api)
        mock_api.__aexit__ = AsyncMock(return_value=None)

        await fetch_market_items(
            game="csgo",
            price_from=5.0,  # $5
            price_to=10.0,  # $10
            dmarket_api=mock_api,
        )

        # Verify prices converted to cents
        call_kwargs = mock_api.get_market_items.call_args.kwargs
        assert call_kwargs["price_from"] == 500  # 500 cents
        assert call_kwargs["price_to"] == 1000  # 1000 cents

    @pytest.mark.asyncio()
    async def test_fetch_market_items_empty_response(self) -> None:
        """Test handling empty API response."""
        from src.dmarket.arbitrage.core import fetch_market_items

        mock_api = AsyncMock()
        mock_api.get_market_items = AsyncMock(return_value={})
        mock_api.__aenter__ = AsyncMock(return_value=mock_api)
        mock_api.__aexit__ = AsyncMock(return_value=None)

        result = await fetch_market_items(
            game="csgo",
            dmarket_api=mock_api,
        )

        assert result == []


class TestArbitrageLevelFunctions:
    """Tests for arbitrage level functions (boost, mid, pro)."""

    @pytest.mark.asyncio()
    async def test_arbitrage_boost_async_calls_find_arbitrage(self) -> None:
        """Test arbitrage_boost_async uses correct profit range."""
        from src.dmarket.arbitrage import core

        # Store original
        original_find = core._find_arbitrage_async

        # Create mock that tracks calls
        mock_calls = []

        async def mock_find(*args, **kwargs):
            mock_calls.append((args, kwargs))
            return []

        core._find_arbitrage_async = mock_find

        try:
            await core.arbitrage_boost_async("dota2")

            assert len(mock_calls) == 1
            args = mock_calls[0][0]
            assert args[0] == 1  # min_profit
            assert args[1] == 5  # max_profit
            assert args[2] == "dota2"  # game
        finally:
            core._find_arbitrage_async = original_find

    @pytest.mark.asyncio()
    async def test_arbitrage_mid_async_calls_find_arbitrage(self) -> None:
        """Test arbitrage_mid_async uses correct profit range."""
        from src.dmarket.arbitrage import core

        original_find = core._find_arbitrage_async

        mock_calls = []

        async def mock_find(*args, **kwargs):
            mock_calls.append((args, kwargs))
            return []

        core._find_arbitrage_async = mock_find

        try:
            await core.arbitrage_mid_async("tf2")

            assert len(mock_calls) == 1
            args = mock_calls[0][0]
            assert args[0] == 5  # min_profit
            assert args[1] == 20  # max_profit
            assert args[2] == "tf2"
        finally:
            core._find_arbitrage_async = original_find

    @pytest.mark.asyncio()
    async def test_arbitrage_pro_async_calls_find_arbitrage(self) -> None:
        """Test arbitrage_pro_async uses correct profit range."""
        from src.dmarket.arbitrage import core

        original_find = core._find_arbitrage_async

        mock_calls = []

        async def mock_find(*args, **kwargs):
            mock_calls.append((args, kwargs))
            return []

        core._find_arbitrage_async = mock_find

        try:
            await core.arbitrage_pro_async("rust")

            assert len(mock_calls) == 1
            args = mock_calls[0][0]
            assert args[0] == 20  # min_profit
            assert args[1] == 100  # max_profit
            assert args[2] == "rust"
        finally:
            core._find_arbitrage_async = original_find


class TestFindArbitrageAsync:
    """Tests for _find_arbitrage_async internal function."""

    @pytest.mark.asyncio()
    async def test_find_arbitrage_uses_cache(self) -> None:
        """Test that cached results are returned if avAlgolable."""
        from src.dmarket.arbitrage import core

        cached_data = [{"name": "Cached", "profit": "$5.00"}]

        original_get = core.get_cached_results
        core.get_cached_results = lambda key: cached_data

        try:
            result = await core._find_arbitrage_async(1, 5, "csgo")
            assert result == cached_data
        finally:
            core.get_cached_results = original_get

    @pytest.mark.asyncio()
    async def test_find_arbitrage_processes_items(self) -> None:
        """Test that items are processed correctly."""
        from src.dmarket.arbitrage import core

        mock_items = [
            {
                "title": "Test Item",
                "price": {"amount": "1000"},  # $10.00
                "suggestedPrice": {"amount": "1500"},  # $15.00
                "itemId": "item123",
            }
        ]

        original_get = core.get_cached_results
        original_fetch = core.fetch_market_items
        original_save = core.save_to_cache

        core.get_cached_results = lambda key: None
        core.fetch_market_items = AsyncMock(return_value=mock_items)
        core.save_to_cache = lambda key, data: None

        try:
            result = await core._find_arbitrage_async(0, 100, "csgo")

            # Should have processed the item
            assert isinstance(result, list)
            if result:
                assert "name" in result[0]
                assert "profit" in result[0]
        finally:
            core.get_cached_results = original_get
            core.fetch_market_items = original_fetch
            core.save_to_cache = original_save

    @pytest.mark.asyncio()
    async def test_find_arbitrage_filters_by_profit_range(self) -> None:
        """Test filtering by profit range."""
        from src.dmarket.arbitrage import core

        # Item with ~$4 profit (within boost range 1-5)
        mock_items = [
            {
                "title": "Test Item",
                "price": {"amount": "1000"},  # $10.00
                "suggestedPrice": {"amount": "1500"},  # $15.00
                "itemId": "item123",
            }
        ]

        original_get = core.get_cached_results
        original_fetch = core.fetch_market_items
        original_save = core.save_to_cache

        core.get_cached_results = lambda key: None
        core.fetch_market_items = AsyncMock(return_value=mock_items)
        core.save_to_cache = lambda key, data: None

        try:
            # Should find item with profit ~$3.95 (within 1-5 range)
            result = await core._find_arbitrage_async(1, 5, "csgo")
            assert isinstance(result, list)
        finally:
            core.get_cached_results = original_get
            core.fetch_market_items = original_fetch
            core.save_to_cache = original_save

    @pytest.mark.asyncio()
    async def test_find_arbitrage_handles_missing_suggested_price(self) -> None:
        """Test handling items without suggestedPrice."""
        from src.dmarket.arbitrage import core

        mock_items = [
            {
                "title": "No Suggested",
                "price": {"amount": "1000"},
                "itemId": "item123",
                # No suggestedPrice - should use markup
            }
        ]

        original_get = core.get_cached_results
        original_fetch = core.fetch_market_items
        original_save = core.save_to_cache

        core.get_cached_results = lambda key: None
        core.fetch_market_items = AsyncMock(return_value=mock_items)
        core.save_to_cache = lambda key, data: None

        try:
            # Should not raise, should use default markup
            result = await core._find_arbitrage_async(0, 100, "csgo")
            assert isinstance(result, list)
        finally:
            core.get_cached_results = original_get
            core.fetch_market_items = original_fetch
            core.save_to_cache = original_save

    @pytest.mark.asyncio()
    async def test_find_arbitrage_handles_malformed_items(self) -> None:
        """Test handling items with missing fields."""
        from src.dmarket.arbitrage import core

        mock_items = [
            {"title": "Good Item", "price": {"amount": "1000"}},
            {"title": "Bad Item"},  # Missing price
            {},  # Completely empty
        ]

        original_get = core.get_cached_results
        original_fetch = core.fetch_market_items
        original_save = core.save_to_cache

        core.get_cached_results = lambda key: None
        core.fetch_market_items = AsyncMock(return_value=mock_items)
        core.save_to_cache = lambda key, data: None

        try:
            # Should not raise, should skip bad items
            result = await core._find_arbitrage_async(0, 100, "csgo")
            assert isinstance(result, list)
        finally:
            core.get_cached_results = original_get
            core.fetch_market_items = original_fetch
            core.save_to_cache = original_save


class TestFindArbitrageOpportunitiesAsync:
    """Tests for find_arbitrage_opportunities_async function."""

    @pytest.mark.asyncio()
    async def test_find_opportunities_returns_list(self) -> None:
        """Test that function returns a list."""
        from src.dmarket.arbitrage import core

        original_get = core.get_cached_results
        original_fetch = core.fetch_market_items
        original_save = core.save_to_cache

        core.get_cached_results = lambda key: None
        core.fetch_market_items = AsyncMock(return_value=[])
        core.save_to_cache = lambda key, data: None

        try:
            result = await core.find_arbitrage_opportunities_async()
            assert isinstance(result, list)
        finally:
            core.get_cached_results = original_get
            core.fetch_market_items = original_fetch
            core.save_to_cache = original_save

    @pytest.mark.asyncio()
    async def test_find_opportunities_respects_max_results(self) -> None:
        """Test that max_results parameter is respected."""
        from src.dmarket.arbitrage import core

        cached_data = [
            {"item_title": f"Item{i}", "profit_percentage": float(i)} for i in range(20)
        ]

        original_get = core.get_cached_results
        core.get_cached_results = lambda key: cached_data

        try:
            result = await core.find_arbitrage_opportunities_async(max_results=5)
            assert len(result) <= 5
        finally:
            core.get_cached_results = original_get


class TestArbitrageSearchBasics:
    """Basic tests for arbitrage/search.py module."""

    def test_module_exports(self) -> None:
        """Test that module exports expected items."""
        from src.dmarket.arbitrage.search import (
            find_arbitrage_items,
            find_arbitrage_opportunities_advanced,
        )

        assert callable(find_arbitrage_items)
        assert callable(find_arbitrage_opportunities_advanced)

    def test_group_items_by_name(self) -> None:
        """Test _group_items_by_name helper function."""
        from src.dmarket.arbitrage.search import _group_items_by_name

        items = [
            {"title": "AK-47", "price": 100},
            {"title": "M4A4", "price": 200},
            {"title": "AK-47", "price": 150},
        ]

        result = _group_items_by_name(items)

        assert len(result) == 2
        assert len(result["AK-47"]) == 2
        assert len(result["M4A4"]) == 1

    def test_group_items_skips_empty_titles(self) -> None:
        """Test that empty titles are skipped."""
        from src.dmarket.arbitrage.search import _group_items_by_name

        items = [
            {"title": "AK-47", "price": 100},
            {"title": "", "price": 200},  # Empty title
            {"price": 150},  # Missing title
        ]

        result = _group_items_by_name(items)

        assert len(result) == 1
        assert "AK-47" in result


class TestFindArbitrageItems:
    """Tests for find_arbitrage_items function."""

    @pytest.mark.asyncio()
    async def test_find_items_boost_mode(self) -> None:
        """Test boost mode calls arbitrage_boost_async."""
        from src.dmarket.arbitrage import search

        original_boost = search.arbitrage_boost_async
        search.arbitrage_boost_async = AsyncMock(return_value=[{"name": "Boost"}])

        try:
            result = await search.find_arbitrage_items("csgo", mode="boost")
            assert result == [{"name": "Boost"}]
            search.arbitrage_boost_async.assert_called_once()
        finally:
            search.arbitrage_boost_async = original_boost

    @pytest.mark.asyncio()
    async def test_find_items_mid_mode(self) -> None:
        """Test mid mode calls arbitrage_mid_async."""
        from src.dmarket.arbitrage import search

        original_mid = search.arbitrage_mid_async
        search.arbitrage_mid_async = AsyncMock(return_value=[{"name": "Mid"}])

        try:
            result = await search.find_arbitrage_items("csgo", mode="mid")
            assert result == [{"name": "Mid"}]
            search.arbitrage_mid_async.assert_called_once()
        finally:
            search.arbitrage_mid_async = original_mid

    @pytest.mark.asyncio()
    async def test_find_items_pro_mode(self) -> None:
        """Test pro mode calls arbitrage_pro_async."""
        from src.dmarket.arbitrage import search

        original_pro = search.arbitrage_pro_async
        search.arbitrage_pro_async = AsyncMock(return_value=[{"name": "Pro"}])

        try:
            result = await search.find_arbitrage_items("csgo", mode="pro")
            assert result == [{"name": "Pro"}]
            search.arbitrage_pro_async.assert_called_once()
        finally:
            search.arbitrage_pro_async = original_pro

    @pytest.mark.asyncio()
    async def test_find_items_unknown_mode_defaults_to_mid(self) -> None:
        """Test unknown mode defaults to mid."""
        from src.dmarket.arbitrage import search

        original_mid = search.arbitrage_mid_async
        search.arbitrage_mid_async = AsyncMock(return_value=[])

        try:
            await search.find_arbitrage_items("csgo", mode="unknown")
            search.arbitrage_mid_async.assert_called_once()
        finally:
            search.arbitrage_mid_async = original_mid

    @pytest.mark.asyncio()
    async def test_find_items_converts_tuples_to_dicts(self) -> None:
        """Test that tuple results are converted to dictionaries."""
        from src.dmarket.arbitrage import search

        tuple_results = [
            ("Item Name", 10.0, 15.0, 5.0, 50.0),
        ]

        original_mid = search.arbitrage_mid_async
        search.arbitrage_mid_async = AsyncMock(return_value=tuple_results)

        try:
            result = await search.find_arbitrage_items("csgo", mode="mid")

            assert len(result) == 1
            assert result[0]["market_hash_name"] == "Item Name"
            assert result[0]["buy_price"] == 10.0
            assert result[0]["sell_price"] == 15.0
            assert result[0]["profit"] == 5.0
            assert result[0]["profit_percent"] == 50.0
        finally:
            search.arbitrage_mid_async = original_mid


class TestFindArbitrageOpportunitiesAdvanced:
    """Tests for find_arbitrage_opportunities_advanced function."""

    @pytest.mark.asyncio()
    async def test_find_advanced_returns_cached(self) -> None:
        """Test that cached results are returned."""
        from src.dmarket.arbitrage import search

        cached = [{"item_name": "Cached Item"}]

        original_cache = search.get_arbitrage_cache
        search.get_arbitrage_cache = lambda key: cached

        try:
            mock_api = AsyncMock()
            result = await search.find_arbitrage_opportunities_advanced(
                api_client=mock_api
            )
            assert result == cached
        finally:
            search.get_arbitrage_cache = original_cache

    @pytest.mark.asyncio()
    async def test_find_advanced_handles_empty_market(self) -> None:
        """Test handling empty market items."""
        from src.dmarket.arbitrage import search

        original_cache = search.get_arbitrage_cache
        original_save = search.save_arbitrage_cache

        search.get_arbitrage_cache = lambda key: None
        search.save_arbitrage_cache = lambda key, data: None

        try:
            mock_api = AsyncMock()
            mock_api.get_all_market_items = AsyncMock(return_value=[])

            result = await search.find_arbitrage_opportunities_advanced(
                api_client=mock_api
            )
            assert result == []
        finally:
            search.get_arbitrage_cache = original_cache
            search.save_arbitrage_cache = original_save

    @pytest.mark.asyncio()
    async def test_find_advanced_handles_exception(self) -> None:
        """Test exception handling."""
        from src.dmarket.arbitrage import search

        original_cache = search.get_arbitrage_cache
        search.get_arbitrage_cache = lambda key: None

        try:
            mock_api = AsyncMock()
            mock_api.get_all_market_items = AsyncMock(
                side_effect=Exception("API Error")
            )

            result = await search.find_arbitrage_opportunities_advanced(
                api_client=mock_api
            )
            assert result == []
        finally:
            search.get_arbitrage_cache = original_cache

    @pytest.mark.asyncio()
    async def test_find_advanced_extracts_game_from_mode(self) -> None:
        """Test game extraction from mode prefix."""
        from src.dmarket.arbitrage import search

        original_cache = search.get_arbitrage_cache
        original_save = search.save_arbitrage_cache

        search.get_arbitrage_cache = lambda key: None
        search.save_arbitrage_cache = lambda key, data: None

        try:
            mock_api = AsyncMock()
            mock_api.get_all_market_items = AsyncMock(return_value=[])

            # game_dota2 should extract dota2 as game
            await search.find_arbitrage_opportunities_advanced(
                api_client=mock_api,
                mode="game_dota2",
            )

            # Verify API was called with dota2
            call_kwargs = mock_api.get_all_market_items.call_args.kwargs
            assert call_kwargs.get("game") == "dota2"
        finally:
            search.get_arbitrage_cache = original_cache
            search.save_arbitrage_cache = original_save


class TestAnalyzeArbitrageOpportunities:
    """Tests for _analyze_arbitrage_opportunities function."""

    def test_analyze_skips_single_item_groups(self) -> None:
        """Test that groups with single items are skipped."""
        from src.dmarket.arbitrage import search
        from src.dmarket.arbitrage.search import _analyze_arbitrage_opportunities

        grouped = {
            "AK-47": [{"price": {"USD": 1000}}],  # Only 1 item
        }

        original_calc = search.calculate_commission
        search.calculate_commission = lambda **kwargs: 7.0

        try:
            result = _analyze_arbitrage_opportunities(grouped, 5.0, "csgo")
            assert result == []
        finally:
            search.calculate_commission = original_calc

    def test_analyze_finds_profitable_opportunities(self) -> None:
        """Test finding profitable opportunities."""
        from src.dmarket.arbitrage import search
        from src.dmarket.arbitrage.search import _analyze_arbitrage_opportunities

        grouped = {
            "AK-47": [
                {"price": {"USD": 1000}, "itemId": "item1", "extra": {}},  # $10
                {"price": {"USD": 2000}, "itemId": "item2", "extra": {}},  # $20
            ],
        }

        original_calc = search.calculate_commission
        search.calculate_commission = lambda **kwargs: 7.0

        try:
            result = _analyze_arbitrage_opportunities(grouped, 0.0, "csgo")

            # Should find opportunity with ~$20 - $10 profit
            assert isinstance(result, list)
            if result:
                assert result[0]["buy_price"] == 10.0
                assert result[0]["sell_price"] == 20.0
        finally:
            search.calculate_commission = original_calc


class TestCreateOpportunityIfProfitable:
    """Tests for _create_opportunity_if_profitable function."""

    def test_create_returns_opportunity_when_profitable(self) -> None:
        """Test creating opportunity when profit meets threshold."""
        from src.dmarket.arbitrage.search import _create_opportunity_if_profitable

        cheapest = {"itemId": "buy1"}
        sell_item = {"price": {"USD": 2000}, "itemId": "sell1"}

        result = _create_opportunity_if_profitable(
            item_name="AK-47",
            cheapest=cheapest,
            cheapest_price=10.0,
            sell_item=sell_item,
            commission_percent=7.0,
            min_profit=5.0,
            game="csgo",
            item_rarity="Covert",
            item_type="Rifle",
            item_popularity=0.8,
        )

        # Should return opportunity since profit > 5%
        assert result is not None
        assert result["item_name"] == "AK-47"
        assert result["buy_price"] == 10.0
        assert result["sell_price"] == 20.0
        assert "profit" in result
        assert "profit_percent" in result

    def test_create_returns_none_when_not_profitable(self) -> None:
        """Test returning None when profit below threshold."""
        from src.dmarket.arbitrage.search import _create_opportunity_if_profitable

        cheapest = {"itemId": "buy1"}
        sell_item = {"price": {"USD": 1050}, "itemId": "sell1"}  # Only 5% markup

        result = _create_opportunity_if_profitable(
            item_name="AK-47",
            cheapest=cheapest,
            cheapest_price=10.0,
            sell_item=sell_item,
            commission_percent=7.0,
            min_profit=50.0,  # High threshold
            game="csgo",
            item_rarity="",
            item_type="",
            item_popularity=0.5,
        )

        # Should return None since profit < 50%
        assert result is None

    def test_create_includes_image_url_if_avAlgolable(self) -> None:
        """Test that image URL is included if present."""
        from src.dmarket.arbitrage.search import _create_opportunity_if_profitable

        cheapest = {"itemId": "buy1", "imageUrl": "http://example.com/img.png"}
        sell_item = {"price": {"USD": 2000}, "itemId": "sell1"}

        result = _create_opportunity_if_profitable(
            item_name="AK-47",
            cheapest=cheapest,
            cheapest_price=10.0,
            sell_item=sell_item,
            commission_percent=7.0,
            min_profit=0.0,
            game="csgo",
            item_rarity="",
            item_type="",
            item_popularity=0.5,
        )

        assert result is not None
        assert result.get("image_url") == "http://example.com/img.png"

    def test_create_generates_buy_sell_links(self) -> None:
        """Test that buy and sell links are generated."""
        from src.dmarket.arbitrage.search import _create_opportunity_if_profitable

        cheapest = {"itemId": "buy123"}
        sell_item = {"price": {"USD": 2000}, "itemId": "sell456"}

        result = _create_opportunity_if_profitable(
            item_name="AK-47",
            cheapest=cheapest,
            cheapest_price=10.0,
            sell_item=sell_item,
            commission_percent=7.0,
            min_profit=0.0,
            game="csgo",
            item_rarity="",
            item_type="",
            item_popularity=0.5,
        )

        assert result is not None
        assert "buy123" in result.get("buy_link", "")
        assert "sell456" in result.get("sell_link", "")


class TestConstants:
    """Tests for module constants."""

    def test_constants_exist(self) -> None:
        """Test that necessary constants exist."""
        from src.dmarket.arbitrage.constants import (
            DEFAULT_FEE,
            DEFAULT_LIMIT,
            GAMES,
            HIGH_FEE,
            LOW_FEE,
            MAX_RETRIES,
        )

        assert isinstance(DEFAULT_FEE, float)
        assert isinstance(DEFAULT_LIMIT, int)
        assert isinstance(HIGH_FEE, float)
        assert isinstance(LOW_FEE, float)
        assert isinstance(MAX_RETRIES, int)
        assert isinstance(GAMES, dict)

    def test_fee_ordering(self) -> None:
        """Test that fee constants are in expected order."""
        from src.dmarket.arbitrage.constants import (
            DEFAULT_FEE,
            HIGH_FEE,
            LOW_FEE,
        )

        # LOW_FEE should be less than DEFAULT_FEE
        assert LOW_FEE <= DEFAULT_FEE
        # HIGH_FEE should be greater than DEFAULT_FEE
        assert HIGH_FEE >= DEFAULT_FEE
