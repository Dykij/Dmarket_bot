"""
Tests for Phase 7: PriceHistoryDB trend analysis and EventShield logic.
"""

import pytest
import time
import os
from datetime import date

# Ensure we import from project root
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db.price_history import PriceHistoryDB
from src.core.event_shield import EventShield


# ============================================================
# PriceHistoryDB Tests
# ============================================================

class TestPriceHistory:
    """Tests for SQLite price history and trend detection."""

    @pytest.fixture(autouse=True)
    def setup_db(self, tmp_path):
        """Create a fresh in-memory-like DB for each test."""
        db_file = str(tmp_path / "test_prices.db")
        self.db = PriceHistoryDB.__new__(PriceHistoryDB)
        self.db.db_path = tmp_path / "test_prices.db"
        import sqlite3
        self.db.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.db.conn.row_factory = sqlite3.Row
        self.db._init_schema()
        yield
        self.db.close()

    def test_record_and_retrieve_price(self):
        """Recording a price and immediately retrieving it works."""
        self.db.record_price("AK-47 | Redline (FT)", 15.50)
        result = self.db.get_latest_price("AK-47 | Redline (FT)", max_age_seconds=60)
        assert result == 15.50

    def test_cache_ttl_expiry(self):
        """Prices older than TTL return None."""
        # Insert a price with a timestamp 4 hours ago
        old_time = time.time() - 14400  # 4 hours ago
        self.db.conn.execute(
            "INSERT INTO price_history (hash_name, price, source, recorded_at) VALUES (?, ?, ?, ?)",
            ("AWP | Asiimov (FT)", 65.0, "csfloat", old_time)
        )
        self.db.conn.commit()
        # With 3-hour TTL, this should be None
        result = self.db.get_latest_price("AWP | Asiimov (FT)", max_age_seconds=10800)
        assert result is None

    def test_is_crashing_detects_downtrend(self):
        """3 consecutive price drops should trigger crash detection."""
        base_time = time.time()
        # Insert prices: 20 -> 18 -> 16 -> 14 (falling)
        prices = [(20.0, -4), (18.0, -3), (16.0, -2), (14.0, -1)]
        for price, offset_hours in prices:
            self.db.conn.execute(
                "INSERT INTO price_history (hash_name, price, source, recorded_at) VALUES (?, ?, ?, ?)",
                ("M4A4 | Howl (FN)", price, "csfloat", base_time + offset_hours * 3600)
            )
        self.db.conn.commit()

        assert self.db.is_crashing("M4A4 | Howl (FN)") is True

    def test_is_crashing_false_for_rising(self):
        """Rising prices should NOT trigger crash detection."""
        base_time = time.time()
        prices = [(10.0, -4), (12.0, -3), (14.0, -2), (16.0, -1)]
        for price, offset_hours in prices:
            self.db.conn.execute(
                "INSERT INTO price_history (hash_name, price, source, recorded_at) VALUES (?, ?, ?, ?)",
                ("Desert Eagle | Blaze (FN)", price, "csfloat", base_time + offset_hours * 3600)
            )
        self.db.conn.commit()

        assert self.db.is_crashing("Desert Eagle | Blaze (FN)") is False

    def test_get_price_trend_falling(self):
        """Falling prices return 'falling' trend."""
        base_time = time.time()
        prices = [(100, -6), (95, -5), (90, -4), (85, -3), (80, -2)]
        for price, h in prices:
            self.db.conn.execute(
                "INSERT INTO price_history (hash_name, price, source, recorded_at) VALUES (?, ?, ?, ?)",
                ("Knife | Fade", price, "csfloat", base_time + h * 3600)
            )
        self.db.conn.commit()

        assert self.db.get_price_trend("Knife | Fade") == "falling"

    def test_get_price_trend_rising(self):
        """Rising prices return 'rising' trend."""
        base_time = time.time()
        prices = [(10, -6), (12, -5), (14, -4), (16, -3), (18, -2)]
        for price, h in prices:
            self.db.conn.execute(
                "INSERT INTO price_history (hash_name, price, source, recorded_at) VALUES (?, ?, ?, ?)",
                ("Glock | Fade", price, "csfloat", base_time + h * 3600)
            )
        self.db.conn.commit()

        assert self.db.get_price_trend("Glock | Fade") == "rising"

    def test_insufficient_data_returns_stable(self):
        """Less than 3 datapoints should return 'stable'."""
        self.db.record_price("P250 | Muertos", 5.0)
        assert self.db.get_price_trend("P250 | Muertos") == "stable"

    def test_avg_price(self):
        """Average price calculation works correctly."""
        base_time = time.time()
        for i, price in enumerate([10.0, 20.0, 30.0]):
            self.db.conn.execute(
                "INSERT INTO price_history (hash_name, price, source, recorded_at) VALUES (?, ?, ?, ?)",
                ("USP-S | Kill Confirmed", price, "csfloat", base_time - i * 3600)
            )
        self.db.conn.commit()
        avg = self.db.get_avg_price("USP-S | Kill Confirmed")
        assert avg == pytest.approx(20.0, abs=0.01)


