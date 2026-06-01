"""
price_history — Bifurcated SQLite storage (v8.0).

Composed from focused mixins:
    core.py         — PriceHistoryDB (lifecycle + schema init)
    history.py      — _HistoryMixin (price observations + analytics)
    state.py        — _StateMixin (scanning_state cursor)
    inventory.py    — _InventoryMixin (virtual_inventory + logs)
    targets.py      — _TargetsMixin (active_targets)
    asset_status.py — _AssetStatusMixin (v12.2 trade_protected, reverted)
    low_fee.py      — _LowFeeMixin (v12.0 daily cache)
"""

from __future__ import annotations

from .asset_status import _AssetStatusMixin
from .core import PriceHistoryDB
from .history import _HistoryMixin
from .inventory import _InventoryMixin
from .low_fee import _LowFeeMixin
from .state import _StateMixin
from .targets import _TargetsMixin

__all__ = [
    "PriceHistoryDB",
    "price_db",
    # Mixins (exposed for advanced use / testing)
    "_HistoryMixin",
    "_StateMixin",
    "_InventoryMixin",
    "_TargetsMixin",
    "_AssetStatusMixin",
    "_LowFeeMixin",
]


# Singleton instance — matches the original behavior (created at import time)
price_db = PriceHistoryDB()

