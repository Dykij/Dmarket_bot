"""
fees.py — Dynamic fee lookups (single + bulk, with 12h cache).

Mixin with fee-lookup endpoints. Mixed into `DMarketAPIClient`
(see `core.py`).
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import structlog

logger = structlog.get_logger("DMarketAPI")

# CS2 fee tiers based on DMarket's dynamic fee policy (March 2026):
# Liquid items (high volume) -> 2%, less liquid -> up to 10%.
_LIQUID_FEE = 0.02
_STANDARD_FEE = 0.05
_HIGH_FEE = 0.07
_MAX_FEE = 0.10

_VOLUME_HIGH = 50
_VOLUME_MEDIUM = 10
_VOLUME_MIN = 5


class _FeesMixin:
    """Fee-lookup endpoints with a 12-hour cache (v7.7)."""

    _fee_cache: Dict[str, Dict[str, Any]]
    _fee_cache_ttl: int

    async def make_request(
        self, method: str, path: str,
        params: Any = None, body: Any = None,
    ) -> Any: ...

    @staticmethod
    def _estimate_fee_from_volume(ask_count: int = 0, bid_count: int = 0) -> float:
        volume = (ask_count or 0) + (bid_count or 0)
        if volume >= _VOLUME_HIGH:
            return _LIQUID_FEE
        elif volume >= _VOLUME_MEDIUM:
            return _STANDARD_FEE
        elif volume >= _VOLUME_MIN:
            return _HIGH_FEE
        elif volume > 0:
            return _MAX_FEE
        return _STANDARD_FEE

    async def get_item_fee(
        self,
        game_id: str,
        item_id: str,
        price_cents: int,
        ask_count: int = 0,
        bid_count: int = 0,
    ) -> float:
        """
        Fee for a single item. Uses volume-based estimation
        when DMarket's per-item fee endpoint is unavailable.
        """
        now = time.time()
        if item_id in self._fee_cache:
            cached = self._fee_cache[item_id]
            if now - cached["timestamp"] < self._fee_cache_ttl:
                return cached["fee"]

        fee = self._estimate_fee_from_volume(ask_count, bid_count)
        self._fee_cache[item_id] = {"fee": fee, "timestamp": now}
        return fee

    _DMARKET_CS2_FEE_RATE = 0.05
    _bulk_fee_endpoint_unavailable = True

    async def get_item_fee_bulk(
        self,
        game_id: str,
        item_ids: List[str],
        title_volume: Optional[Dict[str, int]] = None,
        item_id_to_title: Optional[Dict[str, str]] = None,
    ) -> Dict[str, float]:
        """
        Returns {item_id: fee_rate} for all given item_ids.
        Uses volume-based estimation when title_volume is provided.
        title_volume: {title: ask_count + bid_count} from aggregated prices.
        item_id_to_title: {item_id: title} mapping to resolve volume per item.
        """
        if not item_ids:
            return {}

        results: Dict[str, float] = {}
        now = time.time()

        for fid in item_ids:
            if fid in self._fee_cache:
                cached = self._fee_cache[fid]
                if now - cached["timestamp"] < self._fee_cache_ttl:
                    results[fid] = cached["fee"]
                    continue

            if title_volume and item_id_to_title:
                title = item_id_to_title.get(fid, "")
                if title:
                    volume = title_volume.get(title, 0)
                    fee = self._estimate_fee_from_volume(volume, volume)
                else:
                    fee = self._DMARKET_CS2_FEE_RATE
            else:
                fee = self._DMARKET_CS2_FEE_RATE

            results[fid] = fee
            self._fee_cache[fid] = {"fee": fee, "timestamp": now}

        return results
