"""Local microstructure instrument smoke tests (no API calls)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tests.sandbox_comprehensive.common import log, log_err, log_ok

if TYPE_CHECKING:
    from tests.sandbox_comprehensive.common import SandboxMetrics


def _run_assert(metrics: "SandboxMetrics", condition: bool, label: str) -> None:
    """Track assertion result."""
    if condition:
        metrics.local_tests_passed += 1
        log_ok(label)
    else:
        metrics.local_tests_failed += 1
        log_err(label)


def run_local_tests(metrics: "SandboxMetrics") -> None:
    """Run smoke tests for microstructure instruments."""
    log("\n[LOCAL] Microstructure instrument smoke tests")

    # v14.0 / v14.1 instruments
    from src.analysis.microstructure import (
        reservation_price,
        compute_vwap,
        vwap_signal,
        estimate_slippage,
        compute_cvd,
        cvd_divergence,
        compute_vpin,
        tod_multiplier,
    )

    r1 = reservation_price(10.0, 3, 0, 3, 0.4, 0.3, 7)
    _run_assert(metrics, r1 < 10.0, f"A-S reservation price < mid ({r1:.4f})")

    r2 = reservation_price(10.0, 0, 0, 3, 0.4, 0.3, 7)
    _run_assert(metrics, abs(r2 - 10.0) < 0.01, f"A-S neutral inventory ({r2:.4f})")

    sales = [{"price": 1.0}, {"price": 1.1}, {"price": 0.95}, {"price": 1.05}]
    vwap, vol, _ = compute_vwap(sales)
    sig = vwap_signal(0.85, sales, 0.90)
    _run_assert(metrics, vwap > 0 and vol > 0, f"VWAP computed ({vwap:.4f})")
    _run_assert(metrics, sig is not None, "VWAP signal generated")

    slip = estimate_slippage(10.0, 1, 500, 10.0, 9.5)
    _run_assert(metrics, slip < 0.01, f"Slippage small ({slip:.6f})")

    cvd = compute_cvd(sales, prev_mid=1.0)
    div = cvd_divergence(10.0, -0.02)
    _run_assert(metrics, div == "bullish", f"CVD divergence bullish ({cvd:.4f})")

    vpin = compute_vpin(sales * 5, n_buckets=4)
    _run_assert(metrics, vpin is not None, f"VPIN computed ({vpin})")

    tod = tod_multiplier(4, 10, 0.85, 1.0)
    _run_assert(metrics, 0 < tod < 2, f"ToD multiplier sane ({tod:.2f})")

    # v14.3 instruments
    from src.analysis.microstructure import (
        stoikov_micro_price,
        simple_obi,
        multi_level_obi,
        queue_imbalance,
        queue_imbalance_signal,
        kyle_lambda,
        amihud_illiquidity,
        adverse_selection_check,
        realized_vol_std,
        realized_vol_parkinson,
        classify_volatility_regime,
        roll_effective_spread,
        volume_profile_poc,
        smart_reprice_signal,
        composite_buy_score,
    )

    mp = stoikov_micro_price(10.0, 1.0, 0.5)
    _run_assert(metrics, mp > 10.0, f"Stoikov MP buyer pressure ({mp:.4f})")

    obi = simple_obi(2.0, 1.5, 10, 5)
    _run_assert(metrics, obi > 0.4, f"Simple OBI positive ({obi:.4f})")

    listings_fake = [
        {"price": {"USD": 155}},
        {"price": {"USD": 160}},
        {"price": {"USD": 170}},
    ]
    ml_obi = multi_level_obi(2.0, 1.5, 15, 3, listings=listings_fake, levels=3)
    _run_assert(metrics, -1.0 <= ml_obi <= 1.0, f"Multi-level OBI in range ({ml_obi:.4f})")

    qi = queue_imbalance(20, 10)
    _run_assert(metrics, qi == 2.0, f"Queue imbalance ({qi})")

    qi_sig = queue_imbalance_signal(5, 20)
    _run_assert(metrics, qi_sig == "sell", f"Queue imbalance signal ({qi_sig})")

    lam = kyle_lambda([{"price": 10.0}, {"price": 12.0}, {"price": 9.0}, {"price": 11.0}])
    _run_assert(metrics, lam is not None and lam > 0, f"Kyle lambda positive ({lam})")

    illiq = amihud_illiquidity([{"price": 10.0}, {"price": 10.01}, {"price": 10.0}] * 2)
    _run_assert(metrics, illiq is not None, f"Amihud illiquidity ({illiq})")

    stable = [{"price": 10.0}, {"price": 10.005}, {"price": 10.0}] * 4
    ok, reason = adverse_selection_check(stable)
    _run_assert(metrics, ok, f"Adverse selection pass ({reason})")

    vol_samples = [{"price": 10.0}, {"price": 10.5}, {"price": 9.5}, {"price": 10.2}, {"price": 9.8}] * 3
    rv_std = realized_vol_std(vol_samples)
    rv_pk = realized_vol_parkinson(vol_samples)
    _run_assert(metrics, rv_std and rv_std > 0, f"Realized vol std ({rv_std})")
    _run_assert(metrics, rv_pk and rv_pk > 0, f"Realized vol parkinson ({rv_pk})")

    regime = classify_volatility_regime(rv_pk)
    _run_assert(metrics, regime in ("low", "normal", "high"), f"Vol regime ({regime})")

    roll = roll_effective_spread([10.0, 10.01, 10.0, 10.01])
    _run_assert(metrics, roll is not None and roll >= 0, f"Roll effective spread ({roll})")

    poc = volume_profile_poc(vol_samples)
    _run_assert(metrics, poc > 0, f"Volume profile POC ({poc})")

    action, _new_price = smart_reprice_signal(10, 5, 8, 6, 10.0, 9.5, 10.5)
    _run_assert(metrics, action in ("cancel", "drop", "keep", "boost"), f"Smart reprice ({action})")

    score, _components = composite_buy_score(
        best_ask=10.0, best_bid=10.5, ask_count=5, bid_count=10,
        obi=0.5, ofi=1, cvd=1.0, vpin_val=0.2, vwap_discount=0.05,
        adverse_pass=True, vol_regime="normal", kyle_lam=1.0,
    )
    _run_assert(metrics, 0 <= score <= 1, f"Composite buy score ({score:.4f})")
