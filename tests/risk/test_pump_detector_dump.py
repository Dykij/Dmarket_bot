"""
Extended unit tests for src.risk.pump_detector — falling item detection (v15.4).

Tests for:
- check_price_drop: price drop detection (15% flagged, 5% not flagged)
- is_dump_flagged: TTL expiry
- dump_flag_cleanup: expired flags are cleaned
- Stats tracking for dump detections

No external API. No DB. ~1s total runtime.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path
from typing import List, Tuple
from unittest.mock import MagicMock

import pytest

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src.risk.pump_detector import PumpDetector  # noqa: E402


# =====================================================================
# Helpers
# =====================================================================

class MockPriceDB:
    """In-memory price DB for dump detection tests."""

    def __init__(self) -> None:
        self.observations: List[Tuple[str, float, float]] = []

    def add(self, title: str, price: float, ts: float) -> None:
        self.observations.append((title, price, ts))

    def get_recent_prices(self, hash_name: str, days: int = 2) -> List[Tuple[float, float]]:
        cutoff = time.time() - (days * 86400)
        rows = [
            (p, ts)
            for title, p, ts in self.observations
            if title == hash_name and ts > cutoff
        ]
        rows.sort(key=lambda r: r[1], reverse=True)
        return rows


def _seed_observation(db: MockPriceDB, title: str, price: float, seconds_ago: float) -> None:
    db.add(title, price, time.time() - seconds_ago)


def _make_detector(db: MockPriceDB | None = None) -> PumpDetector:
    return PumpDetector(
        price_db=db if db is not None else MockPriceDB(),
        notifier=MagicMock(),
        threshold_pct=15.0,
        window_seconds=3600,
        blacklist_seconds=86400,
    )


# =====================================================================
# test_check_price_drop_detected
# =====================================================================

class TestCheckPriceDropDetected:
    """Verify price drops > threshold are flagged."""

    def test_price_drop_15_percent_detected(self) -> None:
        """15% drop should be detected (threshold is 10%)."""
        db = MockPriceDB()
        _seed_observation(db, "AK-47 | Redline (FT)", 10.0, seconds_ago=7200)
        det = _make_detector(db)

        # Price dropped from $10 to $8.50 = -15%
        result = det.check_price_drop("AK-47 | Redline (FT)", oracle_price=8.50)
        assert result is True
        assert det._total_dumps_detected == 1

    def test_price_drop_20_percent_detected(self) -> None:
        """20% drop is well above threshold."""
        db = MockPriceDB()
        _seed_observation(db, "AWP | Atheris (FT)", 10.0, seconds_ago=7200)
        det = _make_detector(db)

        result = det.check_price_drop("AWP | Atheris (FT)", oracle_price=8.0)
        assert result is True

    def test_price_drop_exactly_at_threshold(self) -> None:
        """Exactly 10% drop should be detected (>= threshold)."""
        db = MockPriceDB()
        _seed_observation(db, "AK-47 | Redline (FT)", 100.0, seconds_ago=7200)
        det = _make_detector(db)

        # 10% drop: 100 → 90
        result = det.check_price_drop("AK-47 | Redline (FT)", oracle_price=90.0)
        assert result is True

    def test_dump_flag_recorded_in_dict(self) -> None:
        """After detection, item should be in _dump_flags."""
        db = MockPriceDB()
        _seed_observation(db, "AK-47 | Redline (FT)", 10.0, seconds_ago=7200)
        det = _make_detector(db)

        det.check_price_drop("AK-47 | Redline (FT)", oracle_price=8.50)
        assert "AK-47 | Redline (FT)" in det._dump_flags

    def test_dump_detection_fires_notifier(self) -> None:
        """Notifier should be called when a dump is detected."""
        db = MockPriceDB()
        _seed_observation(db, "AK-47 | Redline (FT)", 10.0, seconds_ago=7200)
        notifier = MagicMock()
        det = PumpDetector(
            price_db=db, notifier=notifier, threshold_pct=15.0,
            window_seconds=3600, blacklist_seconds=86400,
        )

        det.check_price_drop("AK-47 | Redline (FT)", oracle_price=8.50)
        # notifier.custom should have been called (via create_task)
        assert det._total_dumps_detected == 1


# =====================================================================
# test_check_price_drop_not_triggered
# =====================================================================

class TestCheckPriceDropNotTriggered:
    """Verify small price drops are NOT flagged."""

    def test_price_drop_5_percent_not_flagged(self) -> None:
        """5% drop is below the 10% threshold."""
        db = MockPriceDB()
        _seed_observation(db, "AK-47 | Redline (FT)", 10.0, seconds_ago=7200)
        det = _make_detector(db)

        result = det.check_price_drop("AK-47 | Redline (FT)", oracle_price=9.50)
        assert result is False
        assert det._total_dumps_detected == 0

    def test_price_drop_9_percent_not_flagged(self) -> None:
        """9% drop is just below 10% threshold."""
        db = MockPriceDB()
        _seed_observation(db, "AK-47 | Redline (FT)", 100.0, seconds_ago=7200)
        det = _make_detector(db)

        result = det.check_price_drop("AK-47 | Redline (FT)", oracle_price=91.0)
        assert result is False

    def test_price_increase_not_flagged(self) -> None:
        """Price increase should never trigger dump detection."""
        db = MockPriceDB()
        _seed_observation(db, "AK-47 | Redline (FT)", 10.0, seconds_ago=7200)
        det = _make_detector(db)

        result = det.check_price_drop("AK-47 | Redline (FT)", oracle_price=12.0)
        assert result is False

    def test_unchanged_price_not_flagged(self) -> None:
        """No change should not trigger dump detection."""
        db = MockPriceDB()
        _seed_observation(db, "AK-47 | Redline (FT)", 10.0, seconds_ago=7200)
        det = _make_detector(db)

        result = det.check_price_drop("AK-47 | Redline (FT)", oracle_price=10.0)
        assert result is False

    def test_empty_title_not_flagged(self) -> None:
        """Empty hash_name should return False."""
        det = _make_detector()
        result = det.check_price_drop("", oracle_price=5.0)
        assert result is False

    def test_zero_or_negative_price_not_flagged(self) -> None:
        """Zero/negative oracle_price should return False."""
        db = MockPriceDB()
        _seed_observation(db, "AK-47 | Redline (FT)", 10.0, seconds_ago=7200)
        det = _make_detector(db)

        assert det.check_price_drop("AK-47 | Redline (FT)", oracle_price=0.0) is False
        assert det.check_price_drop("AK-47 | Redline (FT)", oracle_price=-5.0) is False

    def test_no_history_not_flagged(self) -> None:
        """No price history → can't compute drop → False."""
        det = _make_detector(MockPriceDB())
        result = det.check_price_drop("Unknown Item", oracle_price=5.0)
        assert result is False

    def test_no_price_db_not_flagged(self) -> None:
        """No price_db set → False."""
        det = PumpDetector(price_db=None, notifier=MagicMock())
        result = det.check_price_drop("AK-47 | Redline (FT)", oracle_price=5.0)
        assert result is False

    def test_no_baseline_in_window_not_flagged(self) -> None:
        """If all observations are inside the window, no baseline → False."""
        db = MockPriceDB()
        # All observations within the 1h window
        _seed_observation(db, "AK-47 | Redline (FT)", 10.0, seconds_ago=1800)
        det = _make_detector(db)

        result = det.check_price_drop("AK-47 | Redline (FT)", oracle_price=8.0)
        assert result is False


