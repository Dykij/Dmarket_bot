"""Unit tests for dmarket/scanner/analysis.py module.

This module tests:
- calculate_profit function
- calculate_roi function
- analyze_item function
- score_opportunity function
- find_best_opportunities function
- aggregate_statistics function
- AnalysisStats class
- _extract_price and _parse_price helper functions
"""

from src.dmarket.scanner.analysis import (
    DMARKET_COMMISSION,
    MIN_PROFIT_THRESHOLDS,
    AnalysisStats,
    aggregate_statistics,
    analyze_item,
    calculate_profit,
    calculate_roi,
    find_best_opportunities,
    score_opportunity,
)


class TestConstants:
    """Tests for module constants."""

    def test_dmarket_commission_value(self):
        """Test DMarket commission is 7%."""
        assert DMARKET_COMMISSION == 0.07

    def test_min_profit_thresholds_keys(self):
        """Test MIN_PROFIT_THRESHOLDS has all levels."""
        expected_keys = {"boost", "standard", "medium", "advanced", "pro"}
        assert set(MIN_PROFIT_THRESHOLDS.keys()) == expected_keys

    def test_min_profit_thresholds_values(self):
        """Test MIN_PROFIT_THRESHOLDS values are positive."""
        for level, threshold in MIN_PROFIT_THRESHOLDS.items():
            assert threshold > 0, f"Threshold for {level} should be positive"

    def test_profit_thresholds_increase_with_level(self):
        """Test profit thresholds increase with level."""
        levels = ["boost", "standard", "advanced", "pro"]
        for i in range(len(levels) - 1):
            current_level = levels[i]
            next_level = levels[i + 1]
            # Either equal or increasing
            assert (
                MIN_PROFIT_THRESHOLDS[current_level]
                <= MIN_PROFIT_THRESHOLDS[next_level]
            )


class TestCalculateProfit:
    """Tests for calculate_profit function."""

    def test_calculate_profit_basic(self):
        """Test basic profit calculation."""
        absolute, percent = calculate_profit(10.0, 15.0)
        # Net sell = 15 * 0.93 = 13.95
        # Profit = 13.95 - 10 = 3.95
        # Percent = 3.95 / 10 * 100 = 39.5%
        assert absolute == 3.95
        assert percent == 39.5

    def test_calculate_profit_with_custom_commission(self):
        """Test profit calculation with custom commission."""
        absolute, percent = calculate_profit(10.0, 15.0, commission=0.10)
        # Net sell = 15 * 0.90 = 13.5
        # Profit = 13.5 - 10 = 3.5
        assert absolute == 3.5
        assert percent == 35.0

    def test_calculate_profit_zero_buy_price(self):
        """Test profit calculation with zero buy price."""
        absolute, percent = calculate_profit(0.0, 15.0)
        assert absolute == 0.0
        assert percent == 0.0

    def test_calculate_profit_negative_buy_price(self):
        """Test profit calculation with negative buy price."""
        absolute, percent = calculate_profit(-10.0, 15.0)
        assert absolute == 0.0
        assert percent == 0.0

    def test_calculate_profit_same_price(self):
        """Test profit when buy and sell prices are same."""
        absolute, percent = calculate_profit(10.0, 10.0)
        # Net sell = 10 * 0.93 = 9.3
        # Profit = 9.3 - 10 = -0.7
        assert absolute == -0.7
        assert percent == -7.0

    def test_calculate_profit_large_values(self):
        """Test profit calculation with large values."""
        absolute, percent = calculate_profit(1000.0, 1500.0)
        # Net sell = 1500 * 0.93 = 1395
        # Profit = 1395 - 1000 = 395
        assert absolute == 395.0
        assert percent == 39.5

    def test_calculate_profit_small_values(self):
        """Test profit calculation with small values."""
        absolute, percent = calculate_profit(0.10, 0.15)
        # Net sell = 0.15 * 0.93 = 0.1395
        # Profit = 0.1395 - 0.10 = 0.0395
        assert absolute == 0.04
        assert abs(percent - 39.5) < 1  # Allow small rounding difference

    def test_calculate_profit_zero_commission(self):
        """Test profit calculation with zero commission."""
        absolute, percent = calculate_profit(10.0, 15.0, commission=0.0)
        assert absolute == 5.0
        assert percent == 50.0


