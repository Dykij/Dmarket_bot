"""
microstructure — DMarket-native financial instruments subpackage (v14.3).

All indicators powered by DMarket API data (0 cs2cap quota used).

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
    stoikov_micro_price,
    simple_obi,
    multi_level_obi,
    queue_imbalance,
    queue_imbalance_signal,
    reservation_price,
    reservation_spread,
)

from src.analysis.microstructure.volume import (
    compute_vwap,
    vwap_signal,
    vwap_bands,
    estimate_slippage,
    classify_trade_lee_ready,
    compute_cvd,
    cvd_divergence,
    compute_vpin,
)

from src.analysis.microstructure.volatility import (
    tod_multiplier,
    day_of_week_multiplier,
    kyle_lambda,
    amihud_illiquidity,
    adverse_selection_check,
    realized_vol_std,
    realized_vol_parkinson,
    classify_volatility_regime,
    roll_effective_spread,
    roll_signal,
    volume_profile_poc,
    volume_profile_value_area,
)

from src.analysis.microstructure.signals import (
    smart_reprice_signal,
    composite_buy_score,
)
