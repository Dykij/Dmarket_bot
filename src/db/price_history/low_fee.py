"""
low_fee.py — low_fee_cache table (v12.0 daily refresh).

Mixin with the small low-fee cache table. Mixed into `PriceHistoryDB`
(see `core.py`).

v12.7: write methods wrapped with @with_db_retry.
"""

from __future__ import annotations

import time
from typing import Any

from src.db.db_retry import with_db_retry


class _LowFeeMixin:
    """low_fee_cache table (v12.0 daily refresh)."""

    # These attributes are set on the instance by PriceHistoryDB.__init__
    state_conn: Any  # sqlite3.Connection

    @with_db_retry(operation_name="save_low_fee_items")
    def save_low_fee_items(self, items: list[dict[str, Any]]) -> None:
        """Replace the entire low-fee cache with fresh items from DMarket."""
        with self.state_conn:
            self.state_conn.execute("DELETE FROM low_fee_cache")
            now = time.time()
            self.state_conn.executemany(
                "INSERT OR REPLACE INTO low_fee_cache (title, fee_rate, fetched_at) "
                "VALUES (?, ?, ?)",
                [
                    (item["title"], item["fee_rate"], now)
                    for item in items
                    if item.get("title")
                ],
            )

    def get_low_fee_rate(
        self, title: str, max_age_seconds: int = 86400
    ) -> float | None:
        """Returns the cached low-fee rate for a title, or None if not in cache / expired."""
        cutoff = time.time() - max_age_seconds
        row = self.state_conn.execute(
            "SELECT fee_rate FROM low_fee_cache WHERE title = ? AND fetched_at > ?",
            (title, cutoff),
        ).fetchone()
        return row["fee_rate"] if row else None

    def low_fee_cache_size(self) -> int:
        row = self.state_conn.execute(
            "SELECT COUNT(*) as c FROM low_fee_cache"
        ).fetchone()
        return row["c"] or 0

    def low_fee_cache_age_seconds(self) -> float | None:
        """Returns the age (seconds) of the oldest entry, or None if cache is empty."""
        row = self.state_conn.execute(
            "SELECT MIN(fetched_at) as oldest FROM low_fee_cache"
        ).fetchone()
        if not row or not row["oldest"]:
            return None
        return time.time() - row["oldest"]
