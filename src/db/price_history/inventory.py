"""
inventory.py — virtual_inventory + decision_logs + missed_opportunities.

Mixin with the sandbox-side inventory tables. Mixed into
`PriceHistoryDB` (see `core.py`).
"""

from __future__ import annotations

import logging
import sqlite3
import time
from typing import Any, Dict, List

logger = logging.getLogger("PriceHistoryDB")


class _InventoryMixin:
    """Virtual inventory tables (sandbox OLTP)."""

    # These attributes are set on the instance by PriceHistoryDB.__init__
    state_conn: Any
    data_dir: Any
    state_path: Any

    # ------------------------------------------------------------------
    # Virtual Assets (STATE)
    # ------------------------------------------------------------------
    def add_virtual_item(
        self, hash_name: str, buy_price: float, trade_lock_hours: int = 168
    ) -> None:
        """Add item to virtual sandbox inventory (v9.0 with Trade Lock)."""
        now = time.time()
        unlock_at = now + (trade_lock_hours * 3600)
        with self.state_conn:
            self.state_conn.execute(
                "INSERT INTO virtual_inventory "
                "(hash_name, buy_price, acquired_at, unlock_at, status) "
                "VALUES (?, ?, ?, ?, 'idle')",
                (hash_name, buy_price, now, unlock_at),
            )
        logger.info(
            f"📦 [DB] Virtual item added: {hash_name} "
            f"(Unlocked at: {time.ctime(unlock_at)})"
        )

    def get_virtual_inventory(
        self, status: str = "idle", only_unlocked: bool = False
    ) -> List[sqlite3.Row]:
        """Fetch virtual items. v9.0 adds only_unlocked filter."""
        query = "SELECT * FROM virtual_inventory WHERE status = ?"
        params = [status]

        if only_unlocked:
            query += " AND unlock_at <= ?"
            params.append(time.time())

        return self.state_conn.execute(query, params).fetchall()

    def get_total_equity(self, current_balance: float) -> Dict[str, float]:
        """Sandbox v9.5: Calculates Total Equity (Cash + Virtual Asset Value)."""
        row = self.state_conn.execute(
            "SELECT SUM(buy_price) as total_value, COUNT(*) as item_count "
            "FROM virtual_inventory WHERE status != 'sold'"
        ).fetchone()

        asset_value = row["total_value"] or 0.0
        item_count = row["item_count"] or 0

        return {
            "cash": current_balance,
            "assets": asset_value,
            "total": current_balance + asset_value,
            "count": item_count,
        }

    def calculate_vwap(self, hash_name: str) -> float:
        """Calculates Volume-Weighted Average Price for currently held items."""
        row = self.state_conn.execute(
            "SELECT AVG(buy_price) as avg_price FROM virtual_inventory "
            "WHERE hash_name = ? AND status != 'sold'",
            (hash_name,),
        ).fetchone()
        return row["avg_price"] or 0.0

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

    def backup_state(self, tag: str = "snapshot") -> None:
        """Creates a snapshot of the current trading state."""
        import shutil

        dest = self.data_dir / f"state_{tag}.db"
        self.state_conn.commit()
        shutil.copy2(self.state_path, dest)
        logger.info(f"💾 [DB] State snapshot saved: {dest.name}")

    def restore_state(self, tag: str = "snapshot") -> None:
        """Restores the trading state from a snapshot."""
        import shutil
        import sqlite3

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

    def update_virtual_status(self, item_id: int, new_status: str) -> None:
        with self.state_conn:
            self.state_conn.execute(
                "UPDATE virtual_inventory SET status = ? WHERE id = ?",
                (new_status, item_id),
            )

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
