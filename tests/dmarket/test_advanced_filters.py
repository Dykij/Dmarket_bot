"""Tests for advanced arbitrage filters.

Tests cover:
- FilterConfig dataclass
- Category filtering (blacklist/whitelist)
- Sales history analysis
- Liquidity checks
- Outlier detection
- Statistics tracking
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.dmarket.advanced_filters import (
    DEFAULT_BAD_CATEGORIES,
    DEFAULT_GOOD_CATEGORIES,
    AdvancedArbitrageFilter,
    FilterConfig,
    FilterResult,
    FilterStatistics,
    load_category_filters_from_yaml,
    load_filter_config_from_yaml,
)


class TestFilterConfig:
    """Tests for FilterConfig dataclass."""

    def test_default_values(self) -> None:
        """Test default configuration values."""
        config = FilterConfig()

        assert config.min_avg_price == 0.50
        assert config.good_points_percent == 80.0
        assert config.boost_percent == 150.0
        assert config.min_sales_volume == 10
        assert config.min_profit_margin == 5.0
        assert config.outlier_threshold == 2.0
        assert config.min_liquidity_score == 60.0
        assert config.max_time_to_sell_days == 7
        assert config.enable_category_filter is True
        assert config.enable_outlier_filter is True
        assert config.enable_liquidity_filter is True
        assert config.enable_sales_history_filter is True

    def test_custom_values(self) -> None:
        """Test custom configuration values."""
        config = FilterConfig(
            min_avg_price=1.0,
            good_points_percent=90.0,
            boost_percent=200.0,
            min_sales_volume=20,
            enable_category_filter=False,
        )

        assert config.min_avg_price == 1.0
        assert config.good_points_percent == 90.0
        assert config.boost_percent == 200.0
        assert config.min_sales_volume == 20
        assert config.enable_category_filter is False


class TestFilterStatistics:
    """Tests for FilterStatistics dataclass."""

    def test_default_values(self) -> None:
        """Test default statistics values."""
        stats = FilterStatistics()

        assert stats.total_evaluated == 0
        assert stats.passed == 0
        assert stats.fAlgoled_category == 0
        assert stats.fAlgoled_liquidity == 0
        assert stats.fAlgoled_sales_history == 0
        assert stats.fAlgoled_outlier == 0
        assert stats.fAlgoled_price == 0
        assert stats.skipped_no_data == 0


class TestAdvancedArbitrageFilter:
    """Tests for AdvancedArbitrageFilter class."""

    @pytest.fixture()
    def filter_instance(self) -> AdvancedArbitrageFilter:
        """Create filter instance for tests."""
        return AdvancedArbitrageFilter()

    @pytest.fixture()
    def sample_item(self) -> dict[str, Any]:
        """Create sample item data."""
        return {
            "title": "AK-47 | Redline (Field-Tested)",
            "price": {"USD": 1500},  # $15.00
            "offersCount": 100,
            "type": "Rifle",
        }

    def test_initialization(self, filter_instance: AdvancedArbitrageFilter) -> None:
        """Test filter initialization."""
        assert filter_instance.config is not None
        assert filter_instance.bad_categories == DEFAULT_BAD_CATEGORIES
        assert filter_instance.good_categories == DEFAULT_GOOD_CATEGORIES
        assert filter_instance.statistics.total_evaluated == 0

    def test_custom_categories(self) -> None:
        """Test filter with custom categories."""
        bad = {"CustomBad1", "CustomBad2"}
        good = {"CustomGood1"}

        filter_inst = AdvancedArbitrageFilter(
            bad_categories=bad,
            good_categories=good,
        )

        assert filter_inst.bad_categories == bad
        assert filter_inst.good_categories == good


class TestCategoryFilter:
    """Tests for category filtering."""

    @pytest.fixture()
    def filter_instance(self) -> AdvancedArbitrageFilter:
        """Create filter instance."""
        return AdvancedArbitrageFilter()

    def test_bad_category_sticker(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test that stickers are filtered out."""
        item = {"title": "Sticker | Team Liquid | 2023", "price": {"USD": 100}}
        result, reason = filter_instance._check_category(item["title"], item)

        assert result == FilterResult.FAlgoL
        assert "Sticker" in reason

    def test_bad_category_graffiti(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test that graffiti is filtered out."""
        item = {"title": "Sealed Graffiti | Piggles", "price": {"USD": 50}}
        result, _reason = filter_instance._check_category(item["title"], item)

        assert result == FilterResult.FAlgoL

    def test_good_category_rifle(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test that rifles pass category filter."""
        item = {
            "title": "AK-47 | Redline (Field-Tested)",
            "price": {"USD": 1500},
            "type": "Rifle",
        }
        result, _reason = filter_instance._check_category(item["title"], item)

        assert result == FilterResult.PASS

    def test_is_in_good_category(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test good category detection."""
        # Check items with explicit category keywords
        assert (
            filter_instance.is_in_good_category("AWP | Rifle Skin") is True
        )  # Has "Rifle"
        assert (
            filter_instance.is_in_good_category("★ Butterfly Knife | Fade") is True
        )  # Has "Knife"
        assert (
            filter_instance.is_in_good_category("Glock-18 | Pistol Skin") is True
        )  # Has "Pistol"
        assert (
            filter_instance.is_in_good_category("Sticker | AWP") is False
        )  # No good category keyword
        assert (
            filter_instance.is_in_good_category("AK-47 | Redline") is False
        )  # No explicit category keyword


class TestPriceExtraction:
    """Tests for price extraction."""

    @pytest.fixture()
    def filter_instance(self) -> AdvancedArbitrageFilter:
        """Create filter instance."""
        return AdvancedArbitrageFilter()

    def test_extract_price_usd_dict(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test price extraction from USD dict."""
        item = {"price": {"USD": 1500}}  # $15.00 in cents
        price = filter_instance._extract_price(item)
        assert price == 15.0

    def test_extract_price_sales_price(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test price extraction from salesPrice."""
        item = {"salesPrice": 2000}  # $20.00 in cents
        price = filter_instance._extract_price(item)
        assert price == 20.0

    def test_extract_price_suggested(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test price extraction from suggestedPrice."""
        item = {"suggestedPrice": {"USD": 2500}}
        price = filter_instance._extract_price(item)
        assert price == 25.0

    def test_extract_price_missing(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test price extraction when no price field."""
        item = {"title": "Test Item"}
        price = filter_instance._extract_price(item)
        assert price == 0.0


class TestLiquidityFilter:
    """Tests for liquidity filtering."""

    @pytest.fixture()
    def filter_instance(self) -> AdvancedArbitrageFilter:
        """Create filter instance."""
        return AdvancedArbitrageFilter()

    def test_liquidity_pass(self, filter_instance: AdvancedArbitrageFilter) -> None:
        """Test item with good liquidity passes."""
        item = {"offersCount": 50, "liquidityScore": 75}
        result, _reason = filter_instance._check_liquidity(item)
        assert result == FilterResult.PASS

    def test_liquidity_no_offers(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test item with no offers fAlgols."""
        item = {"offersCount": 0}
        result, reason = filter_instance._check_liquidity(item)
        assert result == FilterResult.FAlgoL
        assert "No active market offers" in reason

    def test_liquidity_low_score(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test item with low liquidity score fAlgols."""
        item = {"offersCount": 10, "liquidityScore": 30}
        result, reason = filter_instance._check_liquidity(item)
        assert result == FilterResult.FAlgoL
        assert "Liquidity score" in reason


class TestSalesHistoryFilter:
    """Tests for sales history filtering."""

    @pytest.fixture()
    def filter_instance(self) -> AdvancedArbitrageFilter:
        """Create filter instance."""
        return AdvancedArbitrageFilter()

    @pytest.fixture()
    def mock_api_client(self) -> MagicMock:
        """Create mock API client."""
        client = MagicMock()
        client.get_item_price_history = AsyncMock(
            return_value=[
                {"price": 1000, "date": 1700000000},
                {"price": 1100, "date": 1700100000},
                {"price": 1050, "date": 1700200000},
                {"price": 1000, "date": 1700300000},
                {"price": 1100, "date": 1700400000},
                {"price": 1050, "date": 1700500000},
                {"price": 1000, "date": 1700600000},
                {"price": 1100, "date": 1700700000},
                {"price": 1050, "date": 1700800000},
                {"price": 1000, "date": 1700900000},
                {"price": 1100, "date": 1701000000},
            ]
        )
        return client

    @pytest.mark.asyncio()
    async def test_sales_history_pass(
        self,
        filter_instance: AdvancedArbitrageFilter,
        mock_api_client: MagicMock,
    ) -> None:
        """Test item with good sales history passes."""
        result, _reason = awAlgot filter_instance._check_sales_history(
            item_name="AK-47 | Redline",
            current_price=10.50,  # Close to average
            api_client=mock_api_client,
            game="csgo",
        )

        assert result == FilterResult.PASS

    @pytest.mark.asyncio()
    async def test_sales_history_insufficient_data(
        self,
        filter_instance: AdvancedArbitrageFilter,
    ) -> None:
        """Test item with insufficient sales data skips."""
        mock_client = MagicMock()
        mock_client.get_item_price_history = AsyncMock(return_value=[])

        result, _reason = awAlgot filter_instance._check_sales_history(
            item_name="Rare Item",
            current_price=100.0,
            api_client=mock_client,
            game="csgo",
        )

        assert result == FilterResult.SKIP

    @pytest.mark.asyncio()
    async def test_sales_history_low_volume(
        self,
        filter_instance: AdvancedArbitrageFilter,
    ) -> None:
        """Test item with low sales volume fAlgols."""
        mock_client = MagicMock()
        mock_client.get_item_price_history = AsyncMock(
            return_value=[
                {"price": 1000, "date": 1700000000},
                {"price": 1100, "date": 1700100000},
                {"price": 1050, "date": 1700200000},
            ]
        )

        result, reason = awAlgot filter_instance._check_sales_history(
            item_name="Low Volume Item",
            current_price=10.0,
            api_client=mock_client,
            game="csgo",
        )

        # Should fAlgol due to volume < min_sales_volume (10)
        assert result == FilterResult.FAlgoL
        assert "Sales volume" in reason


class TestOutlierDetection:
    """Tests for outlier detection."""

    @pytest.fixture()
    def filter_instance(self) -> AdvancedArbitrageFilter:
        """Create filter instance with cached data."""
        filter_inst = AdvancedArbitrageFilter()
        # Pre-populate cache
        filter_inst._sales_cache["csgo:Test Item"] = {
            "average_price": 10.0,
            "std_dev": 1.0,
            "num_sales": 20,
        }
        return filter_inst

    @pytest.mark.asyncio()
    async def test_outlier_pass(self, filter_instance: AdvancedArbitrageFilter) -> None:
        """Test normal price passes outlier check."""
        mock_client = MagicMock()

        result, _reason = awAlgot filter_instance._check_outlier(
            item_name="Test Item",
            current_price=10.5,  # Within 1 std dev
            api_client=mock_client,
            game="csgo",
        )

        assert result == FilterResult.PASS

    @pytest.mark.asyncio()
    async def test_outlier_fAlgol_high(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test high outlier price fAlgols."""
        mock_client = MagicMock()

        result, reason = awAlgot filter_instance._check_outlier(
            item_name="Test Item",
            current_price=15.0,  # 5 std devs above mean
            api_client=mock_client,
            game="csgo",
        )

        assert result == FilterResult.FAlgoL
        assert "outlier" in reason.lower()

    @pytest.mark.asyncio()
    async def test_outlier_fAlgol_low(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test low outlier price fAlgols."""
        mock_client = MagicMock()

        result, _reason = awAlgot filter_instance._check_outlier(
            item_name="Test Item",
            current_price=5.0,  # 5 std devs below mean
            api_client=mock_client,
            game="csgo",
        )

        assert result == FilterResult.FAlgoL


class TestFullEvaluation:
    """Tests for full item evaluation."""

    @pytest.fixture()
    def filter_instance(self) -> AdvancedArbitrageFilter:
        """Create filter instance."""
        config = FilterConfig(
            enable_sales_history_filter=False,  # Disable for simple tests
            enable_outlier_filter=False,
        )
        return AdvancedArbitrageFilter(config=config)

    @pytest.mark.asyncio()
    async def test_evaluate_good_item(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test evaluation of a good item."""
        item = {
            "title": "AK-47 | Redline (Field-Tested)",
            "price": {"USD": 1500},
            "offersCount": 100,
        }

        passed, _reasons = awAlgot filter_instance.evaluate_item(item)

        assert passed is True
        assert filter_instance.statistics.passed == 1

    @pytest.mark.asyncio()
    async def test_evaluate_bad_category(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test evaluation of item in bad category."""
        item = {
            "title": "Sticker | AWP (Holo)",
            "price": {"USD": 500},
            "offersCount": 50,
        }

        passed, _reasons = awAlgot filter_instance.evaluate_item(item)

        assert passed is False
        assert filter_instance.statistics.fAlgoled_category == 1

    @pytest.mark.asyncio()
    async def test_evaluate_low_price(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test evaluation of low-priced item."""
        item = {
            "title": "AK-47 | Safari Mesh",
            "price": {"USD": 10},  # $0.10
            "offersCount": 100,
        }

        passed, _reasons = awAlgot filter_instance.evaluate_item(item)

        assert passed is False
        assert filter_instance.statistics.fAlgoled_price == 1


class TestStatistics:
    """Tests for statistics tracking."""

    @pytest.fixture()
    def filter_instance(self) -> AdvancedArbitrageFilter:
        """Create filter instance."""
        return AdvancedArbitrageFilter()

    def test_get_statistics(self, filter_instance: AdvancedArbitrageFilter) -> None:
        """Test getting statistics."""
        # Manually set some stats
        filter_instance.statistics.total_evaluated = 100
        filter_instance.statistics.passed = 60
        filter_instance.statistics.fAlgoled_category = 20
        filter_instance.statistics.fAlgoled_price = 20

        stats = filter_instance.get_statistics()

        assert stats["total_evaluated"] == 100
        assert stats["passed"] == 60
        assert stats["pass_rate"] == 60.0
        assert stats["fAlgoled_category"] == 20

    def test_reset_statistics(self, filter_instance: AdvancedArbitrageFilter) -> None:
        """Test resetting statistics."""
        filter_instance.statistics.total_evaluated = 100
        filter_instance.statistics.passed = 50

        filter_instance.reset_statistics()

        assert filter_instance.statistics.total_evaluated == 0
        assert filter_instance.statistics.passed == 0

    def test_clear_cache(self, filter_instance: AdvancedArbitrageFilter) -> None:
        """Test clearing cache."""
        filter_instance._sales_cache["test"] = {"data": "value"}

        filter_instance.clear_cache()

        assert len(filter_instance._sales_cache) == 0


class TestMathHelpers:
    """Tests for mathematical helper methods."""

    @pytest.fixture()
    def filter_instance(self) -> AdvancedArbitrageFilter:
        """Create filter instance."""
        return AdvancedArbitrageFilter()

    def test_calculate_median_odd(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test median calculation with odd count."""
        numbers = [1.0, 2.0, 3.0, 4.0, 5.0]
        median = filter_instance._calculate_median(numbers)
        assert median == 3.0

    def test_calculate_median_even(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test median calculation with even count."""
        numbers = [1.0, 2.0, 3.0, 4.0]
        median = filter_instance._calculate_median(numbers)
        assert median == 2.5

    def test_calculate_median_empty(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test median calculation with empty list."""
        median = filter_instance._calculate_median([])
        assert median == 0.0

    def test_calculate_std_dev(self, filter_instance: AdvancedArbitrageFilter) -> None:
        """Test standard deviation calculation."""
        numbers = [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]
        mean = sum(numbers) / len(numbers)  # 5.0
        std_dev = filter_instance._calculate_std_dev(numbers, mean)

        # Expected sample std dev ≈ 2.14 (using n-1 formula)
        assert abs(std_dev - 2.14) < 0.1

    def test_calculate_std_dev_insufficient(
        self, filter_instance: AdvancedArbitrageFilter
    ) -> None:
        """Test std dev with insufficient data."""
        std_dev = filter_instance._calculate_std_dev([1.0], 1.0)
        assert std_dev == 0.0


class TestConfigLoading:
    """Tests for configuration loading."""

    def test_load_filter_config_missing_file(self, tmp_path: Any) -> None:
        """Test loading config from missing file uses defaults."""
        config = load_filter_config_from_yaml(str(tmp_path / "nonexistent.yaml"))

        assert config.min_avg_price == 0.50
        assert config.enable_category_filter is True

    def test_load_category_filters_missing_file(self, tmp_path: Any) -> None:
        """Test loading category filters from missing file uses defaults."""
        bad, good = load_category_filters_from_yaml(str(tmp_path / "nonexistent.yaml"))

        assert bad == DEFAULT_BAD_CATEGORIES
        assert good == DEFAULT_GOOD_CATEGORIES

    def test_load_filter_config_valid_file(self, tmp_path: Any) -> None:
        """Test loading config from valid YAML file."""
        config_content = """
arbitrage_filters:
  MIN_AVG_PRICE: 1.0
  GOOD_POINTS_PERCENT: 90
  ENABLE_CATEGORY_FILTER: false
"""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text(config_content)

        config = load_filter_config_from_yaml(str(config_file))

        assert config.min_avg_price == 1.0
        assert config.good_points_percent == 90.0
        assert config.enable_category_filter is False

    def test_load_category_filters_valid_file(self, tmp_path: Any) -> None:
        """Test loading category filters from valid YAML file."""
        config_content = """
bad_items:
  - "TestBad1"
  - "TestBad2"
good_categories:
  - "TestGood1"
"""
        config_file = tmp_path / "test_filters.yaml"
        config_file.write_text(config_content)

        bad, good = load_category_filters_from_yaml(str(config_file))

        assert "TestBad1" in bad
        assert "TestBad2" in bad
        assert "TestGood1" in good
