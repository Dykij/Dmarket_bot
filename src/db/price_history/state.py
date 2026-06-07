"""
state.py — scanning_state (cursor, etc.) persistence.

Mixin with the small key/value table for scan cursors and other
small persistent state. Mixed into `PriceHistoryDB` (see `core.py`).
"""

from __future__ import annotations

import sqlite3
import time
from typing import List, Optional, Tuple


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
        row = self.state_conn.execute(
            "SELECT value FROM scanning_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def get_state_with_ts(self, key: str) -> Tuple[Optional[str], float]:
        """Return (value, updated_at) for a state key. updated_at=0 if missing."""
        row = self.state_conn.execute(
            "SELECT value, updated_at FROM scanning_state WHERE key = ?", (key,)
        ).fetchone()
        return (row["value"], row["updated_at"]) if row else (None, 0.0)

    def get_all_state(self) -> List[sqlite3.Row]:
        """Return all state rows (for snapshot/diagnostics)."""
        return self.state_conn.execute(
            "SELECT key, value, updated_at FROM scanning_state ORDER BY key"
        ).fetchall()
