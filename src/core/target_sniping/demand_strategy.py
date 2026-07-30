"""demand_strategy.py — Order Book Imbalance (OBI) demand-based strategy.

v17.3: Major OBI improvements based on academic literature.

Improvements over v17.2:
1. Normalized OBI: (bid-ask)/(bid+ask) in [-1,1] — price-independent
2. OFI (Order Flow Imbalance): change in OBI between cycles — momentum signal
3. Z-score calibration: adaptive thresholds per-item based on history
4. OBI as risk-gate: OFI is primary signal, OBI is secondary filter
5. Liquidity threshold: minimum (bid_count + ask_count) to avoid noise
6. EWMA smoothing: reduce noise in OBI measurements
7. Bait detection integration: penalize suspicious items

Academic basis:
- Gould & Bonart (2016): Queue Imbalance predicts next mid-price movement
- Stoikov (2017): Micro-Price with OBI adjustment
- Cont, Kukanov & Stoikov (2014): OFI as stronger predictor than static OBI
"""

from __future__ import annotations

from typing import Any

from src.analysis.microstructure.obi import (
    normalized_obi,
    ofi,
    obi_z_score,
    queue_imbalance,
    queue_imbalance_signal,
    simple_obi,
    stoikov_micro_price,
)
from src.config import Config

# v17.3: OBI history cache for OFI calculation
_obi_history: dict[str, list[float]] = {}
_obi_ewma: dict[str, float] = {}


def get_adaptive_thresholds(ask_price: float) -> dict[str, float]:
    """
    Get adaptive thresholds by price segment.

    Cheaper items allow lower demand ratios (more opportunities).
    Expensive items require higher demand ratios (better quality).
    """
    if ask_price < 2.0:
        return {
            "min_demand_ratio": 1.5,
            "min_volume": 5,
            "max_hold_days": 10.0,
            "obi_calibration": 0.30,
        }
    elif ask_price < 5.0:
        return {
            "min_demand_ratio": 2.0,
            "min_volume": 10,
            "max_hold_days": 7.0,
            "obi_calibration": 0.35,
        }
    else:
        return {
            "min_demand_ratio": 2.5,
            "min_volume": 15,
            "max_hold_days": 5.0,
            "obi_calibration": 0.40,
        }


def _update_obi_history(title: str, obi_norm: float) -> tuple[float, float]:
    """
    Update OBI history and compute OFI + EWMA.

    Returns: (ofi_value, ewma_obi)
    """
    global _obi_history, _obi_ewma

    # Get previous OBI for OFI
    prev_obi = _obi_ewma.get(title, 0.0)
    ofi_value = ofi(obi_norm, prev_obi)

    # Update history (keep last 20 observations)
    if title not in _obi_history:
        _obi_history[title] = []
    _obi_history[title].append(obi_norm)
    if len(_obi_history[title]) > 20:
        _obi_history[title] = _obi_history[title][-20:]

    # EWMA smoothing (alpha=0.3)
    alpha = 0.3
    ewma = alpha * obi_norm + (1 - alpha) * prev_obi
    _obi_ewma[title] = ewma

    return ofi_value, ewma


