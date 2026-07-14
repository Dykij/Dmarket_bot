"""
analytics_logs.py — Decision logs, equity snapshots, risk events.

v15.1: Extracted from inventory.py for single-responsibility.
Mixin for PriceHistoryDB — provides analytics logging methods.
"""

from __future__ import annotations

import logging
import time
from typing import Any

from src.db.db_retry import with_db_retry

logger = logging.getLogger("PriceHistoryDB")


class _AnalyticsLogsMixin:
    """Decision logs, equity snapshots, and risk event recording."""

    # Type stub — state_conn is provided by PriceHistoryDB.__init__
    state_conn: Any

    @with_db_retry(operation_name="record_missed_opportunity")
    def record_missed_opportunity(
        self, hash_name: str, price: float, expected_sell: float, reason: str
    ) -> None:
        """Records items we skipped but might have been profitable."""
        with self.state_conn:
            self.state_conn.execute(
                "INSERT INTO missed_opportunities "
                "(hash_name, price, expected_sell, reason, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (hash_name, price, expected_sell, reason, time.time()),
            )

    @with_db_retry(operation_name="log_decision")
    def log_decision(
        self, hash_name: str, decision: str, reason: str, details: str = ""
    ) -> None:
        """Self-Reflection log — why the bot did what it did."""
        with self.state_conn:
            self.state_conn.execute(
                "INSERT INTO decision_logs "
                "(hash_name, decision, reason, details, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (hash_name, decision, reason, details, time.time()),
            )

    @with_db_retry(operation_name="record_equity_snapshot")
    def record_equity_snapshot(
        self,
        cash: float,
        assets: float,
        total: float,
        realized_pnl: float,
        note: str = "",
    ) -> int:
        """Record equity snapshot (deduplicated per UTC day). Returns row id."""
        today = time.strftime("%Y-%m-%d", time.gmtime())
        ts = time.time()
        with self.state_conn:
            existing = self.state_conn.execute(
                "SELECT id FROM equity_snapshots WHERE snapshot_date = ?", (today,)
            ).fetchone()
            if existing:
                self.state_conn.execute(
                    """UPDATE equity_snapshots
                       SET taken_at = ?, cash = ?, assets = ?, total = ?,
                           realized_pnl = ?, note = ?
                       WHERE id = ?""",
                    (ts, cash, assets, total, realized_pnl, note, existing["id"]),
                )
                return int(existing["id"])
            cur = self.state_conn.execute(
                """INSERT INTO equity_snapshots
                   (taken_at, snapshot_date, cash, assets, total, realized_pnl, note)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (ts, today, cash, assets, total, realized_pnl, note),
            )
            return int(cur.lastrowid)

    def get_equity_snapshot_today(self) -> dict | None:
        """Get today's equity snapshot (or None)."""
        today = time.strftime("%Y-%m-%d", time.gmtime())
        row = self.state_conn.execute(
            "SELECT * FROM equity_snapshots WHERE snapshot_date = ? ORDER BY id DESC LIMIT 1",
            (today,),
        ).fetchone()
        if not row:
            return None
        return {
            "cash": row["cash"],
            "assets": row["assets"],
            "total": row["total"],
            "realized_pnl": row["realized_pnl"],
            "note": row["note"] or "",
            "taken_at": row["taken_at"],
        }

    def get_equity_snapshots(self, days: int = 30) -> list[dict]:
        """Get last N days of equity snapshots (oldest first)."""
        cutoff = time.time() - days * 86400
        rows = self.state_conn.execute(
            "SELECT * FROM equity_snapshots WHERE taken_at > ? ORDER BY taken_at ASC",
            (cutoff,),
        ).fetchall()
        return [
            {
                "date": r["snapshot_date"],
                "cash": r["cash"],
                "assets": r["assets"],
                "total": r["total"],
                "realized_pnl": r["realized_pnl"],
                "note": r["note"] or "",
                "taken_at": r["taken_at"],
            }
            for r in rows
        ]

    @with_db_retry(operation_name="record_risk_event")
    def record_risk_event(
        self, event_type: str, severity: str = "warning", details: str = ""
    ) -> int:
        """Record risk event for audit trail + daily briefing."""
        with self.state_conn:
            cur = self.state_conn.execute(
                "INSERT INTO risk_events (ts, event_type, severity, details) VALUES (?, ?, ?, ?)",
                (time.time(), event_type, severity, details[:1000]),
            )
            return int(cur.lastrowid)

    def get_risk_events_today(self) -> list[dict]:
        """Get today's risk events."""
        midnight = time.time() - (time.time() % 86400)
        rows = self.state_conn.execute(
            "SELECT * FROM risk_events WHERE ts > ? ORDER BY ts DESC",
            (midnight,),
        ).fetchall()
        return [
            {"ts": r["ts"], "type": r["event_type"], "severity": r["severity"], "details": r["details"]}
            for r in rows
        ]
