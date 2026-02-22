"""Tests for GameScanner class.

Tests the refactored version of scan_game() with:
- Early returns pattern
- Helper methods
- Reduced nesting
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.dmarket.game_scanner import GameScanner, ProfitRange, ScanConfig, scan_game


@pytest.fixture()
def mock_cache_manager():
    """Create mock cache manager."""
    manager = MagicMock()
    manager._get_cached_results = MagicMock(return_value=None)
    manager._save_to_cache = MagicMock()
    return manager


@pytest.fixture()
def mock_liquidity_analyzer():
    """Create mock liquidity analyzer."""
    analyzer = AsyncMock()
    analyzer.filter_liquid_items = AsyncMock()
    return analyzer


@pytest.fixture()
def game_scanner(mock_cache_manager):
    """Create GameScanner instance."""
    return GameScanner(
        cache_manager=mock_cache_manager,
        liquidity_analyzer=None,
        enable_liquidity_filter=False,
    )


class TestScanConfig:
    """Test ScanConfig dataclass."""

    def test_init_with_defaults(self):
        """Test initialization with defaults."""
        config = ScanConfig(game="csgo")

        assert config.game == "csgo"
        assert config.mode == "medium"
        assert config.max_items == 20
        assert config.price_from is None
        assert config.price_to is None

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        config = ScanConfig(
            game="dota2",
            mode="high",
            max_items=50,
            price_from=10.0,
            price_to=100.0,
        )

        assert config.game == "dota2"
        assert config.mode == "high"
        assert config.max_items == 50
        assert config.price_from == 10.0
        assert config.price_to == 100.0

    def test_get_cache_key(self):
        """Test cache key generation."""
        config = ScanConfig(game="csgo", mode="medium", price_from=5.0, price_to=50.0)

        cache_key = config.get_cache_key()

        assert cache_key == ("csgo", "medium", 5.0, 50.0)

    def test_get_cache_key_with_none_prices(self):
        """Test cache key with None prices."""
        config = ScanConfig(game="csgo", mode="low")

        cache_key = config.get_cache_key()

        assert cache_key == ("csgo", "low", 0, float("inf"))


class TestProfitRange:
    """Test ProfitRange dataclass."""

    def test_init(self):
        """Test initialization."""
        range_ = ProfitRange(min_profit=5.0, max_profit=20.0)

        assert range_.min_profit == 5.0
        assert range_.max_profit == 20.0


class TestGameScannerInitialization:
    """Test GameScanner initialization."""

    def test_init_with_defaults(self, mock_cache_manager):
        """Test initialization."""
        scanner = GameScanner(
            cache_manager=mock_cache_manager,
            liquidity_analyzer=None,
            enable_liquidity_filter=False,
        )

        assert scanner.cache_manager is mock_cache_manager
        assert scanner.liquidity_analyzer is None
        assert scanner.enable_liquidity_filter is False
        assert scanner.total_scans == 0
        assert scanner.total_items_found == 0

    def test_init_with_liquidity_filter(
        self, mock_cache_manager, mock_liquidity_analyzer
    ):
        """Test initialization with liquidity filter."""
        scanner = GameScanner(
            cache_manager=mock_cache_manager,
            liquidity_analyzer=mock_liquidity_analyzer,
            enable_liquidity_filter=True,
        )

        assert scanner.liquidity_analyzer is mock_liquidity_analyzer
        assert scanner.enable_liquidity_filter is True


class TestCacheOperations:
    """Test cache operations."""

    def test_check_cache_miss(self, game_scanner):
        """Test cache miss."""
        config = ScanConfig(game="csgo", mode="medium")

        result = game_scanner._check_cache(config)

        assert result is None

    def test_check_cache_hit(self, game_scanner, mock_cache_manager):
        """Test cache hit."""
        cached_data = [{"title": "Item 1"}, {"title": "Item 2"}]
        mock_cache_manager._get_cached_results.return_value = cached_data

        config = ScanConfig(game="csgo", mode="medium")
        result = game_scanner._check_cache(config)

        assert result == cached_data


class TestProfitRangeCalculation:
    """Test profit range calculation."""

    def test_get_profit_range_low(self, game_scanner):
        """Test low mode profit range."""
        range_ = game_scanner._get_profit_range("low")

        assert range_.min_profit == 1.0
        assert range_.max_profit == 5.0

    def test_get_profit_range_medium(self, game_scanner):
        """Test medium mode profit range."""
        range_ = game_scanner._get_profit_range("medium")

        assert range_.min_profit == 5.0
        assert range_.max_profit == 20.0

    def test_get_profit_range_high(self, game_scanner):
        """Test high mode profit range."""
        range_ = game_scanner._get_profit_range("high")

        assert range_.min_profit == 20.0
        assert range_.max_profit == 100.0

    def test_get_profit_range_default(self, game_scanner):
        """Test default profit range."""
        range_ = game_scanner._get_profit_range("unknown")

        assert range_.min_profit == 5.0
        assert range_.max_profit == 20.0


class TestPriceRangeCalculation:
    """Test price range calculation."""

    def test_get_price_range_explicit(self, game_scanner):
        """Test explicit price range."""
        config = ScanConfig(game="csgo", mode="medium", price_from=10.0, price_to=50.0)

        min_price, max_price = game_scanner._get_price_range(config)

        assert min_price == 10.0
        assert max_price == 50.0

    def test_get_price_range_low_mode(self, game_scanner):
        """Test low mode price range."""
        config = ScanConfig(game="csgo", mode="low")

        min_price, max_price = game_scanner._get_price_range(config)

        assert min_price == 1.0
        assert max_price == 20.0

    def test_get_price_range_medium_mode(self, game_scanner):
        """Test medium mode price range."""
        config = ScanConfig(game="csgo", mode="medium")

        min_price, max_price = game_scanner._get_price_range(config)

        assert min_price == 20.0
        assert max_price == 100.0

    def test_get_price_range_high_mode(self, game_scanner):
        """Test high mode price range."""
        config = ScanConfig(game="csgo", mode="high")

        min_price, max_price = game_scanner._get_price_range(config)

        assert min_price == 100.0
        assert max_price == 1000.0


class TestItemStandardization:
    """Test item standardization."""

    def test_standardize_items_valid(self, game_scanner):
        """Test standardizing valid items."""
        items = [
            {
                "title": "AK-47 | Redline (FT)",
                "price": 15.0,
                "profit": 3.0,
                "profit_percentage": 20.0,
            }
        ]

        result = game_scanner._standardize_items(
            items, game="csgo", min_profit=1.0, max_profit=10.0
        )

        assert len(result) == 1
        assert result[0]["game"] == "csgo"
        assert result[0]["title"] == "AK-47 | Redline (FT)"
        assert result[0]["profit"] == 3.0

    def test_standardize_items_filters_low_profit(self, game_scanner):
        """Test filtering items below min profit."""
        items = [{"title": "Item", "price": 10.0, "profit": 0.5}]

        result = game_scanner._standardize_items(
            items, game="csgo", min_profit=1.0, max_profit=10.0
        )

        assert len(result) == 0

    def test_standardize_items_filters_high_profit(self, game_scanner):
        """Test filtering items above max profit."""
        items = [{"title": "Item", "price": 50.0, "profit": 15.0}]

        result = game_scanner._standardize_items(
            items, game="csgo", min_profit=1.0, max_profit=10.0
        )

        assert len(result) == 0

    def test_standardize_items_adds_default_title(self, game_scanner):
        """Test adding default title for missing items."""
        items = [{"price": 10.0, "profit": 5.0}]

        result = game_scanner._standardize_items(
            items, game="csgo", min_profit=1.0, max_profit=10.0
        )

        assert len(result) == 1
        assert result[0]["title"] == "Unknown"


@pytest.mark.asyncio()
class TestBuiltinFunctions:
    """Test built-in arbitrage functions."""

    @patch("src.dmarket.game_scanner.arbitrage_boost")
    def test_find_items_builtin_low_mode(self, mock_arbitrage_boost, game_scanner):
        """Test using arbitrage_boost for low mode."""
        mock_arbitrage_boost.return_value = [{"title": "Item 1"}]

        config = ScanConfig(game="csgo", mode="low")
        result = game_scanner._find_items_builtin(config)

        mock_arbitrage_boost.assert_called_once_with("csgo")
        assert len(result) == 1

    @patch("src.dmarket.game_scanner.arbitrage_mid")
    def test_find_items_builtin_medium_mode(self, mock_arbitrage_mid, game_scanner):
        """Test using arbitrage_mid for medium mode."""
        mock_arbitrage_mid.return_value = [{"title": "Item 1"}]

        config = ScanConfig(game="csgo", mode="medium")
        result = game_scanner._find_items_builtin(config)

        mock_arbitrage_mid.assert_called_once_with("csgo")
        assert len(result) == 1

    @patch("src.dmarket.game_scanner.arbitrage_pro")
    def test_find_items_builtin_high_mode(self, mock_arbitrage_pro, game_scanner):
        """Test using arbitrage_pro for high mode."""
        mock_arbitrage_pro.return_value = [{"title": "Item 1"}]

        config = ScanConfig(game="csgo", mode="high")
        result = game_scanner._find_items_builtin(config)

        mock_arbitrage_pro.assert_called_once_with("csgo")
        assert len(result) == 1

    @patch("src.dmarket.game_scanner.arbitrage_boost")
    def test_find_items_builtin_handles_exception(
        self, mock_arbitrage_boost, game_scanner
    ):
        """Test handling exception in built-in functions."""
        mock_arbitrage_boost.side_effect = Exception("API Error")

        config = ScanConfig(game="csgo", mode="low")
        result = game_scanner._find_items_builtin(config)

        assert result == []


@pytest.mark.asyncio()
class TestLiquidityFilter:
    """Test liquidity filtering."""

    async def test_apply_liquidity_filter_disabled(self, game_scanner):
        """Test liquidity filter when disabled."""
        items = [{"title": "Item 1"}, {"title": "Item 2"}]
        config = ScanConfig(game="csgo")

        result = await game_scanner._apply_liquidity_filter(items, config)

        assert result == items

    async def test_apply_liquidity_filter_enabled(
        self, mock_cache_manager, mock_liquidity_analyzer
    ):
        """Test liquidity filter when enabled."""
        scanner = GameScanner(
            cache_manager=mock_cache_manager,
            liquidity_analyzer=mock_liquidity_analyzer,
            enable_liquidity_filter=True,
        )

        items = [
            {"title": "Item 1"},
            {"title": "Item 2"},
            {"title": "Item 3"},
        ]
        filtered = [{"title": "Item 1"}]
        mock_liquidity_analyzer.filter_liquid_items.return_value = filtered

        config = ScanConfig(game="csgo", max_items=2)
        result = await scanner._apply_liquidity_filter(items, config)

        assert result == filtered
        mock_liquidity_analyzer.filter_liquid_items.assert_called_once()


@pytest.mark.asyncio()
class TestScanMethod:
    """Test main scan() method."""

    @patch("src.dmarket.game_scanner.rate_limiter")
    async def test_scan_with_cache_hit(
        self, mock_rate_limiter, game_scanner, mock_cache_manager
    ):
        """Test scan with cache hit."""
        cached_data = [{"title": "Cached Item"}]
        mock_cache_manager._get_cached_results.return_value = cached_data

        config = ScanConfig(game="csgo", max_items=10)
        result = await game_scanner.scan(config)

        assert result == cached_data[:10]
        assert game_scanner.total_scans == 0  # No actual scan performed

    @patch("src.dmarket.game_scanner.rate_limiter")
    @patch("src.dmarket.game_scanner.ArbitrageTrader")
    async def test_scan_increments_counters(
        self, mock_trader_class, mock_rate_limiter, game_scanner
    ):
        """Test scan increments counters."""
        mock_trader = AsyncMock()
        mock_trader.find_profitable_items = AsyncMock(return_value=[])
        mock_trader_class.return_value = mock_trader

        config = ScanConfig(game="csgo")
        await game_scanner.scan(config)

        assert game_scanner.total_scans == 1


@pytest.mark.asyncio()
class TestBackwardCompatibleWrapper:
    """Test backward-compatible wrapper function."""

    @patch("src.dmarket.game_scanner.rate_limiter")
    @patch("src.dmarket.game_scanner.ArbitrageTrader")
    async def test_scan_game_wrapper(
        self, mock_trader_class, mock_rate_limiter, mock_cache_manager
    ):
        """Test scan_game wrapper function."""
        mock_trader = AsyncMock()
        mock_trader.find_profitable_items = AsyncMock(return_value=[])
        mock_trader_class.return_value = mock_trader

        scanner_instance = MagicMock()
        scanner_instance._get_cached_results = MagicMock(return_value=None)
        scanner_instance._save_to_cache = MagicMock()
        scanner_instance.liquidity_analyzer = None
        scanner_instance.enable_liquidity_filter = False

        result = await scan_game(
            scanner_instance=scanner_instance,
            game="csgo",
            mode="medium",
            max_items=20,
        )

        assert isinstance(result, list)
