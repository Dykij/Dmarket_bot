"""
CS2Cap Oracle — Catalog mixin (item name → item_id mapping).
"""

import asyncio
import json
import logging
import time
from typing import Dict, Optional

from src.db.price_history import price_db

logger = logging.getLogger("CS2CapOracle")


class _CatalogMixin:
    """Catalog operations: load item name→ID mapping from CS2Cap API."""

    async def load_catalog(self) -> int:
        """
        O4: Public catalog loader — pre-populates the hash_name → item_id
        map on bot startup. Returns the number of items loaded.

        If the catalog was loaded within the last ITEMS_MEM_TTL (24h),
        returns immediately from in-memory cache. Otherwise, tries
        SQLite cache, then falls back to the CS2Cap API.
        """
        await self._load_catalog()
        return len(self._item_catalog)

    async def _load_catalog(self) -> None:
        """Load item catalog for name-to-id mapping. Paginated (API max 100/page).

        v13.3: Parallel page fetching for faster initial catalog load.
        Falls back to sequential if concurrent requests fail.
        """
        now = time.time()
        if self._item_catalog and (now - self._catalog_ts < self.ITEMS_MEM_TTL):
            return

        # Try loading from SQLite first
        cached = price_db.get_state("cs2cap_catalog")
        if cached:
            try:
                self._item_catalog = json.loads(cached)
                self._catalog_ts = now
                logger.info(f"[CS2Cap] Loaded {len(self._item_catalog)} items from cache")
                return
            except Exception:
                pass

        # Load from API — paginate through all items (API max 100/page)
        logger.info("[CS2Cap] Loading catalog from API (this may take ~1-2 min on first run)...")
        limit = 100
        catalog: Dict[str, int] = {}
        max_pages = 400  # 40k items max (real catalog ~35k)

        logger.info(f"[CS2Cap] Fetching catalog in parallel (max {max_pages} pages)...")

        # Build offset list for all possible pages
        offsets = list(range(0, max_pages * limit, limit))
        page_sem = asyncio.Semaphore(5)  # max 5 concurrent pages

        async def fetch_page(off: int) -> Dict[str, int]:
            async with page_sem:
                data = await self._request("/items", params={"limit": limit, "offset": off})
                if not data:
                    return {}
                page_items = data.get("items", [])
                page_catalog: Dict[str, int] = {}
                for item in page_items:
                    name = item.get("market_hash_name", "")
                    item_id = item.get("item_id")
                    if name and item_id:
                        page_catalog[name] = item_id
                return page_catalog

        # Fetch all pages in parallel (rate-limited to 5 concurrent)
        results = await asyncio.gather(*[fetch_page(off) for off in offsets], return_exceptions=True)
        for r in results:
            if isinstance(r, dict):
                catalog.update(r)
            elif isinstance(r, Exception):
                logger.debug(f"Page fetch error (falling back to partial catalog): {r}")

        if catalog:
            self._item_catalog = catalog
            self._catalog_ts = now
            # Reset rate-limit delay after bulk catalog load
            self._request_delay = 1.0
            price_db.save_state("cs2cap_delay", "1.0")
            price_db.save_state("cs2cap_catalog", json.dumps(catalog))
            logger.info(f"[CS2Cap] Loaded {len(self._item_catalog)} items total ({len(offsets)} pages)")
        else:
            logger.warning("[CS2Cap] Catalog empty — API may be unavailable")

    async def get_item_id(self, hash_name: str) -> Optional[int]:
        """Resolve market_hash_name to item_id."""
        await self._load_catalog()
        return self._item_catalog.get(hash_name)
