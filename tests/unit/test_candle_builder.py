"""Unit tests for CandleBuilder and Candle.

Covers: record_snapshot, get_candles (bucketing, intervals),
get_volatility (GK vol, ATR, regimes), get_stats, edge cases.
"""

from __future__ import annotations

import math
import time
from unittest.mock import patch

import pytest

from src.api.candle_builder import INTERVALS, Candle, CandleBuilder


@pytest.fixture()
def builder():
    return CandleBuilder()


# =====================================================================
# Candle Dataclass
# =====================================================================


class TestCandleDataclass:
    """Tests for Candle.to_dict()."""

    def test_to_dict(self):
        c = Candle(
            title="Item", interval="1h", open_ts=1000.0,
            open=10.0, high=15.0, low=9.0, close=12.0,
            volume=50, vwap=11.5,
        )
        d = c.to_dict()
        assert d["title"] == "Item"
        assert d["interval"] == "1h"
        assert d["open"] == 10.0
        assert d["high"] == 15.0
        assert d["low"] == 9.0
        assert d["close"] == 12.0
        assert d["volume"] == 50
        assert d["vwap"] == 11.5


# =====================================================================
# INTERVALS
# =====================================================================


class TestIntervals:
    """Verify interval definitions."""

    def test_all_intervals_present(self):
        assert set(INTERVALS.keys()) == {"1m", "5m", "15m", "1h", "4h", "1d"}

    def test_interval_seconds(self):
        assert INTERVALS["1m"] == 60
        assert INTERVALS["5m"] == 300
        assert INTERVALS["15m"] == 900
        assert INTERVALS["1h"] == 3600
        assert INTERVALS["4h"] == 14400
        assert INTERVALS["1d"] == 86400


# =====================================================================
# record_snapshot
# =====================================================================


class TestRecordSnapshot:
    """Tests for snapshot recording."""

    def test_single_snapshot(self, builder: CandleBuilder):
        """Single snapshot stored correctly."""
        builder.record_snapshot({"Item": {"best_ask": 12.0, "best_bid": 10.0, "ask_count": 5, "bid_count": 3}})
        assert len(builder._buffer["Item"]) == 1
        ts, mid, vol = builder._buffer["Item"][0]
        assert mid == pytest.approx(11.0)
        assert vol == 8

    def test_ask_only(self, builder: CandleBuilder):
        """Only ask present → mid = ask."""
        builder.record_snapshot({"Item": {"best_ask": 15.0, "best_bid": 0, "ask_count": 2, "bid_count": 0}})
        _, mid, _ = builder._buffer["Item"][0]
        assert mid == pytest.approx(15.0)

    def test_bid_only(self, builder: CandleBuilder):
        """Only bid present → mid = bid."""
        builder.record_snapshot({"Item": {"best_ask": 0, "best_bid": 8.0, "ask_count": 0, "bid_count": 4}})
        _, mid, _ = builder._buffer["Item"][0]
        assert mid == pytest.approx(8.0)

    def test_both_zero_skipped(self, builder: CandleBuilder):
        """Both ask and bid zero → skipped."""
        builder.record_snapshot({"Item": {"best_ask": 0, "best_bid": 0, "ask_count": 1, "bid_count": 1}})
        assert "Item" not in builder._buffer

    def test_none_values_treated_as_zero(self, builder: CandleBuilder):
        """None values → treated as 0."""
        builder.record_snapshot({"Item": {"best_ask": None, "best_bid": None, "ask_count": None, "bid_count": None}})
        assert "Item" not in builder._buffer

    def test_multiple_titles(self, builder: CandleBuilder):
        """Multiple titles tracked independently."""
        builder.record_snapshot({
            "A": {"best_ask": 10.0, "best_bid": 8.0, "ask_count": 1, "bid_count": 1},
            "B": {"best_ask": 20.0, "best_bid": 18.0, "ask_count": 2, "bid_count": 2},
        })
        assert "A" in builder._buffer
        assert "B" in builder._buffer
        assert len(builder._buffer["A"]) == 1
        assert len(builder._buffer["B"]) == 1

    def test_buffer_trim(self, builder: CandleBuilder):
        """Buffer trimmed when exceeding max_buffer_size."""
        builder._max_buffer_size = 5
        for i in range(10):
            builder.record_snapshot({"Item": {"best_ask": 10.0 + i, "best_bid": 9.0 + i, "ask_count": 1, "bid_count": 1}})
        assert len(builder._buffer["Item"]) == 5


# =====================================================================
# get_candles
# =====================================================================


