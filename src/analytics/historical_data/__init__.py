"""
historical_data — Historical price data collection and storage for backtesting.

Public API (all 3 names re-exported for backward compat):
    PricePoint            — single observation (dataclass)
    PriceHistory          — bundle of PricePoints with computed properties
    HistoricalDataCollector — async orchestrator with TTL cache + batch

Package layout:
    models.py    — PricePoint + PriceHistory dataclasses
    sources.py   — collect_from_sales_history, collect_from_aggregated
    collector.py — HistoricalDataCollector class (cache + batch + sources)

Refactor of the original 408-LOC single-file module into a 3-file
package (~110 LOC each) without changing any public behavior.
"""

from __future__ import annotations

from .collector import HistoricalDataCollector
from .models import PriceHistory, PricePoint

__all__ = [
    "HistoricalDataCollector",
    "PriceHistory",
    "PricePoint",
]