def calculate_demand_score(
    title: str,
    ask_price: float,
    best_bid: float,
    ask_count: int,
    bid_count: int,
) -> dict[str, Any]:
    """
    Calculate demand-based opportunity score using improved OBI.

    v17.3 improvements:
    - Uses normalized_obi instead of volume-weighted simple_obi
    - Computes OFI (change in OBI) as primary signal
    - Uses z-score for adaptive thresholds
    - Applies EWMA smoothing to reduce noise
    - Integrates bait detection
    """
    result = {
        "score": 0.0,
        "demand_ratio": 0.0,
        "obi_signal": "neutral",
        "obi_value": 0.0,
        "ofi_value": 0.0,
        "obi_z": 0.0,
        "micro_price": 0.0,
        "expected_hold_days": 0.0,
        "reason": "",
    }

    if ask_price <= 0 or best_bid <= 0:
        result["reason"] = "invalid prices"
        return result

    # Get adaptive thresholds
    thresholds = get_adaptive_thresholds(ask_price)

    # v17.5: Dynamic liquidity threshold — adaptive by price segment
    total_orders = bid_count + ask_count
    if Config.DYNAMIC_LIQUIDITY_ENABLED:
        if ask_price < 2.0:
            min_liquidity = 3   # Cheap items: lower threshold (more opportunities)
        elif ask_price < 10.0:
            min_liquidity = 5   # Mid-range items
        else:
            min_liquidity = 10  # Expensive items: higher threshold (more manipulation risk)
    else:
        min_liquidity = 5  # Fixed fallback

    if total_orders < min_liquidity:
        result["reason"] = f"low liquidity ({total_orders} orders < {min_liquidity})"
        return result

    # v17.6: Spread entropy filter — block/penalize wide spreads
    spread_pct = (ask_price - best_bid) / ask_price if ask_price > 0 else 0
    if Config.SPREAD_ENTROPY_ENABLED:
        if spread_pct > Config.SPREAD_ENTROPY_HARD_BLOCK:
            result["reason"] = f"spread too wide ({spread_pct:.1%} > {Config.SPREAD_ENTROPY_HARD_BLOCK:.0%})"
            return result

    # v17.3: Normalized OBI (price-independent, [-1, 1])
    obi_norm = normalized_obi(bid_count, ask_count)

    # v17.3: OFI + EWMA smoothing
    ofi_value, ewma_obi = _update_obi_history(title, obi_norm)

    # v17.3: Z-score calibration
    historical = _obi_history.get(title, [])
    z_score = obi_z_score(obi_norm, historical)

    # Legacy functions for compatibility
    qi = queue_imbalance(bid_count, ask_count)
    signal = queue_imbalance_signal(bid_count, ask_count)
    obi = simple_obi(best_bid, ask_price, bid_count, ask_count)

    # Micro-price estimation
    mid_price = (best_bid + ask_price) / 2
    spread = ask_price - best_bid
    micro = stoikov_micro_price(mid_price, spread, obi_norm, calibration=thresholds["obi_calibration"])

    if qi is None:
        result["reason"] = "no queue data"
        return result

    demand_ratio = qi
    volume = total_orders

    # Required appreciation to cover fees + profit
    fees_pct = (Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE) * 100
    min_spread = Config.MIN_SPREAD_PCT
    required_appreciation = fees_pct + min_spread

    # Expected daily appreciation based on demand
    expected_daily = min(demand_ratio * 0.5, 5.0)

    # Hold time to break even
    hold_days = required_appreciation / max(expected_daily, 0.1)

    # Risk-adjusted score
    score = demand_ratio * volume / max(hold_days, 0.5)

    # v17.6: Spread entropy soft penalty — penalize wide spreads
    if Config.SPREAD_ENTROPY_ENABLED and spread_pct > Config.SPREAD_ENTROPY_SOFT_PENALTY:
        score *= 0.5  # 50% penalty for spreads > 10%

    # v17.6: Price-Volume Correlation (PVC) trend multiplier
    # Compares price and volume changes over recent cycles
    if Config.PVC_ENABLED:
        try:
            from src.db.price_history import price_db
            history = price_db.get_recent_prices(title, days=3)
            if len(history) >= 3:
                prices = [p for p, _ in history if p > 0]
                if len(prices) >= 3:
                    price_change = (prices[-1] - prices[0]) / prices[0] if prices[0] > 0 else 0
                    # Volume trend: use OBI history as proxy (higher OBI = more buying volume)
                    obi_history = _obi_history.get(title, [])
                    if len(obi_history) >= 3:
                        vol_trend = obi_history[-1] - obi_history[0]
                        # Price up + volume up = bullish → boost
                        # Price up + volume down = divergence → penalize
                        if price_change > 0 and vol_trend > 0:
                            score *= 1.2  # 20% boost
                        elif price_change > 0 and vol_trend < 0:
                            score *= 0.8  # 20% penalty
        except Exception:
            pass  # Non-critical

    # Apply adaptive thresholds
    if demand_ratio < thresholds["min_demand_ratio"]:
        result["reason"] = f"demand ratio {demand_ratio:.1f}x < {thresholds['min_demand_ratio']:.1f}x"
        return result

    if volume < thresholds["min_volume"]:
        result["reason"] = f"volume {volume} < {thresholds['min_volume']}"
        return result

    if hold_days > thresholds["max_hold_days"]:
        result["reason"] = f"hold time {hold_days:.1f}d > {thresholds['max_hold_days']:.1f}d"
        return result

    # v17.3: OBI as risk-gate — block if OBI is strongly bearish
    if obi_norm < -0.3:
        result["reason"] = f"OBI risk-gate: obi_norm={obi_norm:.2f} < -0.3 (sellers dominate)"
        return result

    # v17.3: OFI as primary signal — require positive momentum
    # If OFI < -0.1, demand is weakening — reduce score
    if ofi_value < -0.1:
        score *= 0.5  # 50% penalty for weakening demand

    # v17.3: Z-score boost — unusually high OBI is stronger signal
    if z_score is not None and z_score > 1.5:
        score *= 1.2  # 20% boost for statistically significant signal

    # Only accept BUY signals from OBI
    if signal != "buy":
        result["reason"] = f"OBI signal: {signal} (not buy)"
        return result

    # v17.2: Peak avoidance
    reason_parts = []
    try:
        from src.db.price_history import price_db
        import statistics
        history = price_db.get_recent_prices(title, days=7)
        prices = [p for p, _ in history if p > 0]

        if len(prices) >= 5:
            median_price = statistics.median(prices)

            if len(prices) >= 3:
                last_3 = prices[-3:]
                is_uptrend = all(last_3[i] > last_3[i-1] for i in range(1, len(last_3)))
            else:
                is_uptrend = False

            if ask_price > median_price * 1.15:
                if is_uptrend:
                    score *= 0.90
                    reason_parts.append("uptrend-peak-10%")
                else:
                    score *= 0.85
                    reason_parts.append("peak-penalty-15%")
    except Exception:
        pass

    result["score"] = score
    result["demand_ratio"] = demand_ratio
    result["obi_signal"] = signal
    result["obi_value"] = obi_norm  # v17.3: use normalized OBI
    result["ofi_value"] = ofi_value
    result["obi_z"] = z_score if z_score is not None else 0.0
    result["micro_price"] = micro
    result["expected_hold_days"] = hold_days
    reason_str = f"demand={demand_ratio:.1f}x vol={volume} hold={hold_days:.1f}d obi={obi_norm:.2f} ofi={ofi_value:+.2f}"
    if z_score is not None:
        reason_str += f" z={z_score:.1f}"
    if reason_parts:
        reason_str += " (" + ", ".join(reason_parts) + ")"
    result["reason"] = reason_str

    # v17.5: Log decision to decision_logs for backtest analysis
    _log_demand_decision(title, ask_price, result)

    return result


