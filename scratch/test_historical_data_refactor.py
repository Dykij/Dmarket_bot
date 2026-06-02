"""
Smoke test for src/analytics/historical_data refactor (408 LOC → 4 files).

Verifies:
    1. Public API backward compat (3 names importable from package)
    2. Cross-module re-exports work
    3. PricePoint to_dict / from_dict round-trip
    4. PriceHistory computed properties (avg/min/max/volume/volatility)
    5. Source functions: empty on error (no exceptions leak)
    6. HistoricalDataCollector cache TTL behavior
    7. collect_batch returns dict keyed by title
    8. get_cache_stats shape
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from decimal import Decimal


# ---------------------------------------------------------------------------
# Test 1: Public API backward compat
# ---------------------------------------------------------------------------
def test_public_api():
    from src.analytics.historical_data import (
        HistoricalDataCollector,
        PriceHistory,
        PricePoint,
    )

    # All 3 names from the original __all__ must still be importable
    assert HistoricalDataCollector.__name__ == "HistoricalDataCollector"
    assert PriceHistory.__name__ == "PriceHistory"
    assert PricePoint.__name__ == "PricePoint"
    print("  [OK] 3 public names importable from historical_data package")


# ---------------------------------------------------------------------------
# Test 2: Cross-module re-exports are the SAME objects
# ---------------------------------------------------------------------------
def test_cross_module_identity():
    from src.analytics.historical_data import PricePoint as P1
    from src.analytics.historical_data.models import PricePoint as P2

    assert P1 is P2, "PricePoint should be the SAME class from both paths"
    print("  [OK] PricePoint is the same class from package and submodule")


# ---------------------------------------------------------------------------
# Test 3: PricePoint to_dict / from_dict round-trip
# ---------------------------------------------------------------------------
def test_price_point_roundtrip():
    from src.analytics.historical_data import PricePoint

    pp = PricePoint(
        game="csgo",
        title="AK-47 | Redline (FT)",
        price=Decimal("12.34"),
        timestamp=datetime(2026, 6, 2, 12, 0, 0, tzinfo=UTC),
        volume=42,
        source="market",
    )
    d = pp.to_dict()
    assert d["game"] == "csgo"
    assert d["title"] == "AK-47 | Redline (FT)"
    assert d["price"] == 12.34
    assert d["volume"] == 42
    assert d["source"] == "market"

    pp2 = PricePoint.from_dict(d)
    assert pp2.game == pp.game
    assert pp2.title == pp.title
    assert pp2.price == pp.price
    assert pp2.volume == pp.volume
    assert pp2.source == pp.source
    assert pp2.timestamp == pp.timestamp
    print("  [OK] PricePoint to_dict / from_dict round-trip preserves all fields")


# ---------------------------------------------------------------------------
# Test 4: PriceHistory computed properties
# ---------------------------------------------------------------------------
def test_price_history_properties():
    from src.analytics.historical_data import PriceHistory, PricePoint

    pts = [
        PricePoint(
            game="csgo", title="X", price=Decimal("10"),
            timestamp=datetime(2026, 1, 1, tzinfo=UTC), volume=5,
        ),
        PricePoint(
            game="csgo", title="X", price=Decimal("20"),
            timestamp=datetime(2026, 1, 2, tzinfo=UTC), volume=3,
        ),
        PricePoint(
            game="csgo", title="X", price=Decimal("30"),
            timestamp=datetime(2026, 1, 3, tzinfo=UTC), volume=2,
        ),
    ]
    h = PriceHistory(game="csgo", title="X", points=pts)

    assert h.average_price == Decimal("20")
    assert h.min_price == Decimal("10")
    assert h.max_price == Decimal("30")
    assert h.total_volume == 10
    assert 0.0 < h.price_volatility < 1.0  # ~0.408

    # Empty
    empty = PriceHistory(game="csgo", title="Y")
    assert empty.average_price == Decimal(0)
    assert empty.min_price == Decimal(0)
    assert empty.max_price == Decimal(0)
    assert empty.total_volume == 0
    assert empty.price_volatility == 0.0
    print("  [OK] PriceHistory avg/min/max/volume/volatility (incl. empty case)")


# ---------------------------------------------------------------------------
# Test 5: Source functions return [] on error (no leak)
# ---------------------------------------------------------------------------
def test_sources_no_leak():
    from src.analytics.historical_data.sources import (
        collect_from_aggregated,
        collect_from_sales_history,
    )

    class _BrokenAPI:
        async def get_sales_history(self, **_):
            raise RuntimeError("API down")

        async def get_aggregated_prices_bulk(self, **_):
            raise RuntimeError("API down")

    api = _BrokenAPI()

    async def run():
        sales = await collect_from_sales_history(api, "csgo", "X", 30)
        agg = await collect_from_aggregated(api, "csgo", "X")
        return sales, agg

    sales, agg = asyncio.run(run())
    assert sales == [], f"expected [], got {sales}"
    assert agg == [], f"expected [], got {agg}"
    print("  [OK] source functions return [] on API error (no exception leak)")


# ---------------------------------------------------------------------------
# Test 6: HistoricalDataCollector cache TTL
# ---------------------------------------------------------------------------
def test_collector_cache():
    from src.analytics.historical_data import HistoricalDataCollector

    class _FakeAPI:
        def __init__(self):
            self.sales_calls = 0
            self.agg_calls = 0

        async def get_sales_history(self, **kwargs):
            self.sales_calls += 1
            return {"sales": []}

        async def get_aggregated_prices_bulk(self, **kwargs):
            self.agg_calls += 1
            return {"aggregatedPrices": []}

    async def run():
        api = _FakeAPI()
        c = HistoricalDataCollector(api, cache_ttl_minutes=60)

        # First call: cache miss
        h1 = await c.collect_price_history("csgo", "X", 30, use_cache=True)
        # Second call: cache hit
        h2 = await c.collect_price_history("csgo", "X", 30, use_cache=True)
        return api, h1, h2

    api, h1, h2 = asyncio.run(run())
    assert h1 is h2, "second call should return the SAME cached object"
    assert api.sales_calls == 1, f"expected 1 sales call, got {api.sales_calls}"
    assert api.agg_calls == 1, f"expected 1 agg call, got {api.agg_calls}"
    print("  [OK] collector cache hit returns same object, no extra API calls")


def test_collector_cache_expiry():
    from src.analytics.historical_data import HistoricalDataCollector

    class _FakeAPI:
        def __init__(self):
            self.n = 0

        async def get_sales_history(self, **kw):
            self.n += 1
            return {"sales": []}

        async def get_aggregated_prices_bulk(self, **kw):
            return {"aggregatedPrices": []}

    async def run():
        api = _FakeAPI()
        # ttl = 0 means "expire immediately"
        c = HistoricalDataCollector(api, cache_ttl_minutes=0)
        await c.collect_price_history("csgo", "X", 30)
        # Sleep just enough for the timestamp to be in the past
        await asyncio.sleep(0.05)
        await c.collect_price_history("csgo", "X", 30)
        return api

    api = asyncio.run(run())
    assert api.n == 2, f"expected 2 sales calls (cache miss both), got {api.n}"
    print("  [OK] expired cache entry triggers re-fetch")


# ---------------------------------------------------------------------------
# Test 7: collect_batch returns dict keyed by title
# ---------------------------------------------------------------------------
def test_collect_batch():
    from src.analytics.historical_data import HistoricalDataCollector

    class _FakeAPI:
        async def get_sales_history(self, **kw):
            return {"sales": []}

        async def get_aggregated_prices_bulk(self, **kw):
            return {"aggregatedPrices": []}

    async def run():
        c = HistoricalDataAPI = HistoricalDataCollector(_FakeAPI())
        out = await c.collect_batch("csgo", ["AK-47", "AWP", "M4A4"])
        return out

    out = asyncio.run(run())
    assert set(out.keys()) == {"AK-47", "AWP", "M4A4"}
    for h in out.values():
        assert h.game == "csgo"
    print(f"  [OK] collect_batch returned {len(out)} histories, keyed by title")


# ---------------------------------------------------------------------------
# Test 8: get_cache_stats shape + clear_cache
# ---------------------------------------------------------------------------
def test_cache_stats():
    from src.analytics.historical_data import HistoricalDataCollector

    class _FakeAPI:
        async def get_sales_history(self, **kw):
            return {"sales": []}

        async def get_aggregated_prices_bulk(self, **kw):
            return {"aggregatedPrices": []}

    async def run():
        c = HistoricalDataCollector(_FakeAPI(), cache_ttl_minutes=30)
        await c.collect_price_history("csgo", "X", 30)
        stats = c.get_cache_stats()
        return c, stats

    c, stats = asyncio.run(run())
    assert set(stats.keys()) == {"total_entries", "valid_entries", "ttl_minutes"}
    assert stats["total_entries"] == 1
    assert stats["valid_entries"] == 1
    assert stats["ttl_minutes"] == 30.0

    c.clear_cache()
    stats2 = c.get_cache_stats()
    assert stats2["total_entries"] == 0
    print("  [OK] get_cache_stats has correct shape; clear_cache works")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> int:
    print("\n=== src/analytics/historical_data refactor smoke test ===\n")
    tests = [
        ("Public API", test_public_api),
        ("Cross-module identity", test_cross_module_identity),
        ("PricePoint round-trip", test_price_point_roundtrip),
        ("PriceHistory properties", test_price_history_properties),
        ("Source no-leak", test_sources_no_leak),
        ("Cache TTL hit", test_collector_cache),
        ("Cache TTL expiry", test_collector_cache_expiry),
        ("collect_batch", test_collect_batch),
        ("Cache stats + clear", test_cache_stats),
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