# ============================================================
# EventShield Tests
# ============================================================

class TestEventShield:
    """Tests for CS2 event calendar awareness."""

    @pytest.fixture(autouse=True)
    def setup_shield(self, tmp_path):
        """Create an EventShield with a test events file."""
        import json
        events_file = tmp_path / "test_events.json"
        test_events = [
            {
                "name": "Test Major",
                "start": "2020-01-01",
                "end": "2030-12-31",
                "type": "major",
                "effect": "caution",
                "affected_categories": ["sticker", "souvenir"],
                "margin_multiplier": 2.0,
                "notes": "Test caution event"
            },
            {
                "name": "Test Sale",
                "start": "2020-06-01",
                "end": "2030-06-15",
                "type": "steam_sale",
                "effect": "opportunity",
                "affected_categories": ["rifle", "knife"],
                "margin_multiplier": 1.5,
                "notes": "Test opportunity event"
            },
            {
                "name": "Past Event",
                "start": "2019-01-01",
                "end": "2019-01-15",
                "type": "major",
                "effect": "caution",
                "affected_categories": ["sticker"],
                "margin_multiplier": 2.0,
                "notes": "Should not be active"
            }
        ]
        with open(events_file, "w") as f:
            json.dump(test_events, f)

        # Monkey-patch the events file path
        import src.core.event_shield as es_module
        self._orig_path = es_module.EVENTS_FILE
        es_module.EVENTS_FILE = events_file

        self.shield = EventShield()
        yield

        es_module.EVENTS_FILE = self._orig_path

    def test_active_events_detected(self):
        """Events spanning today should be detected."""
        active = self.shield.get_active_events()
        names = [e["name"] for e in active]
        assert "Test Major" in names
        assert "Test Sale" in names
        assert "Past Event" not in names

    def test_margin_multiplier_uses_max(self):
        """Margin multiplier should be the MAX across all active events."""
        mult = self.shield.get_margin_multiplier()
        assert mult == 2.0  # Test Major has 2.0, Test Sale has 1.5 → max is 2.0

    def test_category_risk_matches(self):
        """Items matching affected categories of caution events are flagged."""
        # "sticker" is in the caution event's affected_categories
        assert self.shield.is_category_risky("Sticker | NaVi 2024") is True
        assert self.shield.is_category_risky("AK-47 | Redline") is False

    def test_opportunity_mode(self):
        """Opportunity mode should be active when an opportunity event exists."""
        assert self.shield.is_opportunity_mode() is True

    def test_status_summary(self):
        """Status summary should mention active events."""
        summary = self.shield.get_status_summary()
        assert "Test Major" in summary
        assert "Test Sale" in summary

    def test_no_events_returns_defaults(self):
        """When no events are active, defaults should apply."""
        # Clear all events
        self.shield.events = []
        assert self.shield.get_margin_multiplier() == 1.0
        assert self.shield.is_category_risky("Sticker | NaVi") is False
        assert self.shield.is_opportunity_mode() is False