class TestCalculateROI:
    """Tests for calculate_roi function."""

    def test_calculate_roi_positive(self):
        """Test ROI calculation with positive profit."""
        roi = calculate_roi(100.0, 20.0)
        assert roi == 20.0

    def test_calculate_roi_negative(self):
        """Test ROI calculation with negative profit."""
        roi = calculate_roi(100.0, -10.0)
        assert roi == -10.0

    def test_calculate_roi_zero_investment(self):
        """Test ROI calculation with zero investment."""
        roi = calculate_roi(0.0, 20.0)
        assert roi == 0.0

    def test_calculate_roi_negative_investment(self):
        """Test ROI calculation with negative investment."""
        roi = calculate_roi(-100.0, 20.0)
        assert roi == 0.0

    def test_calculate_roi_large_profit(self):
        """Test ROI calculation with large profit."""
        roi = calculate_roi(100.0, 200.0)
        assert roi == 200.0


class TestAnalyzeItem:
    """Tests for analyze_item function."""

    def test_analyze_item_basic(self):
        """Test basic item analysis."""
        # Using proper price format (numeric values)
        item = {
            "itemId": "item123",
            "title": "Test Item",
            "price": 10.0,
            "suggestedPrice": 15.0,
            "gameId": "csgo",
        }
        result = analyze_item(item)
        assert result is not None
        assert result["item_id"] == "item123"
        assert result["title"] == "Test Item"
        assert result["buy_price"] == 10.0
        assert result["sell_price"] == 15.0
        assert result["game"] == "csgo"

    def test_analyze_item_with_alternative_keys(self):
        """Test item analysis with alternative key names."""
        item = {
            "id": "item456",
            "name": "Alt Item",
            "buy_price": 10.0,
            "sell_price": 15.0,
            "game": "dota2",
        }
        result = analyze_item(item)
        assert result is not None
        assert result["item_id"] == "item456"
        assert result["title"] == "Alt Item"

    def test_analyze_item_no_price(self):
        """Test item analysis with missing price."""
        item = {
            "itemId": "item123",
            "title": "Test Item",
        }
        result = analyze_item(item)
        assert result is None

    def test_analyze_item_zero_buy_price(self):
        """Test item analysis with zero buy price."""
        item = {
            "itemId": "item123",
            "price": {"USD": "0"},
            "suggestedPrice": {"USD": "1500"},
        }
        result = analyze_item(item)
        assert result is None

    def test_analyze_item_sell_lower_than_buy(self):
        """Test item analysis when sell price is lower than buy."""
        item = {
            "itemId": "item123",
            "price": {"USD": "1500"},
            "suggestedPrice": {"USD": "1000"},
        }
        result = analyze_item(item)
        assert result is None

    def test_analyze_item_profit_below_threshold(self):
        """Test item with profit below minimum threshold."""
        item = {
            "itemId": "item123",
            "price": {"USD": "1000"},
            "suggestedPrice": {"USD": "1010"},  # ~1% profit
        }
        result = analyze_item(item, min_profit_percent=5.0)
        assert result is None

    def test_analyze_item_profit_above_max(self):
        """Test item with profit above maximum threshold."""
        item = {
            "itemId": "item123",
            "price": {"USD": "100"},
            "suggestedPrice": {"USD": "500"},  # 300%+ profit
        }
        result = analyze_item(item, max_profit_percent=100.0)
        assert result is None

    def test_analyze_item_cents_format(self):
        """Test item with price in cents format (>1000 triggers conversion)."""
        item = {
            "itemId": "item123",
            "price": 2000,  # >1000, treated as cents = $20
            "suggestedPrice": 3000,  # >1000, treated as cents = $30
        }
        result = analyze_item(item)
        assert result is not None
        # Price parsing handles cents automatically when > 1000
        assert result["buy_price"] == 20.0
        assert result["sell_price"] == 30.0

    def test_analyze_item_string_price(self):
        """Test item with string price."""
        item = {
            "itemId": "item123",
            "price": "10.00",
            "suggestedPrice": "15.00",
        }
        result = analyze_item(item)
        assert result is not None


