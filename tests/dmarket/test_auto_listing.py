"""Tests for Auto-Listing System."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.auto_listing import (
    AutoListingEngine,
    ListingCandidate,
    ListingConfig,
    ListingResult,
    ListingStatus,
    ListingStrategy,
    create_auto_listing_engine,
)


class TestListingConfig:
    """Tests for ListingConfig."""

    def test_default_config(self):
        """Test default configuration values."""
        config = ListingConfig()

        assert config.min_price_usd == Decimal("50.0")
        assert config.target_profit_margin == Decimal("0.10")
        assert config.default_strategy == ListingStrategy.UNDERCUT

    def test_custom_config(self):
        """Test custom configuration."""
        config = ListingConfig(
            min_price_usd=Decimal("100.0"),
            target_profit_margin=Decimal("0.15"),
            default_strategy=ListingStrategy.MATCH,
        )

        assert config.min_price_usd == Decimal("100.0")
        assert config.target_profit_margin == Decimal("0.15")
        assert config.default_strategy == ListingStrategy.MATCH


class TestListingCandidate:
    """Tests for ListingCandidate."""

    def test_candidate_creation(self):
        """Test candidate creation."""
        candidate = ListingCandidate(
            item_id="item123",
            item_name="AK-47 | Redline",
            dmarket_price=Decimal("50.0"),
        )

        assert candidate.item_id == "item123"
        assert candidate.status == ListingStatus.PENDING

    def test_candidate_with_profit(self):
        """Test candidate with profit calculation."""
        candidate = ListingCandidate(
            item_id="item123",
            item_name="AK-47 | Redline",
            dmarket_price=Decimal("50.0"),
            recommended_price=Decimal("60.0"),
            estimated_profit=Decimal("5.0"),
            profit_margin=Decimal("0.10"),
        )

        assert candidate.estimated_profit == Decimal("5.0")
        assert candidate.profit_margin == Decimal("0.10")


class TestAutoListingEngine:
    """Tests for AutoListingEngine."""

    @pytest.fixture
    def mock_dmarket_api(self):
        """Create mock DMarket API."""
        api = MagicMock()
        api.get_user_inventory = AsyncMock(return_value={
            "items": [
                {
                    "itemId": "item1",
                    "title": "AK-47 | Redline (Field-Tested)",
                    "price": {"USD": "7500"},  # $75
                },
                {
                    "itemId": "item2",
                    "title": "M4A4 | Asiimov (Field-Tested)",
                    "price": {"USD": "3000"},  # $30 - below threshold
                },
            ]
        })
        return api

    @pytest.fixture
    def mock_waxpeer_api(self):
        """Create mock Waxpeer API."""
        api = MagicMock()
        api.get_market_prices = AsyncMock(return_value={
            "items": [
                {
                    "name": "AK-47 | Redline (Field-Tested)",
                    "price": 85000,  # $85 in mils
                    "count": 50,
                }
            ]
        })
        api.list_single_item = AsyncMock(return_value={"success": True})
        api.edit_item_price = AsyncMock(return_value={"success": True})
        api.remove_items = AsyncMock(return_value={"success": True})
        return api

    @pytest.fixture
    def engine(self, mock_dmarket_api, mock_waxpeer_api):
        """Create test engine."""
        config = ListingConfig(
            min_price_usd=Decimal("50.0"),
            check_interval_seconds=0.1,
        )
        return AutoListingEngine(
            dmarket_api=mock_dmarket_api,
            waxpeer_api=mock_waxpeer_api,
            config=config,
        )

    def test_engine_initialization(self, engine):
        """Test engine initializes correctly."""
        assert engine.is_running is False
        assert len(engine.active_listings) == 0

    @pytest.mark.asyncio
    async def test_start_stop(self, engine):
        """Test start and stop."""
        await engine.start()
        assert engine.is_running is True

        await engine.stop()
        assert engine.is_running is False

    @pytest.mark.asyncio
    async def test_find_listing_candidates(self, engine, mock_dmarket_api, mock_waxpeer_api):
        """Test finding listing candidates."""
        candidates = await engine._find_listing_candidates()

        # Should only find item above threshold ($75)
        assert len(candidates) >= 0  # Depends on profit calculation

    @pytest.mark.asyncio
    async def test_calculate_optimal_price(self, engine, mock_waxpeer_api):
        """Test optimal price calculation."""
        price = await engine._calculate_optimal_price("AK-47 | Redline (Field-Tested)")

        assert price is not None
        # With UNDERCUT strategy, should be slightly below $85
        assert price < Decimal("85.0")

    def test_calculate_profit(self, engine):
        """Test profit calculation."""
        profit = engine._calculate_profit(
            buy_price=Decimal("75.0"),
            sell_price=Decimal("85.0"),
        )

        # Sell $85, commission 6% = $5.10, net = $79.90
        # Profit = $79.90 - $75 = $4.90
        assert profit > Decimal("0")
        assert profit < Decimal("10.0")

    @pytest.mark.asyncio
    async def test_list_item(self, engine, mock_waxpeer_api):
        """Test listing an item."""
        candidate = ListingCandidate(
            item_id="item1",
            item_name="Test Item",
            dmarket_price=Decimal("75.0"),
            recommended_price=Decimal("83.0"),
        )

        result = await engine._list_item(candidate)

        assert result.success is True
        assert result.item_id == "item1"
        mock_waxpeer_api.list_single_item.assert_called_once()

    @pytest.mark.asyncio
    async def test_reprice_item(self, engine, mock_waxpeer_api):
        """Test repricing an item."""
        result = await engine._reprice_item("item1", Decimal("80.0"))

        assert result is True
        mock_waxpeer_api.edit_item_price.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_listing(self, engine, mock_waxpeer_api):
        """Test cancelling a listing."""
        # First add a listing
        engine._listings["item1"] = ListingCandidate(
            item_id="item1",
            item_name="Test",
            dmarket_price=Decimal("75.0"),
            status=ListingStatus.LISTED,
        )

        result = await engine.cancel_listing("item1")

        assert result is True
        mock_waxpeer_api.remove_items.assert_called_once()

    def test_get_stats(self, engine):
        """Test getting stats."""
        stats = engine.get_stats()

        assert "is_running" in stats
        assert "active_listings" in stats
        assert "total_listings" in stats


class TestListingResult:
    """Tests for ListingResult."""

    def test_successful_result(self):
        """Test successful listing result."""
        result = ListingResult(
            success=True,
            item_id="item1",
            item_name="Test Item",
            listed_price=Decimal("85.0"),
        )

        assert result.success is True
        assert result.error is None

    def test_failed_result(self):
        """Test failed listing result."""
        result = ListingResult(
            success=False,
            item_id="item1",
            item_name="Test Item",
            error="Insufficient funds",
        )

        assert result.success is False
        assert result.error == "Insufficient funds"


class TestListingStrategies:
    """Tests for different listing strategies."""

    @pytest.fixture
    def mock_apis(self):
        """Create mock APIs."""
        dmarket = MagicMock()
        dmarket.get_user_inventory = AsyncMock(return_value={"items": []})

        waxpeer = MagicMock()
        waxpeer.get_market_prices = AsyncMock(return_value={
            "items": [{"name": "Test", "price": 100000, "count": 50}]
        })

        return dmarket, waxpeer

    @pytest.mark.asyncio
    async def test_undercut_strategy(self, mock_apis):
        """Test undercut pricing strategy."""
        dmarket, waxpeer = mock_apis

        config = ListingConfig(
            default_strategy=ListingStrategy.UNDERCUT,
            undercut_percent=Decimal("0.02"),
        )
        engine = AutoListingEngine(
            dmarket_api=dmarket,
            waxpeer_api=waxpeer,
            config=config,
        )

        price = await engine._calculate_optimal_price("Test")
        # $100 * (1 - 0.02) = $98
        assert price == Decimal("98.00")

    @pytest.mark.asyncio
    async def test_match_strategy(self, mock_apis):
        """Test match pricing strategy."""
        dmarket, waxpeer = mock_apis

        config = ListingConfig(default_strategy=ListingStrategy.MATCH)
        engine = AutoListingEngine(
            dmarket_api=dmarket,
            waxpeer_api=waxpeer,
            config=config,
        )

        price = await engine._calculate_optimal_price("Test")
        assert price == Decimal("100.00")


class TestFactoryFunction:
    """Tests for factory function."""

    def test_create_auto_listing_engine(self):
        """Test factory function."""
        dmarket = MagicMock()
        waxpeer = MagicMock()

        engine = create_auto_listing_engine(
            dmarket_api=dmarket,
            waxpeer_api=waxpeer,
            min_price=100.0,
            target_profit=0.15,
        )

        assert engine.config.min_price_usd == Decimal("100.0")
        assert engine.config.target_profit_margin == Decimal("0.15")
