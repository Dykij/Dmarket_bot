"""Target Sniping v12.0 — Strategy A: Intra-DMarket Spread Arbitrage.

The bot:
1. Scans DMarket for items (50 per batch)
2. Fetches aggregated prices (best_bid, best_ask) for those items
3. Filters: best_bid > best_ask * 1.05 (5%+ spread)
4. CS2Cap oracle validates the spread is real (not a stale data spike)
5. If profitable: buy at best_ask, list at best_bid - 0.01
6. Periodically reprices unsold items

No more BUFF163-csfloat comparison (that strategy never worked).

This module is a thin facade. The actual implementation lives in the
`target_sniping` sub-package:

    core.py       — SnipingLoop lifecycle + run_cycle
    pricing.py    — Float premium + low-fee cache
    resale.py     — Auto-resale + reprice pipeline
    inventory.py  — v12.2 inventory status sync (trade_protected, reverted)
    sandbox.py    — DRY_RUN simulation helpers

Usage:
    ```python
    from src.core.target_sniping import SnipingLoop
    loop = SnipingLoop(client)
    await loop.start()
    ```
"""

from __future__ import annotations

from .target_sniping import SnipingLoop

__all__ = ["SnipingLoop"]