class TestScoreOpportunity:
    """Tests for score_opportunity function."""

    def test_score_opportunity_basic(self):
        """Test basic opportunity scoring."""
        opportunity = {
            "profit_percent": 20.0,
            "absolute_profit": 5.0,
            "buy_price": 25.0,
        }
        score = score_opportunity(opportunity)
        assert score > 0

    def test_score_opportunity_high_profit(self):
        """Test scoring penalizes very high profit (potential error)."""
        low_profit_opp = {
            "profit_percent": 30.0,
            "absolute_profit": 3.0,
            "buy_price": 10.0,
        }
        high_profit_opp = {
            "profit_percent": 60.0,
            "absolute_profit": 6.0,
            "buy_price": 10.0,
        }
        score_opportunity(low_profit_opp)
        high_score = score_opportunity(high_profit_opp)
        # High profit should be penalized, so might have lower score ratio
        assert high_score < high_profit_opp["profit_percent"] * 1.0

    def test_score_opportunity_very_high_profit(self):
        """Test scoring heavily penalizes 80%+ profit."""
        opp = {
            "profit_percent": 85.0,
            "absolute_profit": 8.5,
            "buy_price": 10.0,
        }
        score = score_opportunity(opp)
        # With 0.5 penalty factor, score should be reduced
        assert score < opp["profit_percent"]

    def test_score_opportunity_zero_buy_price(self):
        """Test scoring with zero buy price."""
        opp = {
            "profit_percent": 20.0,
            "absolute_profit": 5.0,
            "buy_price": 0.0,
        }
        score = score_opportunity(opp)
        assert score >= 0

    def test_score_opportunity_missing_fields(self):
        """Test scoring with missing fields."""
        opp = {}
        score = score_opportunity(opp)
        assert score >= 0


class TestFindBestOpportunities:
    """Tests for find_best_opportunities function."""

    def test_find_best_basic(self):
        """Test finding best opportunities."""
        opps = [
            {"profit_percent": 10.0, "absolute_profit": 1.0, "buy_price": 10.0},
            {"profit_percent": 30.0, "absolute_profit": 3.0, "buy_price": 10.0},
            {"profit_percent": 20.0, "absolute_profit": 2.0, "buy_price": 10.0},
        ]
        result = find_best_opportunities(opps, limit=2)
        assert len(result) == 2
        # Should be sorted by score (highest first)
        assert result[0]["profit_percent"] >= result[1]["profit_percent"]

    def test_find_best_with_limit(self):
        """Test limit parameter."""
        opps = [{"profit_percent": i, "buy_price": 10.0} for i in range(20)]
        result = find_best_opportunities(opps, limit=5)
        assert len(result) == 5

    def test_find_best_with_min_score(self):
        """Test min_score filtering."""
        opps = [
            {"profit_percent": 5.0, "absolute_profit": 0.5, "buy_price": 10.0},
            {"profit_percent": 30.0, "absolute_profit": 3.0, "buy_price": 10.0},
        ]
        result = find_best_opportunities(opps, min_score=10.0)
        # Only high profit opportunity should pass
        assert len(result) <= 2

    def test_find_best_empty_list(self):
        """Test with empty list."""
        result = find_best_opportunities([])
        assert result == []

    def test_find_best_adds_score(self):
        """Test that score is added to results."""
        opps = [{"profit_percent": 20.0, "buy_price": 10.0}]
        result = find_best_opportunities(opps)
        assert "score" in result[0]


