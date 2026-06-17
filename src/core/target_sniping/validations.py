"""
validations.py — Standalone microstructure validation checks.

Extracted from _FilterMixin._evaluate_candidate (filter.py).
Each function is a pure helper: reads Config, queries price_db,
imports from src.analysis.microstructure as needed.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.config import Config
from src.db.price_history import price_db


def check_bait_detection(title: str, base_price: float) -> dict:
    """Detect bait/spoof listings with rapidly changing prices."""
    if not Config.BAIT_DETECTION_ENABLED:
        return {"pass": True}
    bait_prices = price_db.get_recent_prices(title, days=0.0035)
    if bait_prices and len(bait_prices) > 1:
        changes = 0
        prev_p = None
        for p, _ in bait_prices:
            if prev_p is not None and abs(p - prev_p) > 0.01:
                changes += 1
            prev_p = p
        if changes > Config.BAIT_MAX_PRICE_CHANGES:
            return {"pass": False}
    return {"pass": True}


def check_obi(
    ask_cnt: int, bid_cnt: int, best_ask: float, best_bid: float
) -> dict:
    """Order Book Imbalance gate: bid_volume / ask_volume pressure ratio."""
    obi_signal = 0.0
    if not Config.OBI_ENABLED or ask_cnt <= 0 or bid_cnt <= 0:
        return {"pass": True, "signal": obi_signal}
    safe_bid = best_bid or 0.01
    safe_ask = best_ask or 0.01
    bid_volume = safe_bid * bid_cnt
    ask_volume = safe_ask * ask_cnt
    obi_ratio = bid_volume / ask_volume if ask_volume > 0 else 1.0
    if obi_ratio < Config.OBI_MIN_RATIO:
        return {"pass": False, "signal": obi_ratio}
    return {"pass": True, "signal": obi_ratio}


def check_vwap_filter(
    title: str,
    best_ask: float,
    sales_cache: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> dict:
    """VWAP undervaluation check: skip if best_ask sits above VWAP."""
    vwap_signal_val = 0.0
    if not Config.VWAP_FILTER_ENABLED:
        return {"pass": True, "signal": vwap_signal_val}
    item_sales = price_db.get_trade_history(title, days=30, limit=200)
    if not item_sales:
        item_sales = (sales_cache or {}).get(title, [])
    if not item_sales:
        return {"pass": True, "signal": vwap_signal_val}
    from src.analysis.microstructure import compute_vwap, vwap_signal

    vwap_signal_val_raw = vwap_signal(
        best_ask, item_sales, Config.VWAP_DISCOUNT_THRESHOLD
    )
    if vwap_signal_val_raw is None and best_ask > 0:
        vwap, _, _ = compute_vwap(item_sales)
        if vwap > 0 and best_ask > vwap:
            return {"pass": False, "signal": 0.0}
    elif vwap_signal_val_raw is not None:
        vwap_signal_val = vwap_signal_val_raw
    return {"pass": True, "signal": vwap_signal_val}


def check_cvd_vpin(
    title: str,
    sales_cache: Optional[Dict[str, List[Dict[str, Any]]]] = None,
) -> dict:
    """CVD / VPIN signals: cumulative volume delta and informed-trading probability."""
    cvd_val = 0.0
    vpin_val = 0.0
    trade_records = price_db.get_trade_history(title, days=30, limit=200)
    if not trade_records:
        trade_records = (sales_cache or {}).get(title, [])
    if trade_records and len(trade_records) >= 3:
        from src.analysis.microstructure import compute_cvd, compute_vpin

        cvd_val = compute_cvd(trade_records)
        if Config.VPIN_ENABLED:
            vpin_val = compute_vpin(trade_records, Config.VPIN_BUCKETS) or 0.0
            if vpin_val > Config.VPIN_THRESHOLD:
                return {
                    "pass": False,
                    "cvd": cvd_val,
                    "vpin": vpin_val,
                    "trade_records": trade_records,
                }
    return {
        "pass": True,
        "cvd": cvd_val,
        "vpin": vpin_val,
        "trade_records": trade_records,
    }


def check_adverse_selection(
    title: str,
    trade_records: List[Dict[str, Any]],
) -> dict:
    """Kyle λ + Amihud adverse-selection check."""
    if (
        not Config.ADVERSER_SELECTION_ENABLED
        or not trade_records
        or len(trade_records) < 3
    ):
        return {"pass": True}
    from src.analysis.microstructure import adverse_selection_check

    adverse_pass, as_reason = adverse_selection_check(
        trade_records,
        max_kyle=Config.KYLE_LAMBDA_MAX,
        max_amihud=Config.AMIHUD_ILLIQUIDITY_MAX,
    )
    if not adverse_pass:
        return {"pass": False, "reason": as_reason}
    return {"pass": True}


def check_vol_regime(
    title: str,
    trade_records: List[Dict[str, Any]],
) -> dict:
    """Realized volatility regime classification (Parkinson)."""
    vol_regime = "medium"
    if (
        not Config.VOL_REGIME_ENABLED
        or not trade_records
        or len(trade_records) < 5
    ):
        return {"pass": True, "regime": vol_regime, "annual_vol": 0.0}
    from src.analysis.microstructure import (
        realized_vol_parkinson,
        classify_volatility_regime,
    )

    annual_vol = realized_vol_parkinson(trade_records) or 0.0
    vol_regime = classify_volatility_regime(annual_vol)
    if vol_regime == "high" and annual_vol > Config.VOL_REGIME_HIGH_THRESHOLD:
        return {"pass": False, "regime": vol_regime, "annual_vol": annual_vol}
    return {"pass": True, "regime": vol_regime, "annual_vol": annual_vol}


def check_roll_spread(
    title: str,
    trade_records: List[Dict[str, Any]],
    best_ask: float,
) -> dict:
    """Roll's effective spread model check."""
    if (
        not Config.ROLL_MODEL_ENABLED
        or not trade_records
        or len(trade_records) < 4
    ):
        return {"pass": True, "signal": None}
    from src.analysis.microstructure import roll_signal

    prices_roll = [r["price"] for r in trade_records if r.get("price", 0) > 0]
    roll_sig = roll_signal(prices_roll, best_ask)
    if roll_sig == "expensive":
        return {"pass": False, "signal": roll_sig}
    return {"pass": True, "signal": roll_sig}


