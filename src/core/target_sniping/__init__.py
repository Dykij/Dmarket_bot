"""
target_sniping — Strategy A intra-DMarket spread arbitrage.

Composed from focused mixins:
    core.py       — SnipingLoop lifecycle + run_cycle
    pricing.py    — _PricingMixin (float premium, low-fee cache)
    resale.py     — _ResaleMixin (auto_resale, reprice)
    inventory.py  — _InventoryMixin (v12.2 status sync)
    sandbox.py    — _SandboxMixin (DRY_RUN helpers)
    filter.py     — _FilterMixin (per-item candidate evaluation)
    execution.py  — _ExecutionMixin (instant-buy execution)
"""

from __future__ import annotations

from .core import SnipingLoop
from .execution import _ExecutionMixin
from .filter import _FilterMixin
from .inventory import _InventoryMixin
from .pricing import _PricingMixin
from .resale import _ResaleMixin
from .sandbox import _SandboxMixin

__all__ = [
    "SnipingLoop",
    # Mixins (exposed for advanced use / testing)
    "_PricingMixin",
    "_ResaleMixin",
    "_InventoryMixin",
    "_SandboxMixin",
    "_FilterMixin",
    "_ExecutionMixin",
]
