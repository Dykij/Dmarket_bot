"""
pump_blacklist.py — pump_blacklist table (v12.7 FOMO protection).

Mixin with the persistent pump-blacklist storage. Mixed into
`PriceHistoryDB` (see `core.py`).

Why this exists separately from the pump_detector in-memory dict:
The detector's blacklist is the bot's primary defense against
FOMO buys on spiked items. If the bot is restarted (watchdog kill,
config crash, memory-leak restart), the in-memory dict is wiped and
the bot could re-buy the same spiked item. The pump_blacklist
table persists each detection so the next startup can restore the
in-memory state.

Schema is identical to the one in the deprecated shim
(src/db/price_history.py), but the live code at runtime imports
this package — so the schema and helpers MUST live here, not in
the shim. The shim is preserved for git-archaeology only.

v12.7 also wires `@with_db_retry` on every write method so that
transient 'database is locked' errors (concurrent background-task
writes) are retried with exponential backoff instead of losing
the price observation / buy record.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import Any, List

from src.db.db_retry import with_db_retry

logger = logging.getLogger("PriceHistoryDB")


class _PumpBlacklistMixin:
    """v12.7: pump_blacklist table — survives watchdog restarts."""

    # These attributes are set on the instance by PriceHistoryDB.__init__
    state_conn: Any  # sqlite3.Connection

    @with_db_retry(operation_name="add_pump_blacklist_entry")
    def add_pump_blacklist_entry(
        self,
        hash_name: str,
        old_price: float,
        new_price: float,
        pct_change: float,
        detected_at: float,
        expires_at: float,
        alerted: bool = False,
    ) -> None:
        """Persist a pump-blacklist entry. Survives watchdog restarts.

        INSERT OR REPLACE on conflict (hash_name is PRIMARY KEY), so
        re-detection of the same item updates the existing row's
        pct_change / new_price / detected_at instead of creating a
        duplicate.
        """
        with self.state_conn:
            self.state_conn.execute(
                """INSERT OR REPLACE INTO pump_blacklist
                   (hash_name, old_price, new_price, pct_change,
                    detected_at, expires_at, alerted)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (hash_name, old_price, new_price, pct_change,
                 detected_at, expires_at, 1 if alerted else 0),
            )

    def get_active_pump_blacklist(self) -> List[sqlite3.Row]:
        """Return non-expired pump-blacklist entries (used at boot to
        restore in-memory state)."""
        now = time.time()
        return self.state_conn.execute(
            "SELECT * FROM pump_blacklist WHERE expires_at > ? ORDER BY detected_at DESC",
            (now,),
        ).fetchall()

    @with_db_retry(operation_name="delete_pump_blacklist_entry")
    def delete_pump_blacklist_entry(self, hash_name: str) -> None:
        """Manual unblock — removes the entry from the DB."""
        with self.state_conn:
            self.state_conn.execute(
                "DELETE FROM pump_blacklist WHERE hash_name = ?",
                (hash_name,),
            )

    @with_db_retry(operation_name="cleanup_expired_pump_blacklist")
    def cleanup_expired_pump_blacklist(self) -> int:
        """Remove expired entries. Returns count deleted."""
        now = time.time()
        with self.state_conn:
            cur = self.state_conn.execute(
                "DELETE FROM pump_blacklist WHERE expires_at <= ?",
                (now,),
            )
        return cur.rowcount

    def count_active_pump_blacklist(self) -> int:
        """Cheap count of active entries (used by health endpoint)."""
        now = time.time()
        row = self.state_conn.execute(
            "SELECT COUNT(*) as n FROM pump_blacklist WHERE expires_at > ?",
            (now,),
        ).fetchone()
        return int(row["n"] or 0)

    def get_pump_blacklist_total_detections(self) -> int:
        """Count of all detections ever (including expired). For /status."""
        row = self.state_conn.execute(
            "SELECT COUNT(*) as n FROM pump_blacklist"
        ).fetchone()
        return int(row["n"] or 0)
