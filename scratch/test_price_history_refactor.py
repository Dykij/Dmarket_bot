"""Smoke test for refactored price_history package — uses temp DBs."""

import sys
import os
import tempfile
import time
import shutil
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Redirect data dir to a temp location BEFORE importing price_history
_tmpdir = tempfile.mkdtemp(prefix="price_history_test_")
os.environ["PRICE_HISTORY_TEST_DIR"] = _tmpdir

from src.db.price_history import PriceHistoryDB
from src.db.price_history import (
    _HistoryMixin,
    _StateMixin,
    _InventoryMixin,
    _TargetsMixin,
    _AssetStatusMixin,
    _LowFeeMixin,
)


def test_imports():
    assert PriceHistoryDB is not None
    assert _HistoryMixin
    assert _StateMixin
    assert _InventoryMixin
    assert _TargetsMixin
    assert _AssetStatusMixin
    assert _LowFeeMixin
    print("[OK] all imports work (PriceHistoryDB + 6 mixins)")


def test_mixin_composition():
    """PriceHistoryDB inherits from all 6 mixins."""
    bases = PriceHistoryDB.__mro__
    for mixin in [
        _HistoryMixin,
        _StateMixin,
        _InventoryMixin,
        _TargetsMixin,
        _AssetStatusMixin,
        _LowFeeMixin,
    ]:
        assert mixin in bases, f"{mixin.__name__} not in MRO"
    print(f"[OK] mixin composition (6 mixins in MRO)")


def _make_test_db():
    """Create a PriceHistoryDB in a temp directory."""
    db_path = Path(_tmpdir) / f"test_{os.getpid()}"
    db_path.mkdir(parents=True, exist_ok=True)
    return PriceHistoryDB(
        state_db=str(db_path / "state.db"),
        history_db=str(db_path / "history.db"),
    )


def test_history():
    """Record and query price observations."""
    db = _make_test_db()
    db.record_price("AK-47 | Redline", 12.50)
    db.record_price("AK-47 | Redline", 13.00)
    db.record_price("AK-47 | Redline", 12.75)

    # Latest
    latest = db.get_latest_price("AK-47 | Redline", max_age_seconds=3600)
    assert latest == 12.75, f"expected 12.75, got {latest}"

    # Recent
    recent = db.get_recent_prices("AK-47 | Redline", days=7)
    assert len(recent) == 3
    assert recent[0][0] == 12.75  # newest first

    # Avg
    avg = db.get_avg_price("AK-47 | Redline", days=7)
    assert abs(avg - (12.50 + 13.00 + 12.75) / 3) < 0.01

    # Crashing
    assert not db.is_crashing("AK-47 | Redline")

    db.close()
    print("[OK] history: record/get_latest/get_recent/get_avg")


def test_trimmed_mean():
    """Trimmed mean removes outliers."""
    db = _make_test_db()
    # Add 6 prices: 5 normal, 1 outlier
    for p in [10, 10, 10, 10, 10, 100]:
        db.record_price("Item", p)

    raw = db.get_avg_price("Item", days=7)
    trimmed = db.get_trimmed_mean("Item", days=7, boost_pct=24.0, max_outliers=1)
    assert raw > trimmed  # Outlier inflated the raw mean
    assert abs(trimmed - 10.0) < 0.01  # Trimmed should be close to 10
    db.close()
    print(f"[OK] trimmed_mean: raw={raw:.2f}, trimmed={trimmed:.2f}")


def test_state_persistence():
    """save_state + get_state."""
    db = _make_test_db()
    db.save_state("dmarket_cursor_a8db", "abc123")
    assert db.get_state("dmarket_cursor_a8db") == "abc123"
    assert db.get_state("nonexistent") is None
    db.close()
    print("[OK] state: save/get")


def test_inventory():
    """Add virtual item + equity + VWAP."""
    db = _make_test_db()
    db.add_virtual_item("AK-47 | Redline", 10.50, trade_lock_hours=168)
    db.add_virtual_item("AK-47 | Redline", 11.00)
    db.add_virtual_item("AWP | Dragon Lore", 500.0)

    items = db.get_virtual_inventory()
    assert len(items) == 3

    # VWAP for AK
    vwap = db.calculate_vwap("AK-47 | Redline")
    assert abs(vwap - (10.50 + 11.00) / 2) < 0.01

    # Total equity
    equity = db.get_total_equity(43.91)
    assert equity["cash"] == 43.91
    assert equity["count"] == 3
    assert abs(equity["assets"] - (10.50 + 11.00 + 500.0)) < 0.01

    # Decision log
    db.log_decision("Item", "skip", "test", "details")
    # Missed opportunity
    db.record_missed_opportunity("Item", 10.0, 12.0, "test reason")
    db.close()
    print("[OK] inventory: add/equity/vwap/decision/missed")


def test_targets():
    """Record and check placed targets."""
    db = _make_test_db()
    db.record_placed_target("item-1", "AK-47 | Redline", 10.50)
    db.record_placed_target("item-2", "AWP | Dragon Lore", 500.0)
    assert db.has_target_been_placed("item-1")
    assert db.has_target_been_placed("item-2")
    assert not db.has_target_been_placed("item-999")
    # Cleanup
    deleted = db.cleanup_old_targets(max_age_seconds=0)
    assert deleted >= 2
    db.close()
    print("[OK] targets: record/has/cleanup")


def test_asset_status():
    """v12.2 asset status tracking."""
    db = _make_test_db()
    db.update_asset_status("item-1", "AK-47 | Redline", "trade_protected", time.time() + 3600)
    assert db.is_known_item("item-1")
    assert db.is_trade_locked("item-1")  # trade_protected
    asset = db.get_asset_status("item-1")
    assert asset["status"] == "trade_protected"
    assert asset["title"] == "AK-47 | Redline"

    # Mark reverted
    db.mark_reverted("item-1")
    assert db.is_trade_locked("item-1")  # reverted is always locked
    assert db.get_asset_status("item-1")["status"] == "reverted"
    db.close()
    print("[OK] asset_status: update/get/is_locked/mark_reverted")


def test_low_fee_cache():
    """v12.0 low-fee cache."""
    db = _make_test_db()
    db.save_low_fee_items([
        {"title": "Item1", "fee_rate": 0.02},
        {"title": "Item2", "fee_rate": 0.03},
    ])
    assert db.get_low_fee_rate("Item1") == 0.02
    assert db.get_low_fee_rate("Item2") == 0.03
    assert db.get_low_fee_rate("Unknown") is None
    assert db.low_fee_cache_size() == 2
    assert db.low_fee_cache_age_seconds() is not None
    db.close()
    print("[OK] low_fee_cache: save/get/size/age")


def cleanup():
    """Remove temp dirs."""
    shutil.rmtree(_tmpdir, ignore_errors=True)


if __name__ == "__main__":
    try:
        test_imports()
        test_mixin_composition()
        test_history()
        test_trimmed_mean()
        test_state_persistence()
        test_inventory()
        test_targets()
        test_asset_status()
        test_low_fee_cache()
        print("\n[ALL PASS] price_history refactor: 9/9 smoke tests passed")
    finally:
        cleanup()
