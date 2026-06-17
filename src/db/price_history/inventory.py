"""
inventory.py — virtual_inventory + decision_logs + missed_opportunities.

Mixin with the sandbox-side inventory tables. Mixed into
`PriceHistoryDB` (see `core.py`).

v12.7: write methods wrapped with @with_db_retry so concurrent
background-task writes retry on transient 'database is locked'.
The hot-path sniping loop calls add_virtual_item, update_virtual_status,
mark_listed, etc. on every buy/sell — losing one of these due to a
lock contention would mean a lost trade record or a stale inventory
state.
"""

from __future__ import annotations

import logging
import re
import sqlite3
import time
from typing import Any, Dict, List

from src.db.db_retry import with_db_retry

logger = logging.getLogger("PriceHistoryDB")


class _InventoryMixin:
    """Virtual inventory tables (sandbox OLTP)."""

    # These attributes are set on the instance by PriceHistoryDB.__init__
    state_conn: Any  # sqlite3.Connection
    data_dir: Any  # pathlib.Path
    state_path: Any  # pathlib.Path

    # ------------------------------------------------------------------
    # Virtual Assets (STATE)
    # ------------------------------------------------------------------
    @with_db_retry(operation_name="add_virtual_item")
    def add_virtual_item(
        self, hash_name: str, buy_price: float, trade_lock_hours: int = 0,
        exclusive: bool = False,
    ) -> None:
        """Add item to virtual sandbox inventory (v9.0 with Trade Lock).

        exclusive: mark item as keep-forever (skipped during auto-resale).
        """
        now = time.time()
        unlock_at = now + (trade_lock_hours * 3600)
        with self.state_conn:
            self.state_conn.execute(
                "INSERT INTO virtual_inventory "
                "(hash_name, buy_price, acquired_at, unlock_at, status, exclusive) "
                "VALUES (?, ?, ?, ?, 'idle', ?)",
                (hash_name, buy_price, now, unlock_at, 1 if exclusive else 0),
            )
        logger.info(
            f"📦 [DB] Virtual item added: {hash_name} "
            f"(Unlocked at: {time.ctime(unlock_at)}, exclusive={exclusive})"
        )

    def is_exclusive(self, row_id: int) -> bool:
        """Check if a virtual_inventory row is marked exclusive."""
        row = self.state_conn.execute(
            "SELECT exclusive FROM virtual_inventory WHERE id = ?", (row_id,)
        ).fetchone()
        return bool(row and row["exclusive"])

    def mark_exclusive(self, row_id: int) -> None:
        """Mark a virtual_inventory row as exclusive (keep-forever)."""
        with self.state_conn:
            self.state_conn.execute(
                "UPDATE virtual_inventory SET exclusive = 1 WHERE id = ?",
                (row_id,),
            )

    def get_non_exclusive_inventory(
        self, status: str = "idle", only_unlocked: bool = False
    ) -> List[sqlite3.Row]:
        """Fetch virtual items that are NOT marked exclusive."""
        query = "SELECT * FROM virtual_inventory WHERE status = ? AND (exclusive IS NULL OR exclusive = 0)"
        params = [status]
        if only_unlocked:
            query += " AND unlock_at <= ?"
            params.append(time.time())
        return self.state_conn.execute(query, params).fetchall()

    def get_virtual_inventory(
        self, status: str = "idle", only_unlocked: bool = False
    ) -> List[sqlite3.Row]:
        """Fetch virtual items. v9.0 adds only_unlocked filter."""
        query = "SELECT * FROM virtual_inventory WHERE status = ?"
        params = [status]

        if only_unlocked:
            query += " AND unlock_at <= ?"
            params.append(time.time())  # type: ignore[arg-type]

        return self.state_conn.execute(query, params).fetchall()

    def get_total_equity(self, current_balance: float) -> Dict[str, float]:
        """Sandbox v9.5: Calculates Total Equity (Cash + Virtual Asset Value).
        v13.1: includes frozen_funds from Trade Protection holds."""
        row = self.state_conn.execute(
            "SELECT SUM(buy_price) as total_value, COUNT(*) as item_count "
            "FROM virtual_inventory WHERE status != 'sold'"
        ).fetchone()

        asset_value = row["total_value"] or 0.0
        item_count = row["item_count"] or 0

        frozen = self.get_frozen_funds()

        return {
            "cash": current_balance,
            "frozen": frozen,
            "available": max(0.0, current_balance - frozen),
            "assets": asset_value,
            "total": current_balance + asset_value,
            "count": item_count,
        }

    def get_frozen_funds(self) -> float:
        """Total sell_price of sold items whose funds are still held (Trade Protection)."""
        now = time.time()
        row = self.state_conn.execute(
            "SELECT SUM(sell_price) as total FROM virtual_inventory "
            "WHERE status = 'sold' AND funds_hold_until IS NOT NULL AND funds_hold_until > ?",
            (now,),
        ).fetchone()
        return float(row["total"] or 0.0)

    def set_funds_hold(self, row_id: int, hold_until: float) -> None:
        """Mark a sold item's proceeds as frozen until hold_until."""
        with self.state_conn:
            self.state_conn.execute(
                "UPDATE virtual_inventory SET funds_hold_until = ? WHERE id = ?",
                (hold_until, row_id),
            )

    def set_rollback_refund(self, dm_offer_id: str) -> None:
        """Mark item as rollback refund (net PnL = 0, not a loss)."""
        row = self.find_by_dm_offer_id(dm_offer_id)
        if row:
            with self.state_conn:
                self.state_conn.execute(
                    "UPDATE virtual_inventory SET rollback_refund = 1, profit = 0, "
                    "fee_paid = 0 WHERE id = ?",
                    (int(row["id"]),),
                )

    def release_expired_funds(self) -> int:
        """Release funds holds that have expired. Returns count of released items."""
        now = time.time()
        with self.state_conn:
            cursor = self.state_conn.execute(
                "UPDATE virtual_inventory SET funds_hold_until = NULL "
                "WHERE funds_hold_until IS NOT NULL AND funds_hold_until <= ?",
                (now,),
            )
            return cursor.rowcount

    def calculate_vwap(self, hash_name: str) -> float:
        """Calculates Volume-Weighted Average Price for currently held items."""
        row = self.state_conn.execute(
            "SELECT AVG(buy_price) as avg_price FROM virtual_inventory "
            "WHERE hash_name = ? AND status != 'sold'",
            (hash_name,),
        ).fetchone()
        return row["avg_price"] or 0.0

    @with_db_retry(operation_name="record_missed_opportunity")
    def record_missed_opportunity(
        self, hash_name: str, price: float, expected_sell: float, reason: str
    ) -> None:
        """Phase 7: Records items we skipped but might have been profitable."""
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
        """Phase 7: 'Self-Reflection' log - why the bot did what it did."""
        with self.state_conn:
            self.state_conn.execute(
                "INSERT INTO decision_logs "
                "(hash_name, decision, reason, details, timestamp) "
                "VALUES (?, ?, ?, ?, ?)",
                (hash_name, decision, reason, details, time.time()),
            )

    def _sanitize_tag(self, tag: str) -> str:
        """Sanitize tag to prevent path traversal. Only alphanumeric, underscore, hyphen."""
        sanitized = re.sub(r'[^a-zA-Z0-9_-]', '_', tag)
        if sanitized != tag:
            logger.warning(f"Sanitized backup tag '{tag}' → '{sanitized}'")
        return sanitized[:128]

    def backup_state(self, tag: str = "snapshot") -> None:
        """Creates a snapshot of the current trading state."""
        import shutil

        tag = self._sanitize_tag(tag)
        dest = self.data_dir / f"state_{tag}.db"
        self.state_conn.commit()
        shutil.copy2(self.state_path, dest)
        logger.info(f"💾 [DB] State snapshot saved: {dest.name}")

    def restore_state(self, tag: str = "snapshot") -> None:
        """Restores the trading state from a snapshot."""
        import shutil
        import sqlite3

        tag = self._sanitize_tag(tag)
        src = self.data_dir / f"state_{tag}.db"
        if not src.exists():
            logger.error(f"❌ [DB] Snapshot {tag} not found!")
            return
        self.state_conn.close()
        shutil.copy2(src, self.state_path)
        # Reconnect
        self.state_conn = sqlite3.connect(str(self.state_path), check_same_thread=False)
        self.state_conn.row_factory = sqlite3.Row
        logger.info(f"🔄 [DB] State restored from: {src.name}")

    @with_db_retry(operation_name="update_virtual_status")
    def update_virtual_status(self, item_id: int, new_status: str) -> None:
        with self.state_conn:
            self.state_conn.execute(
                "UPDATE virtual_inventory SET status = ? WHERE id = ?",
                (new_status, item_id),
            )

    @with_db_retry(operation_name="record_virtual_sale")
    def record_virtual_sale(self, item_id: int, sell_price: float, fee_paid: float) -> None:
        with self.state_conn:
            row = self.state_conn.execute(
                "SELECT buy_price FROM virtual_inventory WHERE id = ?", (item_id,)
            ).fetchone()
            if not row:
                return
            profit = sell_price - row["buy_price"] - fee_paid
            self.state_conn.execute(
                """UPDATE virtual_inventory
                   SET status = 'sold', sell_price = ?, fee_paid = ?, profit = ?, sold_at = ?
                   WHERE id = ?""",
                (sell_price, fee_paid, profit, time.time(), item_id),
            )

    # ------------------------------------------------------------------
    # v12.5: Production sell-side helpers
    # ------------------------------------------------------------------
    @with_db_retry(operation_name="attach_dm_item_id")
    def attach_dm_item_id(self, row_id: int, dm_item_id: str) -> None:
        """Link a virtual_inventory row to its real DMarket itemId.

        Called when we either:
        - Bought an item and DMarket returned the itemId in the buy response
        - Pulled an item from DMarket inventory sync and want to track it locally
        """
        if not dm_item_id:
            return
        with self.state_conn:
            self.state_conn.execute(
                "UPDATE virtual_inventory SET dm_item_id = ? WHERE id = ?",
                (dm_item_id, row_id),
            )

    def find_by_dm_item_id(self, dm_item_id: str) -> sqlite3.Row | None:
        """Look up virtual_inventory by DMarket's itemId (for inventory sync)."""
        if not dm_item_id:
            return None
        return self.state_conn.execute(
            "SELECT * FROM virtual_inventory WHERE dm_item_id = ? ORDER BY id DESC LIMIT 1",
            (dm_item_id,),
        ).fetchone()

    def find_by_dm_offer_id(self, dm_offer_id: str) -> sqlite3.Row | None:
        """Look up virtual_inventory by DMarket's offerId (for sell notifications)."""
        if not dm_offer_id:
            return None
        return self.state_conn.execute(
            "SELECT * FROM virtual_inventory WHERE dm_offer_id = ? ORDER BY id DESC LIMIT 1",
            (dm_offer_id,),
        ).fetchone()

    @with_db_retry(operation_name="mark_listed")
    def mark_listed(self, row_id: int, dm_offer_id: str, list_price: float) -> None:
        """Mark a virtual item as successfully listed on DMarket.

        Status flow: idle → listed (or re-listed: selling → listed).
        listed_at is the timestamp used by reprice_unsold_offers to detect
        stale listings (older than REPRICE_AFTER_HOURS).
        """
        with self.state_conn:
            self.state_conn.execute(
                """UPDATE virtual_inventory
                   SET status = 'listed',
                       dm_offer_id = ?,
                       sell_price = ?,
                       listed_at = ?,
                       list_error = NULL
                   WHERE id = ?""",
                (dm_offer_id, list_price, time.time(), row_id),
            )

    @with_db_retry(operation_name="mark_list_failed")
    def mark_list_failed(self, row_id: int, error_msg: str) -> None:
        """Record a failed listing attempt; status stays 'idle' so we retry next cycle."""
        with self.state_conn:
            self.state_conn.execute(
                """UPDATE virtual_inventory
                   SET list_error = ?
                   WHERE id = ?""",
                (error_msg[:500] if error_msg else None, row_id),
            )

    def get_stale_listings(self, max_age_seconds: int) -> List[sqlite3.Row]:
        """Get items that have been listed for >max_age_seconds.

        Used by reprice_unsold_offers to find listings that haven't sold.
        """
        cutoff = time.time() - max_age_seconds
        return self.state_conn.execute(
            """SELECT * FROM virtual_inventory
               WHERE status = 'listed'
                 AND listed_at IS NOT NULL
                 AND listed_at < ?
               ORDER BY listed_at ASC""",
            (cutoff,),
        ).fetchall()

    def get_recent_sales(self, since_ts: float) -> List[sqlite3.Row]:
        """Get items sold since timestamp (for daily PnL calc)."""
        return self.state_conn.execute(
            """SELECT * FROM virtual_inventory
               WHERE status = 'sold' AND sold_at > ?
               ORDER BY sold_at DESC""",
            (since_ts,),
        ).fetchall()

    def get_daily_realized_pnl(self, since_ts: float) -> float:
        """Sum of profit on items sold since timestamp (for daily briefing)."""
        row = self.state_conn.execute(
            "SELECT COALESCE(SUM(profit), 0) as pnl "
            "FROM virtual_inventory WHERE status = 'sold' AND sold_at > ?",
            (since_ts,),
        ).fetchone()
        return float(row["pnl"] or 0.0)

    def has_dm_item_id(self, row_id: int) -> bool:
        """Check if a virtual_inventory row already has its dm_item_id linked."""
        row = self.state_conn.execute(
            "SELECT dm_item_id FROM virtual_inventory WHERE id = ?", (row_id,)
        ).fetchone()
        return bool(row and row["dm_item_id"])

    # ------------------------------------------------------------------
    # v12.5: Equity snapshots + risk events
    # ------------------------------------------------------------------
    @with_db_retry(operation_name="record_equity_snapshot")
    def record_equity_snapshot(
        self,
        cash: float,
        assets: float,
        total: float,
        realized_pnl: float,
        note: str = "",
    ) -> int:
        """
        Record an equity snapshot for crash-recovery and historical analysis.

        Snapshots are deduplicated per UTC day — calling this multiple times
        on the same day updates the existing snapshot in-place.

        Returns the snapshot row id.
        """
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
        """Get today's equity snapshot (or None if not yet recorded)."""
        today = time.strftime("%Y-%m-%d", time.gmtime())
        row = self.state_conn.execute(
            """SELECT * FROM equity_snapshots WHERE snapshot_date = ?
               ORDER BY id DESC LIMIT 1""",
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
            """SELECT * FROM equity_snapshots
               WHERE taken_at > ?
               ORDER BY taken_at ASC""",
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
        self,
        event_type: str,
        severity: str = "warning",
        details: str = "",
    ) -> int:
        """Record a risk event (soft-halt, daily-halt, drawdown-trip, etc.).

        Used for audit trail + daily briefing diagnostics.
        """
        with self.state_conn:
            cur = self.state_conn.execute(
                """INSERT INTO risk_events (ts, event_type, severity, details)
                   VALUES (?, ?, ?, ?)""",
                (time.time(), event_type, severity, details[:1000]),
            )
            return int(cur.lastrowid)

    def get_risk_events_today(self) -> list[dict]:
        """Get today's risk events (for the daily briefing)."""
        midnight = time.time() - (time.time() % 86400)
        rows = self.state_conn.execute(
            """SELECT * FROM risk_events
               WHERE ts > ?
               ORDER BY ts DESC""",
            (midnight,),
        ).fetchall()
        return [
            {
                "ts": r["ts"],
                "type": r["event_type"],
                "severity": r["severity"],
                "details": r["details"],
            }
            for r in rows
        ]

    def get_virtual_inventory_locked_value(self) -> float:
        """v14.4: Total USD value of idle-but-trade-locked items."""
        now = time.time()
        row = self.state_conn.execute(
            "SELECT COALESCE(SUM(buy_price), 0) as total "
            "FROM virtual_inventory "
            "WHERE status = 'idle' AND unlock_at > ?",
            (now,),
        ).fetchone()
        return float(row["total"] or 0)

    def get_virtual_inventory_weekly_sales(self) -> float:
        """v14.4: Total USD sales in the last 7 days."""
        cutoff = time.time() - 7 * 24 * 3600
        row = self.state_conn.execute(
            "SELECT COALESCE(SUM(sell_price - fee_paid), 0) as total "
            "FROM virtual_inventory "
            "WHERE status = 'sold' AND sold_at > ?",
            (cutoff,),
        ).fetchone()
        return float(row["total"] or 0)
