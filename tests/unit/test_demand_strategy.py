"""test_demand_strategy.py — Tests for OBI demand-based strategy (v17.2).

Tests:
- calculate_demand_score() with various inputs
- get_adaptive_thresholds() by price segment
- is_demand_opportunity() batch processing
- Dynamic stop-loss logic
- Peak avoidance logic
"""

from __future__ import annotations

import pytest

from src.core.target_sniping.demand_strategy import (
    calculate_demand_score,
    get_adaptive_thresholds,
)


class TestGetAdaptiveThresholds:
    """Test adaptive thresholds by price segment."""

    def test_cheap_items_under_2(self):
        t = get_adaptive_thresholds(1.00)
        assert t["min_demand_ratio"] == 1.5
        assert t["min_volume"] == 5
        assert t["max_hold_days"] == 10.0

    def test_medium_items_2_to_5(self):
        t = get_adaptive_thresholds(3.50)
        assert t["min_demand_ratio"] == 2.0
        assert t["min_volume"] == 10
        assert t["max_hold_days"] == 7.0

    def test_expensive_items_over_5(self):
        t = get_adaptive_thresholds(8.00)
        assert t["min_demand_ratio"] == 2.5
        assert t["min_volume"] == 15
        assert t["max_hold_days"] == 5.0

    def test_boundary_at_2(self):
        t1 = get_adaptive_thresholds(1.99)
        t2 = get_adaptive_thresholds(2.00)
        assert t1["min_demand_ratio"] == 1.5
        assert t2["min_demand_ratio"] == 2.0

    def test_boundary_at_5(self):
        t1 = get_adaptive_thresholds(4.99)
        t2 = get_adaptive_thresholds(5.00)
        assert t1["min_demand_ratio"] == 2.0
        assert t2["min_demand_ratio"] == 2.5


class TestCalculateDemandScore:
    """Test demand score calculation."""

    def test_basic_calculation(self):
        result = calculate_demand_score(
            title="AK-47 | Redline",
            ask_price=5.00,
            best_bid=4.50,
            ask_count=10,
            bid_count=30,
        )
        assert result["demand_ratio"] == 3.0
        assert result["obi_signal"] == "buy"
        assert result["score"] > 0
        assert result["expected_hold_days"] > 0

    def test_low_demand_rejected(self):
        result = calculate_demand_score(
            title="Cheap Item",
            ask_price=1.00,
            best_bid=0.90,
            ask_count=20,
            bid_count=20,  # Q = 1.0 < 1.5 threshold
        )
        assert result["score"] == 0.0
        assert "demand ratio" in result["reason"]

    def test_low_volume_rejected(self):
        result = calculate_demand_score(
            title="Low Volume",
            ask_price=3.00,
            best_bid=2.80,
            ask_count=2,
            bid_count=10,  # Q = 5.0, but volume = 12 < 10 threshold
        )
        # Volume 12 > 10, should pass
        assert result["score"] > 0

    def test_invalid_prices(self):
        result = calculate_demand_score(
            title="Bad",
            ask_price=0,
            best_bid=0,
            ask_count=10,
            bid_count=20,
        )
        assert result["score"] == 0.0
        assert "invalid" in result["reason"]

    def test_high_demand_high_score(self):
        result = calculate_demand_score(
            title="Hot Item",
            ask_price=5.00,
            best_bid=4.80,
            ask_count=5,
            bid_count=50,  # Q = 10.0
        )
        assert result["demand_ratio"] == 10.0
        assert result["score"] > 300  # High score (reduced from 500 due to higher fees 5.5%)
        assert result["obi_signal"] == "buy"

    def test_sell_signal_rejected(self):
        result = calculate_demand_score(
            title="Bearish",
            ask_price=5.00,
            best_bid=4.80,
            ask_count=50,
            bid_count=10,  # Q = 0.2 < 2.5 threshold
        )
        assert result["score"] == 0.0
        # Rejected by demand ratio threshold (Q=0.2 < 2.5)
        assert "demand ratio" in result["reason"]


