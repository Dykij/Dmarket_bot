"""
Smoke test for src/analytics/data_collector refactor (324 LOC → 4 files).

Verifies:
    1. Public API backward compat (MarketDataCollector importable)
    2. Class identity across import paths
    3. MarketDataCollector attributes set correctly in __init__
    4. snapshot.collect_market_snapshot works with a fake API
    5. collector.collect_market_snapshot delegates to snapshot + storage
    6. start()/stop() lifecycle (running flag, task creation/cancel)
    7. _collection_loop catches errors (won't crash the loop)
    8. storage helpers signature compat
    9. The package layout: 4 files, all <200 LOC
"""

from __future__ import annotations

import asyncio
import logging
import os
import structlog
import sys

# Configure structlog BEFORE any module-level get_logger() call below.
# (Production would call structlog.configure(...) in src/__init__.py.)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(logging.WARNING),
    logger_factory=structlog.PrintLoggerFactory(),
)


# ---------------------------------------------------------------------------
# Test 1: Public API backward compat
# ---------------------------------------------------------------------------
def test_public_api():
    from src.analytics.data_collector import MarketDataCollector

    assert MarketDataCollector.__name__ == "MarketDataCollector"
    print("  [OK] MarketDataCollector importable from data_collector package")


# ---------------------------------------------------------------------------
# Test 2: Class identity
# ---------------------------------------------------------------------------
def test_class_identity():
    from src.analytics.data_collector import MarketDataCollector as M1
    from src.analytics.data_collector.collector import MarketDataCollector as M2

    assert M1 is M2, "MarketDataCollector should be the SAME class from both paths"
    print("  [OK] MarketDataCollector is the same class from both import paths")


# ---------------------------------------------------------------------------
# Test 3: __init__ parameters
# ---------------------------------------------------------------------------
def test_init_attributes():
    from src.analytics.data_collector import MarketDataCollector

    class _StubAPI:
        pass

    class _StubDB:
        pass

    c = MarketDataCollector(
        api_client=_StubAPI(),
        db_manager=_StubDB(),
        collection_interval_minutes=15,
        retention_days=90,
    )
    assert c.api_client is not None
    assert c.db_manager is not None
    assert c.collection_interval == 15 * 60
    assert c.retention_days == 90
    assert c._running is False
    assert c._task is None
    print("  [OK] __init__ sets api/db/interval/retention/_running/_task correctly")


# ---------------------------------------------------------------------------
# Test 4: snapshot.collect_market_snapshot with a fake API
# ---------------------------------------------------------------------------
def test_snapshot_collection():
    from src.analytics.data_collector.snapshot import collect_market_snapshot

    class _FakeAPI:
        def __init__(self):
            self.calls: list = []

        async def get_market_items(self, game, limit, offset):
            self.calls.append((game, limit, offset))
            if offset >= 100:
                return {"objects": []}
            return {
                "objects": [
                    {
                        "price": {"USD": "1000"},
                        "inMarket": 5,
                    },
                    {
                        "price": {"USD": "2000"},
                        "inMarket": 3,
                    },
                ]
            }

    async def run():
        api = _FakeAPI()
        out = await collect_market_snapshot(api, games=["csgo"])
        return api, out

    api, out = asyncio.run(run())
    assert "csgo" in out["games"]
    assert out["games"]["csgo"]["items_count"] == 2
    assert out["games"]["csgo"]["sales_count"] == 8
    assert out["games"]["csgo"]["avg_price_cents"] == 1500.0
    assert out["games"]["csgo"]["total_market_value_cents"] == 3000
    assert out["total_items"] == 2
    assert out["total_sales"] == 8
    # pagination: offset=0 returns 2 items, len<limit so we stop
    assert api.calls == [("csgo", 100, 0)]
    print(f"  [OK] snapshot collects + paginates: {out['total_items']} items, {out['total_sales']} sales")


