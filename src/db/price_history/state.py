"""
state.py — scanning_state (cursor, etc.) persistence.

Mixin with the small key/value table for scan cursors and other
small persistent state. Mixed into `PriceHistoryDB` (see `core.py`).

v12.7: write methods wrapped with @with_db_retry so concurrent
background-task writes (CS2CapCache refresh, briefing scheduler)
retry on transient 'database is locked' instead of losing the
cursor update.
"""

from __future__ import annotations

import sqlite3
import time
from typing import Any

from src.db.db_retry import with_db_retry


class _StateMixin:
    """scanning_state table (key/value, OLTP side)."""

    # These attributes are set on the instance by PriceHistoryDB.__init__
    state_conn: Any  # sqlite3.Connection (set by PriceHistoryDB.__init__)

    @with_db_retry(operation_name="save_state")
    def save_state(self, key: str, value: str) -> None:
        with self.state_conn:
            self.state_conn.execute(
                "INSERT OR REPLACE INTO scanning_state (key, value, updated_at) "
                "VALUES (?, ?, ?)",
                (key, value, time.time()),
            )

    def get_state(self, key: str) -> str | None:
        row = self.state_conn.execute(
            "SELECT value FROM scanning_state WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None

    def get_state_with_ts(self, key: str) -> tuple[str | None, float]:
        """Return (value, updated_at) for a state key. updated_at=0 if missing."""
        row = self.state_conn.execute(
            "SELECT value, updated_at FROM scanning_state WHERE key = ?", (key,)
        ).fetchone()
        return (row["value"], row["updated_at"]) if row else (None, 0.0)

    def get_all_state(self) -> list[sqlite3.Row]:
        """Return all state rows (for snapshot/diagnostics)."""
        return self.state_conn.execute(
            "SELECT key, value, updated_at FROM scanning_state ORDER BY key"
        ).fetchall()
