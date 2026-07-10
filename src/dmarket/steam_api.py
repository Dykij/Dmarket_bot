"""Steam API integration."""
from typing import Any


async def get_steam_price(market_hash_name: str, app_id: int = 730) -> float:
    """Get current Steam market price for an item."""
    return 0.0


def calculate_arbitrage(
    buy_price: float,
    steam_price: float,
    fee_rate: float = 0.15,
) -> dict[str, Any]:
    """Calculate arbitrage opportunity between DMarket and Steam."""
    net_steam = steam_price * (1 - fee_rate)
    profit = net_steam - buy_price
    margin_pct = (profit / buy_price * 100) if buy_price > 0 else 0
    return {
        "profit": profit,
        "margin_pct": margin_pct,
        "viable": profit > 0 and margin_pct > 5.0,
    }
