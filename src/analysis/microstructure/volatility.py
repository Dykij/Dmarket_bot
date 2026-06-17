"""
volatility.py — Volatility, spread, and seasonality instruments for DMarket (v14.3).

Functions:
  - Time-of-Day / Day-of-Week Seasonality Multipliers
  - Adverse Selection: Kyle lambda, Amihud illiquidity, combined check
  - Realized Volatility (standard deviation, Parkinson)
  - Volatility Regime Classification
  - Roll's Model / Effective Spread
  - Volume Profile / POC / Value Area
"""

from __future__ import annotations

import logging
import math
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("Microstructure")


# ══════════════════════════════════════════════════════════════════════
# 9. TIME-OF-DAY SEASONALITY
# ══════════════════════════════════════════════════════════════════════


def tod_multiplier(
    night_start_utc: int = 4,
    night_end_utc: int = 10,
    night_factor: float = 0.85,
    day_factor: float = 1.0,
) -> float:
    now = datetime.now(timezone.utc)
    hour = now.hour
    if night_start_utc <= hour < night_end_utc:
        return night_factor
    return day_factor


def day_of_week_multiplier() -> float:
    """Adjust thresholds by weekday. Weekends typically have lower CS2 volume."""
    now = datetime.now(timezone.utc)
    weekday = now.weekday()  # 0=Mon, 6=Sun
    if weekday >= 5:   # Saturday, Sunday
        return 0.90    # 10% lower margin - less competition
    return 1.0


# ══════════════════════════════════════════════════════════════════════
# 10. ADVERSE SELECTION (Kyle lambda / Amihud)
# ══════════════════════════════════════════════════════════════════════


def kyle_lambda(
    sales: List[Dict[str, Any]],
) -> Optional[float]:
    """
    Kyle's lambda - price impact sensitivity to volume.

    lambda approx mean(|Delta price| / volume) over the trade sequences.
    Higher lambda = more adverse selection -> avoid.

    Returns None if insufficient data.
    """
    if len(sales) < 3:
        return None
    deltas = []
    prev_price = None
    for s in sales:
        price = s.get("price", 0.0)
        qty = s.get("amount", 1)
        if price <= 0:
            continue
        if prev_price is not None and qty > 0:
            dp = abs(price - prev_price)
            if prev_price > 0 and dp > 0:
                deltas.append(dp / qty)
        prev_price = price
    if not deltas:
        return None
    return round(sum(deltas) / len(deltas), 6)


def amihud_illiquidity(
    sales: List[Dict[str, Any]],
) -> Optional[float]:
    """
    Amihud illiquidity ratio: avg(|return| / dollar_volume).

    Higher values = larger price moves per dollar volume = illiquid.
    Use as an avoid-if-too-large filter.
    """
    if len(sales) < 3:
        return None
    ratios = []
    prev_price = None
    for s in sales:
        price = s.get("price", 0.0)
        if price <= 0:
            continue
        if prev_price is not None and prev_price > 0:
            ret = abs(price - prev_price) / prev_price
            dollar_vol = price * 1  # qty=1 in our trade_history
            if dollar_vol > 0:
                ratios.append(ret / dollar_vol)
        prev_price = price
    if not ratios:
        return None
    return round(sum(ratios) / len(ratios), 8)


def adverse_selection_check(
    sales: List[Dict[str, Any]],
    max_kyle: float = 0.05,
    max_amihud: float = 0.10,
) -> Tuple[bool, str]:
    """
    Combined adverse selection check.

    Returns (pass, reason).
    """
    lam = kyle_lambda(sales)
    if lam is not None and lam > max_kyle:
        return False, f"Kyle lambda={lam:.4f} exceeds max {max_kyle}"

    illiq = amihud_illiquidity(sales)
    if illiq is not None and illiq > max_amihud:
        return False, f"Amihud={illiq:.6f} exceeds max {max_amihud}"

    return True, "low adverse selection"


# ══════════════════════════════════════════════════════════════════════
# 11. REALIZED VOLATILITY (multiple estimators)
# ══════════════════════════════════════════════════════════════════════


def realized_vol_std(sales: List[Dict[str, Any]],
                     annualize_factor: float = 365.0) -> Optional[float]:
    """Standard deviation of trade prices -> annualized vol."""
    prices = [s["price"] for s in sales if s.get("price", 0) > 0]
    if len(prices) < 3:
        return None
    mean = sum(prices) / len(prices)
    variance = sum((p - mean) ** 2 for p in prices) / (len(prices) - 1)
    daily_vol = math.sqrt(variance) / (mean if mean > 0 else 1)
    return round(daily_vol * math.sqrt(annualize_factor), 4)


