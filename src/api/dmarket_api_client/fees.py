"""
fees.py — Dynamic fee lookups (single + bulk, with 12h cache).

Mixin with fee-lookup endpoints. Mixed into `DMarketAPIClient`
(see `core.py`).
"""

from __future__ import annotations

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

        v12.3: DMarket removed the per-item fee endpoint (/exchange/v1/market/fee
        returns 404 as of 2026-06-06). We use a hard 5% default to avoid
        5x retry timeouts.
        """
        now = time.time()
        if item_id in self._fee_cache:
            cached = self._fee_cache[item_id]
            if now - cached["timestamp"] < self._fee_cache_ttl:
                return cached["fee"]

        # v12.3: Skip the network call entirely — DMarket has no per-item
        # fee endpoint anymore. Cached value of 5% (CS2 default).
        self._fee_cache[item_id] = {"fee": 0.05, "timestamp": now}
        return 0.05

    # --- v12.2: Bulk fee fetching (Phase 2.2) ---
    # NOTE: DMarket does NOT expose a bulk-fee endpoint (verified 2026-06-06:
    # /exchange/v1/items/bulk-fee, /v1/exchange/fee, /marketplace-api/v1/fees
    # all return 404). The aggregated-prices response also doesn't include fees.
    # We use DMarket's standard CS2 fee rate (5%) as a conservative default.
    _DMARKET_CS2_FEE_RATE = 0.05
    _bulk_fee_endpoint_unavailable = True  # circuit breaker (set True if endpoint found)

    async def get_item_fee_bulk(self, game_id: str, item_ids: List[str]) -> Dict[str, float]:
        """
        Returns {item_id: fee_rate} for all given item_ids.
        DMarket doesn't expose fees via API, so we use the default 5% for CS2.
        """
        if not item_ids:
            return {}
        if self._bulk_fee_endpoint_unavailable:
            return {fid: self._DMARKET_CS2_FEE_RATE for fid in item_ids}

        # Legacy path — kept for if/when DMarket re-enables bulk-fee endpoint
        results: Dict[str, float] = {}
        chunk_size = 50
        for chunk_start in range(0, len(item_ids), chunk_size):
            chunk = item_ids[chunk_start : chunk_start + chunk_size]
            try:
                ids_param = ",".join(chunk)
                res = await self.make_request(
                    "GET",
                    "/exchange/v1/items/bulk-fee",
                    params={"gameId": game_id, "itemIds": ids_param},
                )
                for entry in res.get("fees", []):
                    fid = entry.get("itemId", "")
                    fee_raw = entry.get("fee", 5.0)
                    try:
                        fee_pct = float(fee_raw) / 100.0
                    except (ValueError, TypeError):
                        fee_pct = self._DMARKET_CS2_FEE_RATE
                    if fid:
                        results[fid] = fee_pct
                        self._fee_cache[fid] = {
                            "fee": fee_pct,
                            "timestamp": time.time(),
                        }
            except Exception as e:
                logger.debug(f"Bulk fee fetch failed for chunk of {len(chunk)}: {e}")
                self._bulk_fee_endpoint_unavailable = True  # trip circuit breaker
                for fid in chunk:
                    if fid not in results:
                        results[fid] = self._DMARKET_CS2_FEE_RATE
        return results