class TestGetCandles:
    """Tests for candle building from buffer."""

    def test_empty_buffer(self, builder: CandleBuilder):
        """No data → empty candles list."""
        assert builder.get_candles("Item") == []

    def test_single_candle_1m(self, builder: CandleBuilder):
        """Single snapshot → single candle."""
        now = time.time()
        builder._buffer["Item"] = [(now, 10.0, 5)]

        candles = builder.get_candles("Item", interval="1m")
        assert len(candles) == 1
        assert candles[0].open == pytest.approx(10.0)
        assert candles[0].high == pytest.approx(10.0)
        assert candles[0].low == pytest.approx(10.0)
        assert candles[0].close == pytest.approx(10.0)
        assert candles[0].volume == 5

    def test_multiple_snapshots_one_bucket(self, builder: CandleBuilder):
        """Multiple snapshots in same 1m bucket → one candle.

        base=1000 → bucket = int(1000//60)*60 = 960
        All timestamps must be < 1020 to stay in bucket 960.
        """
        base = 1000.0
        builder._buffer["Item"] = [
            (base, 10.0, 2),
            (base + 5, 12.0, 3),
            (base + 10, 11.0, 1),
        ]

        candles = builder.get_candles("Item", interval="1m")
        assert len(candles) == 1
        c = candles[0]
        assert c.open == pytest.approx(10.0)
        assert c.high == pytest.approx(12.0)
        assert c.low == pytest.approx(10.0)
        assert c.close == pytest.approx(11.0)
        assert c.volume == 6

    def test_two_buckets(self, builder: CandleBuilder):
        """Snapshots across two 1m buckets → two candles."""
        # base=1000 → bucket 960, base+60=1060 → bucket 1020
        base = 1000.0
        builder._buffer["Item"] = [
            (base, 10.0, 2),
            (base + 60, 15.0, 3),
        ]

        candles = builder.get_candles("Item", interval="1m")
        assert len(candles) == 2
        assert candles[0].close == pytest.approx(10.0)
        assert candles[1].open == pytest.approx(15.0)

    def test_5m_interval(self, builder: CandleBuilder):
        """5m interval groups correctly.

        base=1000 → bucket = int(1000//300)*300 = 900
        base+100=1100 → bucket = int(1100//300)*300 = 900 (same)
        base+200=1200 → bucket = int(1200//300)*300 = 1200 (different!)
        Use base+250=1250 → int(1250//300)*300 = 1200 (different, need base+290=1290 → 1200)
        Keep all within 900 bucket: base+100=1100 → 900, base+250=1250 → 1200 (different!)
        Actually base+200=1200 → 1200 is different. Use base+150=1150 → 900 (same).
        """
        base = 1000.0
        builder._buffer["Item"] = [
            (base, 10.0, 1),
            (base + 100, 12.0, 2),
            (base + 150, 11.0, 3),
        ]

        candles = builder.get_candles("Item", interval="5m")
        assert len(candles) == 1
        assert candles[0].volume == 6

    def test_count_limit(self, builder: CandleBuilder):
        """Only most recent `count` candles returned."""
        base = 0.0
        # Spread across 10 different 1m buckets
        builder._buffer["Item"] = [
            (base + i * 65, float(i), 1) for i in range(10)
        ]

        candles = builder.get_candles("Item", interval="1m", count=3)
        assert len(candles) <= 3

    def test_vwap_calculation(self, builder: CandleBuilder):
        """VWAP = sum(price*vol) / sum(vol)."""
        base = 1000.0
        builder._buffer["Item"] = [
            (base, 10.0, 2),
            (base + 10, 20.0, 8),
        ]

        candles = builder.get_candles("Item", interval="1m")
        expected_vwap = (10.0 * 2 + 20.0 * 8) / (2 + 8)
        assert candles[0].vwap == pytest.approx(expected_vwap)

    def test_unknown_interval_defaults_to_1h(self, builder: CandleBuilder):
        """Unknown interval string defaults to 3600s."""
        base = 1000.0
        builder._buffer["Item"] = [(base, 10.0, 1)]

        candles = builder.get_candles("Item", interval="bogus")
        assert len(candles) == 1


# =====================================================================
# get_volatility
# =====================================================================


