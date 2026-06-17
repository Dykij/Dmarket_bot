"""
signals.py — Composite trading signals for DMarket (v14.3).

Functions:
  - Smart Cancel/Reprice signal (order book dynamics)
  - Composite Buy Score (weighted combination of all signals)
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple


# ══════════════════════════════════════════════════════════════════════
# 14. SMART CANCEL / REPRICE SIGNAL
# ══════════════════════════════════════════════════════════════════════


def smart_reprice_signal(
    current_bid_count: int,
    current_ask_count: int,
    prev_bid_count: int,
    prev_ask_count: int,
    listed_price: float,
    best_bid: float,
    best_ask: float,
) -> Tuple[str, Optional[float]]:
    """
    Decide whether to cancel/reprice a listing based on order book dynamics.

    Returns ("keep", None) - no action
            ("drop", optional_new_price) - reprice with slight discount
            ("cancel", None) - market no longer supports this listing
            ("boost", optional_higher_price) - demand rising, can ask more
    """
    if current_bid_count <= 0 or current_ask_count <= 0:
        return "cancel", None

    # OFI (micro) between snapshots
    ofi = (current_bid_count - prev_bid_count) - (current_ask_count - prev_ask_count)
    qi_curr = current_bid_count / max(1, current_ask_count)
    qi_prev = (prev_bid_count or 1) / max(1, prev_ask_count or 1)

    # Bids drying up rapidly
    if ofi < -15 and qi_curr < 0.4:
        return "cancel", None

    # Bids declining -> reprice lower
    if ofi < -5 or (qi_curr < 0.6 and qi_prev >= 0.6):
        new_price = round(listed_price * 0.97, 2)   # 3% discount
        if new_price > best_bid:
            return "drop", new_price
        return "drop", round(best_bid - 0.01, 2)

    # Demand building - can ask higher
    if ofi > 10 and qi_curr > 2.0:
        boost = round(min(best_ask * 1.03, listed_price * 1.02), 2)
        return "boost", boost

    # Listed too far from market -> reprice closer
    if best_bid > 0 and listed_price > best_bid * 1.15:
        return "drop", round(best_bid * 1.05, 2)

    return "keep", None


# ══════════════════════════════════════════════════════════════════════
# 15. COMPOSITE SCORE (weighted combination of all signals)
# ══════════════════════════════════════════════════════════════════════


def composite_buy_score(
    best_ask: float, best_bid: float,
    ask_count: int, bid_count: int,
    obi: float, ofi: int,
    cvd: float, vpin_val: float,
    vwap_discount: float,
    adverse_pass: bool,
    vol_regime: str,
    kyle_lam: Optional[float] = None,
) -> Tuple[float, Dict[str, float]]:
    """
    Weighted composite score for ranking candidates.

    Returns (total_score, component_scores).
    Higher = better buy opportunity.

    Score components (each 0..1):
      - spread_quality: how wide is the bid-ask spread relative to ask
      - obi_signal: buyer pressure
      - ofi_signal: growing demand
      - cvd_bullish: CVD positive (accumulation)
      - vpin_safe: low adverse selection
      - vwap_undervalued: discount to VWAP
      - adverse_clean: low market impact
      - vol_ok: not in high-vol regime
    """
    components: Dict[str, float] = {}

    # Spread quality (0..1)
    spread_pct = (best_bid - best_ask) / max(best_ask, 0.01)
    components["spread"] = min(1.0, max(0.0, spread_pct / 0.15))

    # OBI (0..1), already in [-1,1] range; map to 0..1
    components["obi"] = (obi + 1.0) / 2.0

    # OFI (0..1)
    components["ofi"] = min(1.0, max(0.0, (ofi + 20) / 40.0))

    # CVD (0..1)
    components["cvd"] = min(1.0, max(0.0, (cvd + 10) / 20.0))

    # VPIN inverted: low VPIN = good
    components["vpin"] = 1.0 - min(1.0, vpin_val)

    # VWAP discount (0..1)
    components["vwap"] = min(1.0, vwap_discount / 0.15)

    # Adverse selection (0 or 1)
    components["adverse"] = 1.0 if adverse_pass else 0.0

    # Volatility regime (0..1)
    vol_scores = {"low": 1.0, "medium": 0.7, "high": 0.3}
    components["vol_regime"] = vol_scores.get(vol_regime, 0.5)

    # Kyle lambda inversion (0..1): lower lambda = higher score
    if kyle_lam is not None and kyle_lam > 0:
        components["kyle"] = 1.0 - min(1.0, kyle_lam / 0.10)
    else:
        components["kyle"] = 0.5

    weights = {
        "spread": 2.0,
        "obi": 1.5,
        "ofi": 1.0,
        "cvd": 0.5,
        "vpin": 1.0,
        "vwap": 1.0,
        "adverse": 2.0,
        "vol_regime": 0.5,
        "kyle": 1.0,
    }

    weighted_sum = sum(components[k] * weights[k] for k in weights)
    total_weight = sum(weights.values())
    total_score = weighted_sum / max(total_weight, 0.01)

    return round(total_score, 4), components
