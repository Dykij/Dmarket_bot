"""
volume.py — Volume-based indicators for DMarket (v14.3).

Functions:
  - VWAP (Volume-Weighted Average Price) with bands and signal
  - Slippage estimator (Almgren-Chriss simplified)
  - CVD (Cumulative Volume Delta) via Lee-Ready classification
  - VPIN-lite (Volume-Synchronized Probability of Informed Trading)
"""

from __future__ import annotations

import math
from typing import Any

# ══════════════════════════════════════════════════════════════════════
# 5. VWAP (Volume-Weighted Average Price)
# ══════════════════════════════════════════════════════════════════════


def compute_vwap(sales: list[dict[str, Any]]) -> tuple[float, int, float]:
    if not sales:
        return 0.0, 0, 0.0
    prices = [s["price"] for s in sales]
    weights = [s.get("amount", 1) for s in sales]
    total_weight = sum(weights)
    if total_weight == 0:
        return 0.0, 0, 0.0
    vwap = sum(p * w for p, w in zip(prices, weights, strict=False)) / total_weight
    if len(prices) > 1:
        variance = sum(w * (p - vwap) ** 2
                       for p, w in zip(prices, weights, strict=False)) / total_weight
        std_dev = math.sqrt(variance)
    else:
        std_dev = 0.0
    return round(vwap, 4), total_weight, round(std_dev, 4)


def vwap_signal(
    best_ask: float, sales: list[dict[str, Any]], threshold: float = 0.90
) -> float | None:
    vwap, _, _ = compute_vwap(sales)
    if vwap <= 0:
        return None
    ratio = best_ask / vwap
    if ratio < threshold:
        return 1.0 - ratio
    return None


def vwap_bands(sales: list[dict[str, Any]], num_std: float = 2.0
               ) -> tuple[float, float, float]:
    """(vwap, lower_band, upper_band) for mean-reversion trading."""
    vwap, _, std = compute_vwap(sales)
    return vwap, round(vwap - num_std * std, 4), round(vwap + num_std * std, 4)


# ══════════════════════════════════════════════════════════════════════
# 6. SLIPPAGE ESTIMATOR (Almgren-Chriss simplified)
# ══════════════════════════════════════════════════════════════════════


def estimate_slippage(
    buy_price: float,
    order_qty: int,
    daily_volume: int,
    best_ask: float,
    best_bid: float,
    temp_impact_bps: float = 5.0,
    perm_impact_bps: float = 2.0,
) -> float:
    if daily_volume <= 0 or buy_price <= 0:
        return 0.001
    available_depth = max(1, daily_volume // 100)
    participation = order_qty / max(1, available_depth)
    temp_impact = (temp_impact_bps / 10000.0) * participation
    perm_impact = (perm_impact_bps / 10000.0) * (order_qty / max(1, daily_volume))
    return temp_impact + perm_impact


# ══════════════════════════════════════════════════════════════════════
# 7. CVD (Cumulative Volume Delta)
# ══════════════════════════════════════════════════════════════════════


def classify_trade_lee_ready(
    price: float, prev_mid: float, prev_bid: float = 0.0, prev_ask: float = 0.0
) -> int | None:
    if price <= 0:
        return None
    mid = (prev_bid + prev_ask) / 2.0 if prev_bid > 0 and prev_ask > 0 else prev_mid
    if mid <= 0:
        return None
    if price > mid:
        return 1
    elif price < mid:
        return -1
    return None


def compute_cvd(sales: list[dict[str, Any]], prev_mid: float = 0.0) -> float:
    cvd = 0.0
    running_mid = prev_mid
    for s in sales:
        price = s.get("price", 0.0)
        qty = s.get("amount", 1)
        direction = classify_trade_lee_ready(price, running_mid)
        if direction is not None:
            cvd += direction * qty
        if price > 0:
            running_mid = running_mid * 0.9 + price * 0.1 if running_mid > 0 else price
    return round(cvd, 4)


def cvd_divergence(cvd: float, price_change_pct: float) -> str | None:
    if cvd > 5 and price_change_pct < -0.01:
        return "bullish"
    if cvd < -5 and price_change_pct > 0.01:
        return "bearish"
    return None


# ══════════════════════════════════════════════════════════════════════
# 8. VPIN-LITE
# ══════════════════════════════════════════════════════════════════════


def compute_vpin(sales: list[dict[str, Any]], n_buckets: int = 8) -> float | None:
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
