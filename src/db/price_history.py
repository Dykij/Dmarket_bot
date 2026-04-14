"""
PriceHistoryDB — Persistent SQLite storage for CSFloat Oracle price observations.

Replaces the volatile in-memory dict cache with a durable database that also enables
trend analysis (crash detection) before executing buy orders.
"""

import sqlite3
import logging
import time
from pathlib import Path
from typing import Optional, List, Tuple

logger = logging.getLogger("PriceHistoryDB")


class PriceHistoryDB:
    """SQLite-backed price history with trend analysis."""

    def __init__(self, db_path: str = "dmarket_trading.db"):
        self.db_path = Path(__file__).parent.parent.parent / "data" / db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def _init_schema(self):
        with self.conn:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS price_history (
                    id          INTEGER PRIMARY KEY AUTOINCREMENT,
                    hash_name   TEXT    NOT NULL,
                    price       REAL    NOT NULL,
                    source      TEXT    NOT NULL DEFAULT 'csfloat',
                    recorded_at REAL    NOT NULL
                )
            """)
            self.conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_ph_name_time
                ON price_history (hash_name, recorded_at DESC)
            """)
        logger.info(f"💾 PriceHistoryDB initialized at {self.db_path}")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def record_price(self, hash_name: str, price: float, source: str = "csfloat"):
        """Insert a new price observation."""
        with self.conn:
            self.conn.execute(
                "INSERT INTO price_history (hash_name, price, source, recorded_at) VALUES (?, ?, ?, ?)",
                (hash_name, price, source, time.time()),
            )

    # ------------------------------------------------------------------
    # Read — cache replacement
    # ------------------------------------------------------------------
    def get_latest_price(self, hash_name: str, max_age_seconds: int = 10800) -> Optional[float]:
        """
        Return the most recent price if it was recorded within *max_age_seconds*.
        Works as a drop-in replacement for the old in-memory TTL cache.
        """
        cutoff = time.time() - max_age_seconds
        row = self.conn.execute(
            "SELECT price FROM price_history WHERE hash_name = ? AND recorded_at > ? ORDER BY recorded_at DESC LIMIT 1",
            (hash_name, cutoff),
        ).fetchone()
        return row["price"] if row else None

    # ------------------------------------------------------------------
    # Trend analysis
    # ------------------------------------------------------------------
    def get_recent_prices(self, hash_name: str, days: int = 7) -> List[Tuple[float, float]]:
        """Return list of (price, timestamp) for the last N days, newest first."""
        cutoff = time.time() - (days * 86400)
        rows = self.conn.execute(
            "SELECT price, recorded_at FROM price_history WHERE hash_name = ? AND recorded_at > ? ORDER BY recorded_at DESC",
            (hash_name, cutoff),
        ).fetchall()
        return [(r["price"], r["recorded_at"]) for r in rows]

    def get_price_trend(self, hash_name: str, days: int = 7) -> str:
        """
        Analyse recent datapoints and return one of:
          'rising'  — more price increases than decreases
          'falling' — more price decreases than increases
          'stable'  — roughly equal or insufficient data
        """
        prices = self.get_recent_prices(hash_name, days)
        if len(prices) < 3:
            return "stable"  # not enough data to judge

        ups = 0
        downs = 0
        # prices are newest-first, so iterate in reverse (oldest → newest)
        ordered = [p for p, _ in reversed(prices)]
        for i in range(1, len(ordered)):
            if ordered[i] > ordered[i - 1]:
                ups += 1
            elif ordered[i] < ordered[i - 1]:
                downs += 1

        if downs > ups and downs >= 3:
            return "falling"
        if ups > downs and ups >= 3:
            return "rising"
        return "stable"

    def is_crashing(self, hash_name: str, consecutive_drops: int = 3) -> bool:
        """
        Returns True if the last *consecutive_drops* price observations are
        each lower than the previous one — a clear downward cascade.
        """
        prices = self.get_recent_prices(hash_name, days=14)
        if len(prices) < consecutive_drops + 1:
            return False  # not enough history

        # prices come newest-first
        for i in range(consecutive_drops):
            if prices[i][0] >= prices[i + 1][0]:
                return False  # price went up or stayed flat at some point
        return True

    def get_avg_price(self, hash_name: str, days: int = 7) -> Optional[float]:
        """Return the average observed price over the last N days."""
        cutoff = time.time() - (days * 86400)
        row = self.conn.execute(
            "SELECT AVG(price) as avg_price FROM price_history WHERE hash_name = ? AND recorded_at > ?",
            (hash_name, cutoff),
        ).fetchone()
        return row["avg_price"] if row and row["avg_price"] else None

    def close(self):
        self.conn.close()


# Singleton instance
price_db = PriceHistoryDB()