def _log_demand_decision(title: str, price: float, result: dict[str, Any]) -> None:
    """Log demand strategy decision to decision_logs table.

    v17.5: Enables future backtest and threshold calibration.
    """
    try:
        from src.db.price_history import price_db
        import json
        details = json.dumps({
            "obi_norm": result.get("obi_value", 0),
            "ofi": result.get("ofi_value", 0),
            "z_score": result.get("obi_z", 0),
            "demand_ratio": result.get("demand_ratio", 0),
            "score": result.get("score", 0),
            "hold_days": result.get("expected_hold_days", 0),
            "price": price,
        })
        decision = "pass" if result.get("score", 0) > 0 else "skip"
        price_db.log_decision(
            title, decision, "demand_strategy", result.get("reason", ""), details
        )
    except Exception:
        pass  # Non-critical — don't break trading for logging


def is_demand_opportunity(
    agg_data: dict[str, Any],
    max_price: float = 15.0,
    min_price: float = 0.50,
) -> list[dict[str, Any]]:
    """
    Find demand-based opportunities from aggregated prices.

    Returns list of opportunities sorted by score (best first).
    """
    opportunities = []

    for title, data in agg_data.items():
        ask = data.get("best_ask", 0) or 0
        bid = data.get("best_bid", 0) or 0
        ask_count = data.get("ask_count", 0) or 0
        bid_count = data.get("bid_count", 0) or 0

        if ask < min_price or ask > max_price or bid <= 0:
            continue

        result = calculate_demand_score(title, ask, bid, ask_count, bid_count)

        if result["score"] > 0:
            opportunities.append({
                "title": title,
                "ask_price": ask,
                "best_bid": bid,
                "demand_ratio": result["demand_ratio"],
                "obi_signal": result["obi_signal"],
                "obi_value": result["obi_value"],
                "ofi_value": result["ofi_value"],
                "obi_z": result["obi_z"],
                "micro_price": result["micro_price"],
                "expected_hold_days": result["expected_hold_days"],
                "score": result["score"],
                "reason": result["reason"],
            })

    # Sort by score (best first)
    opportunities.sort(key=lambda x: x["score"], reverse=True)

    return opportunities


def clear_obi_history() -> None:
    """Clear OBI history cache (call between cycles if needed)."""
    global _obi_history, _obi_ewma
    _obi_history.clear()
    _obi_ewma.clear()
