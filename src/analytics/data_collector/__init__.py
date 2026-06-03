"""
data_collector — Historical Market Data Collector (Roadmap Task #15).

Background task that pulls a market snapshot every N minutes, stores
it in the DB, prunes old rows, and exports to CSV on demand.

Package layout:
    snapshot.py  — collect_market_snapshot, _collect_game_data (data fetchers)
    storage.py   — store_snapshot, cleanup_old_data, export_to_csv (DB + CSV)
    collector.py — MarketDataCollector class (start/stop/loop wrapper)

Public API (re-exported for backward compat):
    MarketDataCollector — the only name in the original module's public surface
"""

from __future__ import annotations

from .collector import MarketDataCollector

__all__ = ["MarketDataCollector"]
