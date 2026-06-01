"""PriceHistoryDB — Native Bifurcated SQLite storage (v8.0).

Splits trading state and historical analysis into two distinct physical databases:
1. dmarket_state.db   — (OLTP) Fast transactions: orders, inventory, scan state.
2. dmarket_history.db — (OLAP) Bulk analytical data: price observations.

This eliminates write-lock contention during heavy market scans.

This module is a thin facade. The actual implementation lives in the
`price_history` sub-package:

    core.py         — PriceHistoryDB (lifecycle + schema init)
    history.py      — _HistoryMixin (price observations + analytics)
    state.py        — _StateMixin (scanning_state cursor)
    inventory.py    — _InventoryMixin (virtual_inventory + logs)
    targets.py      — _TargetsMixin (active_targets)
    asset_status.py — _AssetStatusMixin (v12.2 trade_protected, reverted)
    low_fee.py      — _LowFeeMixin (v12.0 daily cache)

Usage:
    ```python
    from src.db.price_history import price_db

    # History
    price_db.record_price("AK-47 | Redline", 12.34)
    price_db.get_recent_prices("AK-47 | Redline", days=7)
    price_db.get_liquidity_metrics("AK-47 | Redline")
    price_db.detect_wash_trading("AK-47 | Redline")

    # State
    price_db.save_state("dmarket_cursor_a8db", "abc123")
    price_db.get_state("dmarket_cursor_a8db")

    # Virtual inventory
    price_db.add_virtual_item("AK-47 | Redline", 10.50)
    price_db.get_total_equity(43.91)
    ```
"""

from __future__ import annotations

from .price_history import PriceHistoryDB, price_db

__all__ = ["PriceHistoryDB", "price_db"]