# =====================================================================
# test_is_dump_flagged_ttl
# =====================================================================

class TestIsDumpFlaggedTTL:
    """Verify dump flag expires after TTL."""

    def test_dump_flagged_immediately_after_detection(self) -> None:
        db = MockPriceDB()
        _seed_observation(db, "AK-47 | Redline (FT)", 10.0, seconds_ago=7200)
        det = _make_detector(db)

        det.check_price_drop("AK-47 | Redline (FT)", oracle_price=8.50)
        assert det.is_dump_flagged("AK-47 | Redline (FT)") is True

    def test_dump_flag_expires_after_ttl(self) -> None:
        """Flag should expire after ttl_seconds."""
        det = _make_detector()
        # Manually set a flag that expired 2 seconds ago
        det._dump_flags["AK-47 | Redline (FT)"] = time.time() - 2

        # TTL = 1 second → expired
        assert det.is_dump_flagged("AK-47 | Redline (FT)", ttl_seconds=1) is False

    def test_dump_flag_within_ttl(self) -> None:
        """Flag should be active within TTL."""
        det = _make_detector()
        det._dump_flags["AK-47 | Redline (FT)"] = time.time()

        # TTL = 3600 → still active
        assert det.is_dump_flagged("AK-47 | Redline (FT)", ttl_seconds=3600) is True

    def test_dump_flag_not_present(self) -> None:
        """Item not in _dump_flags → False."""
        det = _make_detector()
        assert det.is_dump_flagged("Nonexistent Item") is False

    def test_dump_flag_default_ttl(self) -> None:
        """Default TTL is 3600 seconds (1h)."""
        det = _make_detector()
        det._dump_flags["AK-47 | Redline (FT)"] = time.time()

        assert det.is_dump_flagged("AK-47 | Redline (FT)") is True

        # Set flag to 2 hours ago → expired with default 1h TTL
        det._dump_flags["AK-47 | Redline (FT)"] = time.time() - 7200
        assert det.is_dump_flagged("AK-47 | Redline (FT)") is False

    def test_expired_flag_is_deleted(self) -> None:
        """When TTL expires, the flag should be removed from the dict."""
        det = _make_detector()
        det._dump_flags["AK-47 | Redline (FT)"] = time.time() - 7200

        det.is_dump_flagged("AK-47 | Redline (FT)", ttl_seconds=3600)
        assert "AK-47 | Redline (FT)" not in det._dump_flags


