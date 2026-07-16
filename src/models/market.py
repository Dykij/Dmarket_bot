"""
market.py — High-performance msgspec Struct models for DMarket API.

v15.7: Replaces dict-based data flow with typed Structs.
msgspec.Struct is 10-50x faster than dataclasses for serialization
and 5-10x faster than Pydantic for validation.

These models are used in the hot path:
- API response parsing (DMarket JSON → Struct)
- Pipeline data transfer between stages
- CycleContext enrichment
"""

from __future__ import annotations

import msgspec

# =====================================================================
# DMarket API Response Models
# =====================================================================


class PriceAmount(msgspec.Struct):
    """DMarket price object: {"amount": "1234", "currency": "USD"}"""
    amount: str = ""
    currency: str = "USD"

    @property
    def usd(self) -> float:
        """Convert cents string to USD float."""
        try:
            return int(self.amount) / 100.0
        except (ValueError, TypeError):
            return 0.0


class MarketItem(msgspec.Struct):
    """Single DMarket listing from /exchange/v1/market/items."""
    itemId: str = ""
    title: str = ""
    price: PriceAmount = msgspec.field(default_factory=PriceAmount)
    classId: str = ""
    gameId: str = ""

    @property
    def base_price(self) -> float:
        return self.price.usd


class AggregatedPrice(msgspec.Struct):
    """Aggregated price data from /marketplace-api/v1/aggregated-prices."""
    market_hash_name: str = ""
    best_bid: float = 0.0
    best_ask: float = 0.0
    bid_count: int = 0
    ask_count: int = 0


class PriceSnapshot(msgspec.Struct):
    """Oracle price snapshot for a single item."""
    title: str = ""
    min_price: float = 0.0
    avg_price: float = 0.0
    volume: int = 0
    sources_count: int = 0

    @property
    def has_data(self) -> bool:
        return self.sources_count > 0 and self.min_price > 0


# =====================================================================
# Trade Candidate (filter output → executor input)
# =====================================================================


class TradeCandidate(msgspec.Struct):
    """
    Validated trade candidate returned by _evaluate_candidate().
    Replaces the dict-based return for type safety and performance.
    """
    buy_offer: dict = msgspec.field(default_factory=dict)
    title: str = ""
    item_id: str = ""
    base_price: float = 0.0
    list_price: float = 0.0
    best_bid: float = 0.0
    best_ask: float = 0.0
    strategy: str = "intra_spread"
    target_platform: str = "dmarket"
    dm_underpriced_ref: float = 0.0
    is_rare: bool = False
    fee_rate: float = 0.05
    premium_mult: float = 1.0
    est_sell_price: float = 0.0
    est_profit: float = 0.0
    est_roi_pct: float = 0.0

    @property
    def margin_pct(self) -> float:
        """Calculate gross margin percentage."""
        if self.best_ask <= 0:
            return 0.0
        return ((self.best_bid - self.best_ask) / self.best_ask) * 100.0

    @property
    def net_margin_pct(self) -> float:
        """Calculate net margin after fees."""
        if self.base_price <= 0:
            return 0.0
        sell_net = self.list_price * (1.0 - self.fee_rate)
        return ((sell_net - self.base_price) / self.base_price) * 100.0


# =====================================================================
# Cycle Context (pipeline state)
# =====================================================================


class CycleStats(msgspec.Struct):
    """Statistics for a completed trading cycle."""
    cycle_id: int = 0
    game_id: str = ""
    duration_s: float = 0.0
    items_scanned: int = 0
    candidates_found: int = 0
    trades_executed: int = 0
    total_spent_usd: float = 0.0
    total_earned_usd: float = 0.0
    balance_before: float = 0.0
    balance_after: float = 0.0


# =====================================================================
# Oracle Models
# =====================================================================


class OracleResult(msgspec.Struct):
    """Result from MultiSourceOracle.get_fair_price()."""
    title: str = ""
    fair_price: float = 0.0
    sources_used: int = 0
    confidence: float = 0.0
    marketcsgo_price: float = 0.0
    waxpeer_price: float = 0.0
    csfloat_price: float = 0.0
    steam_price: float = 0.0


# =====================================================================
# Risk Models
# =====================================================================


class RiskSnapshot(msgspec.Struct):
    """Snapshot of current risk state for /status display."""
    daily_realized_pnl: float = 0.0
    daily_loss_limit_usd: float = 0.0
    daily_trade_count: int = 0
    daily_trade_limit: int = 0
    current_drawdown_pct: float = 0.0
    max_drawdown_pct: float = 0.0
    peak_equity_usd: float = 0.0
    current_equity_usd: float = 0.0
    win_rate: float = 0.55
    win_loss_ratio: float = 1.5
    consecutive_losses: int = 0
    drawdown_freeze_active: bool = False
    soft_halt_active: bool = False
    daily_halt_active: bool = False


# =====================================================================
# JSON Helpers
# =====================================================================


def encode_struct(obj: msgspec.Struct) -> bytes:
    """Encode a Struct to JSON bytes (5-10x faster than json.dumps)."""
    return msgspec.json.encode(obj)


def decode_struct(data: bytes | str, type_: type) -> msgspec.Struct:
    """Decode JSON bytes to a Struct with validation."""
    if isinstance(data, str):
        data = data.encode("utf-8")
    return msgspec.json.decode(data, type=type_)
