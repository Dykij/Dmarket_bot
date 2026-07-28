"""demand_strategy.py — Demand-based trading strategy for low balance.

v17.0: Finds items with high buyer-to-seller ratios (demand > supply) on DMarket.
Strategy: Buy at current ask, hold until demand pushes price up, sell at profit.

For items with $40-50 balance, this targets the $1-$10 range where:
- High demand ratio (>2x) indicates bullish pressure
- Good volume (>10 trades) ensures liquidity
- Expected hold time: 1-3 days
"""

from __future__ import annotations

from typing import Any

from src.config import Config


def calculate_demand_score(
    title: str,
    ask_price: float,
    best_bid: float,
    ask_count: int,
    bid_count: int,
) -> dict[str, Any]:
    """
    Calculate demand-based opportunity score.
    
    Returns dict with:
    - score: float (higher = better opportunity)
    - demand_ratio: float (bid_count / ask_count)
    - expected_hold_days: float (estimated days to profit)
    - reason: str (explanation)
    """
    result = {
        "score": 0.0,
        "demand_ratio": 0.0,
        "expected_hold_days": 0.0,
        "reason": "",
    }
    
    if ask_price <= 0 or best_bid <= 0:
        result["reason"] = "invalid prices"
        return result
    
    # Demand ratio: more buyers than sellers = bullish
    demand_ratio = bid_count / max(ask_count, 1)
    
    # Volume: higher = more liquid
    volume = ask_count + bid_count
    
    # Spread: tighter = more liquid
    spread_pct = (best_bid - ask_price) / ask_price * 100
    
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
    
    # Filters
    if demand_ratio < 2.0:
        result["reason"] = f"demand ratio {demand_ratio:.1f}x < 2.0x"
        return result
    
    if volume < 10:
        result["reason"] = f"volume {volume} < 10"
        return result
    
    if hold_days > 7:
        result["reason"] = f"hold time {hold_days:.1f}d > 7d"
        return result
    
    result["score"] = score
    result["demand_ratio"] = demand_ratio
    result["expected_hold_days"] = hold_days
    result["reason"] = f"demand={demand_ratio:.1f}x vol={volume} hold={hold_days:.1f}d"
    
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
                "expected_hold_days": result["expected_hold_days"],
                "score": result["score"],
                "reason": result["reason"],
            })
    
    # Sort by score (best first)
    opportunities.sort(key=lambda x: x["score"], reverse=True)
    
    return opportunities
