"""
asset_status.py — asset_status table (v12.2 trade_protected, reverted).

Mixin with the v12.2 asset-status tracking. Mixed into `PriceHistoryDB`
(see `core.py`).

v12.7: write methods wrapped with @with_db_retry.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from src.db.db_retry import with_db_retry

logger = logging.getLogger("PriceHistoryDB")


class _AssetStatusMixin:
    """v12.2 asset_status table (trade_protected, reverted, FinalizationTime)."""

    # These attributes are set on the instance by PriceHistoryDB.__init__
    state_conn: Any

    @with_db_retry(operation_name="update_asset_status")
    def update_asset_status(
        self,
        item_id: str,
        title: str,
        status: str,
        finalization_time: float = 0.0,
    ) -> None:
        """
        Insert or update asset status. Called when we detect a status change
        from DMarket (trade_protected, reverted, etc.).
        """
        now = time.time()
        with self.state_conn:
            existing = self.state_conn.execute(
                "SELECT created_at FROM asset_status WHERE item_id = ?", (item_id,)
            ).fetchone()
            if existing:
                self.state_conn.execute(
                    """UPDATE asset_status
                       SET title = ?, status = ?, finalization_time = ?, updated_at = ?
                       WHERE item_id = ?""",
                    (title, status, finalization_time, now, item_id),
                )
            else:
                self.state_conn.execute(
                    """INSERT INTO asset_status
                       (item_id, title, status, finalization_time, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (item_id, title, status, finalization_time, now, now),
                )

    def get_asset_status(self, item_id: str) -> Optional[Dict[str, Any]]:
        """Get the current status of an asset. Returns None if unknown."""
        row = self.state_conn.execute(
            "SELECT * FROM asset_status WHERE item_id = ?", (item_id,)
        ).fetchone()
        if not row:
            return None
        return {
            "item_id": row["item_id"],
            "title": row["title"],
            "status": row["status"],
            "finalization_time": row["finalization_time"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }

    def get_active_assets(self) -> List[Dict[str, Any]]:
        """Return all assets with status='active' (tradable)."""
        rows = self.state_conn.execute(
            "SELECT * FROM asset_status WHERE status = 'active' ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_trade_protected_assets(self) -> List[Dict[str, Any]]:
        """Return all assets that are still in trade_protected status."""
        rows = self.state_conn.execute(
            "SELECT * FROM asset_status WHERE status = 'trade_protected' "
            "ORDER BY finalization_time ASC"
        ).fetchall()
        return [dict(r) for r in rows]

    def get_reverted_assets(self) -> List[Dict[str, Any]]:
        """Return all assets that have been reverted (DMarket rolled back the transaction)."""
        rows = self.state_conn.execute(
            "SELECT * FROM asset_status WHERE status = 'reverted' ORDER BY updated_at DESC"
        ).fetchall()
        return [dict(r) for r in rows]

    def mark_reverted(self, item_id: str) -> None:
        """Convenience: mark an asset as reverted."""
        existing = self.get_asset_status(item_id)
        title = existing["title"] if existing else ""
        self.update_asset_status(item_id, title, "reverted", finalization_time=0.0)
        logger.warning(f"[DB] Asset {item_id} ({title}) marked as REVERTED")

    def is_trade_locked(self, item_id: str) -> bool:
        """
        Returns True if the asset is currently trade_protected (locked).
        An asset is locked if:
        - status='trade_protected' AND finalization_time > now (still locked)
        - status='reverted' (always)
        """
        asset = self.get_asset_status(item_id)
        if not asset:
            return False
        if asset["status"] == "reverted":
            return True
        if asset["status"] == "trade_protected":
            fin = asset["finalization_time"]
            if fin <= 0:
                return True  # No end time, assume locked
            return fin > time.time()
        return False

    def is_known_item(self, item_id: str) -> bool:
        """Returns True if we've ever tracked this item_id."""
        row = self.state_conn.execute(
            "SELECT 1 FROM asset_status WHERE item_id = ?", (item_id,)
        ).fetchone()
        return row is not None
