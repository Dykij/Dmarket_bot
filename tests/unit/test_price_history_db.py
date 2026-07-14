"""Unit tests for price_history database modules.

Tests: price recording/retrieval, TTL filtering, state store, low-fee cache,
pump blacklist, inventory CRUD, and decision logging.

Uses tmp_path fixture for real SQLite in a temp directory.
"""

from __future__ import annotations

import time

import pytest

from src.db.price_history.core import PriceHistoryDB


@pytest.fixture()
def db(tmp_path):
    """Create a PriceHistoryDB backed by temp files."""
    state_db = str(tmp_path / "test_state.db")
    history_db = str(tmp_path / "test_history.db")
    instance = PriceHistoryDB(state_db=state_db, history_db=history_db)
    yield instance
    instance.close()


# =====================================================================
# Price History (history.py)
# =====================================================================


class TestPriceHistory:
    """Tests for price_history table operations."""

    def test_record_and_retrieve_price(self, db: PriceHistoryDB) -> None:
        """Write a price, read it back."""
        db.record_price("AK-47 | Redline (FT)", 12.50, source="oracle")
        price = db.get_latest_price("AK-47 | Redline (FT)", max_age_seconds=60)
        assert price == pytest.approx(12.50)

    def test_get_latest_price_within_ttl(self, db: PriceHistoryDB) -> None:
        """Price within TTL should be returned."""
        db.record_price("AWP | Asiimov (FT)", 35.00)
        price = db.get_latest_price("AWP | Asiimov (FT)", max_age_seconds=10800)
        assert price == pytest.approx(35.00)

    def test_get_latest_price_expired(self, db: PriceHistoryDB) -> None:
        """Price outside TTL should return None."""
        # Insert with a very old timestamp
        old_time = time.time() - 100000
        with db.history_conn:
            db.history_conn.execute(
                "INSERT INTO price_history (hash_name, price, source, recorded_at) "
                "VALUES (?, ?, ?, ?)",
                ("AK-47 | Vulcan (FN)", 50.0, "oracle", old_time),
            )
        price = db.get_latest_price("AK-47 | Vulcan (FN)", max_age_seconds=60)
        assert price is None

    def test_get_latest_price_nonexistent(self, db: PriceHistoryDB) -> None:
        """Non-existent item returns None."""
        assert db.get_latest_price("NonExistentItem") is None

    def test_get_recent_prices(self, db: PriceHistoryDB) -> None:
        """Verify date range filtering."""
        now = time.time()
        # Insert prices at different times
        with db.history_conn:
            for i in range(5):
                db.history_conn.execute(
                    "INSERT INTO price_history (hash_name, price, source, recorded_at) "
                    "VALUES (?, ?, ?, ?)",
                    ("AK-47 | Redline (FT)", 10.0 + i, "oracle", now - i * 3600),
                )
        prices = db.get_recent_prices("AK-47 | Redline (FT)", days=1)
        assert len(prices) == 5
        # Should be ordered by recorded_at DESC
        assert prices[0][0] == pytest.approx(10.0)  # most recent (now - 0*3600)

    def test_get_recent_prices_empty(self, db: PriceHistoryDB) -> None:
        """No data returns empty list."""
        assert db.get_recent_prices("NonExistent") == []

    def test_record_price_multiple_sources(self, db: PriceHistoryDB) -> None:
        """Different sources are stored separately."""
        db.record_price("Item", 10.0, source="oracle")
        db.record_price("Item", 12.0, source="dmarket")
        prices = db.get_recent_prices("Item", days=1)
        assert len(prices) == 2


# =====================================================================
# State Store (state.py)
# =====================================================================


