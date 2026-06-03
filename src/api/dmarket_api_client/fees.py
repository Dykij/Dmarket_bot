"""
fees.py — Dynamic fee lookups (single + bulk, with 12h cache).

Mixin with fee-lookup endpoints. Mixed into `DMarketAPIClient`
(see `core.py`).
"""

from __future__ import annotations

import os
import time
from typing import Any, Dict, List

import structlog

logger = structlog.get_logger("DMarketAPI")


class _FeesMixin:
    """Fee-lookup endpoints with a 12-hour cache (v7.7)."""

    # These attributes are set on the instance by DMarketAPIClient.__init__
    _fee_cache: Dict[str, Dict[str, Any]]
    _fee_cache_ttl: int

    # --- Fee Analysis (v7.6) ---
    async def get_item_fee(self, game_id: str, item_id: str, price_cents: int) -> float:
        """
        Fetches dynamic fee for a specific item at a given price.
        Implements 12-hour caching (v7.7) to avoid rate limits.
        """
        now = time.time()
        if item_id in self._fee_cache:
            cached = self._fee_cache[item_id]
            if now - cached["timestamp"] < self._fee_cache_ttl:
                return cached["fee"]

        try:
            params = {
                "gameId": game_id,
                "itemId": item_id,
                "price": price_cents,
                "currency": "USD",
            }
            res = await self.make_request("GET", "/exchange/v1/market/fee", params=params)
            fee_pct = float(res.get("fee", 5.0)) / 100.0

            # Update Cache
            self._fee_cache[item_id] = {"fee": fee_pct, "timestamp": now}
            return fee_pct
        except Exception as e:
            if os.getenv("DRY_RUN", "true").lower() != "true":
                logger.warning(
                    f"Could not fetch dynamic fee for {item_id}, fallback to 5%: {e}"
                )
            return 0.05

    # --- v12.2: Bulk fee fetching (Phase 2.2) ---
    async def get_item_fee_bulk(self, game_id: str, item_ids: List[str]) -> Dict[str, float]:
        """
        Batch fetch fees for up to N items in 1 request.
        Returns: {item_id: fee_rate} (e.g., {"abc123": 0.025})

        Endpoint: GET /exchange/v1/items/bulk-fee?gameId=a8db&itemIds=id1,id2,...
        Up to 50 items per request.
        """
        if not item_ids:
            return {}

        results: Dict[str, float] = {}
        chunk_size = 50
        for chunk_start in range(0, len(item_ids), chunk_size):
            chunk = item_ids[chunk_start : chunk_start + chunk_size]
            try:
                # Comma-separated item IDs (DMarket bulk format)
                ids_param = ",".join(chunk)
                res = await self.make_request(
                    "GET",
                    "/exchange/v1/items/bulk-fee",
                    params={"gameId": game_id, "itemIds": ids_param},
                )
                # Response: {"fees": [{"itemId": "abc", "fee": 2.5}, ...]}
                for entry in res.get("fees", []):
                    fid = entry.get("itemId", "")
                    fee_raw = entry.get("fee", 5.0)
                    try:
                        fee_pct = float(fee_raw) / 100.0
                    except (ValueError, TypeError):
                        fee_pct = 0.05
                    if fid:
                        results[fid] = fee_pct
                        # Update single-item cache too
                        self._fee_cache[fid] = {
                            "fee": fee_pct,
                            "timestamp": time.time(),
                        }
            except Exception as e:
                logger.debug(f"Bulk fee fetch failed for chunk of {len(chunk)}: {e}")
                # Fallback to 5% for failed items
                for fid in chunk:
                    if fid not in results:
                        results[fid] = 0.05

        return results
