"""
microstructure.py — DMarket-native financial instruments (v14.1).

All indicators powered by DMarket API data (0 cs2cap quota used):
  - A-S reservation price (Avellaneda-Stoikov)
  - VWAP (Volume-Weighted Average Price)
  - Slippage estimator (Almgren-Chriss simplified)
  - CVD (Cumulative Volume Delta) via trade classification
  - VPIN-lite (Volume-Synchronized Probability of Informed Trading)
  - Time-of-day seasonality adjustment
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Microstructure")


# ==================================================================
# 1. A-S RESERVATION PRICE (Avellaneda-Stoikov simplified)
# ==================================================================

def reservation_price(
    mid_price: float,
    inventory_qty: int,
    target_qty: int,
    max_qty: int,
    volatility: float,
    gamma: float = 0.3,
    T_days: float = 7.0,
) -> float:
    """
    Compute inventory-aware reservation price.

    Formula:  r = mid - (inv - target) / max * gamma * sigma^2 * T / 365

    Args:
        mid_price: current fair mid-price (e.g., cs2cap micro-price)
        inventory_qty: current holdings of this item
        target_qty: target holdings (0 = neutral, >0 for accumulation)
        max_qty: maximum allowed holdings
        volatility: annualized vol estimate (e.g., 0.0-2.0)
        gamma: risk aversion (higher = faster inventory mean reversion)
        T_days: time horizon in days (trade lock + settlement)

    Returns:
        Reservation price — the price at which the agent is indifferent
        between holding and selling. List BELOW this to sell faster;
        list ABOVE this only if there's no urgency.
    """
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
) -> Tuple[float, float]:
    """
    Compute optimal bid-ask spread around reservation price.

    Returns (bid_price, ask_price) for market-making.
    """
    sigma_sq = max(volatility, 0.01) ** 2
    half_spread = gamma * sigma_sq * (T_days / 365.0) * mid_price * 0.5
    bid = reservation - half_spread
    ask = reservation + half_spread
    return round(bid, 4), round(ask, 4)


# ==================================================================
# 2. VWAP (Volume-Weighted Average Price)
# ==================================================================

def compute_vwap(sales: List[Dict[str, Any]]) -> Tuple[float, int, float]:
    """
    Compute VWAP, total volume, and standard deviation from sales.

    Args:
        sales: list of {"price": float, ...} dicts

    Returns:
        (vwap, total_volume, std_dev)
    """
    if not sales:
        return 0.0, 0, 0.0

    prices = [s["price"] for s in sales]
    weights = [s.get("amount", 1) for s in sales]
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0, 0, 0.0
    vwap = sum(p * w for p, w in zip(prices, weights)) / total_weight
    if len(prices) > 1:
        variance = sum(w * (p - vwap) ** 2 for p, w in zip(prices, weights)) / total_weight
        std_dev = math.sqrt(variance)
    else:
        std_dev = 0.0
    return round(vwap, 4), total_weight, round(std_dev, 4)


def vwap_signal(
    best_ask: float, sales: List[Dict[str, Any]], threshold: float = 0.90
) -> Optional[float]:
    """
    Return discount ratio if best_ask is significantly below VWAP.

    Returns None if no signal, or (1 - best_ask/vwap) as undervaluation ratio.
    """
    vwap, _, _ = compute_vwap(sales)
    if vwap <= 0:
        return None
    ratio = best_ask / vwap
    if ratio < threshold:
        return 1.0 - ratio
    return None


# ==================================================================
# 3. SLIPPAGE ESTIMATOR (Almgren-Chriss simplified)
# ==================================================================

def estimate_slippage(
    buy_price: float,
    order_qty: int,
    daily_volume: int,
    best_ask: float,
    best_bid: float,
    temp_impact_bps: float = 5.0,
    perm_impact_bps: float = 2.0,
) -> float:
    """
    Estimate total expected slippage in USD for a market order.

    Uses a simplified Almgren-Chriss two-component impact model:
      - Temporary impact: linear in participation rate (order_qty / available_depth)
      - Permanent impact: proportional to order_qty / daily_volume

    Returns total slippage as a fraction of buy_price (e.g., 0.005 = 0.5%).
    """
    if daily_volume <= 0 or buy_price <= 0:
        return 0.001

    available_depth = max(1, daily_volume // 100)  # approximate top-of-book depth
    participation = order_qty / max(1, available_depth)

    temp_impact = (temp_impact_bps / 10000.0) * participation
    perm_impact = (perm_impact_bps / 10000.0) * (order_qty / max(1, daily_volume))

    return temp_impact + perm_impact


# ==================================================================
# 4. CVD (Cumulative Volume Delta)
# ==================================================================

def classify_trade_lee_ready(
    price: float, prev_mid: float, prev_bid: float = 0.0, prev_ask: float = 0.0
) -> Optional[int]:
    """
    Lee-Ready trade classification.

    Returns +1 (buyer-initiated), -1 (seller-initiated), or None (unclassified).
    """
    if price <= 0:
        return None
    mid = (prev_bid + prev_ask) / 2.0 if prev_bid > 0 and prev_ask > 0 else prev_mid
    if mid <= 0:
        return None
    if price > mid:
        return 1
    elif price < mid:
        return -1
    return None  # at mid — ambiguous


def compute_cvd(sales: List[Dict[str, Any]], prev_mid: float = 0.0) -> float:
    """
    Compute Cumulative Volume Delta from a list of trades.

    Uses price-vs-previous-mid as the classification rule.
    Returns raw CVD value (positive = buying pressure).
    """
    cvd = 0.0
    running_mid = prev_mid
    for s in sales:
        price = s.get("price", 0.0)
        qty = s.get("amount", 1)
        direction = classify_trade_lee_ready(price, running_mid)
        if direction is not None:
            cvd += direction * qty
        # Update running mid for next trade in sequence
        if price > 0:
            running_mid = running_mid * 0.9 + price * 0.1 if running_mid > 0 else price
    return round(cvd, 4)


def cvd_divergence(cvd: float, price_change_pct: float) -> Optional[str]:
    """
    Detect CVD-price divergence.

    Returns "bullish" if CVD rising while price falling (accumulation),
    "bearish" if CVD falling while price rising (distribution), else None.
    """
    if cvd > 5 and price_change_pct < -0.01:
        return "bullish"
    if cvd < -5 and price_change_pct > 0.01:
        return "bearish"
    return None


# ==================================================================
# 5. VPIN-LITE (Volume-Synchronized Probability of Informed Trading)
# ==================================================================

def compute_vpin(sales: List[Dict[str, Any]], n_buckets: int = 8) -> Optional[float]:
    """
    Compute VPIN-lite: probability of informed trading from volume imbalance.

    Algorithm:
      1. Group trades into equal-volume buckets
      2. In each bucket, compute signed imbalance V_B = sum(direction * volume)
      3. VPIN = avg(|V_B|) / avg(total_volume_per_bucket)

    Returns VPIN in [0, 1] or None if insufficient data.
    """
    if not sales or len(sales) < n_buckets * 2:
        return None

    total_volume = sum(s.get("amount", 1) for s in sales)
    if total_volume <= 0:
        return None

    bucket_vol = total_volume / n_buckets if n_buckets > 0 else 1

    imbalances = []
    bucket_total = 0.0
    bucket_imbalance = 0.0
    running_mid = sales[0].get("price", 1.0)

    for s in sales:
        price = s.get("price", 0.0)
        qty = s.get("amount", 1)
        direction = classify_trade_lee_ready(price, running_mid) or 0

        bucket_total += qty
        bucket_imbalance += direction * qty
        running_mid = running_mid * 0.9 + price * 0.1 if price > 0 else running_mid

        if bucket_total >= bucket_vol:
            imbalances.append(abs(bucket_imbalance) / max(1, bucket_total))
            bucket_total = 0.0
            bucket_imbalance = 0.0

    if not imbalances:
        return None

    return round(sum(imbalances) / len(imbalances), 4)


# ==================================================================
# 6. TIME-OF-DAY SEASONALITY
# ==================================================================

def tod_multiplier(
    night_start_utc: int = 4,
    night_end_utc: int = 10,
    night_factor: float = 0.85,
    day_factor: float = 1.0,
) -> float:
    """
    Return a multiplier for spread/min-margin thresholds based on time of day.

    Night hours (low demand, sellers dumping): lower threshold = buy more aggressively.
    Day hours (peak demand): normal threshold.
    """
    now = datetime.now(timezone.utc)
    hour = now.hour
    if night_start_utc <= hour < night_end_utc:
        return night_factor
    return day_factor
