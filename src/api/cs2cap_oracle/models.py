"""
CS2Cap Oracle data models — exceptions, dataclasses, and constants.
"""

from dataclasses import dataclass, field

BATCH_MAX_ITEMS = 100


class CS2CapRateLimit(Exception):
    pass


# Alias used across the codebase (consistency with csfloat_oracle).
# The v12.0 loop in src/core/target_sniping/core.py imports
# `RateLimitException` directly; aliasing prevents a pre-existing
# ImportError that has kept the v12.0 loop un-wired in production.
RateLimitException = CS2CapRateLimit


@dataclass
class MarketPrice:
    provider: str
    lowest_ask: float
    quantity: int
    timestamp: float = 0.0


@dataclass
class CrossMarketData:
    hash_name: str
    global_min_ask: float = 0.0
    global_max_bid: float = 0.0
    provider_prices: dict[str, float] = field(default_factory=dict)
    buy_orders: dict[str, float] = field(default_factory=dict)
    sales_count: int = 0
    avg_sale_price: float = 0.0
    volatility_1h: float = 0.0
    volatility_24h: float = 0.0
    rsi: float = 50.0
    macd_signal: float = 0.0
    bollinger_position: float = 0.5
    liquidity_score: float = 0.0

    def __post_init__(self):
        if self.provider_prices and self.global_min_ask == 0.0:
            self.global_min_ask = min(self.provider_prices.values())
        if self.buy_orders and self.global_max_bid == 0.0:
            self.global_max_bid = max(self.buy_orders.values())


@dataclass
class PriceSnapshot:
    """
    Unified per-item view returned by /prices/batch (1 HTTP call).

    Fields:
        hash_name: market_hash_name (CS2 item key)
        min_price: USD; lowest ask across all providers (0.0 = no data)
        max_bid:   USD; highest buy order across all providers (0.0 = no data)
        provider_prices: {provider: ask_usd} for all providers seen
        provider_quantities: {provider: int qty} for liquidity score
        total_quantity: sum of quantities across providers
    """
    hash_name: str
    min_price: float = 0.0
    max_bid: float = 0.0
    provider_prices: dict[str, float] = field(default_factory=dict)
    provider_quantities: dict[str, int] = field(default_factory=dict)
    total_quantity: int = 0

    @property
    def liquidity_score(self) -> float:
        """0.0-1.0 normalized liquidity (1.0 at 100+ units across providers)."""
        return min(1.0, self.total_quantity / 100.0)

    @property
    def has_data(self) -> bool:
        return self.min_price > 0.0


@dataclass
class BidsSnapshot:
    """
    Unified per-item view returned by /bids/batch (1 HTTP call).

    Fields:
        hash_name: market_hash_name
        max_bid: USD; highest buy order across all providers (0.0 = no data)
        provider_bids: {provider: bid_usd}
    """
    hash_name: str
    max_bid: float = 0.0
    provider_bids: dict[str, float] = field(default_factory=dict)

    @property
    def has_data(self) -> bool:
        return self.max_bid > 0.0