def test_snapshot_handles_api_error():
    """The original behavior: _collect_game_data swallows per-game errors
    internally and returns empty data. The outer try/except in
    collect_market_snapshot never fires (it was a defensive guard)."""
    from src.analytics.data_collector.snapshot import collect_market_snapshot

    class _BrokenAPI:
        async def get_market_items(self, **kw):
            raise RuntimeError("API down")

    async def run():
        out = await collect_market_snapshot(_BrokenAPI(), games=["csgo"])
        return out

    out = asyncio.run(run())
    assert "csgo" in out["games"]
    # The _collect_game_data catches the error and returns zeros
    assert out["games"]["csgo"]["items_count"] == 0
    assert out["games"]["csgo"]["sales_count"] == 0
    assert out["total_items"] == 0
    assert out["total_sales"] == 0
    print("  [OK] snapshot handles API error gracefully (returns zeros, no crash)")


# ---------------------------------------------------------------------------
# Test 5: MarketDataCollector.collect_market_snapshot delegates correctly
# ---------------------------------------------------------------------------
def test_collector_delegates():
    """Verify that MarketDataCollector.collect_market_snapshot calls both
    the snapshot fetcher and the storage layer."""
    from unittest.mock import patch

    from src.analytics.data_collector import MarketDataCollector

    class _FakeAPI:
        async def get_market_items(self, game, limit, offset):
            return {
                "objects": [
                    {"price": {"USD": "500"}, "inMarket": 1},
                ]
            }

    async def run():
        c = MarketDataCollector(_FakeAPI(), db_manager="dummy")
        with patch(
            "src.analytics.data_collector.collector.collect_market_snapshot"
        ) as m_snap, patch(
            "src.analytics.data_collector.collector.store_snapshot"
        ) as m_store:
            m_snap.return_value = {
                "timestamp": "now",
                "games": {"csgo": {"items_count": 1, "sales_count": 1}},
                "total_items": 1,
                "total_sales": 1,
            }
            m_store.return_value = None
            out = await c.collect_market_snapshot()
            return m_snap, m_store, out

    m_snap, m_store, out = asyncio.run(run())
    assert m_snap.await_count == 1, "snapshot should be called once"
    assert m_store.await_count == 1, "store_snapshot should be called once"
    assert out["total_items"] == 1
    print("  [OK] MarketDataCollector.collect_market_snapshot calls both layers")


# ---------------------------------------------------------------------------
# Test 6: start/stop lifecycle (idempotency, task creation)
# ---------------------------------------------------------------------------
def test_lifecycle():
    from unittest.mock import patch

    from src.analytics.data_collector import MarketDataCollector

    class _FakeAPI:
        async def get_market_items(self, **kw):
            return {"objects": []}

    async def run():
        c = MarketDataCollector(_FakeAPI(), "dummy", collection_interval_minutes=1)
        with patch(
            "src.analytics.data_collector.collector.collect_market_snapshot"
        ) as m_snap, patch(
            "src.analytics.data_collector.collector.cleanup_old_data"
        ) as m_clean:
            m_snap.return_value = {
                "timestamp": "now", "games": {},
                "total_items": 0, "total_sales": 0,
            }
            m_clean.return_value = 0
            await c.start()
            assert c._running is True
            assert c._task is not None

            # second start is a no-op
            await c.start()
            assert c._running is True

            await asyncio.sleep(0.05)
            await c.stop()
            assert c._running is False
            return m_snap, m_clean

    m_snap, m_clean = asyncio.run(run())
    assert m_snap.await_count >= 1, "snapshot should have been called"
    print(f"  [OK] start/stop lifecycle: {m_snap.await_count} snapshots taken")


