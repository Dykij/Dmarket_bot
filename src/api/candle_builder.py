"""
candle_builder.py — Build OHLCV candles from DMarket price snapshots.

Collects aggregated prices (best_bid, best_ask, bid_count, ask_count)
every cycle and builds 1min/5min/15min/1h/4h/1d candles in SQLite.

Replaces CS2Cap's /prices/candles endpoint for DMarket-only strategies.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("CandleBuilder")

# Candle intervals in seconds
INTERVALS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "1h": 3600,
    "4h": 14400,
    "1d": 86400,
}


@dataclass
class Candle:
    """OHLCV candle."""
    title: str
    interval: str
    open_ts: float
    open: float
    high: float
    low: float
    close: float
    volume: int  # ask_count + bid_count
    vwap: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "interval": self.interval,
            "open_ts": self.open_ts,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "volume": self.volume,
            "vwap": self.vwap,
        }


class CandleBuilder:
    """
    Builds OHLCV candles from periodic price snapshots.

    Usage:
        builder = CandleBuilder()
        builder.record_snapshot(agg_prices)  # call each cycle
        candles = builder.get_candles("AK-47 | Redline (FT)", interval="1h")
    """

    def __init__(self) -> None:
        # In-memory buffer: {title: [(ts, mid_price, volume), ...]}
        self._buffer: dict[str, list[tuple[float, float, int]]] = {}
        self._max_buffer_size = 10000  # per title

    def record_snapshot(self, agg_prices: dict[str, Any]) -> None:
        """Record a price snapshot from DMarket aggregated prices."""
        ts = time.time()
        for title, agg in agg_prices.items():
            ask = agg.get("best_ask", 0) or 0
            bid = agg.get("best_bid", 0) or 0
            ask_cnt = agg.get("ask_count", 0) or 0
            bid_cnt = agg.get("bid_count", 0) or 0

            if ask <= 0 and bid <= 0:
                continue

            mid = (ask + bid) / 2.0 if ask > 0 and bid > 0 else (ask or bid)
            volume = ask_cnt + bid_cnt

            if title not in self._buffer:
                self._buffer[title] = []
            buf = self._buffer[title]
            buf.append((ts, mid, volume))

            # Trim buffer
            if len(buf) > self._max_buffer_size:
                self._buffer[title] = buf[-self._max_buffer_size:]

    def get_candles(
        self,
        title: str,
        interval: str = "1h",
        count: int = 100,
    ) -> list[Candle]:
        """
        Build OHLCV candles for a title from buffered snapshots.

        Args:
            title: Item market_hash_name
            interval: "1m", "5m", "15m", "1h", "4h", "1d"
            count: Number of candles to return (most recent)

        Returns:
            List of Candle objects (oldest first)
        """
        buf = self._buffer.get(title, [])
        if not buf:
            return []

        interval_sec = INTERVALS.get(interval, 3600)

        # Group snapshots into candle buckets
        buckets: dict[int, list[tuple[float, float, int]]] = {}
        for ts, price, vol in buf:
            bucket_ts = int(ts // interval_sec) * interval_sec
            if bucket_ts not in buckets:
                buckets[bucket_ts] = []
            buckets[bucket_ts].append((ts, price, vol))

        # Build candles from buckets
        candles: list[Candle] = []
        for bucket_ts in sorted(buckets.keys()):
            entries = buckets[bucket_ts]
            if not entries:
                continue

            prices = [e[1] for e in entries]
            volumes = [e[2] for e in entries]

            candle = Candle(
                title=title,
                interval=interval,
                open_ts=bucket_ts,
                open=prices[0],
                high=max(prices),
                low=min(prices),
                close=prices[-1],
                volume=sum(volumes),
                vwap=sum(p * v for p, v in zip(prices, volumes, strict=False)) / max(sum(volumes), 1),
            )
            candles.append(candle)

        return candles[-count:]

    def get_volatility(
        self,
        title: str,
        interval: str = "1h",
        periods: int = 20,
    ) -> dict[str, float]:
        """
        Calculate Garman-Klass volatility from candles.

        Returns:
            {"volatility": float, "regime": str, "atr": float}
        """
        candles = self.get_candles(title, interval=interval, count=periods)
        if len(candles) < 3:
            return {"volatility": 0.0, "regime": "unknown", "atr": 0.0}

        # Garman-Klass volatility
        import math
        gk_values = []
        for c in candles:
            if c.high > 0 and c.low > 0 and c.close > 0 and c.open > 0:
                hl = math.log(c.high / c.low)
                co = math.log(c.close / c.open)
                gk = 0.5 * hl ** 2 - (2 * math.log(2) - 1) * co ** 2
                gk_values.append(max(0, gk))

        if not gk_values:
            return {"volatility": 0.0, "regime": "unknown", "atr": 0.0}

        volatility = math.sqrt(sum(gk_values) / len(gk_values))

        # ATR (Average True Range)
        atr_values = []
        for i in range(1, len(candles)):
            prev_close = candles[i - 1].close
            curr = candles[i]
            if prev_close > 0:
                tr = max(
                    curr.high - curr.low,
                    abs(curr.high - prev_close),
                    abs(curr.low - prev_close),
                )
                atr_values.append(tr)

        atr = sum(atr_values) / len(atr_values) if atr_values else 0.0

        # Regime detection
        if volatility < 0.01:
            regime = "low"
        elif volatility < 0.03:
            regime = "normal"
        elif volatility < 0.05:
            regime = "high"
        else:
            regime = "extreme"

        return {
            "volatility": round(volatility, 4),
            "regime": regime,
            "atr": round(atr, 4),
        }

    def get_stats(self) -> dict[str, Any]:
        """Get builder statistics."""
        total_snapshots = sum(len(buf) for buf in self._buffer.values())
        return {
            "titles_tracked": len(self._buffer),
            "total_snapshots": total_snapshots,
            "memory_mb": round(total_snapshots * 24 / 1024 / 1024, 2),
        }


# Singleton
candle_builder = CandleBuilder()
