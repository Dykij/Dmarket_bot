"""Tests for SalesHistoryAnalyzer module."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.scanner.sales_history import SalesHistoryAnalyzer, SalesStats


@pytest.fixture()
def mock_api():
    """Mock DMarket API client."""
    api = AsyncMock()
    return api


@pytest.fixture()
def analyzer(mock_api):
    """Create SalesHistoryAnalyzer instance."""
    return SalesHistoryAnalyzer(
        api_client=mock_api,
        min_sales_for_liquid=5,
        analysis_days=7,
        cache_ttl=3600,
    )


@pytest.fixture()
def sample_sales_data():
    """Sample sales history data."""
    now = datetime.now()
    return {
        "sales": [
            {
                "title": "AK-47 | Redline (FT)",
                "price": {"USD": "1500"},  # $15.00
                "date": (now - timedelta(days=i)).isoformat(),
            }
            for i in range(10)
        ]
    }


class TestSalesHistoryAnalyzer:
    """Test cases for SalesHistoryAnalyzer."""

    @pytest.mark.asyncio()
    async def test_initialization(self, mock_api):
        """Test analyzer initialization."""
        analyzer = SalesHistoryAnalyzer(
            api_client=mock_api,
            min_sales_for_liquid=5,
            analysis_days=7,
        )

        assert analyzer.api is mock_api
        assert analyzer.min_sales_for_liquid == 5
        assert analyzer.analysis_days == 7
        assert analyzer.cache_ttl == 3600
        assert len(analyzer._cache) == 0

    @pytest.mark.asyncio()
    async def test_get_sales_history_success(self, analyzer, mock_api, sample_sales_data):
        """Test successful sales history fetch."""
        mock_api.get_last_sales = AsyncMock(return_value=sample_sales_data)

        result = await analyzer.get_sales_history(
            title="AK-47 | Redline (FT)",
            game_id="csgo",
            limit=20,
        )

        assert len(result) == 10
        assert result[0]["title"] == "AK-47 | Redline (FT)"
        mock_api.get_last_sales.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_sales_history_with_filters(self, analyzer, mock_api, sample_sales_data):
        """Test sales history fetch with filters."""
        mock_api.get_last_sales = AsyncMock(return_value=sample_sales_data)

        filters = {
            "exterior": ["Factory New"],
            "float": [0.0, 0.07],
        }

        await analyzer.get_sales_history(
            title="AK-47 | Redline (FT)",
            game_id="csgo",
            filters=filters,
        )

        call_kwargs = mock_api.get_last_sales.call_args.kwargs
        assert "exterior[]" in call_kwargs
        assert call_kwargs["exterior[]"] == ["Factory New"]

    @pytest.mark.asyncio()
    async def test_get_sales_history_no_data(self, analyzer, mock_api):
        """Test handling of empty sales history."""
        mock_api.get_last_sales = AsyncMock(return_value={"sales": []})

        result = await analyzer.get_sales_history(
            title="Unknown Item",
            game_id="csgo",
        )

        assert result == []

    @pytest.mark.asyncio()
    async def test_get_sales_history_api_error(self, analyzer, mock_api):
        """Test handling of API errors."""
        mock_api.get_last_sales = AsyncMock(side_effect=Exception("API Error"))

        result = await analyzer.get_sales_history(
            title="AK-47 | Redline (FT)",
            game_id="csgo",
        )

        assert result == []

    @pytest.mark.asyncio()
    async def test_analyze_sales_success(self, analyzer, mock_api, sample_sales_data):
        """Test successful sales analysis."""
        mock_api.get_last_sales = AsyncMock(return_value=sample_sales_data)

        stats = await analyzer.analyze_sales(
            title="AK-47 | Redline (FT)",
            game_id="csgo",
        )

        assert stats is not None
        assert isinstance(stats, SalesStats)
        assert stats.title == "AK-47 | Redline (FT)"
        assert stats.game_id == "csgo"
        assert stats.total_sales == 10
        assert stats.avg_price_usd == 15.0
        assert stats.is_liquid is True

    @pytest.mark.asyncio()
    async def test_analyze_sales_trending_up(self, analyzer, mock_api):
        """Test detection of upward price trend."""
        now = datetime.now()
        trending_data = {
            "sales": [
                {
                    "title": "Item",
                    "price": {"USD": str(1000 + i * 100)},  # Increasing
                    "date": (now - timedelta(days=i)).isoformat(),
                }
                for i in range(10)
            ]
        }

        mock_api.get_last_sales = AsyncMock(return_value=trending_data)

        stats = await analyzer.analyze_sales(
            title="Item",
            game_id="csgo",
        )

        assert stats is not None
        assert stats.trend == "up"

    @pytest.mark.asyncio()
    async def test_analyze_sales_trending_down(self, analyzer, mock_api):
        """Test detection of downward price trend."""
        now = datetime.now()
        trending_data = {
            "sales": [
                {
                    "title": "Item",
                    "price": {"USD": str(2000 - i * 100)},  # Decreasing
                    "date": (now - timedelta(days=i)).isoformat(),
                }
                for i in range(10)
            ]
        }

        mock_api.get_last_sales = AsyncMock(return_value=trending_data)

        stats = await analyzer.analyze_sales(
            title="Item",
            game_id="csgo",
        )

        assert stats is not None
        assert stats.trend == "down"

    @pytest.mark.asyncio()
    async def test_analyze_sales_illiquid_item(self, analyzer, mock_api):
        """Test detection of illiquid items."""
        # Only 2 sales - below threshold
        illiquid_data = {
            "sales": [
                {
                    "title": "Rare Item",
                    "price": {"USD": "10000"},
                    "date": datetime.now().isoformat(),
                },
                {
                    "title": "Rare Item",
                    "price": {"USD": "10500"},
                    "date": (datetime.now() - timedelta(days=5)).isoformat(),
                },
            ]
        }

        mock_api.get_last_sales = AsyncMock(return_value=illiquid_data)

        stats = await analyzer.analyze_sales(
            title="Rare Item",
            game_id="csgo",
        )

        assert stats is not None
        assert stats.is_liquid is False
        assert stats.total_sales == 2

    @pytest.mark.asyncio()
    async def test_analyze_sales_insufficient_data(self, analyzer, mock_api):
        """Test handling of insufficient sales data."""
        mock_api.get_last_sales = AsyncMock(
            return_value={"sales": [{"title": "Item", "price": {"USD": "1000"}}]}
        )

        stats = await analyzer.analyze_sales(
            title="Item",
            game_id="csgo",
        )

        assert stats is None

    @pytest.mark.asyncio()
    async def test_analyze_sales_cache_hit(self, analyzer, mock_api, sample_sales_data):
        """Test cache usage for repeated queries."""
        mock_api.get_last_sales = AsyncMock(return_value=sample_sales_data)

        # First call
        stats1 = await analyzer.analyze_sales(
            title="AK-47 | Redline (FT)",
            game_id="csgo",
        )

        # Second call (should use cache)
        stats2 = await analyzer.analyze_sales(
            title="AK-47 | Redline (FT)",
            game_id="csgo",
        )

        assert stats1 == stats2
        assert mock_api.get_last_sales.call_count == 1

    @pytest.mark.asyncio()
    async def test_analyze_sales_cache_bypass(self, analyzer, mock_api, sample_sales_data):
        """Test cache bypass when use_cache=False."""
        mock_api.get_last_sales = AsyncMock(return_value=sample_sales_data)

        # First call
        await analyzer.analyze_sales(
            title="AK-47 | Redline (FT)",
            game_id="csgo",
        )

        # Second call with cache bypass
        await analyzer.analyze_sales(
            title="AK-47 | Redline (FT)",
            game_id="csgo",
            use_cache=False,
        )

        assert mock_api.get_last_sales.call_count == 2

    @pytest.mark.asyncio()
    async def test_filter_by_liquidity(self, analyzer, mock_api):
        """Test filtering opportunities by liquidity."""
        opportunities = [
            {"title": "Liquid Item 1", "profit": 5.0},
            {"title": "Liquid Item 2", "profit": 3.0},
            {"title": "Illiquid Item", "profit": 10.0},
        ]

        # Mock analyze_sales to return liquid/illiquid
        async def mock_analyze(title, game_id, **kwargs):
            if "Illiquid" in title:
                return SalesStats(
                    title=title,
                    game_id=game_id,
                    total_sales=2,
                    avg_price_usd=10.0,
                    min_price_usd=9.0,
                    max_price_usd=11.0,
                    price_volatility=0.5,
                    turnover_rate=0.2,
                    trend="stable",
                    is_liquid=False,
                )
            return SalesStats(
                title=title,
                game_id=game_id,
                total_sales=10,
                avg_price_usd=10.0,
                min_price_usd=9.0,
                max_price_usd=11.0,
                price_volatility=0.5,
                turnover_rate=1.5,
                trend="stable",
                is_liquid=True,
            )

        analyzer.analyze_sales = mock_analyze

        filtered = await analyzer.filter_by_liquidity(
            opportunities,
            game_id="csgo",
        )

        assert len(filtered) == 2
        assert all("Liquid Item" in opp["title"] for opp in filtered)
        assert all("sales_stats" in opp for opp in filtered)

    @pytest.mark.asyncio()
    async def test_filter_by_liquidity_empty_list(self, analyzer):
        """Test filtering empty opportunities list."""
        filtered = await analyzer.filter_by_liquidity([], game_id="csgo")
        assert filtered == []

    @pytest.mark.asyncio()
    async def test_filter_by_liquidity_with_errors(self, analyzer, mock_api):
        """Test liquidity filtering handles analysis errors."""
        opportunities = [
            {"title": "Item 1", "profit": 5.0},
            {"title": "Item 2", "profit": 3.0},
        ]

        # Mock to raise exception for first item
        call_count = 0

        async def mock_analyze(title, game_id, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Analysis failed")
            return SalesStats(
                title=title,
                game_id=game_id,
                total_sales=10,
                avg_price_usd=10.0,
                min_price_usd=9.0,
                max_price_usd=11.0,
                price_volatility=0.5,
                turnover_rate=1.5,
                trend="stable",
                is_liquid=True,
            )

        analyzer.analyze_sales = mock_analyze

        filtered = await analyzer.filter_by_liquidity(
            opportunities,
            game_id="csgo",
        )

        assert len(filtered) == 1
        assert filtered[0]["title"] == "Item 2"

    def test_clear_cache(self, analyzer, sample_sales_data):
        """Test cache clearing."""
        # Add some items to cache
        analyzer._cache["key1"] = (MagicMock(), datetime.now())
        analyzer._cache["key2"] = (MagicMock(), datetime.now())

        assert len(analyzer._cache) == 2

        analyzer.clear_cache()

        assert len(analyzer._cache) == 0

    @pytest.mark.asyncio()
    async def test_get_trending_items(self, analyzer):
        """Test getting trending items."""
        titles = ["Item 1", "Item 2", "Item 3"]

        # Mock analyze_sales
        async def mock_analyze(title, game_id, **kwargs):
            if title == "Item 1":
                trend = "up"
            elif title == "Item 2":
                trend = "down"
            else:
                trend = "stable"

            return SalesStats(
                title=title,
                game_id=game_id,
                total_sales=10,
                avg_price_usd=10.0,
                min_price_usd=9.0,
                max_price_usd=11.0,
                price_volatility=0.5,
                turnover_rate=1.5,
                trend=trend,
                is_liquid=True,
            )

        analyzer.analyze_sales = mock_analyze

        # Get only uptrending items
        trending = await analyzer.get_trending_items(
            game_id="csgo",
            titles=titles,
            trend_type="up",
        )

        assert len(trending) == 1
        assert trending[0].title == "Item 1"
        assert trending[0].trend == "up"

    @pytest.mark.asyncio()
    async def test_get_trending_items_empty(self, analyzer):
        """Test get trending with no matches."""
        titles = ["Item 1", "Item 2"]

        # Mock to return all stable
        async def mock_analyze(title, game_id, **kwargs):
            return SalesStats(
                title=title,
                game_id=game_id,
                total_sales=10,
                avg_price_usd=10.0,
                min_price_usd=9.0,
                max_price_usd=11.0,
                price_volatility=0.5,
                turnover_rate=1.5,
                trend="stable",
                is_liquid=True,
            )

        analyzer.analyze_sales = mock_analyze

        trending = await analyzer.get_trending_items(
            game_id="csgo",
            titles=titles,
            trend_type="up",
        )

        assert len(trending) == 0