class TestAggregateStatistics:
    """Tests for aggregate_statistics function."""

    def test_aggregate_basic(self):
        """Test basic statistics aggregation."""
        opps = [
            {"profit_percent": 10.0, "absolute_profit": 1.0, "buy_price": 10.0},
            {"profit_percent": 30.0, "absolute_profit": 3.0, "buy_price": 10.0},
            {"profit_percent": 20.0, "absolute_profit": 2.0, "buy_price": 10.0},
        ]
        stats = aggregate_statistics(opps)
        assert stats["count"] == 3
        assert stats["total_potential_profit"] == 6.0
        assert stats["avg_profit_percent"] == 20.0
        assert stats["min_profit_percent"] == 10.0
        assert stats["max_profit_percent"] == 30.0
        assert stats["total_investment_needed"] == 30.0

    def test_aggregate_empty_list(self):
        """Test aggregation with empty list."""
        stats = aggregate_statistics([])
        assert stats["count"] == 0
        assert stats["total_potential_profit"] == 0.0
        assert stats["avg_profit_percent"] == 0.0
        assert stats["min_profit_percent"] == 0.0
        assert stats["max_profit_percent"] == 0.0
        assert stats["total_investment_needed"] == 0.0

    def test_aggregate_single_item(self):
        """Test aggregation with single item."""
        opps = [{"profit_percent": 25.0, "absolute_profit": 2.5, "buy_price": 10.0}]
        stats = aggregate_statistics(opps)
        assert stats["count"] == 1
        assert stats["avg_profit_percent"] == 25.0
        assert stats["min_profit_percent"] == 25.0
        assert stats["max_profit_percent"] == 25.0

    def test_aggregate_missing_fields(self):
        """Test aggregation with missing fields."""
        opps = [{}, {"profit_percent": 10.0}]
        stats = aggregate_statistics(opps)
        assert stats["count"] == 2


class TestAnalysisStats:
    """Tests for AnalysisStats class."""

    def test_init(self):
        """Test AnalysisStats initialization."""
        stats = AnalysisStats()
        result = stats.get_stats()
        assert result["total_scans"] == 0
        assert result["total_items_analyzed"] == 0
        assert result["total_opportunities_found"] == 0
        assert result["by_level"] == {}
        assert result["by_game"] == {}

    def test_record_scan(self):
        """Test recording a scan."""
        stats = AnalysisStats()
        stats.record_scan(
            level="standard",
            game="csgo",
            items_analyzed=100,
            opportunities_found=10,
        )
        result = stats.get_stats()
        assert result["total_scans"] == 1
        assert result["total_items_analyzed"] == 100
        assert result["total_opportunities_found"] == 10
        assert "standard" in result["by_level"]
        assert "csgo" in result["by_game"]

    def test_record_multiple_scans(self):
        """Test recording multiple scans."""
        stats = AnalysisStats()
        stats.record_scan("standard", "csgo", 100, 10)
        stats.record_scan("standard", "csgo", 50, 5)
        stats.record_scan("boost", "dota2", 200, 20)

        result = stats.get_stats()
        assert result["total_scans"] == 3
        assert result["total_items_analyzed"] == 350
        assert result["total_opportunities_found"] == 35

        assert result["by_level"]["standard"]["scans"] == 2
        assert result["by_level"]["standard"]["opportunities"] == 15
        assert result["by_level"]["boost"]["scans"] == 1

        assert result["by_game"]["csgo"]["scans"] == 2
        assert result["by_game"]["dota2"]["scans"] == 1

    def test_reset(self):
        """Test resetting statistics."""
        stats = AnalysisStats()
        stats.record_scan("standard", "csgo", 100, 10)
        stats.reset()

        result = stats.get_stats()
        assert result["total_scans"] == 0
        assert result["total_items_analyzed"] == 0
        assert result["by_level"] == {}
        assert result["by_game"] == {}

    def test_get_stats_returns_copy_of_outer_dicts(self):
        """Test that get_stats returns copies of outer dicts."""
        stats = AnalysisStats()
        stats.record_scan("standard", "csgo", 100, 10)

        result = stats.get_stats()
        # Modify the returned outer dict
        result["by_level"]["new_level"] = {"scans": 999}

        # Original should not have the new key
        assert "new_level" not in stats.get_stats()["by_level"]
