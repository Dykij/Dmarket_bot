"""demand_strategy.py — Order Book Imbalance (OBI) demand-based strategy.

v17.1: Refactored to use existing OBI infrastructure from obi.py.
Academic basis: Gould & Bonart 2016 (Queue Imbalance), Stoikov 2017 (Micro-Price).

Strategy: Find items with high buyer-to-seller ratios (demand > supply) on DMarket.
Buy at current ask, hold until demand pushes price up, sell at profit.

For items with $40-100 balance, this targets the $0.50-$15 range where:
- Queue Imbalance > 2.0 indicates bullish pressure
- Good volume (>10 orders) ensures liquidity
- Expected hold time: 1-3 days
"""

from __future__ import annotations

from typing import Any

from src.analysis.microstructure.obi import (
    queue_imbalance,
    queue_imbalance_signal,
    simple_obi,
    stoikov_micro_price,
)
from src.config import Config


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
            "obi_calibration": 0.30,  # Slightly lower for cheap items
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
            "obi_calibration": 0.40,  # Higher for expensive items
        }


def calculate_demand_score(
    title: str,
    ask_price: float,
    best_bid: float,
    ask_count: int,
    bid_count: int,
) -> dict[str, Any]:
    """
    Calculate demand-based opportunity score using OBI infrastructure.
    
    Uses:
    - queue_imbalance() from obi.py (Gould & Bonart 2016)
    - queue_imbalance_signal() for BUY/SELL/NEUTRAL
    - simple_obi() for volume-weighted OBI
    - stoikov_micro_price() for fair price estimation
    
    Returns dict with:
    - score: float (higher = better opportunity)
    - demand_ratio: float (queue_imbalance)
    - obi_signal: str ("buy", "sell", "neutral")
    - obi_value: float (simple_obi in [-1, 1])
    - micro_price: float (Stoikov fair price)
    - expected_hold_days: float (estimated days to profit)
    - reason: str (explanation)
    """
    result = {
        "score": 0.0,
        "demand_ratio": 0.0,
        "obi_signal": "neutral",
        "obi_value": 0.0,
        "micro_price": 0.0,
        "expected_hold_days": 0.0,
        "reason": "",
    }
    
    if ask_price <= 0 or best_bid <= 0:
        result["reason"] = "invalid prices"
        return result
    
    # Get adaptive thresholds
    thresholds = get_adaptive_thresholds(ask_price)
    
    # Use existing OBI functions
    qi = queue_imbalance(bid_count, ask_count)
    signal = queue_imbalance_signal(bid_count, ask_count)
    obi = simple_obi(best_bid, ask_price, bid_count, ask_count)
    
    # Micro-price estimation
    mid_price = (best_bid + ask_price) / 2
    spread = ask_price - best_bid
    micro = stoikov_micro_price(mid_price, spread, obi, calibration=thresholds["obi_calibration"])
    
    if qi is None:
        result["reason"] = "no queue data"
        return result
    
    demand_ratio = qi
    volume = ask_count + bid_count
    
    # Required appreciation to cover fees + profit
    fees_pct = (Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE) * 100
    min_spread = Config.MIN_SPREAD_PCT
    required_appreciation = fees_pct + min_spread
    
    # Expected daily appreciation based on demand
    # Heuristic: demand_ratio * 0.5% per day (capped at 5%)
    expected_daily = min(demand_ratio * 0.5, 5.0)
    
    # Hold time to break even
    hold_days = required_appreciation / max(expected_daily, 0.1)
    
    # Risk-adjusted score
    # Higher demand, higher volume, lower hold time = better
    score = demand_ratio * volume / max(hold_days, 0.5)
    
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
    
    # Only accept BUY signals from OBI
    if signal != "buy":
        result["reason"] = f"OBI signal: {signal} (not buy)"
        return result
    
    result["score"] = score
    result["demand_ratio"] = demand_ratio
    result["obi_signal"] = signal
    result["obi_value"] = obi
    result["micro_price"] = micro
    result["expected_hold_days"] = hold_days
    result["reason"] = f"demand={demand_ratio:.1f}x vol={volume} hold={hold_days:.1f}d obi={obi:.2f}"
    
    return result


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
                "micro_price": result["micro_price"],
                "expected_hold_days": result["expected_hold_days"],
                "score": result["score"],
                "reason": result["reason"],
            })
    
    # Sort by score (best first)
    opportunities.sort(key=lambda x: x["score"], reverse=True)
    
    return opportunities
