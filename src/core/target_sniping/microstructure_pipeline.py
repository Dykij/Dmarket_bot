"""
microstructure_pipeline.py — Extracted microstructure filter checks.

v15.7: Extracted from filter.py._evaluate_candidate() to reduce CC from 190 → ~60.
Each function is a pure helper: reads Config, queries price_db,
imports from src.analysis.microstructure as needed.

The main entry point is run_microstructure_pipeline() which runs all
enabled checks in order and returns a MicrostructureResult.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

from src.config import Config
from src.core.target_sniping.validations import (
    check_adverse_selection,
    check_cvd_vpin,
    check_obi,
    check_roll_spread,
    check_slippage_at_risk,
    check_vol_regime,
    check_volume_profile_poc,
    check_vwap_filter,
)

logger = logging.getLogger("SnipingBot")


@dataclass
class MicrostructureResult:
    """Result of the microstructure filter pipeline."""
    passed: bool = True
    reason: str = ""
    # Signals (for composite score)
    obi_signal: float = 0.0
    vwap_signal: float = 0.0
    cvd: float = 0.0
    vpin: float = 0.0
    vol_regime: str = "medium"
    trade_records: list[dict[str, Any]] = field(default_factory=list)
    multi_obi: float = 0.0
    # v15.9: New algorithm signals
    hawkes_intensity: float = 0.0
    hawkes_activity: str = "normal"
    bollinger_squeeze: str = "normal"
    bollinger_pctb: float = 0.5
    dema_crossover: str = "neutral"
    macd_signal: str = "neutral"
    hurst_exponent: float | None = None


def run_microstructure_pipeline(
    *,
    title: str,
    base_price: float,
    best_ask: float,
    best_bid: float,
    ask_count: int,
    bid_count: int,
    sales_cache: dict[str, list[dict[str, Any]]] | None = None,
    prev_agg_prices: dict[str, Any] | None = None,
    dom_listings: list[dict[str, Any]] | None = None,
    price_history: list[float] | None = None,
) -> MicrostructureResult:
    """
    Run all enabled microstructure checks in order.

    Returns MicrostructureResult with passed=False if any check fails.
    All checks are gated by Config.STRICT_MICROSTRUCTURE_FILTERS.
    """
    result = MicrostructureResult()

    if not Config.STRICT_MICROSTRUCTURE_FILTERS:
        return result

    # 1. OBI (Order Book Imbalance)
    obi_result = check_obi(ask_count, bid_count, best_ask, best_bid)
    if not obi_result["pass"]:
        result.passed = False
        result.reason = "OBI failed"
        return result
    result.obi_signal = obi_result.get("signal", 0.0)

    # 2. Slippage-at-Risk
    sar = check_slippage_at_risk(title, base_price, best_ask, best_bid, ask_count, bid_count)
    if not sar["pass"]:
        result.passed = False
        result.reason = f"Slippage-at-Risk: {sar.get('reason', '')}"
        return result

    # 3. Queue Imbalance
    if Config.QUEUE_IMBALANCE_ENABLED and ask_count > 0:
        from src.analysis.microstructure import queue_imbalance
        qi = queue_imbalance(bid_count, ask_count)
        if qi is not None and qi < Config.QI_SELL_THRESHOLD:
            result.passed = False
            result.reason = f"Queue Imbalance: {qi:.2f} < {Config.QI_SELL_THRESHOLD}"
            return result

    # 4. Multi-Level OBI
    if Config.MULTI_LEVEL_OBI_ENABLED and ask_count > 0:
        from src.analysis.microstructure import multi_level_obi
        result.multi_obi = multi_level_obi(
            best_bid, best_ask, bid_count, ask_count,
            listings=dom_listings or [], levels=Config.MULTI_LEVEL_OBI_DEPTH,
        )
        if result.multi_obi < -0.3:
            result.passed = False
            result.reason = f"Multi-Level OBI: {result.multi_obi:.2f} < -0.3"
            return result

    # 5. OFI (Order Flow Imbalance)
    if Config.OFI_ENABLED and prev_agg_prices:
        prev = prev_agg_prices.get(title, {})
        if prev:
            prev_ask_cnt = prev.get("ask_count", 0) or 0
            prev_bid_cnt = prev.get("bid_count", 0) or 0
            curr_ask_cnt = ask_count or 0
            curr_bid_cnt = bid_count or 0
            ofi = (curr_bid_cnt - prev_bid_cnt) - (curr_ask_cnt - prev_ask_cnt)
            if ofi < Config.OFI_SELL_THRESHOLD:
                result.passed = False
                result.reason = f"OFI: {ofi} < {Config.OFI_SELL_THRESHOLD}"
                return result

    # 6. VWAP Filter
    vwap_result = check_vwap_filter(title, best_ask, sales_cache)
    if not vwap_result["pass"]:
        result.passed = False
        result.reason = "VWAP filter failed"
        return result
    result.vwap_signal = vwap_result.get("signal", 0.0)

    # 7. CVD / VPIN
    cvd_vpin_result = check_cvd_vpin(title, sales_cache)
    if not cvd_vpin_result["pass"]:
        result.passed = False
        result.reason = f"VPIN too high: {cvd_vpin_result.get('vpin', 0):.2f}"
        return result
    result.cvd = cvd_vpin_result.get("cvd", 0.0)
    result.vpin = cvd_vpin_result.get("vpin", 0.0)
    result.trade_records = cvd_vpin_result.get("trade_records", [])

    # 8. Adverse Selection (Kyle λ + Amihud)
    adverse_result = check_adverse_selection(title, result.trade_records)
    if not adverse_result["pass"]:
        result.passed = False
        result.reason = "Adverse selection too high"
        return result

    # 9. Realized Volatility Regime
    vol_result = check_vol_regime(title, result.trade_records)
    if not vol_result["pass"]:
        result.passed = False
        result.reason = f"Vol regime: {vol_result.get('regime', 'unknown')}"
        return result
    result.vol_regime = vol_result.get("regime", "medium")

    # 10. Roll's Model (effective spread)
    roll_result = check_roll_spread(title, result.trade_records, best_ask)
    if not roll_result["pass"]:
        result.passed = False
        result.reason = "Roll spread too wide"
        return result

    # 11. Volume Profile / POC
    check_volume_profile_poc(title, result.trade_records)

    # ═══════════════════════════════════════════════════════════════════
    # v15.9: NEW ALGORITHMS — Hawkes, Bollinger, DEMA, MACD, Hurst
    # ═══════════════════════════════════════════════════════════════════

    # 12. Hawkes Process — detect ажиотаж (listing clusters)
    try:
        from src.analysis.algo_pack.hawkes import (
            HawkesEstimator,
            classify_activity_level,
        )

        # Build timestamps from trade records (seconds since epoch)
        trade_timestamps: list[float] = []
        for tr in result.trade_records:
            ts = tr.get("timestamp", 0)
            if ts > 0:
                trade_timestamps.append(float(ts))

        if len(trade_timestamps) >= 3:
            hawkes = HawkesEstimator(baseline=0.01, alpha=0.5, beta=0.1)
            for ts in sorted(trade_timestamps):
                hawkes.update(ts)
            result.hawkes_intensity = hawkes.get_intensity_ratio()
            result.hawkes_activity = classify_activity_level(result.hawkes_intensity)

            # Block buying during frenzy (ажиотаж)
            if result.hawkes_activity == "frenzy":
                result.passed = False
                result.reason = (
                    f"Hawkes frenzy: intensity={result.hawkes_intensity:.1f}x "
                    f"(>{3.0}x threshold)"
                )
                return result
    except Exception as e:
        logger.debug(f"[Hawkes] Skipped: {e}")

    # 13. Bollinger Bands — squeeze detection + %B
    if price_history and len(price_history) >= 20:
        try:
            from src.analysis.microstructure.volatility import (
                bollinger_pctb,
                bollinger_squeeze_signal,
            )

            result.bollinger_squeeze = bollinger_squeeze_signal(
                price_history, period=20, squeeze_threshold=0.02
            )
            result.bollinger_pctb = bollinger_pctb(
                price_history, base_price, period=20
            ) or 0.5

            # Block buying if price is above upper Bollinger Band (overbought)
            if result.bollinger_pctb > 1.0 and result.bollinger_squeeze != "squeeze":
                result.passed = False
                result.reason = (
                    f"Bollinger overbought: %B={result.bollinger_pctb:.2f} > 1.0"
                )
                return result
        except Exception as e:
            logger.debug(f"[Bollinger] Skipped: {e}")

    # 14. DEMA Crossover — momentum direction
    if price_history and len(price_history) >= 22:
        try:
            from src.analysis.algo_pack.ewma import ema_crossover

            result.dema_crossover = ema_crossover(
                price_history, fast_period=9, slow_period=21
            )

            # Block buying on bearish crossover (momentum against us)
            if result.dema_crossover == "bearish":
                result.passed = False
                result.reason = "DEMA bearish crossover"
                return result
        except Exception as e:
            logger.debug(f"[DEMA] Skipped: {e}")

    # 15. MACD — momentum confirmation
    if price_history and len(price_history) >= 27:
        try:
            from src.analysis.algo_pack.ewma import macd_signal as _macd_sig

            result.macd_signal = _macd_sig(price_history)

            # Block buying on bearish MACD
            if result.macd_signal == "bearish":
                result.passed = False
                result.reason = "MACD bearish signal"
                return result
        except Exception as e:
            logger.debug(f"[MACD] Skipped: {e}")

    # 16. Hurst Exponent — regime strength (informational, no blocking)
    if price_history and len(price_history) >= 40:
        try:
            from src.analysis.algo_pack.regime_detector import hurst_exponent

            result.hurst_exponent = hurst_exponent(price_history, max_lag=20)
        except Exception as e:
            logger.debug(f"[Hurst] Skipped: {e}")

    return result
