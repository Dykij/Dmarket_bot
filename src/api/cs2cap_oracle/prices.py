"""
CS2Cap Oracle — Prices mixin (ask/bid lookups, single + batch).
"""

import logging
import time
from typing import Any

from src.db.price_history import price_db

from .models import (
    BATCH_MAX_ITEMS,
    BidsSnapshot,
    CrossMarketData,
    PriceSnapshot,
)

logger = logging.getLogger("CS2CapOracle")


class _PricesMixin:
    """Price data operations: single-item + cross-market + batch lookups."""

    # ----------------------------------------------------------------
    # 2. PRICE DATA (GET /prices) — requires item_id (integer)
    # ----------------------------------------------------------------
    async def get_item_price(self, hash_name: str, offset: int = 0) -> float:
        """
        Get the global minimum ask price across all providers.
        Uses GET /prices?item_id=<int> (NOT market_hash_name).
        Returns 0.0 if no data available.
        """
        now = time.time()
        cache_key = f"{hash_name}_{offset}"

        # Layer 1: Memory
        if cache_key in self._price_cache:
            price, ts = self._price_cache[cache_key]
            if now - ts < self.MEM_TTL:
                return price

        # Layer 2: SQLite
        cached = price_db.get_latest_price(hash_name, max_age_seconds=self.CACHE_TTL)
        if cached is not None:
            self._price_cache[cache_key] = (cached, now)
            return cached

        # Layer 3: Live API
        item_id = await self.get_item_id(hash_name)
        if not item_id:
            logger.debug(f"[CS2Cap] No item_id for: {hash_name}")
            return 0.0

        data = await self._request(
            "/prices",
            params={
                "item_id": item_id,
                "currency": "USD",
                "limit": 100,
                "offset": offset,
            }
        )

        if not data:
            return 0.0

        # Parse response: {"items": [{"provider": "buff163", "lowest_ask": 435886, ...}]}
        items = data.get("items", [])
        if not items:
            return 0.0

        # Find minimum ask across all providers
        prices = []
        for entry in items:
            ask = entry.get("lowest_ask", 0)
            if isinstance(ask, (int, float)) and ask > 0:
                prices.append(ask / 100.0)

        if prices:
            min_price = min(prices)
            price_db.record_price(hash_name, min_price, source="cs2cap")
            self._price_cache[cache_key] = (min_price, now)
            return min_price

        return 0.0

    # ----------------------------------------------------------------
    # 3. CROSS-MARKET DATA (GET /prices with all providers)
    # ----------------------------------------------------------------
    async def get_price_snapshot(self, hash_name: str) -> PriceSnapshot | None:
        """
        Single-item variant of the batch snapshot. Hits /prices once and
        returns a fully-populated PriceSnapshot (min_price + per-provider
        breakdown + liquidity).

        Phase 2 optimization: replaces the pattern of calling
        get_item_price() + get_cross_market_data() back-to-back (2 HTTP
        calls, 2 chances of drift between the two responses).

        Returns None only if the API key has no item_id mapping for the
        given hash_name. For "no data on any market" the snapshot has
        min_price == 0.0 (callers can distinguish via .has_data).
        """
        cache_key = f"snap_{hash_name}"
        now = time.time()
        if cache_key in self._price_cache:
            # _price_cache stores (min_price, ts); the snapshot variant
            # is just a stricter getter, so reuse the same TTL.
            price, ts = self._price_cache[cache_key]
            if now - ts < self.MEM_TTL:
                if price == 0.0:
                    return PriceSnapshot(hash_name=hash_name)
                return PriceSnapshot(hash_name=hash_name, min_price=price)

        item_id = await self.get_item_id(hash_name)
        if not item_id:
            logger.debug(f"[CS2Cap] No item_id for: {hash_name}")
            return None

        data = await self._request(
            "/prices",
            params={"item_id": item_id, "currency": "USD", "limit": 100},
        )
        if not data:
            return None

        # Reuse the batch parser: a single-item /prices response is the
        # same shape as one element of /prices/batch.
        placeholder = {hash_name: PriceSnapshot(hash_name=hash_name)}
        synthetic = {"items": [{
            "market_hash_name": hash_name,
            "providers": [
                {
                    "provider": e.get("provider", "unknown"),
                    "lowest_ask": e.get("lowest_ask", 0),
                    "quantity": e.get("quantity", 0),
                }
                for e in data.get("items", [])
            ],
        }]}
        self._parse_batch_prices(synthetic, placeholder)
        snap = placeholder[hash_name]
        if snap.has_data:
            price_db.record_price(hash_name, snap.min_price, source="cs2cap")
            self._price_cache[cache_key] = (snap.min_price, now)
        return snap

    async def get_cross_market_data(self, hash_name: str) -> CrossMarketData | None:
        """Fetch cross-market snapshot: prices from all providers."""
        now = time.time()
        cache_key = f"cross_{hash_name}"

        if cache_key in self._candles_cache:
            data_list, ts = self._candles_cache[cache_key]
            if now - ts < 180:
                return data_list[0] if data_list else None

        item_id = await self.get_item_id(hash_name)
        if not item_id:
            return None

        data = await self._request(
            "/prices",
            params={
                "item_id": item_id,
                "currency": "USD",
                "limit": 100,
            }
        )

        if not data:
            return None

        items = data.get("items", [])
        if not items:
            return None

        result = CrossMarketData(hash_name=hash_name)

        providers = {}
        total_qty = 0
        for entry in items:
            provider = entry.get("provider", "unknown")
            ask = entry.get("lowest_ask", 0)
            qty = entry.get("quantity", 0)

            if isinstance(ask, (int, float)) and ask > 0:
                providers[provider] = ask / 100.0
            total_qty += qty

        result.provider_prices = providers
        result.liquidity_score = min(1.0, total_qty / 100.0)

        if providers:
            result.global_min_ask = min(providers.values())

        self._candles_cache[cache_key] = ([result], now)
        return result

    # ----------------------------------------------------------------
    # 3b. BATCH PRICE / BID LOOKUPS (Starter+ tier)
    #     POST /prices/batch and POST /bids/batch
    #     Up to 100 items per call, 1 unit of quota per call (not per item).
    #     No per-call throttle (batched endpoints are burst-safe).
    # ----------------------------------------------------------------
    async def get_prices_batch(
        self, hash_names: list[str]
    ) -> dict[str, PriceSnapshot]:
        """
        Fetch lowest asks for up to 100 items in 1 POST request.

        Tier: Starter+ (40 RPM, 50K req/month). 1 call = 1 quota unit.

        Returns dict: {hash_name: PriceSnapshot}. Items with no data on
        CS2Cap are still present in the dict with min_price=0.0 (so callers
        can distinguish "no listing on any market" from "API error").
        """
        if not hash_names:
            return {}

        # Always seed dict with empty snapshots so callers can rely on key presence
        results: dict[str, PriceSnapshot] = {
            name: PriceSnapshot(hash_name=name) for name in hash_names
        }

        for chunk_start in range(0, len(hash_names), BATCH_MAX_ITEMS):
            chunk = hash_names[chunk_start : chunk_start + BATCH_MAX_ITEMS]
            data = await self._request_post(
                "/prices/batch",
                body={
                    "market_hash_names": chunk,
                    "currency": "USD",
                },
                bypass_throttle=True,
            )
            if not data:
                continue
            self._parse_batch_prices(data, results)

        # Persist snapshots to history (post-cache so reads in this cycle are free)
        for name, snap in results.items():
            if snap.has_data:
                price_db.record_price(name, snap.min_price, source="cs2cap")

        return results

    def _parse_batch_prices(
        self,
        data: dict[str, Any],
        out: dict[str, PriceSnapshot],
    ) -> None:
        """
        Parse the /prices/batch response and merge into the out dict.

        Expected response shape (per docs.cs2cap.com/api-reference/prices):
        {
          "items": [
            {
              "item_id": 12632,
              "market_hash_name": "AK-47 | Redline (Field-Tested)",
              "phase": null,
              "quotes": [
                {"provider": "buff163", "lowest_ask": 435886, "quantity": 3},
                {"provider": "csfloat", "lowest_ask": 440100, "quantity": 1}
              ]
            },
            ...
          ]
        }
        """
        for entry in data.get("items", []):
            name = entry.get("market_hash_name", "")
            if not name:
                # Fallback: some responses use 'title' or 'name'
                name = entry.get("title") or entry.get("name", "")
            if not name or name not in out:
                continue
            snap = out[name]
            # Actual API field is "quotes" (verified 2026-06-06), but accept
            # legacy "providers" for back-compat.
            quotes = entry.get("quotes") or entry.get("providers", [])
            for prov in quotes:
                provider = prov.get("provider", "unknown")
                ask_cents = prov.get("lowest_ask", 0)
                qty = prov.get("quantity", 0)
                if isinstance(ask_cents, (int, float)) and ask_cents > 0:
                    ask_usd = ask_cents / 100.0
                    snap.provider_prices[provider] = ask_usd
                    if snap.min_price == 0.0 or ask_usd < snap.min_price:
                        snap.min_price = ask_usd
                if isinstance(qty, (int, float)) and qty > 0:
                    snap.provider_quantities[provider] = int(qty)
                    snap.total_quantity += int(qty)

    async def get_bids_batch(
        self, hash_names: list[str]
    ) -> dict[str, BidsSnapshot]:
        """
        Fetch highest bids for up to 100 items in 1 POST request.

        Tier: Starter+ (40 RPM). 1 call = 1 quota unit.

        Returns dict: {hash_name: BidsSnapshot}. Used for sell-side validation
        (CS2Cap highest buy-order = upper bound for listing price).
        """
        if not hash_names:
            return {}

        results: dict[str, BidsSnapshot] = {
            name: BidsSnapshot(hash_name=name) for name in hash_names
        }

        for chunk_start in range(0, len(hash_names), BATCH_MAX_ITEMS):
            chunk = hash_names[chunk_start : chunk_start + BATCH_MAX_ITEMS]
            data = await self._request_post(
                "/bids/batch",
                body={
                    "market_hash_names": chunk,
                    "currency": "USD",
                },
                bypass_throttle=True,
            )
            if not data:
                continue
            self._parse_batch_bids(data, results)

        return results

    def _parse_batch_bids(
        self,
        data: dict[str, Any],
        out: dict[str, BidsSnapshot],
    ) -> None:
        """
        Parse the /bids/batch response and merge into the out dict.

        Expected response shape (per docs.cs2cap.com/api-reference/bids):
        {
          "items": [
            {
              "item_id": 12632,
              "market_hash_name": "AK-47 | Redline (Field-Tested)",
              "phase": null,
              "quotes": [
                {"provider": "buff163", "highest_bid": 2926},
                {"provider": "c5", "highest_bid": 5778}
              ]
            }
          ]
        }
        """
        for entry in data.get("items", []):
            name = (
                entry.get("market_hash_name")
                or entry.get("title")
                or entry.get("name", "")
            )
            if not name or name not in out:
                continue
            snap = out[name]
            # Actual API field is "quotes" (verified 2026-06-06), but accept
            # legacy "providers" for back-compat.
            quotes = entry.get("quotes") or entry.get("providers", [])
            for prov in quotes:
                provider = prov.get("provider", "unknown")
                bid_cents = prov.get("highest_bid", 0)
                if isinstance(bid_cents, (int, float)) and bid_cents > 0:
                    bid_usd = bid_cents / 100.0
                    snap.provider_bids[provider] = bid_usd
                    if snap.max_bid == 0.0 or bid_usd > snap.max_bid:
                        snap.max_bid = bid_usd
