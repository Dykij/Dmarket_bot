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
import os
from dataclasses import dataclass, field
from typing import Any

from src.config import Config
from src.db.price_history import price_db
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

    return result
