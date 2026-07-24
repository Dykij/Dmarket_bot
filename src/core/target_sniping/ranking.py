"""
ranking.py — Volume-weighted spread ranking (standalone, extracted from filter.py).

v14.6: Commission optimizer — boosts score for low-fee items.
v15.8: Algo-pack integration — trend strength (LIS) and regime-adjusted scoring.
"""

from __future__ import annotations

import math
from typing import Any

from src.config import Config


# Singleton regime detector (shared across ranking calls within a cycle)
_regime_detector = None
_trend_cache: dict[str, float] = {}


def _get_regime_detector():
    """Lazy-init regime detector singleton."""
    global _regime_detector
    if _regime_detector is None:
        try:
            from src.analysis.algo_pack.regime_detector import MarkovRegimeDetector
            _regime_detector = MarkovRegimeDetector()
        except Exception:
            pass
    return _regime_detector


def clear_trend_cache() -> None:
    """Clear trend cache between cycles."""
    _trend_cache.clear()


def rank_candidates_by_spread(
    items: list[dict[str, Any]],
    agg_prices: dict[str, dict[str, Any]],
    max_price_usd: float | None = None,
    low_fee_titles: set | None = None,
    price_histories: dict[str, list[float]] | None = None,
) -> list[tuple[str, float]]:
    """
    v12.7: Rank items by volume-weighted spread score (P2-3).

    Formula: score = spread_usd * sqrt(ask_count + bid_count)
    This prioritizes items with both good spread AND reasonable volume,
    avoiding low-liquidity items that are hard to sell.

    v14.6: Commission optimizer — items with 2% fee get +15% score boost
    (higher effective profit margin due to lower fees).

    v15.8: Trend boost — items in uptrend get +10% score boost (LIS).
           Regime-adjusted spread threshold (Markov detector).

    Returns: [(title, score), ...] sorted best-score first.
    Items with no agg_prices entry or zero bid/ask are filtered out.

    max_price_usd: optional cap to exclude items too expensive for our
    balance (avoids wasting oracle quota on $1000 Karambits when balance
    is $43.91).

    low_fee_titles: optional set of titles known to have 2% commission.

    price_histories: optional dict {title: [prices...]} for trend analysis.
    """
    ranked: list[tuple[str, float]] = []
    for it in items:
        title = it.get("title", "")
        if not title:
            continue
        if max_price_usd is not None:
            base_price_cents = int(
                it.get("priceCents", 0)
                or it.get("price", {}).get("USD", 0)
            )
            base_price = base_price_cents / 100.0
            if base_price > max_price_usd:
                continue
        agg = agg_prices.get(title, {})
        best_bid = agg.get("best_bid", 0.0) or 0.0
        best_ask = agg.get("best_ask", 0.0) or 0.0
        ask_count = agg.get("ask_count", 0) or 0
        bid_count = agg.get("bid_count", 0) or 0
        if best_bid <= 0 or best_ask <= 0:
            continue

        # v14.8: Fee-aware ranking. Prefer high margin% * liquidity rather than
        # absolute spread, so a 10% margin on a $2 item ranks above a 2% margin
        # on a $20 item with the same volume.
        effective_min_spread = Config.INTRA_MIN_SPREAD_PCT
        if Config.SEASONAL_TIMING_ENABLED:
            try:
                from src.analysis.seasonal import get_timing_multiplier
                effective_min_spread *= get_timing_multiplier()
            except Exception:
                pass

        # v15.8: Regime-adjusted spread threshold
        regime_mult = 1.0
        detector = _get_regime_detector()
        if detector is not None:
            try:
                # Use a simple price change estimate from best_bid/best_ask
                price_change = (best_bid - best_ask) / max(best_ask, 0.01)
                regime = detector.update(price_change, abs(price_change) * 0.5)
                params = detector.get_params()
                regime_mult = params.min_spread_mult
            except Exception:
                pass

        spread = best_bid - best_ask
        spread_pct = spread / best_ask if best_ask > 0 else 0.0
        if spread_pct < float(effective_min_spread) / 100.0 * regime_mult:
            continue

        # Estimated cost to buy + sell + cash out. Low-fee items get a lower
        # effective cost and therefore a higher score.
        fee_estimate = float(Config.FEE_RATE + Config.WITHDRAWAL_FEE_RATE)
        if Config.COMMISSION_OPTIMIZER_ENABLED and low_fee_titles is not None and title in low_fee_titles:
            fee_estimate *= 0.70  # ~30% cheaper fee stack (e.g. 2% vs 4.5%)

        net_margin = spread_pct - fee_estimate
        if net_margin <= 0:
            continue

        volume = ask_count + bid_count
        liquidity = math.sqrt(max(volume, 1))
        # Score = expected net margin × liquidity. Items with no volume still
        # score margin × 1, but liquidity is strongly preferred.
        score = net_margin * liquidity

        # v14.6: Filler skin boost — higher demand = faster resale
        if Config.FILLER_TRACKING_ENABLED:
            try:
                from src.analytics.filler_tracker import is_filler
                if is_filler(title):
                    score *= 1.08  # +8% for filler skins (faster turnover)
            except Exception:
                pass

        # v15.8: Trend boost — items in uptrend get +10% score (LIS algorithm)
        if price_histories and title in price_histories:
            try:
                from src.analysis.algo_pack.trend_strength import trend_strength as _ts
                ts = _ts(price_histories[title])
                if ts > 0.6:
                    score *= 1.10  # +10% for uptrend
                elif ts < 0.3:
                    score *= 0.85  # -15% for downtrend
            except Exception:
                pass

        # v15.9: Bollinger Squeeze — volatility contraction = breakout imminent
        if price_histories and title in price_histories:
            try:
                from src.analysis.microstructure.volatility import (
                    bollinger_pctb,
                    bollinger_squeeze_signal,
                )
                ph = price_histories[title]
                if len(ph) >= 20:
                    squeeze = bollinger_squeeze_signal(ph, period=20, squeeze_threshold=0.02)
                    pctb = bollinger_pctb(ph, best_ask, period=20)

                    if squeeze == "squeeze":
                        # Squeeze detected — breakout imminent
                        if pctb is not None and pctb < 0.3:
                            # Price near lower band + squeeze = potential upside breakout
                            score *= 1.15  # +15% for squeeze near support
                        else:
                            score *= 1.08  # +8% for squeeze (direction unknown)
                    elif squeeze == "expanded":
                        # Bands expanded — volatility contracting expected
                        score *= 0.95  # -5% for expanded bands

                    # %B signal: oversold = boost, overbought = penalize
                    if pctb is not None:
                        if pctb < 0.0:
                            score *= 1.10  # +10% for oversold (below lower band)
                        elif pctb > 1.0:
                            score *= 0.85  # -15% for overbought (above upper band)
            except Exception:
                pass

        # v15.9: Hurst Exponent — regime strength confirmation
        if price_histories and title in price_histories:
            try:
                from src.analysis.algo_pack.regime_detector import hurst_exponent
                ph = price_histories[title]
                if len(ph) >= 40:
                    hurst = hurst_exponent(ph, max_lag=20)
                    if hurst is not None:
                        if hurst > 0.6:
                            # Strong trend — boost trend-following score
                            score *= 1.08  # +8% for trending regime
                        elif hurst < 0.4:
                            # Mean-reverting — boost reversion score
                            score *= 1.05  # +5% for mean-reversion regime
            except Exception:
                pass

        ranked.append((title, score))
    ranked.sort(key=lambda x: x[1], reverse=True)
    return ranked
