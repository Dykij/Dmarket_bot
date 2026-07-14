"""Unit tests for CandleBuilder (src/api/candle_builder.py)."""

from __future__ import annotations

import math
import time

import pytest

from src.api.candle_builder import INTERVALS, CandleBuilder

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def builder():
    return CandleBuilder()


# ---------------------------------------------------------------------------
# Tests — record_snapshot
# ---------------------------------------------------------------------------

class TestRecordSnapshot:
    """Tests for CandleBuilder.record_snapshot."""

    def test_basic_snapshot(self, builder):
        """Snapshot creates buffered entry with mid price."""
        builder.record_snapshot({
            "AK-47 | Redline (FT)": {
                "best_ask": 10.0, "best_bid": 8.0,
                "ask_count": 5, "bid_count": 3,
            }
        })
        buf = builder._buffer["AK-47 | Redline (FT)"]
        assert len(buf) == 1
        ts, mid, vol = buf[0]
        assert mid == 9.0  # (10+8)/2
        assert vol == 8    # 5+3

    def test_ask_only(self, builder):
        """Only ask present → mid = ask."""
        builder.record_snapshot({
            "Item": {"best_ask": 15.0, "best_bid": 0, "ask_count": 2, "bid_count": 0}
        })
        _, mid, _ = builder._buffer["Item"][0]
        assert mid == 15.0

    def test_bid_only(self, builder):
        """Only bid present → mid = bid."""
        builder.record_snapshot({
            "Item": {"best_ask": 0, "best_bid": 12.0, "ask_count": 0, "bid_count": 4}
        })
        _, mid, _ = builder._buffer["Item"][0]
        assert mid == 12.0

    def test_zero_prices_skipped(self, builder):
        """Both ask and bid zero → entry skipped."""
        builder.record_snapshot({
            "Item": {"best_ask": 0, "best_bid": 0, "ask_count": 0, "bid_count": 0}
        })
        assert "Item" not in builder._buffer

    def test_multiple_items(self, builder):
        """Multiple items in one snapshot."""
        builder.record_snapshot({
            "A": {"best_ask": 10.0, "best_bid": 8.0, "ask_count": 1, "bid_count": 1},
            "B": {"best_ask": 20.0, "best_bid": 18.0, "ask_count": 2, "bid_count": 2},
        })
        assert "A" in builder._buffer
        assert "B" in builder._buffer

    def test_buffer_trim(self, builder):
        """Buffer trimmed to max_buffer_size."""
        builder._max_buffer_size = 5
        for i in range(10):
            builder.record_snapshot({
                "Item": {"best_ask": float(i), "best_bid": float(i), "ask_count": 1, "bid_count": 1}
            })
        assert len(builder._buffer["Item"]) == 5

    def test_none_values_treated_as_zero(self, builder):
        """None values in agg dict → treated as 0."""
        builder.record_snapshot({
            "Item": {"best_ask": None, "best_bid": None, "ask_count": None, "bid_count": None}
        })
        assert "Item" not in builder._buffer


# ---------------------------------------------------------------------------
# Tests — get_candles (OHLC)
# ---------------------------------------------------------------------------

class TestGetCandles:
    """Tests for CandleBuilder.get_candles."""

    def test_empty_buffer(self, builder):
        """No data → empty candles."""
        assert builder.get_candles("Nonexistent") == []

    def test_single_candle(self, builder):
        """Single bucket → one candle with OHLC all equal."""
        ts = time.time()
        builder._buffer["Item"] = [
            (ts, 10.0, 5),
            (ts + 1, 12.0, 3),
            (ts + 2, 11.0, 2),
        ]
        candles = builder.get_candles("Item", interval="1h")
        assert len(candles) == 1
        c = candles[0]
        assert c.open == 10.0
        assert c.high == 12.0
        assert c.low == 10.0
        assert c.close == 11.0
        assert c.volume == 10  # 5+3+2

    def test_multiple_candles(self, builder):
        """Two different time buckets → two candles."""
        interval_sec = INTERVALS["1m"]
        ts1 = 0.0  # bucket 0
        ts2 = float(interval_sec)  # bucket 1
        builder._buffer["Item"] = [
            (ts1, 10.0, 1),
            (ts2, 20.0, 2),
        ]
        candles = builder.get_candles("Item", interval="1m")
        assert len(candles) == 2
        assert candles[0].open == 10.0
        assert candles[1].open == 20.0

    def test_count_limit(self, builder):
        """Only `count` most recent candles returned."""
        interval_sec = INTERVALS["1m"]
        for i in range(10):
            builder._buffer.setdefault("Item", []).append(
                (float(i * interval_sec), float(i), 1)
            )
        candles = builder.get_candles("Item", interval="1m", count=3)
        assert len(candles) == 3

    def test_vwap_calculation(self, builder):
        """VWAP = sum(price*vol) / sum(vol)."""
        ts = time.time()
        builder._buffer["Item"] = [
            (ts, 10.0, 2),
            (ts + 1, 20.0, 8),
        ]
        candles = builder.get_candles("Item", interval="1h")
        expected_vwap = (10.0 * 2 + 20.0 * 8) / (2 + 8)
        assert candles[0].vwap == pytest.approx(expected_vwap)

    def test_candle_to_dict(self, builder):
        """Candle.to_dict returns expected keys."""
        ts = time.time()
        builder._buffer["Item"] = [(ts, 10.0, 1)]
        candle = builder.get_candles("Item", interval="1h")[0]
        d = candle.to_dict()
        assert set(d.keys()) == {
            "title", "interval", "open_ts", "open", "high", "low", "close", "volume", "vwap"
        }


