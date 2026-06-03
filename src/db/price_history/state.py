"""
state.py — scanning_state (cursor, etc.) persistence.

Mixin with the small key/value table for scan cursors and other
small persistent state. Mixed into `PriceHistoryDB` (see `core.py`).
"""

from __future__ import annotations

import time
from typing import Optional


class _StateMixin:
    """scanning_state table (key/value, OLTP side)."""

    # These attributes are set on the instance by PriceHistoryDB.__init__
    state_conn: object

    def save_state(self, key: str, value: str) -> None:
        with self.state_conn:  # type: ignore[attr-defined]
            self.state_conn.execute(  # type: ignore[attr-defined]
                "INSERT OR REPLACE INTO scanning_state (key, value, updated_at) "
                "VALUES (?, ?, ?)",
                (key, value, time.time()),
            )

    def get_state(self, key: str) -> Optional[str]:
        row = self.state_conn.execute(  # type: ignore[attr-defined]
            "SELECT value FROM scanning_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None
