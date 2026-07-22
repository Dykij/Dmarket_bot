"""Tests for supply_tracking.py — DMarket supply monitoring."""

from __future__ import annotations

from src.core.supply_tracking import SupplyMetrics, SupplyTracker


class TestSupplyMetrics:

    def test_is_liquid_true(self):
        m = SupplyMetrics(ask_count=5, bid_count=2)
        assert m.is_liquid is True

    def test_is_liquid_false_low_asks(self):
        m = SupplyMetrics(ask_count=2, bid_count=2)
        assert m.is_liquid is False

    def test_is_liquid_false_no_bids(self):
        m = SupplyMetrics(ask_count=5, bid_count=0)
        assert m.is_liquid is False


class TestSupplyTracker:

    def test_analyze_supply_thin_market(self):
        tracker = SupplyTracker()
        m = tracker.analyze_supply("Item A", ask_count=2, bid_count=1)
        assert m.is_thin_market is True
        assert m.margin_boost_pct == 3.0

    def test_analyze_supply_liquid_market(self):
        tracker = SupplyTracker()
        m = tracker.analyze_supply("Item B", ask_count=20, bid_count=5)
        assert m.is_thin_market is False
        assert m.margin_boost_pct == 0.0

    def test_analyze_supply_moderate_thin(self):
        tracker = SupplyTracker()
        m = tracker.analyze_supply("Item C", ask_count=4, bid_count=1)
        assert m.is_thin_market is True
        assert m.margin_boost_pct == 1.5

    def test_analyze_supply_slightly_thin(self):
        tracker = SupplyTracker()
        m = tracker.analyze_supply("Item D", ask_count=8, bid_count=2)
        assert m.margin_boost_pct == 0.5

    def test_supply_ratio(self):
        tracker = SupplyTracker()
        m = tracker.analyze_supply("Item E", ask_count=3, bid_count=7)
        assert m.supply_ratio == 0.3

    def test_supply_ratio_zero_total(self):
        tracker = SupplyTracker()
        m = tracker.analyze_supply("Item F", ask_count=0, bid_count=0)
        assert m.supply_ratio == 0.5

    def test_analyze_batch(self):
        tracker = SupplyTracker()
        agg = {
            "Item A": {"ask_count": 2, "bid_count": 1},
            "Item B": {"ask_count": 20, "bid_count": 5},
        }
        results = tracker.analyze_batch(agg)
        assert len(results) == 2
        assert results["Item A"].is_thin_market is True
        assert results["Item B"].is_thin_market is False

    def test_get_thin_market_items(self):
        tracker = SupplyTracker()
        tracker.analyze_supply("Thin", ask_count=2, bid_count=1)
        tracker.analyze_supply("Liquid", ask_count=20, bid_count=5)
        thin = tracker.get_thin_market_items(min_boost_pct=1.0)
        assert len(thin) == 1
        assert thin[0].title == "Thin"

    def test_thin_market_count(self):
        tracker = SupplyTracker()
        tracker.analyze_supply("A", ask_count=2, bid_count=1)
        tracker.analyze_supply("B", ask_count=20, bid_count=5)
        assert tracker.thin_market_count == 1

    def test_get_supply_summary(self):
        tracker = SupplyTracker()
        tracker.analyze_supply("A", ask_count=2, bid_count=1)
        tracker.analyze_supply("B", ask_count=20, bid_count=5)
        summary = tracker.get_supply_summary()
        assert summary["total_items"] == 2
        assert summary["thin_market_items"] == 1
        assert summary["thin_market_pct"] == 50.0

    def test_supply_summary_empty(self):
        tracker = SupplyTracker()
        summary = tracker.get_supply_summary()
        assert summary["total_items"] == 0
        assert summary["thin_market_pct"] == 0
