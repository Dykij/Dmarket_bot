"""
microstructure.py — backwards-compatible shim (v14.3).

This module is now a subpackage at src/analysis/microstructure/.
Existing imports like `from src.analysis.microstructure import stoikov_micro_price`
continue to work via this shim.
"""

from src.analysis.microstructure import (
    adverse_selection_check,
    amihud_illiquidity,
    classify_trade_lee_ready,
    classify_volatility_regime,
    composite_buy_score,
    compute_cvd,
    compute_vpin,
    compute_vwap,
    cvd_divergence,
    day_of_week_multiplier,
    estimate_slippage,
    kyle_lambda,
    multi_level_obi,
    queue_imbalance,
    queue_imbalance_signal,
    realized_vol_parkinson,
    realized_vol_std,
    reservation_price,
    reservation_spread,
    roll_effective_spread,
    roll_signal,
    simple_obi,
    smart_reprice_signal,
    stoikov_micro_price,
    tod_multiplier,
    volume_profile_poc,
    volume_profile_value_area,
    vwap_bands,
    vwap_signal,
)

__all__ = [
    "adverse_selection_check", "amihud_illiquidity",
    "classify_trade_lee_ready", "classify_volatility_regime",
    "composite_buy_score", "compute_cvd", "compute_vpin", "compute_vwap",
    "cvd_divergence", "day_of_week_multiplier", "estimate_slippage",
    "kyle_lambda", "multi_level_obi", "queue_imbalance", "queue_imbalance_signal",
    "realized_vol_parkinson", "realized_vol_std",
    "reservation_price", "reservation_spread",
    "roll_effective_spread", "roll_signal", "simple_obi", "smart_reprice_signal",
    "stoikov_micro_price", "tod_multiplier",
    "volume_profile_poc", "volume_profile_value_area",
    "vwap_bands", "vwap_signal",
]
