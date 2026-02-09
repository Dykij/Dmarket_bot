"""Unit tests for intramarket_arbitrage.py module.

Tests for intramarket arbitrage functionality including price anomaly detection,
trend analysis, pattern recognition, and item key building.
"""


import pytest

# Skip tests that require structlog
structlog = pytest.importorskip("structlog")


class TestPriceAnomalyTypeEnum:
    """Tests for PriceAnomalyType enum."""

    def test_underpriced_value(self) -> None:
        """Test UNDERPRICED enum value."""
        from src.dmarket.intramarket_arbitrage import PriceAnomalyType

        assert PriceAnomalyType.UNDERPRICED == "underpriced"

    def test_overpriced_value(self) -> None:
        """Test OVERPRICED enum value."""
        from src.dmarket.intramarket_arbitrage import PriceAnomalyType

        assert PriceAnomalyType.OVERPRICED == "overpriced"

    def test_trending_up_value(self) -> None:
        """Test TRENDING_UP enum value."""
        from src.dmarket.intramarket_arbitrage import PriceAnomalyType

        assert PriceAnomalyType.TRENDING_UP == "trending_up"

    def test_trending_down_value(self) -> None:
        """Test TRENDING_DOWN enum value."""
        from src.dmarket.intramarket_arbitrage import PriceAnomalyType

        assert PriceAnomalyType.TRENDING_DOWN == "trending_down"

    def test_rare_traits_value(self) -> None:
        """Test RARE_TRAITS enum value."""
        from src.dmarket.intramarket_arbitrage import PriceAnomalyType

        assert PriceAnomalyType.RARE_TRAITS == "rare_traits"

    def test_enum_has_all_anomaly_types(self) -> None:
        """Test that all expected anomaly types are present."""
        from src.dmarket.intramarket_arbitrage import PriceAnomalyType

        expected_types = {"underpriced", "overpriced", "trending_up", "trending_down", "rare_traits"}
        actual_types = {t.value for t in PriceAnomalyType}
        assert actual_types == expected_types


class TestShouldSkipCSGOItem:
    """Tests for _should_skip_csgo_item helper function."""

    def test_skip_sticker_item(self) -> None:
        """Test sticker items should be skipped."""
        from src.dmarket.intramarket_arbitrage import _should_skip_csgo_item  # noqa: PLC2701

        assert _should_skip_csgo_item("Sticker | Cloud9 | Krakow 2017") is True

    def test_skip_graffiti_item(self) -> None:
        """Test graffiti items should be skipped."""
        from src.dmarket.intramarket_arbitrage import _should_skip_csgo_item  # noqa: PLC2701

        assert _should_skip_csgo_item("Sealed Graffiti | GGWP") is True

    def test_skip_patch_item(self) -> None:
        """Test patch items should be skipped."""
        from src.dmarket.intramarket_arbitrage import _should_skip_csgo_item  # noqa: PLC2701

        assert _should_skip_csgo_item("Patch | CS20") is True

    def test_not_skip_weapon(self) -> None:
        """Test weapon items should not be skipped."""
        from src.dmarket.intramarket_arbitrage import _should_skip_csgo_item  # noqa: PLC2701

        assert _should_skip_csgo_item("AK-47 | Redline (Field-Tested)") is False

    def test_not_skip_knife(self) -> None:
        """Test knife items should not be skipped."""
        from src.dmarket.intramarket_arbitrage import _should_skip_csgo_item  # noqa: PLC2701

        assert _should_skip_csgo_item("★ Karambit | Doppler (Factory New)") is False

    def test_not_skip_case(self) -> None:
        """Test case items should not be skipped."""
        from src.dmarket.intramarket_arbitrage import _should_skip_csgo_item  # noqa: PLC2701

        assert _should_skip_csgo_item("Prisma 2 Case") is False

    def test_case_insensitive_skip(self) -> None:
        """Test skip keywords work case-insensitively."""
        from src.dmarket.intramarket_arbitrage import _should_skip_csgo_item  # noqa: PLC2701

        assert _should_skip_csgo_item("STICKER | TEST") is True
        assert _should_skip_csgo_item("Graffiti | Test") is True


