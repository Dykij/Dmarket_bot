"""
telemetry.py — Health reporting + diagnostic logging.

Mixin with _update_health_metrics(), _send_equity_milestone(), and _log_cycle_diag().
Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

# P1-1: Lazy import

logger = logging.getLogger("SnipingBot")



class _TelemetryMixin:
    """Health-state, equity milestones, and per-cycle diagnostics."""

    client: Any
    deep_scan_counter: int
    risk: Any
    pump_detector: Any
    _last_milestone: float