class TestGetVolatility:
    """Tests for Garman-Klass volatility calculation."""

    def test_too_few_candles(self, builder: CandleBuilder):
        """Less than 3 candles → unknown regime."""
        builder._buffer["Item"] = [(1000.0, 10.0, 1)]
        result = builder.get_volatility("Item")
        assert result["volatility"] == 0.0
        assert result["regime"] == "unknown"
        assert result["atr"] == 0.0

    def test_low_volatility_regime(self, builder: CandleBuilder):
        """Near-zero price changes → low regime."""
        base = 0.0
        for i in range(10):
            builder._buffer["Item"] = builder._buffer.get("Item", [])
            builder._buffer["Item"].append((base + i * 70, 10.0, 1))

        result = builder.get_volatility("Item", interval="1m", periods=10)
        assert result["regime"] == "low"
        assert result["volatility"] < 0.01

    def test_high_volatility_regime(self, builder: CandleBuilder):
        """Large price swings → high or extreme regime.

        Each candle bucket gets multiple snapshots with different prices
        so that high != low and open != close, producing nonzero GK values.
        """
        base = 0.0
        # 10 buckets, each with 2 snapshots at different prices
        for i in range(10):
            lo = 5.0 + i * 3.0
            hi = lo + 20.0 + i * 5.0
            builder._buffer["Item"] = builder._buffer.get("Item", [])
            builder._buffer["Item"].append((base + i * 70, lo, 1))
            builder._buffer["Item"].append((base + i * 70 + 30, hi, 1))

        result = builder.get_volatility("Item", interval="1m", periods=10)
        assert result["volatility"] > 0.0
        assert result["regime"] in ("high", "extreme")

    def test_atr_positive(self, builder: CandleBuilder):
        """ATR is positive when prices move across candles."""
        base = 0.0
        # 4 buckets, each with a single snapshot but different prices
        prices = [10.0, 25.0, 8.0, 30.0]
        for i, p in enumerate(prices):
            builder._buffer["Item"] = builder._buffer.get("Item", [])
            builder._buffer["Item"].append((base + i * 70, p, 1))

        result = builder.get_volatility("Item", interval="1m", periods=4)
        assert result["atr"] > 0.0

    def test_empty_title(self, builder: CandleBuilder):
        """Title not in buffer → unknown regime."""
        result = builder.get_volatility("NoSuch")
        assert result["regime"] == "unknown"

    def test_zero_price_candles_skipped(self, builder: CandleBuilder):
        """Candles with zero OHLC values skipped in GK calc."""
        base = 0.0
        # First candle has open=0 → skipped in GK
        builder._buffer["Item"] = [
            (base, 0.0, 1),
            (base + 70, 10.0, 1),
            (base + 140, 12.0, 1),
            (base + 210, 11.0, 1),
        ]

        result = builder.get_volatility("Item", interval="1m", periods=4)
        assert result["volatility"] >= 0.0


# =====================================================================
# get_stats
# =====================================================================


class TestGetStats:
    """Tests for builder statistics."""

    def test_stats_empty(self, builder: CandleBuilder):
        stats = builder.get_stats()
        assert stats["titles_tracked"] == 0
        assert stats["total_snapshots"] == 0
        assert stats["memory_mb"] == 0.0

    def test_stats_with_data(self, builder: CandleBuilder):
        """Need enough snapshots for memory_mb to round > 0.

        memory_mb = round(total_snapshots * 24 / 1024 / 1024, 2)
        8 * 24 = 192 bytes → 0.000183 MB → rounds to 0.0
        Need ~87k snapshots to get 0.01 MB. Use many more.
        """
        builder._buffer["A"] = [(1.0, 10.0, 1)] * 500
        builder._buffer["B"] = [(1.0, 20.0, 2)] * 500

        stats = builder.get_stats()
        assert stats["titles_tracked"] == 2
        assert stats["total_snapshots"] == 1000
        # 1000 * 24 / 1024 / 1024 ≈ 0.0229 MB → rounds to 0.02
        assert stats["memory_mb"] > 0.0


# =====================================================================
# Singleton
# =====================================================================


class TestSingleton:
    """Verify module-level singleton exists."""

    def test_singleton_exists(self):
        from src.api.candle_builder import candle_builder
        assert isinstance(candle_builder, CandleBuilder)


# =====================================================================
# Edge Cases
# =====================================================================


class TestEdgeCases:
    """Edge cases for candle builder."""

    def test_snapshot_with_missing_keys(self, builder: CandleBuilder):
        """Missing keys default to 0."""
        builder.record_snapshot({"Item": {}})
        # ask=0, bid=0 → skipped
        assert "Item" not in builder._buffer

    def test_negative_prices(self, builder: CandleBuilder):
        """Negative ask/bid treated as <=0 → skipped if both zero."""
        builder.record_snapshot({"Item": {"best_ask": -5.0, "best_bid": -3.0, "ask_count": 1, "bid_count": 1}})
        # -5 <= 0 and -3 <= 0 → skip
        assert "Item" not in builder._buffer

    def test_large_volume(self, builder: CandleBuilder):
        """Handles large volume numbers."""
        builder.record_snapshot({"Item": {"best_ask": 10.0, "best_bid": 9.0, "ask_count": 1000000, "bid_count": 500000}})
        _, _, vol = builder._buffer["Item"][0]
        assert vol == 1500000

    def test_candle_ordering_oldest_first(self, builder: CandleBuilder):
        """Candles returned oldest first.

        base=1000 → bucket 960 (ts < 1020)
        base+70=1070 → bucket 1020 (different bucket)
        """
        base = 1000.0
        builder._buffer["Item"] = [
            (base + 70, 30.0, 1),  # bucket 1020
            (base, 10.0, 1),       # bucket 960
        ]

        candles = builder.get_candles("Item", interval="1m")
        assert len(candles) == 2
        # Oldest first
        assert candles[0].open == pytest.approx(10.0)
        assert candles[1].open == pytest.approx(30.0)