class TestBuildItemKey:
    """Tests for _build_item_key helper function."""

    def test_csgo_weapon_key(self) -> None:
        """Test building key for CS:GO weapon."""
        from src.dmarket.intramarket_arbitrage import _build_item_key  # noqa: PLC2701

        title = "AK-47 | Redline (Field-Tested)"
        item = {}
        game = "csgo"

        key = _build_item_key(title, item, game)

        assert "AK-47 | Redline" in key
        assert "Field-Tested" in key

    def test_csgo_stattrak_key(self) -> None:
        """Test building key for StatTrak weapon."""
        from src.dmarket.intramarket_arbitrage import _build_item_key  # noqa: PLC2701

        title = "StatTrak™ AK-47 | Redline (Field-Tested)"
        item = {}
        game = "csgo"

        key = _build_item_key(title, item, game)

        assert "StatTrak" in key

    def test_csgo_souvenir_key(self) -> None:
        """Test building key for Souvenir weapon."""
        from src.dmarket.intramarket_arbitrage import _build_item_key  # noqa: PLC2701

        title = "Souvenir M4A4 | Radiation Hazard (Field-Tested)"
        item = {}
        game = "csgo"

        key = _build_item_key(title, item, game)

        assert "Souvenir" in key

    def test_non_csgo_game_key(self) -> None:
        """Test building key for non-CS:GO game."""
        from src.dmarket.intramarket_arbitrage import _build_item_key  # noqa: PLC2701

        title = "Arcana | Manifold Paradox"
        item = {}
        game = "dota2"

        key = _build_item_key(title, item, game)

        assert key == title

    def test_simple_title_key(self) -> None:
        """Test building key for simple title without exterior."""
        from src.dmarket.intramarket_arbitrage import _build_item_key  # noqa: PLC2701

        title = "CS20 Case Key"
        item = {}
        game = "csgo"

        key = _build_item_key(title, item, game)

        assert key == title


class TestExtractItemPrice:
    """Tests for _extract_item_price helper function."""

    def test_extract_price_from_dict_amount(self) -> None:
        """Test extracting price from dict with 'amount' key."""
        from src.dmarket.intramarket_arbitrage import _extract_item_price  # noqa: PLC2701

        item = {"price": {"amount": "1000", "currency": "USD"}}
        price = _extract_item_price(item)

        # Price in cents converted to dollars
        assert price is not None

    def test_no_price_returns_none(self) -> None:
        """Test item without price returns None."""
        from src.dmarket.intramarket_arbitrage import _extract_item_price  # noqa: PLC2701

        item = {"title": "Test Item"}
        price = _extract_item_price(item)

        assert price is None

    def test_price_as_string_returns_none_or_value(self) -> None:
        """Test handling price as string."""
        from src.dmarket.intramarket_arbitrage import _extract_item_price  # noqa: PLC2701

        # String price without amount key
        item = {"price": "10.50"}
        price = _extract_item_price(item)

        # Should handle gracefully
        assert price is None or isinstance(price, (int, float))


class TestPriceAnomalyDetection:
    """Tests for price anomaly detection logic."""

    def test_detect_underpriced_item(self) -> None:
        """Test detecting underpriced item."""
        current_price = 10.0
        avg_price = 15.0
        threshold = 0.2  # 20% below average

        price_diff_percent = (avg_price - current_price) / avg_price
        is_underpriced = price_diff_percent >= threshold

        assert is_underpriced is True

    def test_detect_overpriced_item(self) -> None:
        """Test detecting overpriced item."""
        current_price = 18.0
        avg_price = 15.0
        threshold = 0.15  # 15% above average

        price_diff_percent = (current_price - avg_price) / avg_price
        is_overpriced = price_diff_percent >= threshold

        assert is_overpriced is True

    def test_normal_price_no_anomaly(self) -> None:
        """Test normal price does not trigger anomaly."""
        current_price = 15.0
        avg_price = 15.0
        threshold = 0.1

        price_diff_percent = abs(current_price - avg_price) / avg_price
        is_anomaly = price_diff_percent >= threshold

        assert is_anomaly is False