# ---------------------------------------------------------------------------
# Test 7: _collection_loop catches errors (won't crash the loop)
# ---------------------------------------------------------------------------
def test_collection_loop_error_swallower():
    from unittest.mock import patch

    from src.analytics.data_collector import MarketDataCollector

    class _FakeAPI:
        pass

    async def run():
        # collection_interval_minutes=0 → 0s sleep, so the loop spins
        c = MarketDataCollector(_FakeAPI(), "dummy", collection_interval_minutes=0)
        c._running = True

        call_count = 0

        async def fake_collect(*a, **kw):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("first call fails")
            return {
                "timestamp": "now", "games": {},
                "total_items": 0, "total_sales": 0,
            }

        async def fake_cleanup(*a, **kw):
            return 0

        with patch(
            "src.analytics.data_collector.collector.collect_market_snapshot",
            side_effect=fake_collect,
        ), patch(
            "src.analytics.data_collector.collector.cleanup_old_data",
            side_effect=fake_cleanup,
        ):
            async def stopper():
                await asyncio.sleep(0.1)
                c._running = False

            await asyncio.gather(c._collection_loop(), stopper())
        return call_count

    n = asyncio.run(run())
    assert n >= 2, f"loop should survive the first error and run again (got {n})"
    print(f"  [OK] _collection_loop survives errors ({n} iterations)")


# ---------------------------------------------------------------------------
# Test 8: storage helpers signatures
# ---------------------------------------------------------------------------
def test_storage_signatures():
    from src.analytics.data_collector.storage import (
        cleanup_old_data,
        export_to_csv,
        store_snapshot,
    )
    import inspect

    # store_snapshot(db_manager, snapshot) -> None
    s1 = inspect.signature(store_snapshot)
    assert "db_manager" in s1.parameters
    assert "snapshot" in s1.parameters

    # cleanup_old_data(db_manager, retention_days) -> int
    s2 = inspect.signature(cleanup_old_data)
    assert "db_manager" in s2.parameters
    assert "retention_days" in s2.parameters

    # export_to_csv(db_manager, output_path, start_date, end_date) -> int
    s3 = inspect.signature(export_to_csv)
    assert "db_manager" in s3.parameters
    assert "output_path" in s3.parameters
    assert "start_date" in s3.parameters
    assert "end_date" in s3.parameters
    print("  [OK] storage helpers have expected signatures")


# ---------------------------------------------------------------------------
# Test 9: package layout — all files exist and are <200 LOC
# ---------------------------------------------------------------------------
def test_package_layout():
    pkg_dir = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        os.pardir,
        "src",
        "analytics",
        "data_collector",
    )
    pkg_dir = os.path.abspath(pkg_dir)
    expected = ["__init__.py", "collector.py", "snapshot.py", "storage.py"]
    present = sorted(
        f for f in os.listdir(pkg_dir) if not f.startswith("__pycache__")
    )
    assert sorted(expected) == present, f"expected {expected}, got {present}"

    # Check all files < 200 LOC
    for fname in expected:
        path = os.path.join(pkg_dir, fname)
        with open(path) as f:
            loc = sum(1 for _ in f)
        assert loc < 200, f"{fname} is {loc} LOC, expected < 200"
    print(f"  [OK] package has {len(expected)} files, all < 200 LOC")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("\n=== src/analytics/data_collector refactor smoke test ===\n")
    tests = [
        ("Public API", test_public_api),
        ("Class identity", test_class_identity),
        ("__init__ attributes", test_init_attributes),
        ("Snapshot collection", test_snapshot_collection),
        ("Snapshot error handling", test_snapshot_handles_api_error),
        ("Collector delegation", test_collector_delegates),
        ("Start/stop lifecycle", test_lifecycle),
        ("Loop error swallow", test_collection_loop_error_swallower),
        ("Storage signatures", test_storage_signatures),
        ("Package layout", test_package_layout),
    ]
    passed = 0
    for label, fn in tests:
        try:
            fn()
            passed += 1
        except AssertionError as e:
            print(f"  [FAIL] {label}: {e}")
        except Exception as e:
            print(f"  [ERROR] {label}: {type(e).__name__}: {e}")
    print(f"\n{passed}/{len(tests)} tests passed")
    return 0 if passed == len(tests) else 1


if __name__ == "__main__":
    raise SystemExit(main())
