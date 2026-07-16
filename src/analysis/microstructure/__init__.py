"""
microstructure — DMarket-native financial instruments subpackage (v14.3).

All indicators powered by DMarket API data (0 oracle quota used).

Order Book Signals (obi.py):
  - Stoikov Micro-Price (OBI-adjusted fair price)
  - Multi-Level OBI (depth-weighted from listing data)
  - Queue Imbalance (bid/ask count ratio for large-tick assets)

Volume-Based Indicators (volume.py):
  - VWAP (Volume-Weighted Average Price)
  - CVD (Cumulative Volume Delta) via Lee-Ready classification
  - VPIN-lite (Volume-Synchronized Probability of Informed Trading)
  - Slippage estimator (Almgren-Chriss simplified)

Volatility & Spread (volatility.py):
  - Realized Volatility (Parkinson, standard deviation)
  - Roll's Model / Effective Spread
  - Kyle lambda / Amihud illiquidity / Adverse Selection
  - Volume Profile / POC (Point of Control)
  - Time-of-day and day-of-week seasonality

Signals (signals.py):
  - Smart Cancel/Reprice signal
  - Composite buy score (weighted combination of all signals)
"""

from src.analysis.microstructure.obi import (
    multi_level_obi,
    queue_imbalance,
    queue_imbalance_signal,
    reservation_price,
    reservation_spread,
    simple_obi,
    stoikov_micro_price,
)
from src.analysis.microstructure.signals import (
    composite_buy_score,
    smart_reprice_signal,
)
from src.analysis.microstructure.volatility import (
    adverse_selection_check,
    amihud_illiquidity,
    bollinger_bands,
    bollinger_bandwidth,
    bollinger_pctb,
    bollinger_squeeze_signal,
    classify_volatility_regime,
    day_of_week_multiplier,
    kyle_lambda,
    realized_vol_parkinson,
    realized_vol_std,
    roll_effective_spread,
    roll_signal,
    tod_multiplier,
    volume_profile_poc,
    volume_profile_value_area,
)
from src.analysis.microstructure.volume import (
    classify_trade_lee_ready,
    compute_cvd,
    compute_vpin,
    compute_vwap,
    cvd_divergence,
    estimate_slippage,
    vwap_bands,
    vwap_signal,
)

__all__ = [
    # obi
    "multi_level_obi", "queue_imbalance", "queue_imbalance_signal",
    "reservation_price", "reservation_spread", "simple_obi", "stoikov_micro_price",
    # signals
    "composite_buy_score", "smart_reprice_signal",
    # volatility
    "adverse_selection_check", "amihud_illiquidity", "bollinger_bands",
    "bollinger_bandwidth", "bollinger_pctb", "bollinger_squeeze_signal",
    "classify_volatility_regime", "day_of_week_multiplier", "kyle_lambda",
    "realized_vol_parkinson", "realized_vol_std", "roll_effective_spread",
    "roll_signal", "tod_multiplier", "volume_profile_poc", "volume_profile_value_area",
    # volume
    "classify_trade_lee_ready", "compute_cvd", "compute_vpin", "compute_vwap",
    "cvd_divergence", "estimate_slippage", "vwap_bands", "vwap_signal",
]