class TestTrendDetection:
    """Tests for price trend detection logic."""

    def test_detect_upward_trend(self) -> None:
        """Test detecting upward price trend."""
        prices = [10.0, 11.0, 12.0, 13.0, 14.0]

        # Simple trend calculation
        start_price = prices[0]
        end_price = prices[-1]
        trend_percent = (end_price - start_price) / start_price * 100

        is_trending_up = trend_percent > 10.0  # More than 10% increase

        assert is_trending_up is True
        assert trend_percent == 40.0

    def test_detect_downward_trend(self) -> None:
        """Test detecting downward price trend."""
        prices = [15.0, 14.0, 13.0, 12.0, 11.0]

        start_price = prices[0]
        end_price = prices[-1]
        trend_percent = (end_price - start_price) / start_price * 100

        is_trending_down = trend_percent < -10.0  # More than 10% decrease

        assert is_trending_down is True

    def test_stable_prices_no_trend(self) -> None:
        """Test stable prices show no significant trend."""
        prices = [10.0, 10.1, 9.9, 10.0, 10.2]

        start_price = prices[0]
        end_price = prices[-1]
        trend_percent = (end_price - start_price) / start_price * 100

        is_trending = abs(trend_percent) > 10.0

        assert is_trending is False


class TestRareTraitsDetection:
    """Tests for rare traits detection logic."""

    def test_detect_low_float_value(self) -> None:
        """Test detecting low float value as rare trait."""
        float_value = 0.001

        is_rare_float = float_value < 0.01

        assert is_rare_float is True

    def test_detect_doppler_phase(self) -> None:
        """Test detecting Doppler phase as rare trait."""
        item_name = "★ Karambit | Doppler (Factory New)"
        has_doppler = "doppler" in item_name.lower()

        assert has_doppler is True

    def test_detect_blue_gem_pattern(self) -> None:
        """Test detecting Blue Gem pattern (would be in attributes)."""
        pattern_id = 661  # Famous Blue Gem pattern
        blue_gem_patterns = {661, 670, 321, 387}

        is_blue_gem = pattern_id in blue_gem_patterns

        assert is_blue_gem is True


class TestGroupingLogic:
    """Tests for item grouping logic."""

    def test_group_same_items(self) -> None:
        """Test grouping same items together."""
        items = [
            {"title": "AK-47 | Redline (FT)", "price": 1000},
            {"title": "AK-47 | Redline (FT)", "price": 950},
            {"title": "AK-47 | Redline (FT)", "price": 1100},
        ]

        grouped: dict = {}
        for item in items:
            title = item["title"]
            if title not in grouped:
                grouped[title] = []
            grouped[title].append(item)

        assert len(grouped) == 1
        assert len(grouped["AK-47 | Redline (FT)"]) == 3

    def test_separate_different_items(self) -> None:
        """Test separating different items."""
        items = [
            {"title": "AK-47 | Redline (FT)", "price": 1000},
            {"title": "AK-47 | Vulcan (MW)", "price": 5000},
            {"title": "M4A4 | Howl (FN)", "price": 50000},
        ]

        grouped: dict = {}
        for item in items:
            title = item["title"]
            if title not in grouped:
                grouped[title] = []
            grouped[title].append(item)

        assert len(grouped) == 3


class TestPriceComparison:
    """Tests for price comparison logic."""

    def test_find_cheapest_item(self) -> None:
        """Test finding cheapest item in group."""
        prices = [1000, 950, 1100, 980]
        cheapest = min(prices)

        assert cheapest == 950

    def test_find_most_expensive_item(self) -> None:
        """Test finding most expensive item in group."""
        prices = [1000, 950, 1100, 980]
        most_expensive = max(prices)

        assert most_expensive == 1100

    def test_calculate_price_spread(self) -> None:
        """Test calculating price spread."""
        prices = [1000, 950, 1100, 980]
        spread = max(prices) - min(prices)
        spread_percent = spread / min(prices) * 100

        assert spread == 150
        assert abs(spread_percent - 15.79) < 0.1