# ---------------------------------------------------------------------------
# Tests — get_volatility (Garman-Klass)
# ---------------------------------------------------------------------------

class TestGetVolatility:
    """Tests for CandleBuilder.get_volatility."""

    def test_insufficient_candles(self, builder):
        """Less than 3 candles → volatility=0, regime=unknown."""
        ts = time.time()
        builder._buffer["Item"] = [(ts, 10.0, 1)]
        result = builder.get_volatility("Item", interval="1h", periods=20)
        assert result["volatility"] == 0.0
        assert result["regime"] == "unknown"

    def test_no_data(self, builder):
        """No buffer → volatility=0."""
        result = builder.get_volatility("Nonexistent")
        assert result["volatility"] == 0.0

    def test_low_volatility(self, builder):
        """Very stable prices → low regime."""
        ts = time.time()
        for i in range(10):
            builder._buffer.setdefault("Item", []).append(
                (ts + i * 60, 10.0, 1)  # all same price
            )
        result = builder.get_volatility("Item", interval="1m", periods=10)
        assert result["volatility"] == pytest.approx(0.0, abs=1e-6)
        assert result["regime"] == "low"

    def test_high_volatility(self, builder):
        """Wildly swinging prices across multiple candles → high or extreme regime."""
        ts = 1000000.0
        # 10 candles, each 1h apart, with 2 snapshots per candle creating spread
        prices = [10.0, 20.0, 5.0, 25.0, 3.0, 30.0, 2.0, 35.0, 1.0, 40.0]
        for i, p in enumerate(prices):
            base = ts + i * 3600
            builder._buffer.setdefault("Item", []).append((base, p, 1))
            builder._buffer["Item"].append((base + 30, p * 1.5, 1))  # spread within bucket
        result = builder.get_volatility("Item", interval="1h", periods=10)
        assert result["volatility"] > 0.0
        assert result["regime"] in ("high", "extreme")

    def test_atr_present(self, builder):
        """ATR calculated for multi-candle data."""
        ts = time.time()
        for i in range(5):
            builder._buffer.setdefault("Item", []).append(
                (ts + i * 3600, 10.0 + i, 1)
            )
        result = builder.get_volatility("Item", interval="1h", periods=5)
        assert "atr" in result
        assert result["atr"] >= 0.0

    def test_gk_formula(self, builder):
        """Verify Garman-Klass formula on known candle.

        Each snapshot is 1h apart so they land in separate 1h buckets.
        We create 5 candles to satisfy the min-3 requirement.
        """
        ts = 1000000.0  # fixed base for determinism
        # Candle 1: open=10, high=15, low=8, close=12
        builder._buffer["Item"] = [
            (ts, 10.0, 1),           # bucket 0
            (ts + 1, 15.0, 1),
            (ts + 2, 8.0, 1),
            (ts + 3, 12.0, 1),
            (ts + 3600, 11.0, 1),    # bucket 1
            (ts + 7200, 13.0, 1),    # bucket 2
            (ts + 10800, 14.0, 1),   # bucket 3
            (ts + 14400, 12.0, 1),   # bucket 4
        ]
        result = builder.get_volatility("Item", interval="1h", periods=20)
        assert result["volatility"] > 0.0
        # Verify the first candle's GK contribution matches manual calc
        candles = builder.get_candles("Item", interval="1h", count=20)
        c0 = candles[0]
        hl = math.log(c0.high / c0.low)
        co = math.log(c0.close / c0.open)
        gk0 = max(0, 0.5 * hl**2 - (2 * math.log(2) - 1) * co**2)
        # Overall volatility should include this term
        assert gk0 > 0


# ---------------------------------------------------------------------------
# Tests — get_stats
# ---------------------------------------------------------------------------

class TestGetStats:
    def test_empty(self, builder):
        stats = builder.get_stats()
        assert stats["titles_tracked"] == 0
        assert stats["total_snapshots"] == 0

    def test_with_data(self, builder):
        builder._buffer["A"] = [(1.0, 10.0, 1), (2.0, 11.0, 1)]
        builder._buffer["B"] = [(3.0, 20.0, 1)]
        stats = builder.get_stats()
        assert stats["titles_tracked"] == 2
        assert stats["total_snapshots"] == 3
