"""
price_history — Bifurcated SQLite storage (v15.1).

Composed from focused mixins:
    core.py            — PriceHistoryDB (lifecycle + schema init)
    history.py         — _HistoryMixin (price observations + analytics)
    state.py           — _StateMixin (scanning_state cursor)
    inventory.py       — _InventoryMixin (virtual_inventory CRUD)
    analytics_logs.py  — _AnalyticsLogsMixin (decision logs, equity, risk events)
    targets.py         — _TargetsMixin (active_targets)
    asset_status.py    — _AssetStatusMixin (v12.2 trade_protected, reverted)
    low_fee.py         — _LowFeeMixin (v12.0 daily cache)
    pump_blacklist.py  — _PumpBlacklistMixin (v12.7 FOMO protection, persistent)
"""

from __future__ import annotations

from .analytics_logs import _AnalyticsLogsMixin
from .asset_status import _AssetStatusMixin
from .core import PriceHistoryDB
from .history import _HistoryMixin
from .inventory import _InventoryMixin
from .low_fee import _LowFeeMixin
from .pump_blacklist import _PumpBlacklistMixin
from .state import _StateMixin
from .targets import _TargetsMixin

__all__ = [
    "PriceHistoryDB",
    "price_db",
    "_HistoryMixin",
    "_StateMixin",
    "_InventoryMixin",
    "_AnalyticsLogsMixin",
    "_TargetsMixin",
    "_AssetStatusMixin",
    "_LowFeeMixin",
    "_PumpBlacklistMixin",
]


price_db = PriceHistoryDB()

# v15.5: Register shutdown hook for clean WAL checkpoint
import atexit

atexit.register(price_db.close)