class TestStateStore:
    """Tests for scanning_state key-value store."""

    def test_save_and_get_state(self, db: PriceHistoryDB) -> None:
        """Save a key, read it back."""
        db.save_state("cursor", "abc123")
        assert db.get_state("cursor") == "abc123"

    def test_get_state_nonexistent(self, db: PriceHistoryDB) -> None:
        """Non-existent key returns None."""
        assert db.get_state("nonexistent") is None

    def test_save_state_overwrite(self, db: PriceHistoryDB) -> None:
        """Saving same key overwrites value."""
        db.save_state("cursor", "v1")
        db.save_state("cursor", "v2")
        assert db.get_state("cursor") == "v2"

    def test_get_state_with_ts(self, db: PriceHistoryDB) -> None:
        """Returns (value, updated_at) tuple."""
        db.save_state("key", "val")
        value, ts = db.get_state_with_ts("key")
        assert value == "val"
        assert ts > 0

    def test_get_state_with_ts_missing(self, db: PriceHistoryDB) -> None:
        """Missing key returns (None, 0.0)."""
        value, ts = db.get_state_with_ts("missing")
        assert value is None
        assert ts == pytest.approx(0.0)

    def test_get_all_state(self, db: PriceHistoryDB) -> None:
        """Returns all state rows."""
        db.save_state("a", "1")
        db.save_state("b", "2")
        db.save_state("c", "3")
        rows = db.get_all_state()
        keys = {r["key"] for r in rows}
        assert keys == {"a", "b", "c"}


# =====================================================================
# Low-Fee Cache (low_fee.py)
# =====================================================================


class TestLowFeeCache:
    """Tests for low_fee_cache CRUD."""

    def test_save_and_get_low_fee(self, db: PriceHistoryDB) -> None:
        """Save items, read fee rate back."""
        items = [
            {"title": "AK-47 | Redline (FT)", "fee_rate": 0.02},
            {"title": "AWP | Asiimov (FT)", "fee_rate": 0.03},
        ]
        db.save_low_fee_items(items)
        assert db.get_low_fee_rate("AK-47 | Redline (FT)") == pytest.approx(0.02)
        assert db.get_low_fee_rate("AWP | Asiimov (FT)") == pytest.approx(0.03)

    def test_low_fee_expired(self, db: PriceHistoryDB) -> None:
        """Expired entries return None."""
        old_time = time.time() - 100000
        with db.state_conn:
            db.state_conn.execute(
                "INSERT INTO low_fee_cache (title, fee_rate, fetched_at) VALUES (?, ?, ?)",
                ("Old Item", 0.02, old_time),
            )
        assert db.get_low_fee_rate("Old Item", max_age_seconds=60) is None

    def test_low_fee_cache_size(self, db: PriceHistoryDB) -> None:
        items = [{"title": f"Item{i}", "fee_rate": 0.02} for i in range(5)]
        db.save_low_fee_items(items)
        assert db.low_fee_cache_size() == 5

    def test_low_fee_cache_replaces_all(self, db: PriceHistoryDB) -> None:
        """save_low_fee_items replaces entire cache."""
        db.save_low_fee_items([{"title": "A", "fee_rate": 0.01}])
        db.save_low_fee_items([{"title": "B", "fee_rate": 0.02}])
        assert db.low_fee_cache_size() == 1
        assert db.get_low_fee_rate("A") is None
        assert db.get_low_fee_rate("B") == pytest.approx(0.02)

    def test_low_fee_cache_age(self, db: PriceHistoryDB) -> None:
        """Cache age should be ~0 right after save."""
        db.save_low_fee_items([{"title": "X", "fee_rate": 0.02}])
        age = db.low_fee_cache_age_seconds()
        assert age is not None
        assert age < 5  # should be very fresh

    def test_low_fee_cache_empty(self, db: PriceHistoryDB) -> None:
        assert db.low_fee_cache_size() == 0
        assert db.low_fee_cache_age_seconds() is None


# =====================================================================
# Pump Blacklist (pump_blacklist.py)
# =====================================================================