def realized_vol_parkinson(sales: List[Dict[str, Any]],
                           annualize_factor: float = 365.0) -> Optional[float]:
    """
    Parkinson high-low range estimator.
    Uses max/min price within a bucket as proxy for intraday range.
    More efficient than close-to-close (5.2x for Brownian motion).
    """
    prices = [s["price"] for s in sales if s.get("price", 0) > 0]
    if len(prices) < 5:
        return None
    bucket_size = max(1, len(prices) // 5)
    estimates = []
    for i in range(0, len(prices) - bucket_size, bucket_size):
        bucket = prices[i:i + bucket_size]
        high = max(bucket)
        low = min(bucket)
        if low > 0:
            hl = math.log(high / low)
            estimates.append(hl * hl)
    if not estimates:
        return None
    mean_sq = sum(estimates) / len(estimates)
    daily_vol = math.sqrt(mean_sq / (4.0 * math.log(2.0)))
    return round(daily_vol * math.sqrt(annualize_factor), 4)


def classify_volatility_regime(annualized_vol: float) -> str:
    """Categorise volatility regime for adaptive thresholds."""
    if annualized_vol < 0.20:
        return "low"
    elif annualized_vol < 0.50:
        return "medium"
    else:
        return "high"


# ══════════════════════════════════════════════════════════════════════
# 12. ROLL'S MODEL / EFFECTIVE SPREAD
# ══════════════════════════════════════════════════════════════════════


def roll_effective_spread(prices: List[float]) -> Optional[float]:
    """
    Roll (1984) model: effective bid-ask spread estimation
    from price-change serial covariance.

    s = 2 x sqrt(-cov(Delta p_t, Delta p_{t-1}))

    Returns None if cov > 0 (no estimable spread).
    """
    if len(prices) < 4:
        return None
    dp = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    if len(dp) < 3:
        return None
    mean_dp = sum(dp) / len(dp)
    cov_sum = 0.0
    for i in range(len(dp) - 1):
        cov_sum += (dp[i] - mean_dp) * (dp[i + 1] - mean_dp)
    cov = cov_sum / max(len(dp) - 1, 1)
    if cov >= -1e-15:
        return None
    spread = 2.0 * math.sqrt(-cov)
    if spread < 1e-12:
        return None
    return round(spread, 6)


def roll_signal(prices: List[float], best_ask: float) -> Optional[str]:
    """
    Compare Roll-effective-spread to observed spread.

    Returns:
      - "cheap": observed spread << Roll spread -> cheap liquidity
      - "expensive": observed spread >> Roll spread -> overpaying
      - None: inconclusive
    """
    roll = roll_effective_spread(prices)
    if roll is None or roll <= 0:
        return None
    avg_price = sum(prices) / len(prices) if prices else 0
    if avg_price <= 0:
        return None
    obs_spread_pct = (best_ask - avg_price) / avg_price if avg_price > 0 else 0
    roll_spread_pct = roll / avg_price
    if obs_spread_pct < roll_spread_pct * 0.7:
        return "cheap"
    if obs_spread_pct > roll_spread_pct * 1.5:
        return "expensive"
    return None


# ══════════════════════════════════════════════════════════════════════
# 13. VOLUME PROFILE / POC
# ══════════════════════════════════════════════════════════════════════


def volume_profile_poc(
    sales: List[Dict[str, Any]],
    num_buckets: int = 10,
) -> Optional[float]:
    """
    Point of Control - the price level with the highest trade volume.

    Returns POC price or None if insufficient data.
    """
    prices = [s["price"] for s in sales if s.get("price", 0) > 0]
    if len(prices) < 5:
        return None
    p_min, p_max = min(prices), max(prices)
    if p_max <= p_min:
        return round(p_min, 4)
    bucket_width = (p_max - p_min) / num_buckets
    if bucket_width <= 0:
        return round(prices[0], 4)
    counts = Counter()
    for p in prices:
        bucket = int((p - p_min) / bucket_width)
        bucket = min(num_buckets - 1, max(0, bucket))
        bucket_center = p_min + (bucket + 0.5) * bucket_width
        counts[round(bucket_center, 2)] += 1
    if not counts:
        return None
    return counts.most_common(1)[0][0]


def volume_profile_value_area(
    sales: List[Dict[str, Any]],
    value_area_pct: float = 0.70,
    num_buckets: int = 10,
) -> Optional[Tuple[float, float, float]]:
    """
    Value Area - the price range containing value_area_pct% of total volume.
    Returns (VALUE_AREA_HIGH, POC, VALUE_AREA_LOW) or None.
    """
    poc = volume_profile_poc(sales, num_buckets)
    if poc is None:
        return None
    prices = [s["price"] for s in sales if s.get("price", 0) > 0]
    p_min, p_max = min(prices), max(prices)
    if p_max <= p_min:
        return (p_max, poc, p_min)
    bucket_width = (p_max - p_min) / num_buckets
    bucket_vols: Dict[float, int] = defaultdict(int)
    for p in prices:
        bucket = int((p - p_min) / bucket_width)
        bucket = min(num_buckets - 1, max(0, bucket))
        center = round(p_min + (bucket + 0.5) * bucket_width, 2)
        bucket_vols[center] += 1
    total_vol = sum(bucket_vols.values())
    target_vol = total_vol * value_area_pct
    sorted_buckets = sorted(bucket_vols.items(), key=lambda x: x[0])
    # Expand from POC outward
    poc_idx = next((i for i, (c, _) in enumerate(sorted_buckets) if abs(c - poc) < bucket_width * 0.6), len(sorted_buckets) // 2)
    cum_vol = bucket_vols.get(sorted_buckets[poc_idx][0], 0)
    lo_idx = hi_idx = poc_idx
    while cum_vol < target_vol and (lo_idx > 0 or hi_idx < len(sorted_buckets) - 1):
        if lo_idx > 0:
            lo_idx -= 1
            cum_vol += sorted_buckets[lo_idx][1]
            if cum_vol >= target_vol:
                break
        if hi_idx < len(sorted_buckets) - 1:
            hi_idx += 1
            cum_vol += sorted_buckets[hi_idx][1]
    vah = sorted_buckets[hi_idx][0]
    val = sorted_buckets[lo_idx][0]
    return (vah, poc, val)