def check_volume_profile_poc(
    title: str,
    trade_records: List[Dict[str, Any]],
) -> float:
    """Volume Profile Point of Control (price magnet)."""
    if (
        not Config.VOLUME_PROFILE_ENABLED
        or not trade_records
        or len(trade_records) < 5
    ):
        return 0.0
    from src.analysis.microstructure import volume_profile_poc

    return volume_profile_poc(trade_records, Config.VP_NUM_BUCKETS) or 0.0


def check_slippage(
    ask_cnt: int,
    bid_cnt: int,
    base_price: float,
    best_ask: float,
    best_bid: float,
) -> float:
    """Estimate expected market-impact slippage (returns percentage points)."""
    if not Config.SLIPPAGE_GATE_ENABLED:
        return 0.0
    from src.analysis.microstructure import estimate_slippage

    daily_vol = (ask_cnt + bid_cnt) * 10
    expected_slippage = estimate_slippage(
        buy_price=base_price,
        order_qty=1,
        daily_volume=max(daily_vol, 1),
        best_ask=best_ask,
        best_bid=best_bid,
        temp_impact_bps=Config.SLIPPAGE_TEMP_IMPACT_BPS,
        perm_impact_bps=Config.SLIPPAGE_PERM_IMPACT_BPS,
    )
    return expected_slippage * 100.0


def check_tod_adjustment() -> float:
    """Time-of-day / day-of-week margin multiplier."""
    if not Config.TOD_ENABLED:
        return 1.0
    from src.analysis.microstructure import tod_multiplier, day_of_week_multiplier

    tod_m = tod_multiplier(
        Config.TOD_NIGHT_START_UTC,
        Config.TOD_NIGHT_END_UTC,
        Config.TOD_NIGHT_MULTIPLIER,
        Config.TOD_DAY_MULTIPLIER,
    )
    if Config.TOD_WEEKEND_ENABLED:
        tod_m *= day_of_week_multiplier()
    return tod_m


def evaluate_cross_market_arb(
    title: str,
    best_ask: float,
    cs_bids: Optional[Dict[str, Any]] = None,
) -> dict:
    """Cross-market arbitrage check (CS2Cap provider bids vs DMarket ask).

    Returns {"provider": str|None, "bid": float, "is_viable": bool}
    """
    logger = logging.getLogger("SnipingBot")
    provider = None
    bid = 0.0
    is_viable = False

    if not (Config.CROSS_MARKET_ENABLED and cs_bids):
        return {"provider": provider, "bid": bid, "is_viable": is_viable}

    bid_snap = cs_bids.get(title)
    if bid_snap is not None and getattr(bid_snap, "has_data", False):
        provider_bids = getattr(bid_snap, "provider_bids", {}) or {}
        if provider_bids:
            provider, bid = max(provider_bids.items(), key=lambda kv: kv[1])
            cm_threshold = best_ask * (1 + Config.INTRA_MIN_SPREAD_PCT / 100.0)
            if best_ask > 0 and bid > cm_threshold:
                is_viable = True
                logger.info(
                    f"Cross-market arb HIT: {title} "
                    f"DM_ask=${best_ask:.2f} < "
                    f"{provider}_bid=${bid:.2f} "
                    f"(+{((bid / best_ask) - 1) * 100:.1f}%)"
                )
            else:
                if best_ask > 0:
                    logger.debug(
                        f"Cross-market miss: {title} "
                        f"DM_ask=${best_ask:.2f} >= "
                        f"{provider}_bid=${bid:.2f} "
                        f"(threshold=${cm_threshold:.2f})"
                    )
                provider = None
                bid = 0.0
    elif cs_bids:
        logger.debug(
            f"Cross-market: {title} not in cs_bids "
            f"(has_data={getattr(bid_snap, 'has_data', 'N/A')})"
        )

    return {"provider": provider, "bid": bid, "is_viable": is_viable}


