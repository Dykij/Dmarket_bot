"""DMarket Trading API v2 Client.

Thin facade around the v2 endpoints used by the bot. The actual
implementation lives in the `dmarket_api_client` sub-package:

    core.py     — DMarketAPIClient lifecycle + request pipeline
    market.py   — Market data (scans, aggregated prices, last sales)
    account.py  — Balance, inventory, transactions
    offers.py   — Sell-side offers (single, batch, v2)
    targets.py  — Buy-side targets and instant purchase
    fees.py     — Fee lookups (single + bulk, with 12h cache)
    exceptions.py — SecurityViolation

Usage:
    ```python
    from src.api.dmarket_api_client import DMarketAPIClient

    client = DMarketAPIClient(public_key="...", secret_key="...")
    balance = await client.get_real_balance()
    items = await client.get_user_inventory_detailed("a8db")
    ```
"""

from __future__ import annotations

from .dmarket_api_client import DMarketAPIClient, SecurityViolation

__all__ = ["DMarketAPIClient", "SecurityViolation"]