class TestPumpBlacklist:
    """Tests for pump_blacklist CRUD."""

    def test_add_and_get_active(self, db: PriceHistoryDB) -> None:
        """Add entry, retrieve active entries."""
        now = time.time()
        db.add_pump_blacklist_entry(
            hash_name="AK-47 | Vulcan (FN)",
            old_price=50.0,
            new_price=80.0,
            pct_change=60.0,
            detected_at=now,
            expires_at=now + 86400,
        )
        active = db.get_active_pump_blacklist()
        assert len(active) == 1
        assert active[0]["hash_name"] == "AK-47 | Vulcan (FN)"

    def test_pump_blacklist_expired_not_returned(self, db: PriceHistoryDB) -> None:
        """Expired entries should not be returned."""
        now = time.time()
        db.add_pump_blacklist_entry(
            hash_name="Old Item",
            old_price=10.0,
            new_price=20.0,
            pct_change=100.0,
            detected_at=now - 100000,
            expires_at=now - 10,
        )
        assert len(db.get_active_pump_blacklist()) == 0

    def test_cleanup_expired(self, db: PriceHistoryDB) -> None:
        """Cleanup should remove expired entries."""
        now = time.time()
        db.add_pump_blacklist_entry("A", 10, 20, 100, now - 100, now - 10)
        db.add_pump_blacklist_entry("B", 10, 20, 100, now, now + 86400)
        deleted = db.cleanup_expired_pump_blacklist()
        assert deleted == 1
        assert len(db.get_active_pump_blacklist()) == 1

    def test_delete_entry(self, db: PriceHistoryDB) -> None:
        """Manual deletion removes entry."""
        now = time.time()
        db.add_pump_blacklist_entry("X", 10, 20, 100, now, now + 86400)
        db.delete_pump_blacklist_entry("X")
        assert len(db.get_active_pump_blacklist()) == 0

    def test_count_active(self, db: PriceHistoryDB) -> None:
        now = time.time()
        db.add_pump_blacklist_entry("A", 10, 20, 100, now, now + 86400)
        db.add_pump_blacklist_entry("B", 10, 20, 100, now, now - 10)  # expired
        assert db.count_active_pump_blacklist() == 1

    def test_total_detections(self, db: PriceHistoryDB) -> None:
        now = time.time()
        db.add_pump_blacklist_entry("A", 10, 20, 100, now, now + 86400)
        db.add_pump_blacklist_entry("B", 10, 20, 100, now, now - 10)
        assert db.get_pump_blacklist_total_detections() == 2


# =====================================================================
# Inventory CRUD (inventory.py)
# =====================================================================


class TestInventory:
    """Tests for virtual_inventory operations."""

    def test_add_virtual_item(self, db: PriceHistoryDB) -> None:
        """Add item and list idle items."""
        db.add_virtual_item("AK-47 | Redline (FT)", 12.50)
        items = db.get_virtual_inventory(status="idle")
        assert len(items) == 1
        assert items[0]["hash_name"] == "AK-47 | Redline (FT)"
        assert items[0]["buy_price"] == pytest.approx(12.50)

    def test_add_virtual_item_exclusive(self, db: PriceHistoryDB) -> None:
        """Exclusive items are flagged."""
        db.add_virtual_item("Rare Item", 100.0, exclusive=True)
        items = db.get_virtual_inventory(status="idle")
        assert items[0]["exclusive"] == 1
        assert db.is_exclusive(items[0]["id"]) is True

    def test_update_virtual_status(self, db: PriceHistoryDB) -> None:
        """Status transitions work."""
        db.add_virtual_item("Item", 10.0)
        items = db.get_virtual_inventory(status="idle")
        db.update_virtual_status(items[0]["id"], "listed")
        listed = db.get_virtual_inventory(status="listed")
        assert len(listed) == 1

    def test_record_virtual_sale(self, db: PriceHistoryDB) -> None:
        """Sale records profit correctly."""
        db.add_virtual_item("Item", 10.0)
        items = db.get_virtual_inventory(status="idle")
        db.record_virtual_sale(items[0]["id"], sell_price=15.0, fee_paid=0.5)
        sold = db.get_virtual_inventory(status="sold")
        assert len(sold) == 1
        assert sold[0]["profit"] == pytest.approx(4.5)  # 15 - 10 - 0.5

    def test_mark_listed(self, db: PriceHistoryDB) -> None:
        """mark_listed sets status and dm_offer_id."""
        db.add_virtual_item("Item", 10.0)
        items = db.get_virtual_inventory(status="idle")
        db.mark_listed(items[0]["id"], "offer_123", 15.0)
        listed = db.get_virtual_inventory(status="listed")
        assert listed[0]["dm_offer_id"] == "offer_123"
        assert listed[0]["sell_price"] == pytest.approx(15.0)

    def test_get_non_exclusive_inventory(self, db: PriceHistoryDB) -> None:
        """Non-exclusive filter works."""
        db.add_virtual_item("Normal", 10.0, exclusive=False)
        db.add_virtual_item("Exclusive", 20.0, exclusive=True)
        non_excl = db.get_non_exclusive_inventory(status="idle")
        assert len(non_excl) == 1
        assert non_excl[0]["hash_name"] == "Normal"

    def test_attach_dm_item_id(self, db: PriceHistoryDB) -> None:
        """dm_item_id can be attached to a row."""
        db.add_virtual_item("Item", 10.0)
        items = db.get_virtual_inventory(status="idle")
        db.attach_dm_item_id(items[0]["id"], "dm_abc")
        assert db.has_dm_item_id(items[0]["id"]) is True
        found = db.find_by_dm_item_id("dm_abc")
        assert found is not None
        assert found["hash_name"] == "Item"

    def test_find_by_dm_offer_id(self, db: PriceHistoryDB) -> None:
        """Look up by dm_offer_id."""
        db.add_virtual_item("Item", 10.0)
        items = db.get_virtual_inventory(status="idle")
        db.mark_listed(items[0]["id"], "offer_xyz", 15.0)
        found = db.find_by_dm_offer_id("offer_xyz")
        assert found is not None

    def test_vwap(self, db: PriceHistoryDB) -> None:
        """VWAP should average buy prices for same item."""
        db.add_virtual_item("Item", 10.0)
        db.add_virtual_item("Item", 20.0)
        vwap = db.calculate_vwap("Item")
        assert vwap == pytest.approx(15.0)

    def test_get_total_equity(self, db: PriceHistoryDB) -> None:
        """Equity = cash + asset value."""
        db.add_virtual_item("A", 10.0)
        db.add_virtual_item("B", 20.0)
        equity = db.get_total_equity(current_balance=100.0)
        assert equity["cash"] == pytest.approx(100.0)
        assert equity["assets"] == pytest.approx(30.0)
        assert equity["total"] == pytest.approx(130.0)
        assert equity["count"] == 2


