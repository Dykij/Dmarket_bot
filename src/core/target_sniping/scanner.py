"""
scanner.py — Parallel listing fetcher + float/phase secondary scan.

Mixin with the marketplace scanning helpers used by the sniping loop.
Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List

from src.config import Config

logger = logging.getLogger("SnipingBot")


class _ScannerMixin:
    """Parallel cheapest-listing fetcher + float/phase secondary scan."""

    # These attributes are set on the instance by SnipingLoop.__init__
    client: Any  # DMarketAPIClient

    async def _fetch_cheapest_listings(
        self, game_id: str, titles: List[str]
    ) -> List[Dict[str, Any]]:
        """
        v12.3: For each top-traded title, fetch the N cheapest DMarket
        listings and return a list of buy candidates (one per title: the
        cheapest listing available).

        This replaces the v12.0 page-of-100-listings scan, which was
        dominated by overpriced listings (a single page contains random
        listings, not necessarily the cheapest). With the agg-prices-first
        approach, we know which items are interesting (high market
        activity, wide bid-ask spread) and then find the actual cheapest
        listing for each.

        Returns: list of listing dicts (same shape as
        get_market_items_v2["objects"]), ready for the existing per-item
        filter.
        """
        if not titles:
            return []

        # Parallel fetch: DMarket market-items endpoint has 600 RPM, so
        # 20 titles in parallel is safe.
        async def _fetch_one(title: str) -> List[Dict[str, Any]]:
            try:
                resp = await self.client.get_market_items_v2(
                    game_id,
                    limit=Config.LISTINGS_FETCH_LIMIT,
                    title=title,
                )
                return resp.get("objects", [])
            except Exception as e:
                logger.debug(f"Listing fetch failed for {title!r}: {e}")
                return []

        results = await asyncio.gather(*[_fetch_one(t) for t in titles])

        # Pick the cheapest listing per title. If multiple titles return
        # the same listing object (rare), dedupe.
        cheapest: List[Dict[str, Any]] = []
        seen_ids = set()
        for title, listings in zip(titles, results):
            if not listings:
                continue
            sorted_by_price = sorted(
                listings,
                key=lambda x: int(x.get("price", {}).get("USD", 0)),
            )
            for cand in sorted_by_price:
                item_id = cand.get("itemId", "")
                if not item_id or item_id in seen_ids:
                    continue
                seen_ids.add(item_id)
                cheapest.append(cand)
                break  # only need the cheapest per title

            # v14.0: Save all listings for DOM gap analysis in resale
            if not hasattr(self, '_dom_cache'):
                self._dom_cache: Dict[str, List[Dict[str, Any]]] = {}
            self._dom_cache[title] = sorted_by_price

        logger.info(
            f"[v12.3 SCAN] top_titles={len(titles)} "
            f"fetched_listings={sum(len(r) for r in results)} "
            f"buy_candidates={len(cheapest)}"
        )
        return cheapest

    async def _fetch_float_filtered_listings(
        self, game_id: str, top_titles: List[str]
    ) -> List[Dict[str, Any]]:
        """
        v14.0: Secondary scan for low-float and rare-phase items that may
        be listed at general market price without float/phase premium.

        Uses DMarket treeFilters to find:
        - FN-0..FN-3 and MW-0..MW-1 (low-float, near-perfect wear)
        - Doppler Ruby/Sapphire/Black Pearl/Emerald phases

        Only runs on items matching high-value patterns (knives, Doppler, etc.)
        to avoid wasting API calls on $0.10 consumer-grade skins.
        """
        FLOAT_FILTER = "floatPart=FN-0,FN-1,FN-2,FN-3,MW-0,MW-1"
        PHASE_FILTERS = {
            "ruby": "phase=ruby",
            "sapphire": "phase=sapphire",
            "black-pearl": "phase=black-pearl",
            "emerald": "phase=emerald",
        }
        HIGH_VALUE_PATTERNS = [
            "Doppler", "Gamma Doppler", "Fade", "Marble Fade",
            "Crimson Web", "Case Hardened", "Emerald",
            "Lore", "Howl", "Medusa", "Hydroponic",
            "Poseidon", "Fire Serpent", "Dragon Lore",
        ]

        def _is_high_value(title: str) -> bool:
            if "★" in title:
                return True
            return any(p in title for p in HIGH_VALUE_PATTERNS)

        candidates: List[Dict[str, Any]] = []
        calls_made = 0
        max_calls = Config.FLOAT_PHASE_MAX_EXTRA_CALLS

        for title in top_titles:
            if calls_made >= max_calls:
                break
            if not _is_high_value(title):
                continue

            # 1. Low-float filter
            try:
                resp = await self.client.get_market_items_v2(
                    game_id, title=title, limit=10, treeFilters=FLOAT_FILTER,
                )
                calls_made += 1
                for obj in resp.get("objects", []):
                    if obj.get("itemId"):
                        candidates.append(obj)
            except Exception as e:
                logger.debug(f"[v14.0 FLOAT] Low-float fetch failed for {title!r}: {e}")
                continue

            if calls_made >= max_calls:
                break

            # 2. Doppler rare-phase filters
            if "Doppler" in title or "Gamma Doppler" in title:
                for phase_name, phase_filter in PHASE_FILTERS.items():
                    if calls_made >= max_calls:
                        break
                    try:
                        resp = await self.client.get_market_items_v2(
                            game_id, title=title, limit=5, treeFilters=phase_filter,
                        )
                        calls_made += 1
                        for obj in resp.get("objects", []):
                            if obj.get("itemId"):
                                candidates.append(obj)
                    except Exception as e:
                        logger.debug(
                            f"[v14.0 FLOAT] Phase filter ({phase_name}) "
                            f"failed for {title!r}: {e}"
                        )
                        continue

        return candidates