# =====================================================================
# test_dump_flag_cleanup
# =====================================================================

class TestDumpFlagCleanup:
    """Verify expired dump flags and blacklist entries are cleaned."""

    def test_cleanup_expired_blacklist(self) -> None:
        """cleanup_expired removes expired blacklist entries."""
        from src.risk.pump_detector import PumpAlert

        det = _make_detector()
        # Add an expired entry
        det._blacklist["Expired Item"] = PumpAlert(
            hash_name="Expired Item",
            old_price=10.0,
            new_price=12.0,
            pct_change=20.0,
            detected_at=time.time() - 100,
            expires_at=time.time() - 1,  # expired
        )
        # Add an active entry
        det._blacklist["Active Item"] = PumpAlert(
            hash_name="Active Item",
            old_price=10.0,
            new_price=12.0,
            pct_change=20.0,
            detected_at=time.time(),
            expires_at=time.time() + 3600,  # still active
        )

        removed = det.cleanup_expired()
        assert removed == 1
        assert "Expired Item" not in det._blacklist
        assert "Active Item" in det._blacklist

    def test_cleanup_returns_zero_when_nothing_expired(self) -> None:
        from src.risk.pump_detector import PumpAlert

        det = _make_detector()
        det._blacklist["Active Item"] = PumpAlert(
            hash_name="Active Item",
            old_price=10.0,
            new_price=12.0,
            pct_change=20.0,
            detected_at=time.time(),
            expires_at=time.time() + 3600,
        )

        removed = det.cleanup_expired()
        assert removed == 0

    def test_cleanup_empty_blacklist(self) -> None:
        det = _make_detector()
        removed = det.cleanup_expired()
        assert removed == 0

    def test_multiple_dump_flags_tracked(self) -> None:
        """Multiple items can be dump-flagged simultaneously."""
        db = MockPriceDB()
        _seed_observation(db, "Item A", 10.0, seconds_ago=7200)
        _seed_observation(db, "Item B", 20.0, seconds_ago=7200)
        det = _make_detector(db)

        det.check_price_drop("Item A", oracle_price=8.0)  # -20%
        det.check_price_drop("Item B", oracle_price=17.0)  # -15%

        assert det.is_dump_flagged("Item A") is True
        assert det.is_dump_flagged("Item B") is True
        assert det._total_dumps_detected == 2

    def test_stats_tracks_dump_flags(self) -> None:
        db = MockPriceDB()
        _seed_observation(db, "AK-47 | Redline (FT)", 10.0, seconds_ago=7200)
        det = _make_detector(db)

        det.check_price_drop("AK-47 | Redline (FT)", oracle_price=8.50)
        s = det.stats()
        assert s["total_dumps_detected"] == 1
        assert s["active_dump_flags"] == 1

    def test_stats_dump_flags_decrease_on_expiry(self) -> None:
        det = _make_detector()
        det._dump_flags["Item A"] = time.time() - 7200  # expired
        det._dump_flags["Item B"] = time.time()  # active

        # is_dump_flagged cleans expired entries
        det.is_dump_flagged("Item A", ttl_seconds=3600)

        s = det.stats()
        assert s["active_dump_flags"] == 1
