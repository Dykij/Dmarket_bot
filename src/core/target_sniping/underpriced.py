"""DMarket-internal underpriced detection helpers.

v14.8.1: Detect DMarket listings that are cheap relative to recent DMarket
sales history, even when no external marketplace (CS2Cap) edge exists.
"""

from __future__ import annotations

import statistics
from typing import Any, Dict, List, Optional

from src.config import Config


def _percentile(values: List[float], p: float) -> Optional[float]:
    """Return the p-th percentile of a sorted list (0 <= p <= 1)."""
    if not values:
        return None
    sorted_vals = sorted(values)
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    idx = p * (n - 1)
    lower = int(idx)
    upper = min(lower + 1, n - 1)
    frac = idx - lower
    return sorted_vals[lower] * (1 - frac) + sorted_vals[upper] * frac


async def is_dmarket_underpriced(
    client,
    game_id: str,
    title: str,
    current_price: float,
    fee_rate: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Check if a DMarket listing is underpriced vs recent market reference.

    Uses price_db history first (avoids DMarket /last-sales auth issues),
    then falls back to DMarket last-sales if available. Returns
    {"underpriced": bool, "reference_price": float, "margin_pct": float}.
    """
    result = {"underpriced": False, "reference_price": 0.0, "margin_pct": 0.0}

    if not Config.DMARKET_INTERNAL_UNDERPRICED_ENABLED:
        return result

    if current_price <= 0 or not title:
        return result

    prices: List[float] = []

    # 1. Local price history (CS2Cap / DMarket prices recorded by the bot).
    try:
        from src.db.price_history import price_db
        history = price_db.get_recent_prices(title, days=Config.DM_UNDERPRICED_SALES_DAYS)
        prices = [p for p, _ in history if p > 0]
    except Exception:
        prices = []

    # 2. Fallback to DMarket last-sales (currently requires JWT auth on
    #    trade-aggregator endpoints, so often unavailable with API keys).
    if len(prices) < 3:
        try:
            sales = await client.get_last_sales(
                game_id, title, days=Config.DM_UNDERPRICED_SALES_DAYS, limit=20
            )
            prices = [s["price"] for s in sales if s.get("price", 0) > 0]
        except Exception:
            prices = []

    if len(prices) < 3:
        return result

    ref = _percentile(prices, Config.DM_UNDERPRICED_PERCENTILE)
    if ref is None or ref <= 0:
        return result

    # Net reference after selling fees (we'll sell at reference price)
    sell_fee = fee_rate if fee_rate is not None else Config.FEE_RATE
    net_reference = ref * (1 - sell_fee - Config.WITHDRAWAL_FEE_RATE)

    if net_reference <= current_price:
        return result

    margin_pct = (net_reference - current_price) / current_price * 100.0
    if margin_pct < Config.DM_UNDERPRICED_MIN_MARGIN_PCT:
        return result

    result["underpriced"] = True
    result["reference_price"] = ref
    result["margin_pct"] = margin_pct
    return result


async def fetch_low_fee_titles(client, game_id: str) -> Dict[str, float]:
    """
    Fetch DMarket low-fee items and return {title: fee_rate}.

    Limited by Config.LOW_FEE_ITEMS_SCAN_LIMIT.
    """
    if not Config.LOW_FEE_ITEMS_SCAN_ENABLED:
        return {}

    items = await client.get_low_fee_items(game_id, limit=Config.LOW_FEE_ITEMS_SCAN_LIMIT)
    result: Dict[str, float] = {}
    for it in items[: Config.LOW_FEE_ITEMS_SCAN_LIMIT]:
        title = it.get("title", "")
        fee = it.get("fee_rate", 0.05)
        if title:
            result[title] = fee
    return result
