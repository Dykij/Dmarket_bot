"""
obi.py — Order Book Imbalance signals for DMarket (v14.3).

Functions:
  - Stoikov Micro-Price (OBI-adjusted fair price)
  - Simple OBI (best-level volume imbalance)
  - Multi-Level OBI (depth-weighted from listing data)
  - Queue Imbalance (bid/ask count ratio)
  - Avellaneda-Stoikov Reservation Price & Spread
"""

from __future__ import annotations

from typing import Any

# ══════════════════════════════════════════════════════════════════════
# 1. STOIKOV MICRO-PRICE (OBI-adjusted fair price)
# ══════════════════════════════════════════════════════════════════════


def stoikov_micro_price(
    mid_price: float,
    spread: float,
    obi: float,
    calibration: float = 0.35,
) -> float:
    """
    OBI-adjusted fair price (Stoikov 2017).

    Formula:  P_micro = mid_price + c * spread * obi

    obi within [-1, 1] where +1 = max buyer pressure, -1 = max seller pressure.
    spread = best_bid - best_ask.

    This micro-price is a better predictor of short-term mid-price
    movements than simple mid or VWAP (Stoikov 2017, Bieganowski 2026).
    """
    if spread <= 0:
        return mid_price
    return round(mid_price + calibration * spread * obi, 4)


def simple_obi(best_bid: float, best_ask: float,
               bid_count: int, ask_count: int) -> float:
    """
    Compute simple OBI in [-1, 1] range from best-level counts.

    obi = (bid_volume - ask_volume) / (bid_volume + ask_volume)
    """
    bid_vol = (best_bid or 0.01) * (bid_count or 0)
    ask_vol = (best_ask or 0.01) * (ask_count or 0)
    total = bid_vol + ask_vol
    if total == 0:
        return 0.0
    return round((bid_vol - ask_vol) / total, 4)


# ══════════════════════════════════════════════════════════════════════
# 2. MULTI-LEVEL OBI (depth-weighted from listings)
# ══════════════════════════════════════════════════════════════════════


def multi_level_obi(
    best_bid: float,
    best_ask: float,
    bid_count: int,
    ask_count: int,
    listings: list[dict[str, Any]] | None = None,
    levels: int = 5,
) -> float:
    """
    Depth-weighted OBI using sell-side listing depth.

    On DMarket, we lack buy-side depth. We reconstruct sell-side depth
    from market/items listings (up to 30 cheapest). Buy-side depth is
    approximated using ask_count/bid_count ratios.

    Returns OBI in [-1, 1]. Positive = buyer pressure.
    """
    sell_prices: list[float] = []
    if listings:
        for li in listings:
            px = int(li.get("price", {}).get("USD", 0)) / 100.0
            if px > 0:
                sell_prices.append(px)
    sell_prices.sort()

    ask_volume = (best_ask or 0.01) * (ask_count or 1)
    ask_levels = 0.0
    for i in range(min(levels, len(sell_prices))):
        weight = 1.0 / (i + 1)
        ask_levels += sell_prices[i] * weight

    safe_bid = best_bid or 0.01
    bid_volume = safe_bid * (bid_count or 1)
    bid_levels = safe_bid * sum(1.0 / (i + 1) for i in range(levels))

    if ask_levels > 0:
        sell_side_mean = ask_levels / bid_levels
    else:
        sell_side_mean = 1.0   # neutral if no depth data

    imbalance = (bid_volume - ask_volume) / max(bid_volume + ask_volume, 0.01)
    depth_adj = 1.0 / max(sell_side_mean, 0.01) if sell_side_mean > 0 else 0.0
    return round(max(-1.0, min(1.0, 0.6 * imbalance + 0.4 * ((depth_adj - 1.0) / 10.0))), 4)


# ══════════════════════════════════════════════════════════════════════
# 3. QUEUE IMBALANCE (ratio for large-tick detection)
# ══════════════════════════════════════════════════════════════════════


def queue_imbalance(
    bid_count: int,
    ask_count: int,
) -> float | None:
    """
    Queue size ratio. Best for large-tick assets (like CS2 skins
    where prices move in discrete $0.01-$0.05 steps).

    Gould & Bonart: queue imbalance predicts next mid-price movement.
    q > 1.0 -> bid queue larger -> likely upward move.
    q < 1.0 -> ask queue larger -> likely downward move.

    Returns None if either count is zero.
    """
    if ask_count <= 0:
        return None
    return round(bid_count / ask_count, 4)


def queue_imbalance_signal(
    bid_count: int,
    ask_count: int,
) -> str:
    """
    Signal interpretation: "buy", "sell", "neutral".
    """
    qi = queue_imbalance(bid_count, ask_count)
    if qi is None:
        return "neutral"
    if qi > 1.5:
        return "buy"
    if qi < 0.5:
        return "sell"
    return "neutral"


# ══════════════════════════════════════════════════════════════════════
# 4. A-S RESERVATION PRICE (Avellaneda-Stoikov simplified)
# ══════════════════════════════════════════════════════════════════════


def reservation_price(
    mid_price: float,
    inventory_qty: int,
    target_qty: int,
    max_qty: int,
    volatility: float,
    gamma: float = 0.3,
    T_days: float = 7.0,
) -> float:
    if max_qty <= 0:
        return mid_price
    inventory_deviation = (inventory_qty - target_qty) / max_qty
    sigma_sq = max(volatility, 0.01) ** 2
    skew = gamma * sigma_sq * (T_days / 365.0)
    return mid_price - inventory_deviation * skew * mid_price


def reservation_spread(
    reservation: float,
    mid_price: float,
    volatility: float,
    gamma: float = 0.3,
    T_days: float = 7.0,
) -> tuple[float, float]:
    sigma_sq = max(volatility, 0.01) ** 2
    half_spread = gamma * sigma_sq * (T_days / 365.0) * mid_price * 0.5
    bid_price = reservation - half_spread
    ask_price = reservation + half_spread
    return round(bid_price, 4), round(ask_price, 4)
