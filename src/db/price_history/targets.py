"""
targets.py — active_targets table (placed buy orders).

Mixin with the small targets table. Mixed into `PriceHistoryDB`
(see `core.py`).

v12.7: write methods wrapped with @with_db_retry so concurrent
background-task writes retry on transient 'database is locked'.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.db.db_retry import with_db_retry

logger = logging.getLogger("PriceHistoryDB")


class _TargetsMixin:
    """active_targets table (placed buy orders)."""

    # These attributes are set on the instance by PriceHistoryDB.__init__
    state_conn: Any  # sqlite3.Connection

    @with_db_retry(operation_name="record_placed_target")
    def record_placed_target(self, item_id: str, hash_name: str, price: float) -> None:
        with self.state_conn:
            self.state_conn.execute(
                "INSERT OR REPLACE INTO active_targets "
                "(item_id, hash_name, price, created_at) VALUES (?, ?, ?, ?)",
                (item_id, hash_name, price, time.time()),
            )

    def has_target_been_placed(
        self, item_id: str, max_age_seconds: int = 2592000
    ) -> bool:
        cutoff = time.time() - max_age_seconds
        row = self.state_conn.execute(
            "SELECT 1 FROM active_targets WHERE item_id = ? AND created_at > ?",
            (item_id, cutoff),
        ).fetchone()
        return row is not None
