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
    spread = best_ask - best_bid.  # P2-6: Fixed sign convention (was best_bid - best_ask)

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


def normalized_obi(bid_count: int, ask_count: int) -> float:
    """
    Normalized Order Book Imbalance in [-1, 1].

    Formula: OBI_norm = (bid_count - ask_count) / (bid_count + ask_count)

    This is the standard academic formulation (Cont et al. 2014).
    Independent of price level — works across all item categories.

    Returns:
        +1.0 = all buyers, no sellers (maximum bullish)
        -1.0 = all sellers, no buyers (maximum bearish)
         0.0 = balanced

    v17.3: Added as standard OBI metric for demand strategy.
    """
    total = bid_count + ask_count
    if total == 0:
        return 0.0
    return round((bid_count - ask_count) / total, 4)


def ofi(current_obi: float, previous_obi: float) -> float:
    """
    Order Flow Imbalance (OFI) — change in OBI between cycles.

    OFI = OBI_current - OBI_previous

    Academic basis: Cont, Kukanov & Stoikov (2014) — OFI is a stronger
    predictor of short-term price movements than static OBI.

    Returns:
        > 0 = increasing buyer pressure (bullish momentum)
        < 0 = increasing seller pressure (bearish momentum)

    v17.3: Added for demand strategy signal persistence.
    """
    return round(current_obi - previous_obi, 4)


def obi_z_score(current_obi: float, historical_obis: list[float]) -> float | None:
    """
    Z-score of current OBI relative to historical distribution.

    z = (current - mean) / std

    Used for adaptive threshold calibration per-item.
    z > 1.5 = unusually high buyer pressure (strong signal)
    z < -1.5 = unusually high seller pressure (avoid)

    Returns None if insufficient history (<5 observations).
    """
    if len(historical_obis) < 5:
        return None
    import statistics
    mean = statistics.mean(historical_obis)
    std = statistics.stdev(historical_obis)
    if std < 0.001:  # Avoid division by zero
        return 0.0
    return round((current_obi - mean) / std, 2)


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

    Returns None if both counts are zero.
    v17.3: Returns large value (999.0) when ask_count=0 but bid_count>0
    (infinite demand, no supply) — consistent with normalized_obi behavior.
    """
    if bid_count <= 0 and ask_count <= 0:
        return None
    if ask_count <= 0:
        return 999.0  # Infinite demand, no supply
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
    kappa: float | None = None,
) -> tuple[float, float]:
    """
    Avellaneda-Stoikov optimal spread.

    Original formula (verified against A-S 2008):
        δ* = γσ²(T-t) + (2/γ)ln(1 + γ/κ)

    Where κ = order arrival decay rate. When κ is None (unknown),
    the adverse selection term is omitted — this UNDERSTATES the spread.

    The `kappa` parameter enables the full formula when estimated
    from historical listing event data.
    """
    import logging
    import math

    _logger = logging.getLogger("SnipingBot")

    sigma_sq = max(volatility, 0.01) ** 2
    T_years = T_days / 365.0

    # Inventory risk component (always present)
    inventory_risk = gamma * sigma_sq * T_years * mid_price

    # Adverse selection component (only when kappa is known)
    adverse_selection = 0.0
    if kappa is not None and kappa > 0 and gamma > 0:
        adverse_selection = (2.0 / gamma) * math.log(1.0 + gamma / kappa) * mid_price

    # Full A-S half-spread
    full_half_spread = (inventory_risk + adverse_selection) * 0.5

    # Current simplified formula (what the code uses today)
    simplified_half_spread = gamma * sigma_sq * T_years * mid_price * 0.5

    # Diagnostic logging: compare the two formulas
    spread_diff = full_half_spread - simplified_half_spread
    spread_diff_pct = (spread_diff / max(simplified_half_spread, 0.001)) * 100

    if spread_diff_pct > 5.0:  # Only log when difference is material
        _logger.info(
            f"[A-S AUDIT] {mid_price:.2f}: "
            f"simplified_half_spread=${simplified_half_spread:.4f}, "
            f"full_half_spread=${full_half_spread:.4f} "
            f"(kappa={kappa:.2f}), "
            f"adverse_selection=${adverse_selection:.4f}, "
            f"understatement={spread_diff_pct:.1f}%"
        )

    bid_price = reservation - full_half_spread
    ask_price = reservation + full_half_spread
    return round(bid_price, 4), round(ask_price, 4)
