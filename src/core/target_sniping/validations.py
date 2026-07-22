"""
validations.py — Standalone microstructure validation checks.

Extracted from _FilterMixin._evaluate_candidate (filter.py).
Each function is a pure helper: reads Config, queries price_db,
imports from src.analysis.microstructure as needed.
"""

from __future__ import annotations

import logging
from typing import Any

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
    safe_bid = float(best_bid) if best_bid and float(best_bid) > 0 else 0.01
    safe_ask = float(best_ask) if best_ask and float(best_ask) > 0 else 0.01
    bid_volume = safe_bid * bid_cnt
    ask_volume = safe_ask * ask_cnt
    obi_ratio = bid_volume / ask_volume if ask_volume > 0 else 1.0
    obi_min = float(Config.OBI_MIN_RATIO)
    if obi_ratio < obi_min:
        return {"pass": False, "signal": obi_ratio}
    return {"pass": True, "signal": obi_ratio}


def check_vwap_filter(
    title: str,
    best_ask: float,
    sales_cache: dict[str, list[dict[str, Any]]] | None = None,
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
    sales_cache: dict[str, list[dict[str, Any]]] | None = None,
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
    trade_records: list[dict[str, Any]],
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
    trade_records: list[dict[str, Any]],
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
        classify_volatility_regime,
        realized_vol_parkinson,
    )

    annual_vol = realized_vol_parkinson(trade_records) or 0.0
    vol_regime = classify_volatility_regime(annual_vol)
    if vol_regime == "high" and annual_vol > Config.VOL_REGIME_HIGH_THRESHOLD:
        return {"pass": False, "regime": vol_regime, "annual_vol": annual_vol}
    return {"pass": True, "regime": vol_regime, "annual_vol": annual_vol}


