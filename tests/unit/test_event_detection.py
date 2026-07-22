"""Tests for event_detection.py — CS2 event detection."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from src.core.event_detection import CS2Event, EventDetector, EventImpact


class TestCS2Event:

    def test_is_active_true(self):
        e = CS2Event(event_type="update", expires_at=time.time() + 3600)
        assert e.is_active is True

    def test_is_active_false(self):
        e = CS2Event(event_type="update", expires_at=time.time() - 1)
        assert e.is_active is False

    def test_default_values(self):
        e = CS2Event(event_type="tournament")
        assert e.title == ""
        assert e.impact_estimate == 0.0
        assert e.affected_categories == []


class TestEventImpact:

    def test_default_multiplier(self):
        ei = EventImpact(title="AK-47")
        assert ei.event_multiplier == 1.0
        assert ei.active_events == 0


class TestEventDetector:

    def test_init(self):
        d = EventDetector()
        assert d._active_events == []
        assert d._last_scan_ts == 0.0

    def test_bind(self):
        d = EventDetector()
        mock_db = MagicMock()
        d.bind(mock_db)
        assert d._price_db is mock_db

    def test_detect_events_no_db(self):
        d = EventDetector()
        events = d.detect_events()
        assert events == []

    def test_get_item_impact_no_events(self):
        d = EventDetector()
        impact = d.get_item_impact("AK-47 | Redline")
        assert impact.event_multiplier == 1.0
        assert impact.active_events == 0

    def test_get_item_impact_with_active_event(self):
        d = EventDetector()
        e = CS2Event(
            event_type="update",
            title="CS2 Update",
            impact_estimate=5.0,
            affected_categories=[],  # empty = affects all items
            expires_at=time.time() + 3600,
        )
        d._active_events = [e]
        impact = d.get_item_impact("AK-47 | Redline")
        assert impact.active_events == 1
        assert impact.event_multiplier > 1.0

    def test_active_event_count(self):
        d = EventDetector()
        assert d.active_event_count == 0
        d._active_events = [CS2Event(event_type="update", expires_at=time.time() + 3600)]
        assert d.active_event_count == 1

    def test_detect_events_too_soon_returns_cache(self):
        """If called within scan_interval, returns cached events (line 83-84)."""
        d = EventDetector()
        d._last_scan_ts = time.time()  # just scanned
        d._scan_interval = 300.0
        d._active_events = [CS2Event(event_type="test", expires_at=time.time() + 3600)]
        events = d.detect_events()
        assert len(events) == 1

    def test_detect_events_no_price_db(self):
        """No price_db returns empty (line 89-90)."""
        d = EventDetector()
        d._price_db = None
        d._last_scan_ts = 0.0
        events = d.detect_events()
        assert events == []

    def test_detect_events_volume_spike(self):
        """Volume spike detection (lines 93-105)."""
        d = EventDetector()
        mock_db = MagicMock()
        # Return 25 trades for same item (threshold is 20)
        trades = [{"title": "AK-47", "price": 10.0}] * 25
        mock_db.get_trade_history.return_value = trades
        mock_db.get_recent_prices.return_value = []
        d.bind(mock_db)
        d._last_scan_ts = 0.0

        events = d.detect_events()
        assert len(events) >= 1
        assert events[0].event_type == "volume_spike"

    def test_detect_events_no_volume_spikes(self):
        """No volume spikes when trade count is low (line 181)."""
        d = EventDetector()
        mock_db = MagicMock()
        trades = [{"title": "AK-47", "price": 10.0}] * 5  # below threshold
        mock_db.get_trade_history.return_value = trades
        mock_db.get_recent_prices.return_value = []
        d.bind(mock_db)
        d._last_scan_ts = 0.0

        events = d.detect_events()
        assert len(events) == 0

    def test_detect_events_empty_trades(self):
        """Empty trade history returns no events (line 169-170)."""
        d = EventDetector()
        mock_db = MagicMock()
        mock_db.get_trade_history.return_value = []
        mock_db.get_recent_prices.return_value = []
        d.bind(mock_db)
        d._last_scan_ts = 0.0

        events = d.detect_events()
        assert len(events) == 0

    def test_detect_events_exception_handled(self):
        """Exception in volume spike detection is caught (line 106-107)."""
        d = EventDetector()
        mock_db = MagicMock()
        mock_db.get_trade_history.side_effect = Exception("db error")
        mock_db.get_recent_prices.return_value = []
        d.bind(mock_db)
        d._last_scan_ts = 0.0

        events = d.detect_events()
        assert events == []

    def test_merge_events_removes_expired(self):
        """Expired events are removed during merge (line 213)."""
        d = EventDetector()
        existing = [CS2Event(event_type="old", title="expired", expires_at=time.time() - 1)]
        new = [CS2Event(event_type="new", title="fresh", expires_at=time.time() + 3600)]
        merged = d._merge_events(existing, new)
        assert len(merged) == 1
        assert merged[0].title == "fresh"

    def test_merge_events_deduplicates(self):
        """Duplicate titles are not added twice (lines 216-218)."""
        d = EventDetector()
        existing = [CS2Event(event_type="test", title="Same", expires_at=time.time() + 3600)]
        new = [CS2Event(event_type="test", title="Same", expires_at=time.time() + 3600)]
        merged = d._merge_events(existing, new)
        assert len(merged) == 1

    def test_merge_events_adds_new(self):
        """New events with different titles are added (line 219)."""
        d = EventDetector()
        existing = [CS2Event(event_type="test", title="A", expires_at=time.time() + 3600)]
        new = [CS2Event(event_type="test", title="B", expires_at=time.time() + 3600)]
        merged = d._merge_events(existing, new)
        assert len(merged) == 2

    def test_get_item_impact_negative_estimate(self):
        """Negative impact estimate reduces multiplier (lines 150-152)."""
        d = EventDetector()
        e = CS2Event(
            event_type="crash",
            title="Market Crash",
            impact_estimate=-10.0,
            affected_categories=[],
            expires_at=time.time() + 3600,
        )
        d._active_events = [e]
        impact = d.get_item_impact("AK-47")
        assert impact.event_multiplier < 1.0
        assert "Negative" in impact.reason

    def test_get_item_impact_expired_event_skipped(self):
        """Expired events are skipped in get_item_impact (line 142-143)."""
        d = EventDetector()
        e = CS2Event(
            event_type="old",
            title="Expired",
            impact_estimate=50.0,
            affected_categories=[],
            expires_at=time.time() - 1,
        )
        d._active_events = [e]
        impact = d.get_item_impact("AK-47")
        assert impact.active_events == 0
        assert impact.event_multiplier == 1.0

    def test_get_item_impact_category_mismatch_skipped(self):
        """Events with non-matching categories are skipped (line 144)."""
        d = EventDetector()
        e = CS2Event(
            event_type="update",
            title="Knife Update",
            impact_estimate=10.0,
            affected_categories=["knife"],
            expires_at=time.time() + 3600,
        )
        d._active_events = [e]
        impact = d.get_item_impact("AK-47 | Redline")  # not a knife
        assert impact.active_events == 0

    def test_detect_volume_spikes_no_get_trade_history(self):
        """price_db without get_trade_history returns empty (line 160-161)."""
        d = EventDetector()
        mock_db = MagicMock(spec=[])  # no get_trade_history
        d._price_db = mock_db
        spikes = d._detect_volume_spikes()
        assert spikes == []

    def test_detect_new_items_no_get_recent_prices(self):
        """price_db without get_recent_prices returns empty (line 196-197)."""
        d = EventDetector()
        mock_db = MagicMock(spec=[])  # no get_recent_prices
        d._price_db = mock_db
        items = d._detect_new_items()
        assert items == []

    def test_detect_events_new_items_detected(self):
        """New items detection creates events (lines 111-122)."""
        d = EventDetector()
        mock_db = MagicMock()
        mock_db.get_trade_history.return_value = []
        mock_db.get_recent_prices.return_value = []
        d.bind(mock_db)
        d._last_scan_ts = 0.0

        # Mock _detect_new_items to return a new item
        with patch.object(d, '_detect_new_items', return_value=[{"title": "New Case"}]):
            events = d.detect_events()

        assert len(events) == 1
        assert events[0].event_type == "new_case"
        assert events[0].impact_estimate == -5.0

    def test_detect_events_new_items_exception(self):
        """Exception in new item detection is caught (lines 123-124)."""
        d = EventDetector()
        mock_db = MagicMock()
        mock_db.get_trade_history.return_value = []
        mock_db.get_recent_prices.return_value = []
        d.bind(mock_db)
        d._last_scan_ts = 0.0

        with patch.object(d, '_detect_new_items', side_effect=Exception("db error")):
            events = d.detect_events()

        assert events == []
