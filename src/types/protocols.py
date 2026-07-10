"""
protocols.py — Protocol types for mixin composition.

Defines structural typing interfaces that mixins depend on from the
composed class. This replaces `object` annotations with actual type
contracts, fixing mypy's "has no attribute" errors.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Protocol, runtime_checkable

# =====================================================================
# Database protocols (used by price_history mixins)
# =====================================================================


@runtime_checkable
class HasSQLiteConnection(Protocol):
    """Protocol for a connection-like object that supports context manager + execute."""

    def execute(self, sql: str, params: tuple = ()) -> sqlite3.Cursor: ...
    def executemany(self, sql: str, params_list: list[tuple]) -> sqlite3.Cursor: ...
    def commit(self) -> None: ...
    def close(self) -> None: ...
    def __enter__(self) -> HasSQLiteConnection: ...
    def __exit__(self, *args: Any) -> None: ...


@runtime_checkable
class HasDBConnections(Protocol):
    """Protocol for classes that hold state_conn and history_conn."""

    state_conn: HasSQLiteConnection
    history_conn: HasSQLiteConnection

    def close(self) -> None: ...


# =====================================================================
# API client protocols (used by dmarket_api_client mixins)
# =====================================================================


@runtime_checkable
class HasMakeRequest(Protocol):
    """Protocol for a class that can make signed API requests."""

    async def make_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]: ...


# =====================================================================
# Notifier protocols (used by pump_detector)
# =====================================================================


@runtime_checkable
class HasNotifier(Protocol):
    """Protocol for a Telegram notifier that can send messages."""

    async def custom(self, text: str, severity: str = "info") -> None: ...


# =====================================================================
# Oracle protocols (used by resale_pipeline, inventory_manager)
# =====================================================================


@runtime_checkable
class HasItemPrice(Protocol):
    """Protocol for an oracle that can get item prices."""

    async def get_item_price(self, title: str) -> float: ...


@runtime_checkable
class HasCrossMarketData(Protocol):
    """Protocol for an oracle that supports cross-market data + batch pricing."""

    async def get_item_price(self, title: str) -> float: ...
    async def get_prices_batch(
        self, titles: list[str]
    ) -> dict[str, Any]: ...
    async def get_cross_market_data(self, title: str) -> Any: ...
    async def close(self) -> None: ...


# =====================================================================
# Circuit breaker protocols (used by core.py)
# =====================================================================


@runtime_checkable
class HasCircuitBreaker(Protocol):
    """Protocol for the circuit breaker pattern."""

    def allow_request(self) -> bool: ...
    def record_failure(self, error: Any) -> None: ...
    def record_success(self) -> None: ...
    def status(self) -> dict[str, Any]: ...


# =====================================================================
# Target sniping loop protocols (used by filter, pricing, execution mixins)
# =====================================================================


@runtime_checkable
class HasSimulateMethods(Protocol):
    """Protocol for the sniping loop's simulation helpers."""

    async def _simulate_network_latency(self, client_type: str = "dmarket") -> None: ...
    def _maybe_inject_error(self, method_name: str) -> None: ...
    def _simulate_competition(self, margin: float) -> bool: ...


@runtime_checkable
class HasSnipingLoopAttrs(Protocol):
    """Protocol for attributes expected on SnipingLoop by its mixins."""

    client: Any
    inventory_mgr: Any
    resale_pipeline: Any
    target_games: list[str]
    deep_scan_counter: int
    buy_budget: float
    empty_page_count: int
    liquidity: Any
    valuation: Any
    stickers: Any
    market_maker: Any
    cross_market: Any
    resale_cycle_limit: int

    async def _simulate_network_latency(self, client_type: str = "dmarket") -> None: ...
    def _maybe_inject_error(self, method_name: str) -> None: ...
    def _simulate_competition(self, margin: float) -> bool: ...