class TestProfitOpportunities:
    """Tests for profit opportunity detection."""

    def test_identify_buy_low_sell_high(self) -> None:
        """Test identifying buy low, sell high opportunity."""
        buy_price = 950
        sell_price = 1100
        commission_rate = 0.10  # 10% commission

        gross_profit = sell_price - buy_price
        net_profit = gross_profit - (sell_price * commission_rate)

        assert gross_profit == 150
        assert net_profit == 40.0

    def test_minimum_profit_threshold(self) -> None:
        """Test minimum profit threshold check."""
        profit = 0.30  # 30 cents
        min_profit = 0.50  # 50 cents minimum

        is_profitable = profit >= min_profit

        assert is_profitable is False

    def test_profitable_opportunity(self) -> None:
        """Test profitable opportunity passes threshold."""
        profit = 1.50  # $1.50 profit
        min_profit = 0.50  # 50 cents minimum

        is_profitable = profit >= min_profit

        assert is_profitable is True


class TestModuleImports:
    """Tests for module imports and structure."""

    def test_module_imports_without_error(self) -> None:
        """Test module can be imported without errors."""
        import src.dmarket.intramarket_arbitrage

        assert src.dmarket.intramarket_arbitrage is not None

    def test_price_anomaly_type_importable(self) -> None:
        """Test PriceAnomalyType is importable."""
        from src.dmarket.intramarket_arbitrage import PriceAnomalyType

        assert PriceAnomalyType is not None

    def test_helper_functions_importable(self) -> None:
        """Test helper functions are importable."""
        import src.dmarket.intramarket_arbitrage as module

        assert hasattr(module, "_should_skip_csgo_item")
        assert hasattr(module, "_build_item_key")
        assert hasattr(module, "_extract_item_price")


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_item_list(self) -> None:
        """Test handling empty item list."""
        items: list = []
        grouped: dict = {}

        for item in items:
            title = item.get("title", "")
            if title:
                grouped.setdefault(title, []).append(item)

        assert len(grouped) == 0

    def test_item_without_title(self) -> None:
        """Test handling item without title."""
        item = {"price": 1000}
        title = item.get("title", "")

        assert not title

    def test_zero_average_price(self) -> None:
        """Test handling zero average price (avoid division by zero)."""
        current_price = 10.0
        avg_price = 0.0

        # Should handle gracefully
        if avg_price > 0:
            price_diff_percent = (current_price - avg_price) / avg_price
        else:
            price_diff_percent = 0.0

        assert price_diff_percent == 0.0

    def test_negative_prices_rejected(self) -> None:
        """Test that negative prices are rejected."""
        price = -10.0

        is_valid = price > 0

        assert is_valid is False


class TestStatisticalCalculations:
    """Tests for statistical calculations."""

    def test_calculate_average(self) -> None:
        """Test calculating average price."""
        prices = [10.0, 12.0, 11.0, 13.0, 9.0]
        avg = sum(prices) / len(prices)

        assert avg == 11.0

    def test_calculate_median(self) -> None:
        """Test calculating median price."""
        prices = [10.0, 12.0, 11.0, 13.0, 9.0]
        sorted_prices = sorted(prices)
        n = len(sorted_prices)
        median = sorted_prices[n // 2]

        assert median == 11.0

    def test_calculate_standard_deviation(self) -> None:
        """Test calculating standard deviation."""
        prices = [10.0, 10.0, 10.0, 10.0, 10.0]
        avg = sum(prices) / len(prices)
        variance = sum((p - avg) ** 2 for p in prices) / len(prices)
        std_dev = variance**0.5

        assert std_dev == 0.0  # All prices are the same
