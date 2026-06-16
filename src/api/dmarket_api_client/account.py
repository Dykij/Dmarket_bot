"""
account.py — Account, balance, inventory, and transaction history.

Mixin with read-only account endpoints. Mixed into `DMarketAPIClient`
(see `core.py`).
"""

from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("DMarketAPI")


class _AccountMixin:
    """Read-only account endpoints (balance, inventory, transactions)."""

    # Declared here so mypy knows the composed class has this method.
    async def make_request(
        self, method: str, path: str,
        params: Any = None, body: Any = None,
    ) -> Any: ...

    async def get_real_balance(self) -> float:
        """Fetches the current USD & DMC balance. Supports Real Balance in Dry Run."""
        try:
            # We fetch the real account balance even in Dry Run to ground the simulation in reality
            res = await self.make_request("GET", "/account/v1/balance")
            # DMarket balance is usually in cents or has a specific structure
            # Logic: USD section
            usd_balance = float(res.get("usd", 0)) / 100.0
            return usd_balance
        except Exception as e:
            if os.getenv("DRY_RUN", "true").lower() == "true":
                logger.debug(f"Real balance fetch failed, using fallback: {e}")
                return 10000.0
            raise e

    async def get_user_inventory(
        self, game_id: str, limit: int = 50, cursor: Optional[str] = None
    ) -> Dict[str, Any]:
        """Fetches items owned by the user but NOT currently on sale."""
        params = {"gameId": game_id, "limit": limit}
        if cursor:
            params["cursor"] = cursor
        return await self.make_request(
            "GET", "/marketplace-api/v1/user-inventory", params=params
        )

    # --- v12.2: Detailed Inventory with Status (Phase 2.1) ---
    async def get_user_inventory_detailed(
        self,
        game_id: str,
        limit: int = 100,
        cursor: Optional[str] = None,
        basic: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Fetch user inventory with FULL status info: trade_protected, reverted, FinalizationTime.

        Returns list of items with normalized fields:
        [{
            "itemId": "...",
            "title": "...",
            "status": "active" | "trade_protected" | "reverted" | "sold",
            "FinalizationTime": 1234567890.0,  # Unix timestamp when status changes
            "price": {"USD": "102", "DMC": ""},
            "createdAt": 1234567890.0,
        }]

        Endpoint: GET /exchange/v1/user-inventory?gameId=a8db&basic={basic}&limit=100
        basic=true returns minimal fields, basic=false returns full status
        """
        all_items: List[Dict[str, Any]] = []
        current_cursor = cursor or ""

        for _ in range(10):  # max 10 pages = 1000 items
            params = {
                "gameId": game_id,
                "limit": limit,
                "basic": str(basic).lower(),
            }
            if current_cursor:
                params["cursor"] = current_cursor
            try:
                res = await self.make_request(
                    "GET", "/exchange/v1/user-inventory", params=params
                )
            except Exception as e:
                logger.warning(f"Detailed inventory fetch failed: {e}", exc_info=True)
                return all_items

            items = res.get("items", res.get("objects", []))
            for it in items:
                status = it.get("status", "active")
                if isinstance(status, str):
                    status_lower = status.lower()
                else:
                    status_lower = "active"

                # FinalizationTime can be int (seconds) or string
                fin_raw = it.get("FinalizationTime") or it.get("finalizationTime") or 0
                try:
                    finalization_time = float(fin_raw) if fin_raw else 0.0
                except (ValueError, TypeError):
                    finalization_time = 0.0

                # createdAt
                created_raw = it.get("createdAt") or it.get("acquiredAt") or 0
                try:
                    created_at = float(created_raw) if created_raw else 0.0
                except (ValueError, TypeError):
                    created_at = 0.0

                all_items.append(
                    {
                        "itemId": it.get("itemId", ""),
                        "title": it.get("title", ""),
                        "status": status_lower,
                        "FinalizationTime": finalization_time,
                        "price": it.get("price", {}),
                        "createdAt": created_at,
                    }
                )

            current_cursor = res.get("cursor", "")
            if not current_cursor:
                break

        return all_items

    async def get_transaction_history(
        self,
        days: int = 30,
        limit: int = 100,
        transaction_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Get recent transactions to detect rollbacks (reverted status).

        Returns list of transactions:
        [{
            "type": "buy" | "sell" | "reverted",
            "itemId": "...",
            "amount": 100.0,  # USD value
            "status": "completed" | "reverted" | "trade_protected",
            "timestamp": 1234567890.0,
        }]

        Endpoint: GET /exchange/v1/transactions?days=30&limit=100
        """
        params: Dict[str, Any] = {
            "days": days,
            "limit": limit,
        }
        if transaction_type:
            params["type"] = transaction_type
        try:
            res = await self.make_request(
                "GET", "/exchange/v1/transactions", params=params
            )
        except Exception as e:
            logger.debug(f"Transaction history fetch failed: {e}")
            return []

        txs = res.get("transactions", res.get("items", []))
        normalized = []
        for tx in txs:
            ts_raw = tx.get("createdAt") or tx.get("timestamp") or 0
            try:
                ts = float(ts_raw) if ts_raw else 0.0
            except (ValueError, TypeError):
                ts = 0.0

            amount_raw = tx.get("amount", 0)
            if isinstance(amount_raw, dict):
                cents = amount_raw.get("USD", 0)
                try:
                    amount = float(cents) / 100.0
                except (ValueError, TypeError):
                    amount = 0.0
            else:
                try:
                    amount = float(amount_raw) / 100.0
                except (ValueError, TypeError):
                    amount = 0.0

            status = tx.get("status", "completed")
            tx_type = tx.get("type", "")
            # Map DMarket status to our schema
            if status in ("reverted", "rollback", "rolled_back"):
                tx_type = "reverted"

            normalized.append(
                {
                    "type": tx_type,
                    "itemId": tx.get("itemId", ""),
                    "amount": amount,
                    "status": status,
                    "timestamp": ts,
                }
            )
        return normalized