def check_roll_spread(
    title: str,
    trade_records: list[dict[str, Any]],
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
    trade_records: list[dict[str, Any]],
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

    daily_vol = (ask_cnt + bid_cnt) * (24 * 3600 // Config.SCAN_INTERVAL)
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
    if not Config.TIME_OF_DAY_ENABLED:
        return 1.0
    from src.analysis.microstructure import day_of_week_multiplier, tod_multiplier

    tod_m = tod_multiplier(
        Config.TIME_OF_DAY_NIGHT_START_UTC,
        Config.TIME_OF_DAY_NIGHT_END_UTC,
        Config.TIME_OF_DAY_NIGHT_MULTIPLIER,
        Config.TIME_OF_DAY_DAY_MULTIPLIER,
    )
    if Config.TIME_OF_DAY_WEEKEND_ENABLED:
        tod_m *= day_of_week_multiplier()
    return tod_m


def evaluate_cross_market_arb(
    title: str,
    best_ask: float,
    cs_bids: dict[str, Any] | None = None,
) -> dict:
    """Cross-market arbitrage check (oracle provider bids vs DMarket ask).

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
            # v14.8: fee-aware cross-market gate.
            # The external bid must cover DMarket ask + DMarket sell fee +
            # destination marketplace fee + withdrawal cost + target margin.
            if Config.CROSS_MARKET_FEE_AWARE:
                cm_threshold = best_ask * (
                    1
                    + Config.FEE_RATE
                    + Config.CROSS_MARKET_DESTINATION_FEE
                    + Config.WITHDRAWAL_FEE_RATE
                    + Config.INTRA_MIN_SPREAD_PCT / 100.0
                )
            else:
                cm_threshold = best_ask * (1 + Config.INTRA_MIN_SPREAD_PCT / 100.0)
            if best_ask > 0 and bid > cm_threshold:
                is_viable = True
                logger.info(
                    f"Cross-market arb HIT: {title} "
                    f"DM_ask=${best_ask:.2f} < "
                    f"{provider}_bid=${bid:.2f} "
                    f"(+{((bid / best_ask) - 1) * 100:.1f}%, "
                    f"fee-aware threshold=${cm_threshold:.2f})"
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
    prev_agg_prices: dict[str, dict[str, Any]] | None = None,
    # v15.9: New algorithm signals
    hawkes_activity: str = "normal",
    bollinger_squeeze: str = "normal",
    bollinger_pctb: float = 0.5,
    dema_crossover: str = "neutral",
    macd_signal_val: str = "neutral",
    hurst_exponent: float | None = None,
    hmm_regime: str = "",
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
        kyle_lambda,
        simple_obi,
    )
    from src.analysis.microstructure import (
        compute_cvd as _cvd_local,
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
        # v15.9: New algorithm signals
        hawkes_activity=hawkes_activity,
        bollinger_squeeze=bollinger_squeeze,
        bollinger_pctb=bollinger_pctb,
        dema_crossover=dema_crossover,
        macd_signal_val=macd_signal_val,
        hurst_exponent=hurst_exponent,
        hmm_regime=hmm_regime,
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
    item_id: str | None = None,
    cs_ask_price: float | None = None,
) -> dict:
    """Fee calculation with slippage, TOD adjustment, and arbitrage profit validation.

    Supports both intra-DMarket spread and cross-market underpriced opportunities.
    Returns {"pass": bool, "reason": str|None}
    """
    from src.risk.price_validator import PriceValidationError, validate_arbitrage_profit

    # v14.8: fee-aware minimum spread.
    # Intra-DMarket arbitrage must cover the sell fee, a realistic withdrawal
    # cost, and the target profit margin. No double-counting of buyer fees:
    # DMarket does not charge the buyer on instant purchases.
    total_cost = fee_rate + Config.WITHDRAWAL_FEE_RATE
    min_spread_for_fee = total_cost + current_margin

    spread_ratio = (best_bid - best_ask) / best_ask if best_ask > 0 else 0

    # Cross-market underpriced opportunity: DMarket ask is cheaper than the
    # external market ask. We can buy on DMarket and resell at/near oracle ask.
    cs_ask_price = cs_ask_price or 0.0
    has_cross_market_discount = (
        cs_ask_price > 0
        and base_price < cs_ask_price * (1 - min_spread_for_fee)
    )

    if not has_cross_market_discount:
        if spread_ratio < min_spread_for_fee:
            if is_sandbox:
                price_db.log_decision(
                    title,
                    "skip",
                    "Spread too thin for fee",
                    f"spread={spread_ratio:.1%} need>{min_spread_for_fee:.1%} cost={total_cost:.1%}",
                )
            return {"pass": False, "reason": "Spread too thin for fee"}

        # Additional safety: require spread at least 1.3x the fee stack so a small
        # bid/ask move doesn't instantly erase the edge.
        if spread_ratio < total_cost * 1.3:
            if is_sandbox:
                price_db.log_decision(
                    title,
                    "skip",
                    "Spread/fee ratio too low",
                    f"spread={spread_ratio:.1%} cost={total_cost:.1%}",
                )
            return {"pass": False, "reason": "Spread/fee ratio too low"}

    effective_margin = current_margin
    # check_slippage returns percentage points; convert to decimal fraction
    effective_margin += check_slippage(ask_count, bid_count, base_price, best_ask, best_bid) / 100.0
    effective_margin *= check_tod_adjustment()

    try:
        validate_arbitrage_profit(
            buy_price=base_price,
            expected_sell_price=list_price,
            fee_markup=total_cost,
            min_profit_margin=effective_margin,
            lock_days=Config.TRADE_LOCK_HOURS / 24.0,
        )
    except PriceValidationError as e:
        if is_sandbox:
            price_db.log_decision(title, "skip", "Low profit", str(e))
        return {"pass": False, "reason": str(e)}

    return {"pass": True, "reason": None}


def check_slippage_at_risk(
    title: str,
    base_price: float,
    best_ask: float,
    best_bid: float,
    ask_count: int,
    bid_count: int,
    max_slippage_pct: float = 0.05,
) -> dict:
    """v15.5: Slippage-at-Risk pre-trade filter.

    Source: arXiv:2603.09164 — "Forward-looking liquidity risk framework"
    Estimates expected slippage based on order book depth and spread.
    Rejects trades where expected slippage exceeds threshold.

    Concentration penalty: if a single seller dominates the book,
    reduce confidence (higher effective slippage).
    """
    if best_ask <= 0 or best_bid <= 0:
        return {"pass": True, "slippage": 0.0}

    # Spread-based slippage estimate
    spread_pct = (best_ask - best_bid) / best_ask if best_ask > 0 else 0.0

    # Depth-based adjustment: thin book = higher slippage
    # ask_count represents number of listings at best ask
    depth_factor = 1.0
    if ask_count <= 1:
        depth_factor = 2.0  # single seller = 2x slippage risk
    elif ask_count <= 3:
        depth_factor = 1.5  # thin book
    elif ask_count <= 10:
        depth_factor = 1.0  # normal
    else:
        depth_factor = 0.8  # deep book = lower slippage

    # Concentration penalty: if bid_count / ask_count is very low,
    # the book is one-sided (sellers dominate)
    concentration = 1.0
    if bid_count > 0 and ask_count > 0:
        ratio = bid_count / ask_count
        if ratio < 0.3:
            concentration = 1.5  # heavily one-sided
        elif ratio < 0.5:
            concentration = 1.2

    estimated_slippage = spread_pct * depth_factor * concentration

    if estimated_slippage > max_slippage_pct:
        return {
            "pass": False,
            "slippage": estimated_slippage,
            "reason": (
                f"Slippage-at-Risk {estimated_slippage*100:.1f}% > "
                f"{max_slippage_pct*100:.1f}% threshold "
                f"(spread={spread_pct*100:.1f}%, depth={depth_factor:.1f}x, "
                f"conc={concentration:.1f}x, asks={ask_count}, bids={bid_count})"
            ),
        }

    return {"pass": True, "slippage": estimated_slippage}
