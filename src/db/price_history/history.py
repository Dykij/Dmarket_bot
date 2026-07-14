"""
history.py — Price history (price_history) reads + writes + analytics.

Mixin with the OLAP-side methods: observation writes, recent-price queries,
liquidity metrics, trimmed mean, and wash-trading detection.
Mixed into `PriceHistoryDB` (see `core.py`).

v12.7: write methods wrapped with @with_db_retry.
"""

from __future__ import annotations

import time
from typing import Any

from src.db.db_retry import with_db_retry


class _HistoryMixin:
    """Read + write for the price_history table and its analytics."""

    # These attributes are set on the instance by PriceHistoryDB.__init__
    history_conn: Any

    # ------------------------------------------------------------------
    # Write (HISTORY)
    # ------------------------------------------------------------------
    @with_db_retry(operation_name="record_price")
    def record_price(self, hash_name: str, price: float, source: str = "oracle") -> None:
        """Insert a new price observation into the history DB."""
        with self.history_conn:
            self.history_conn.execute(
                "INSERT INTO price_history (hash_name, price, source, recorded_at) "
                "VALUES (?, ?, ?, ?)",
                (hash_name, price, source, time.time()),
            )

    # ------------------------------------------------------------------
    # Read (HISTORY)
    # ------------------------------------------------------------------
    def get_latest_price(
        self, hash_name: str, max_age_seconds: int = 10800
    ) -> float | None:
        cutoff = time.time() - max_age_seconds
        row = self.history_conn.execute(
            "SELECT price FROM price_history WHERE hash_name = ? AND recorded_at > ? "
            "ORDER BY recorded_at DESC LIMIT 1",
            (hash_name, cutoff),
        ).fetchone()
        return row["price"] if row else None

    def get_latest_price_timestamp(
        self, hash_name: str, max_age_seconds: int = 10800
    ) -> float | None:
        """v12.7: Get timestamp of most recent price for staleness check (P4-3)."""
        cutoff = time.time() - max_age_seconds
        row = self.history_conn.execute(
            "SELECT recorded_at FROM price_history WHERE hash_name = ? AND recorded_at > ? "
            "ORDER BY recorded_at DESC LIMIT 1",
            (hash_name, cutoff),
        ).fetchone()
        return row["recorded_at"] if row else None

    def get_recent_prices(self, hash_name: str, days: int = 7) -> list[tuple[float, float]]:
        cutoff = time.time() - (days * 86400)
        rows = self.history_conn.execute(
            "SELECT price, recorded_at FROM price_history "
            "WHERE hash_name = ? AND recorded_at > ? ORDER BY recorded_at DESC",
            (hash_name, cutoff),
        ).fetchall()
        return [(r["price"], r["recorded_at"]) for r in rows]

    def is_crashing(self, hash_name: str, consecutive_drops: int = 3) -> bool:
        prices = self.get_recent_prices(hash_name, days=14)
        if len(prices) < consecutive_drops + 1:
            return False
        return all(prices[i][0] < prices[i + 1][0] for i in range(consecutive_drops))

    # ------------------------------------------------------------------
    # v12.2 Phase 2.4: Multi-level liquidity verification
    # ------------------------------------------------------------------
    def get_liquidity_metrics(self, hash_name: str, days: int = 23) -> dict[str, Any]:
        """
        Calculate liquidity metrics for an asset based on historical price observations.
        Mirrors the Gemini-recommended multi-level filter:
        - ALL_SALES (total historical observations)
        - DAYS_COUNT (lookback window in days)
        - SALE_COUNT (sales in window)
        - FIRST_SALE (oldest sale in window, in days)
        - LAST_SALE (most recent sale age, in days)

        Returns dict with metrics and an is_liquid flag computed from Config thresholds.
        """
        prices = self.get_recent_prices(hash_name, days=days)
        now = time.time()

        if not prices:
            return {
                "total_sales": 0,
                "sales_in_window": 0,
                "first_sale_age_days": None,
                "last_sale_age_days": None,
                "is_liquid": False,
                "reason": "no_data",
            }

        timestamps = [t for _, t in prices]
        oldest_ts = min(timestamps)
        newest_ts = max(timestamps)

        first_sale_age_days = (now - oldest_ts) / 86400.0
        last_sale_age_days = (now - newest_ts) / 86400.0

        metrics: dict[str, Any] = {
            "total_sales": len(prices),
            "sales_in_window": len(prices),
            "first_sale_age_days": first_sale_age_days,
            "last_sale_age_days": last_sale_age_days,
            "is_liquid": True,
            "reason": "ok",
        }

        # Apply thresholds from config
        from src.config import Config

        if metrics["total_sales"] < Config.MIN_TOTAL_SALES:
            metrics["is_liquid"] = False
            metrics["reason"] = (
                f"insufficient_total_sales({metrics['total_sales']}<{Config.MIN_TOTAL_SALES})"
            )
        elif metrics["sales_in_window"] < Config.MIN_SALES_IN_WINDOW:
            metrics["is_liquid"] = False
            metrics["reason"] = (
                f"insufficient_window_sales"
                f"({metrics['sales_in_window']}<{Config.MIN_SALES_IN_WINDOW})"
            )
        elif metrics["first_sale_age_days"] > Config.MAX_FIRST_SALE_AGE_DAYS:
            metrics["is_liquid"] = False
            metrics["reason"] = (
                f"first_sale_too_old"
                f"({metrics['first_sale_age_days']:.1f}d>{Config.MAX_FIRST_SALE_AGE_DAYS}d)"
            )
        elif metrics["last_sale_age_days"] > Config.MAX_LAST_SALE_AGE_DAYS:
            metrics["is_liquid"] = False
            metrics["reason"] = (
                f"last_sale_too_old"
                f"({metrics['last_sale_age_days']:.1f}d>{Config.MAX_LAST_SALE_AGE_DAYS}d)"
            )

        return metrics

    def passes_liquidity_filter(self, hash_name: str) -> bool:
        """
        Returns True if asset passes all liquidity thresholds from Config.
        """
        metrics = self.get_liquidity_metrics(hash_name)
        return metrics["is_liquid"]

    def get_avg_price(self, hash_name: str, days: int = 7) -> float | None:
        cutoff = time.time() - (days * 86400)
        row = self.history_conn.execute(
            "SELECT AVG(price) as avg_price FROM price_history "
            "WHERE hash_name = ? AND recorded_at > ?",
            (hash_name, cutoff),
        ).fetchone()
        return row["avg_price"] if row and row["avg_price"] else None

    # ------------------------------------------------------------------
    # v12.2 Phase 2.3: Trimmed Mean (resistant to wash trading)
    # ------------------------------------------------------------------
    def get_trimmed_mean(
        self,
        hash_name: str,
        days: int = 14,
        boost_pct: float = 24.0,
        max_outliers: int = 3,
    ) -> float | None:
        """
        Compute the trimmed mean of historical prices.

        Algorithm:
        1. Get all prices within the time window
        2. Compute the arithmetic mean
        3. Iteratively remove up to `max_outliers` points that exceed the mean
           by `boost_pct`% (in either direction)
        4. Recompute the mean on the cleaned set

        Returns None if no data available.

        Example:
            prices = [10, 10, 10, 100, 10, 10]
            raw_mean = 25
            100 is +300% from mean → outlier, remove
            cleaned = [10, 10, 10, 10, 10]
            trimmed_mean = 10
        """
        prices_with_time = self.get_recent_prices(hash_name, days=days)
        if not prices_with_time:
            return None

        prices = [p for p, _ in prices_with_time]
        if not prices:
            return None

        current_prices = list(prices)
        for _ in range(max_outliers):
            if len(current_prices) < 3:
                break
            mean = sum(current_prices) / len(current_prices)
            if mean <= 0:
                break
            upper = mean * (1.0 + boost_pct / 100.0)
            lower = mean * (1.0 - boost_pct / 100.0)
            # Find the most extreme outlier
            worst_idx = -1
            worst_dev = 0.0
            for i, p in enumerate(current_prices):
                if p > upper:
                    dev = (p - mean) / mean
                    if dev > worst_dev:
                        worst_dev = dev
                        worst_idx = i
                elif p < lower:
                    dev = (mean - p) / mean
                    if dev > worst_dev:
                        worst_dev = dev
                        worst_idx = i
            if worst_idx < 0:
                break  # No more outliers
            current_prices.pop(worst_idx)

        if not current_prices:
            return None
        return sum(current_prices) / len(current_prices)

    def detect_wash_trading(
        self,
        hash_name: str,
        days: int = 14,
        boost_pct: float = 24.0,
        max_outliers: int = 3,
        divergence_pct: float = 50.0,
    ) -> bool:
        """
        Returns True if the asset looks LEGITIMATE (not wash-traded).
        Returns False if raw mean is X% higher than trimmed mean,
        indicating anomalous trades inflating the price.

        divergence_pct=50.0 means raw mean is 50% higher than trimmed → flagged.
        """
        trimmed = self.get_trimmed_mean(
            hash_name, days=days, boost_pct=boost_pct, max_outliers=max_outliers
        )
        raw = self.get_avg_price(hash_name, days=days)
        if trimmed is None or raw is None:
            return True  # No data, don't flag
        if trimmed <= 0:
            return True
        # If raw mean is much higher than trimmed mean, wash trading suspected
        divergence = ((raw - trimmed) / trimmed) * 100.0
        return divergence < divergence_pct

    # ------------------------------------------------------------------
    # v14.1 Trade History (CVD / VPIN / VWAP accumulation)
    # ------------------------------------------------------------------
    @with_db_retry(operation_name="save_trades_batch")
    def save_trades_batch(
        self, hash_name: str, trades: list[dict[str, Any]],
    ) -> int:
        """Bulk-insert trade records into trade_history. Returns count inserted.
        
        v15.2: Uses executemany for ~10x speedup on batch inserts.
        """
        now = time.time()
        rows = [
            (hash_name, t["price"], str(t.get("date")) if t.get("date") else None, now)
            for t in trades
            if t.get("price", 0) > 0
        ]
        if not rows:
            return 0
        with self.history_conn:
            self.history_conn.executemany(
                "INSERT OR IGNORE INTO trade_history "
                "(hash_name, price, trade_date, recorded_at) "
                "VALUES (?, ?, ?, ?)",
                rows,
            )
        return len(rows)

    def get_trade_history(
        self, hash_name: str, days: int = 30, limit: int = 200,
    ) -> list[dict[str, Any]]:
        """Read accumulated trade history for microstructure analysis."""
        cutoff = time.time() - (days * 86400)
        rows = self.history_conn.execute(
            "SELECT price, recorded_at FROM trade_history "
            "WHERE hash_name = ? AND recorded_at > ? "
            "ORDER BY recorded_at ASC LIMIT ?",
            (hash_name, cutoff, limit),
        ).fetchall()
        return [{"price": r["price"]} for r in rows]  # compatible with microstructure API

    def cleanup_old_trades(self, days: int = 90) -> int:
        """Prune trade_history records older than N days. Returns count deleted."""
        cutoff = time.time() - (days * 86400)
        cursor = self.history_conn.execute(
            "DELETE FROM trade_history WHERE recorded_at < ?", (cutoff,)
        )
        self.history_conn.commit()
        return cursor.rowcount
