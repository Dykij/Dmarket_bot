"""
target_sniping — Strategy A intra-DMarket spread arbitrage.

Composed from focused mixins:
    core.py       — SnipingLoop lifecycle + run_cycle
    scheduler.py  — _SchedulerMixin (start, scan delay, CS2Cap cache)
    telemetry.py  — _TelemetryMixin (health, equity, diag)
    pricing.py    — _PricingMixin (float premium, low-fee cache)
    resale.py     — _ResaleMixin (auto_resale, reprice)
    inventory.py  — _InventoryMixin (v12.2 status sync)
    sandbox.py    — _SandboxMixin (DRY_RUN helpers)
    scanner.py    — _ScannerMixin (parallel listing fetch)
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
from .scanner import _ScannerMixin
from .scheduler import _SchedulerMixin
from .telemetry import _TelemetryMixin

__all__ = [
    "SnipingLoop",
    # Mixins (exposed for advanced use / testing)
    "_SchedulerMixin",
    "_TelemetryMixin",
    "_PricingMixin",
    "_ResaleMixin",
    "_InventoryMixin",
    "_SandboxMixin",
    "_ScannerMixin",
    "_FilterMixin",
    "_ExecutionMixin",
]