# =====================================================================
# Decision Logs (analytics_logs.py)
# =====================================================================


class TestDecisionLogs:
    """Tests for decision_logs and analytics."""

    def test_log_decision(self, db: PriceHistoryDB) -> None:
        """Log a decision and retrieve it."""
        db.log_decision("AK-47 | Redline", "buy", "spread > 10%", details="price=12.50")
        # Verify it's in the DB
        row = db.state_conn.execute(
            "SELECT * FROM decision_logs WHERE hash_name = ?",
            ("AK-47 | Redline",),
        ).fetchone()
        assert row is not None
        assert row["decision"] == "buy"
        assert row["reason"] == "spread > 10%"

    def test_record_missed_opportunity(self, db: PriceHistoryDB) -> None:
        db.record_missed_opportunity("Item", 10.0, 15.0, "too risky")
        row = db.state_conn.execute(
            "SELECT * FROM missed_opportunities WHERE hash_name = ?",
            ("Item",),
        ).fetchone()
        assert row is not None
        assert row["price"] == pytest.approx(10.0)

    def test_record_equity_snapshot(self, db: PriceHistoryDB) -> None:
        """Equity snapshot is recorded."""
        row_id = db.record_equity_snapshot(
            cash=100.0, assets=50.0, total=150.0, realized_pnl=10.0, note="test"
        )
        assert row_id > 0
        snap = db.get_equity_snapshot_today()
        assert snap is not None
        assert snap["cash"] == pytest.approx(100.0)
        assert snap["total"] == pytest.approx(150.0)

    def test_equity_snapshot_upsert(self, db: PriceHistoryDB) -> None:
        """Same-day snapshot is updated, not duplicated."""
        db.record_equity_snapshot(100, 50, 150, 10)
        db.record_equity_snapshot(200, 80, 280, 20)
        snapshots = db.get_equity_snapshots(days=1)
        assert len(snapshots) == 1
        assert snapshots[0]["cash"] == pytest.approx(200.0)

    def test_record_risk_event(self, db: PriceHistoryDB) -> None:
        event_id = db.record_risk_event("drawdown_freeze", severity="critical", details="balance < 85%")
        assert event_id > 0
        events = db.get_risk_events_today()
        assert len(events) >= 1
        assert events[0]["type"] == "drawdown_freeze"


# =====================================================================
# Targets (targets.py)
# =====================================================================


class TestTargets:
    """Tests for active_targets operations."""

    def test_targets_table_exists(self, db: PriceHistoryDB) -> None:
        """active_targets table should be created."""
        row = db.state_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='active_targets'"
        ).fetchone()
        assert row is not None