def compute_microstructure_scores(
    title: str,
    best_ask: float,
    best_bid: float,
    ask_count: int,
    bid_count: int,
    trade_records: list,
    vwap_signal_val: float,
    cvd_val: float,
    vpin_val: float,
    adverse_pass: bool,
    vol_regime: str,
    prev_agg_prices: Optional[Dict[str, Dict[str, Any]]] = None,
) -> dict:
    """Composite buy score from microstructure signals.

    Returns {"composite_score": float, "components": dict}
    """
    composite_score = 0.0
    composite_components: dict = {}

    if not (Config.COMPOSITE_SCORE_ENABLED and len(trade_records) >= 3):
        return {"composite_score": composite_score, "components": composite_components}

    from src.analysis.microstructure import (
        composite_buy_score,
        compute_cvd as _cvd_local,
        kyle_lambda,
        simple_obi,
    )

    _s_obi = simple_obi(best_bid, best_ask, bid_count, ask_count)
    _s_ofi = 0
    if Config.OFI_ENABLED and prev_agg_prices:
        prev = prev_agg_prices.get(title, {})
        if prev:
            _s_ofi = (bid_count - (prev.get("bid_count", 0) or 0)) - \
                     (ask_count - (prev.get("ask_count", 0) or 0))
    _s_cvd = cvd_val if cvd_val else _cvd_local(trade_records)
    _s_vwap_disc = vwap_signal_val if vwap_signal_val else 0.0
    _kyle = kyle_lambda(trade_records)
    composite_score, composite_components = composite_buy_score(
        best_ask=best_ask,
        best_bid=best_bid,
        ask_count=ask_count,
        bid_count=bid_count,
        obi=_s_obi,
        ofi=_s_ofi,
        cvd=_s_cvd,
        vpin_val=vpin_val,
        vwap_discount=_s_vwap_disc,
        adverse_pass=adverse_pass,
        vol_regime=vol_regime,
        kyle_lam=_kyle,
    )

    return {"composite_score": composite_score, "components": composite_components}


def evaluate_fee_slippage_tod(
    title: str,
    base_price: float,
    best_ask: float,
    best_bid: float,
    ask_count: int,
    bid_count: int,
    fee_rate: float,
    current_margin: float,
    list_price: float,
    is_sandbox: bool = False,
    item_id: Optional[str] = None,
) -> dict:
    """Fee calculation with slippage, TOD adjustment, and arbitrage profit validation.

    Returns {"pass": bool, "reason": str|None}
    """
    from src.risk.price_validator import PriceValidationError, validate_arbitrage_profit

    logger = logging.getLogger("SnipingBot")

    total_fee = fee_rate + Config.WITHDRAWAL_FEE_RATE
    spread_ratio = (best_bid - best_ask) / best_ask if best_ask > 0 else 0
    min_spread_for_fee = total_fee * 2.0 + 0.03

    if spread_ratio < min_spread_for_fee:
        if is_sandbox:
            price_db.log_decision(
                title,
                "skip",
                "Spread too thin for fee",
                f"spread={spread_ratio:.1%} need>{min_spread_for_fee:.1%} fee={total_fee:.1%}",
            )
        return {"pass": False, "reason": "Spread too thin for fee"}

    effective_margin = current_margin
    effective_margin += check_slippage(ask_count, bid_count, base_price, best_ask, best_bid)
    effective_margin *= check_tod_adjustment()

    try:
        validate_arbitrage_profit(
            buy_price=base_price,
            expected_sell_price=list_price,
            fee_markup=total_fee,
            min_profit_margin=effective_margin,
            lock_days=7,
        )
    except PriceValidationError as e:
        if is_sandbox:
            price_db.log_decision(title, "skip", "Low profit", str(e))
        return {"pass": False, "reason": str(e)}

    return {"pass": True, "reason": None}
