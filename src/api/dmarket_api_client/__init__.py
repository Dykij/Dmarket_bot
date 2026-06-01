"""
dmarket_api_client — DMarket Trading API v2 client.

A thin wrapper around the v2 endpoints used by the bot. Composed from
focused mixins:

    core.py     — DMarketAPIClient lifecycle + request pipeline
    market.py   — Market data (scans, aggregated prices, last sales)
    account.py  — Balance, inventory, transactions
    offers.py   — Sell-side offers (single, batch, v2)
    targets.py  — Buy-side targets and instant purchase
    fees.py     — Fee lookups (single + bulk, with 12h cache)
    exceptions.py — SecurityViolation
"""

from __future__ import annotations

from .account import _AccountMixin
from .core import DMarketAPIClient
from .exceptions import SecurityViolation
from .fees import _FeesMixin
from .market import _MarketMixin
from .offers import _OffersMixin
from .targets import _TargetsMixin

__all__ = [
    "DMarketAPIClient",
    "SecurityViolation",
    # Mixins (exposed for advanced use / testing)
    "_MarketMixin",
    "_AccountMixin",
    "_OffersMixin",
    "_TargetsMixin",
    "_FeesMixin",
]
