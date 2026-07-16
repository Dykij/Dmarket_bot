"""Unit tests for event_detection.py and supply_tracking.py (v15.7)."""

from __future__ import annotations

import time
from unittest.mock import MagicMock

import pytest

from src.core.event_detection import CS2Event, EventDetector, EventImpact
from src.core.supply_tracking import SupplyMetrics, SupplyTracker


# =====================================================================
# Event Detection Tests
# =====================================================================


class TestCS2Event:
    """Tests for CS2Event dataclass."""

    def test_is_active_when_not_expired(self) -> None:
        event = CS2Event(
            event_type="update",
            title="Test",
            expires_at=time.time() + 3600,
        )
        assert event.is_active is True

    def test_is_active_when_expired(self) -> None:
        event = CS2Event(
            event_type="update",
            title="Test",
            expires_at=time.time() - 1,
        )
        assert event.is_active is False


class TestEventDetector:
    """Tests for EventDetector."""

    def test_init(self) -> None:
        detector = EventDetector()
        assert detector.active_event_count == 0

    def test_bind(self) -> None:
        detector = EventDetector()
        mock_db = MagicMock()
        detector.bind(mock_db)
        assert detector._price_db is mock_db

    def test_detect_events_no_db(self) -> None:
        detector = EventDetector()
        events = detector.detect_events()
        assert events == []

    def test_get_item_impact_no_events(self) -> None:
        detector = EventDetector()
        impact = detector.get_item_impact("AK-47 | Redline (FT)")
        assert impact.event_multiplier == 1.0
        assert impact.active_events == 0

    def test_get_item_impact_with_event(self) -> None:
        detector = EventDetector()
        detector._active_events = [
            CS2Event(
                event_type="volume_spike",
                title="Spike: AK-47",
                impact_estimate=10.0,
                affected_categories=["AK-47 | Redline (FT)"],
                expires_at=time.time() + 3600,
            )
        ]
        impact = detector.get_item_impact("AK-47 | Redline (FT)")
        assert impact.active_events == 1
        assert impact.event_multiplier == pytest.approx(1.10)

    def test_get_item_impact_negative_event(self) -> None:
        detector = EventDetector()
        detector._active_events = [
            CS2Event(
                event_type="new_case",
                title="New case released",
                impact_estimate=-5.0,
                affected_categories=["AK-47 | Redline (FT)"],
                expires_at=time.time() + 3600,
            )
        ]
        impact = detector.get_item_impact("AK-47 | Redline (FT)")
        assert impact.event_multiplier == pytest.approx(0.95)

    def test_merge_events_dedup(self) -> None:
        detector = EventDetector()
        existing = [
            CS2Event(event_type="update", title="Event A", expires_at=time.time() + 3600)
        ]
        new = [
            CS2Event(event_type="update", title="Event A", expires_at=time.time() + 3600),
            CS2Event(event_type="update", title="Event B", expires_at=time.time() + 3600),
        ]
        merged = detector._merge_events(existing, new)
        assert len(merged) == 2  # A deduplicated, B added

    def test_merge_events_expire_old(self) -> None:
        detector = EventDetector()
        existing = [
            CS2Event(event_type="update", title="Old", expires_at=time.time() - 1),
            CS2Event(event_type="update", title="Active", expires_at=time.time() + 3600),
        ]
        merged = detector._merge_events(existing, [])
        assert len(merged) == 1
        assert merged[0].title == "Active"


class TestEventImpact:
    """Tests for EventImpact dataclass."""

    def test_defaults(self) -> None:
        impact = EventImpact()
        assert impact.event_multiplier == 1.0
        assert impact.active_events == 0


# =====================================================================
# Supply Tracking Tests
# =====================================================================


class TestSupplyMetrics:
    """Tests for SupplyMetrics dataclass."""

    def test_is_liquid_with_enough_listings(self) -> None:
        m = SupplyMetrics(title="test", ask_count=5, bid_count=3)
        assert m.is_liquid is True

    def test_is_liquid_with_few_listings(self) -> None:
        m = SupplyMetrics(title="test", ask_count=1, bid_count=0)
        assert m.is_liquid is False

    def test_is_liquid_with_no_bids(self) -> None:
        m = SupplyMetrics(title="test", ask_count=10, bid_count=0)
        assert m.is_liquid is False


class TestSupplyTracker:
    """Tests for SupplyTracker."""

    def test_analyze_supply_thin_market(self) -> None:
        tracker = SupplyTracker()
        metrics = tracker.analyze_supply("test", ask_count=2, bid_count=5)
        assert metrics.is_thin_market is True
        assert metrics.margin_boost_pct == 3.0

    def test_analyze_supply_liquid_market(self) -> None:
        tracker = SupplyTracker()
        metrics = tracker.analyze_supply("test", ask_count=20, bid_count=10)
        assert metrics.is_thin_market is False
        assert metrics.margin_boost_pct == 0.0

    def test_analyze_supply_moderate_thin(self) -> None:
        tracker = SupplyTracker()
        metrics = tracker.analyze_supply("test", ask_count=4, bid_count=3)
        assert metrics.margin_boost_pct == 1.5

    def test_analyze_supply_ratio(self) -> None:
        tracker = SupplyTracker()
        metrics = tracker.analyze_supply("test", ask_count=8, bid_count=2)
        assert metrics.supply_ratio == pytest.approx(0.8)

    def test_analyze_batch(self) -> None:
        tracker = SupplyTracker()
        agg = {
            "Item A": {"ask_count": 3, "bid_count": 8},
            "Item B": {"ask_count": 20, "bid_count": 10},
        }
        results = tracker.analyze_batch(agg)
        assert len(results) == 2
        assert results["Item A"].is_thin_market is True
        assert results["Item B"].is_thin_market is False

    def test_get_thin_market_items(self) -> None:
        tracker = SupplyTracker()
        tracker.analyze_supply("Thin", ask_count=2, bid_count=5)
        tracker.analyze_supply("Liquid", ask_count=20, bid_count=10)
        thin = tracker.get_thin_market_items(min_boost_pct=1.0)
        assert len(thin) == 1
        assert thin[0].title == "Thin"

    def test_thin_market_count(self) -> None:
        tracker = SupplyTracker()
        tracker.analyze_supply("A", ask_count=2, bid_count=5)
        tracker.analyze_supply("B", ask_count=20, bid_count=10)
        assert tracker.thin_market_count == 1

    def test_get_supply_summary(self) -> None:
        tracker = SupplyTracker()
        tracker.analyze_supply("A", ask_count=2, bid_count=5)
        tracker.analyze_supply("B", ask_count=20, bid_count=10)
        summary = tracker.get_supply_summary()
        assert summary["total_items"] == 2
        assert summary["thin_market_items"] == 1
        assert summary["thin_market_pct"] == pytest.approx(50.0)
