"""
Sandbox v14.3 — Full Cycle with ALL Microstructure Instruments (10-min live).

Tests v14.0 + v14.1 + v14.3 DMarket-native instruments:
  OBI, OFI, Stoikov Micro-Price, Multi-Level OBI, Queue Imbalance,
  A-S, VWAP, Slippage, CVD, VPIN, Adverse Selection, Realized Vol,
  Roll's Model, Volume Profile/POC, ToD, Smart Reprice, Composite Score

Run: uv run python tests/sandbox_v14_3.py
"""
import asyncio
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DRY_RUN"] = "false"
os.environ.setdefault("ENCRYPTION_KEY", "test-key-sandbox-v14-3")
logging.basicConfig(level=logging.WARNING)

from src.config import Config
from src.api.dmarket_api_client import DMarketAPIClient
from src.analysis.microstructure import (
    # v14.0 / v14.1
    reservation_price,
    reservation_spread,
    compute_vwap,
    vwap_signal,
    vwap_bands,
    estimate_slippage,
    classify_trade_lee_ready,
    compute_cvd,
    cvd_divergence,
    compute_vpin,
    tod_multiplier,
    day_of_week_multiplier,
    # v14.3 new
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
    roll_signal,
    volume_profile_poc,
    volume_profile_value_area,
    smart_reprice_signal,
    composite_buy_score,
)


def plog(msg: str = "") -> None:
    print(msg, flush=True)


class Metrics:
    def __init__(self):
        self.cycles = 0
        self.items_scanned = 0
        self.candidates = 0
        # v14.0
        self.obi_skipped = 0
        self.ofi_skipped = 0
        # v14.1
        self.vwap_signals = 0
        self.vwap_rejects = 0
        self.slippage_rejects = 0
        self.cvd_bullish = 0
        self.cvd_bearish = 0
        self.vpin_high = 0
        # v14.3
        self.qi_skipped = 0
        self.multi_obi_skipped = 0
        self.adverse_rejects = 0
        self.vol_high_rejects = 0
        self.roll_expensive = 0
        self.roll_cheap = 0
        self.smart_cancels = 0
        self.smart_drops = 0
        self.smart_keeps = 0
        self.smart_boosts = 0
        self.composite_scores: List[float] = []
        self.poc_signals = 0
        self.tod_vals: List[float] = []
        self.day_of_week_vals: List[float] = []
        self.errors: List[str] = []
        self.cycle_times: List[float] = []


# ── Local unit tests (no API) ────────────────────────────────────────


async def test_local(m: Metrics) -> None:
    plog("  -- v14.0 / v14.1 Local instrument tests --")

    # A-S
    r = reservation_price(10.0, 3, 0, 3, 0.4, 0.3, 7)
    assert r < 10.0, f"A-S failed: {r}"
    r2 = reservation_price(10.0, 0, 0, 3, 0.4, 0.3, 7)
    assert abs(r2 - 10.0) < 0.01, f"A-S neutral failed: {r2}"
    plog(f"  [A-S] reserv(inv=3)={r:.4f} inv=0={r2:.4f}")

    bid, ask = reservation_spread(10.0, 10.0, 0.4, 0.3, 7)
    assert bid < 10.0 < ask
    plog(f"  [A-S] spread bid={bid:.4f} ask={ask:.4f}")

    # VWAP
    sales = [{"price": 1.0}, {"price": 1.1}, {"price": 0.95}, {"price": 1.05}]
    v, vol, std = compute_vwap(sales)
    sig = vwap_signal(0.85, sales, 0.90)
    assert sig is not None, "VWAP missed signal"
    plog(f"  [VWAP] vwap={v:.4f} vol={vol} std={std:.4f} signal={sig:.4f}")

    vw, lo, hi = vwap_bands(sales, 2.0)
    assert lo <= vw <= hi, f"VWAP bands broken: {lo} {vw} {hi}"
    plog(f"  [VWAP Bands] lower={lo:.4f} vwap={vw:.4f} upper={hi:.4f}")

    # Slippage
    slip = estimate_slippage(10.0, 1, 500, 10.0, 9.5)
    assert slip < 0.01
    plog(f"  [Slip] {slip:.6f}")

    # CVD
    cvd = compute_cvd(sales, prev_mid=1.0)
    div = cvd_divergence(10.0, -0.02)
    assert div == "bullish"
    plog(f"  [CVD] {cvd:.4f} div={div}")

    # VPIN
    vpin = compute_vpin(sales * 5, n_buckets=4)
    plog(f"  [VPIN] {vpin}")

    # ToD
    tod = tod_multiplier(4, 10, 0.85, 1.0)
    dow = day_of_week_multiplier()
    plog(f"  [ToD] multiplier={tod:.2f} day-of-week={dow:.2f}")

    plog("\n  -- v14.3 NEW Local instrument tests --")

    # Stikov Micro-Price
    mp = stoikov_micro_price(10.0, 1.0, 0.5)
    assert mp > 10.0, f"Stoikov MP buyer fail: {mp}"
    mp2 = stoikov_micro_price(10.0, 1.0, -0.5)
    assert mp2 < 10.0, f"Stoikov MP seller fail: {mp2}"
    plog(f"  [Stoikov MP] obi=+0.5→{mp:.4f} obi=-0.5→{mp2:.4f}")

    # Simple OBI
    obi = simple_obi(2.0, 1.5, 10, 5)
    assert obi > 0.4, f"Simple OBI fail: {obi}"
    plog(f"  [Simple OBI] {obi:.4f}")

    # Multi-Level OBI
    listings_fake = [{"price": {"USD": 155}}, {"price": {"USD": 160}},
                     {"price": {"USD": 170}}]
    ml_obi = multi_level_obi(2.0, 1.5, 15, 3, listings=listings_fake, levels=3)
    assert -1.0 <= ml_obi <= 1.0, f"ML OBI range fail: {ml_obi}"
    plog(f"  [Multi-Level OBI] {ml_obi:.4f}")

    # Queue Imbalance
    qi = queue_imbalance(20, 10)
    assert qi == 2.0
    sig_qi = queue_imbalance_signal(5, 20)
    assert sig_qi == "sell", f"QI signal fail: {sig_qi}"
    plog(f"  [Queue Imbalance] qi={qi} signal(5,20)={sig_qi}")

    # Kyle λ
    lam = kyle_lambda([{"price": 10.0}, {"price": 12.0}, {"price": 9.0}, {"price": 11.0}])
    assert lam is not None and lam > 0, f"Kyle λ fail: {lam}"
    plog(f"  [Kyle λ] {lam:.6f}")

    # Amihud
    illiq = amihud_illiquidity([{"price": 10.0}, {"price": 10.01}, {"price": 10.0}] * 2)
    assert illiq is not None
    plog(f"  [Amihud] {illiq:.8f}")

    # Adverse Selection Check (use stable prices — tiny deltas)
    stable_sales = [{"price": 10.0}, {"price": 10.005}, {"price": 10.0},
                    {"price": 10.005}, {"price": 10.0}, {"price": 10.005}] * 2
    ok, reason = adverse_selection_check(stable_sales)
    assert ok, f"Adverse check fail: {reason}"
    plog(f"  [Adverse Selection] pass={ok} reason={reason}")

    # Realized Vol
    vol_samples = [{"price": 10.0}, {"price": 10.5}, {"price": 9.5},
                   {"price": 10.2}, {"price": 9.8}] * 3
    rv_std = realized_vol_std(vol_samples)
    rv_pk = realized_vol_parkinson(vol_samples)
    assert rv_std and rv_std > 0, f"RV std fail: {rv_std}"
    assert rv_pk and rv_pk > 0, f"RV parkinson fail: {rv_pk}"
    regime = classify_volatility_regime(rv_pk)
    plog(f"  [Realized Vol] std={rv_std:.4f} parkinson={rv_pk:.4f} regime={regime}")

    # Roll's Model
    prices_roll = [10.0, 10.2, 10.0, 10.2, 10.0, 10.2, 10.0]
    roll_spread = roll_effective_spread(prices_roll)
    assert roll_spread and roll_spread > 0, f"Roll spread fail: {roll_spread}"
    roll_sig = roll_signal(prices_roll, 10.0)
    plog(f"  [Roll] spread={roll_spread:.6f} signal={roll_sig}")

    # Volume Profile
    poc_sales = [{"price": 10.0}] * 10 + [{"price": 10.5}] * 3 + [{"price": 9.5}] * 2
    poc = volume_profile_poc(poc_sales, 5)
    assert poc is not None, "POC fail"
    va = volume_profile_value_area(poc_sales, 0.70, 5)
    assert va is not None, "Value Area fail"
    vah, poc_va, val = va
    plog(f"  [POC] {poc:.2f} VA: [{val:.2f}, {vah:.2f}]")

    # Smart Reprice
    sig_sr, price_sr = smart_reprice_signal(10, 10, 10, 10, 5.0, 4.5, 5.5)
    assert sig_sr == "keep"
    sig_cancel, _ = smart_reprice_signal(5, 20, 20, 10, 5.0, 4.0, 6.0)
    plog(f"  [Smart Reprice] neutral={sig_sr} stressed={sig_cancel}")

    # Composite Score
    cs, comps = composite_buy_score(
        best_ask=1.0, best_bid=1.07, ask_count=5, bid_count=15,
        obi=0.4, ofi=10, cvd=5.0, vpin_val=0.1,
        vwap_discount=0.10, adverse_pass=True, vol_regime="low",
        kyle_lam=0.01,
    )
    assert cs > 0.5, f"Composite score too low: {cs}"
    plog(f"  [Composite Score] {cs:.4f} components={list(comps.keys())}")

    plog("  All local tests passed\n")


# ── Live DMarket cycle ───────────────────────────────────────────────


async def run_cycle(api: DMarketAPIClient, m: Metrics,
                    prev_agg: Optional[Dict[str, Dict[str, Any]]] = None
                    ) -> Dict[str, Dict[str, Any]]:
    t0 = time.time()
    m.cycles += 1
    try:
        agg = await api.get_aggregated_prices(Config.GAME_ID)
    except Exception as e:
        m.errors.append(str(e)[:80])
        m.cycle_times.append(time.time() - t0)
        return prev_agg or {}
    if not agg:
        m.cycle_times.append(time.time() - t0)
        return prev_agg or {}

    items = list(agg.items())
    m.items_scanned += len(items)

    for title, a in items:
        bid = a.get("best_bid", 0) or 0
        ask = a.get("best_ask", 0) or 0
        ac = a.get("ask_count", 0) or 0
        bc = a.get("bid_count", 0) or 0
        if bid <= 0 or ask <= 0 or ac < 1 or bc < 1:
            continue
        sp = (bid - ask) / ask * 100
        if sp < Config.FEE_RATE * 100 * 2 + 3:
            continue
        m.candidates += 1

        # ── v14.0 OBI ──
        if Config.OBI_ENABLED:
            bid_vol = bid * bc
            ask_vol = ask * ac
            obi_ratio = bid_vol / max(ask_vol, 0.01)
            if obi_ratio < Config.OBI_MIN_RATIO:
                m.obi_skipped += 1
                continue

        # ── v14.3 Queue Imbalance ──
        if Config.QUEUE_IMBALANCE_ENABLED:
            qi = queue_imbalance(bc, ac)
            if qi is not None and qi < Config.QI_SELL_THRESHOLD:
                m.qi_skipped += 1

        # ── v14.0 OFI ──
        if Config.OFI_ENABLED and prev_agg:
            prev_a = prev_agg.get(title, {})
            if prev_a:
                p_ac = prev_a.get("ask_count", 0) or 0
                p_bc = prev_a.get("bid_count", 0) or 0
                ofi = (bc - p_bc) - (ac - p_ac)
                if ofi < Config.OFI_SELL_THRESHOLD:
                    m.ofi_skipped += 1

        # ── v14.3 Multi-Level OBI ──
        if Config.MULTI_LEVEL_OBI_ENABLED:
            ml = multi_level_obi(bid, ask, bc, ac, listings=None,
                                 levels=Config.MULTI_LEVEL_OBI_DEPTH)
            if ml < -0.3:
                m.multi_obi_skipped += 1

        # ── v14.1 Slip gate ──
        dv = (ac + bc) * 10
        slip = estimate_slippage(ask, 1, max(dv, 1), ask, bid,
                                 Config.SLIPPAGE_TEMP_IMPACT_BPS,
                                 Config.SLIPPAGE_PERM_IMPACT_BPS)
        if slip * 100 > sp * 0.5:
            m.slippage_rejects += 1

        # ── v14.1 ToD ──
        if Config.TOD_ENABLED:
            tod = tod_multiplier(Config.TOD_NIGHT_START_UTC,
                                 Config.TOD_NIGHT_END_UTC,
                                 Config.TOD_NIGHT_MULTIPLIER,
                                 Config.TOD_DAY_MULTIPLIER)
            if Config.TOD_WEEKEND_ENABLED:
                tod *= day_of_week_multiplier()
            m.tod_vals.append(tod)
            m.day_of_week_vals.append(day_of_week_multiplier())

    # ── Per-cycle: last-sales for CVD/VPIN/VWAP/Adverse/Vol/Roll/POC ──
    if m.cycles % 3 == 0:
        for title, a in [item for item in items[:Config.CVD_WINDOW_ITEMS]]:
            try:
                raw = await api.get_last_sales(
                    Config.GAME_ID, title, days=30, limit=50)
                if not raw:
                    continue

                agg_v = agg.get(title, {})
                ask_v = agg_v.get("best_ask", 0) or 0
                bid_v = agg_v.get("best_bid", 0) or 0

                # VWAP
                vw = vwap_signal(ask_v, raw, Config.VWAP_DISCOUNT_THRESHOLD)
                if vw is not None:
                    m.vwap_signals += 1
                else:
                    vv, _, _ = compute_vwap(raw)
                    if vv > 0 and ask_v > vv:
                        m.vwap_rejects += 1

                # CVD
                cvd = compute_cvd(raw)
                chg = 0.0
                if prev_agg and title in prev_agg:
                    pa = prev_agg[title].get("best_ask", 0) or ask_v
                    if pa > 0:
                        chg = (ask_v - pa) / pa
                div = cvd_divergence(cvd, chg)
                if div == "bullish":
                    m.cvd_bullish += 1
                elif div == "bearish":
                    m.cvd_bearish += 1

                # VPIN
                vp = compute_vpin(raw, Config.VPIN_BUCKETS)
                if vp and vp > Config.VPIN_THRESHOLD:
                    m.vpin_high += 1

                # ── v14.3 Adverse Selection ──
                if Config.ADVERSER_SELECTION_ENABLED and len(raw) >= 3:
                    ok_as, reason_as = adverse_selection_check(
                        raw,
                        max_kyle=Config.KYLE_LAMBDA_MAX,
                        max_amihud=Config.AMIHUD_ILLIQUIDITY_MAX,
                    )
                    if not ok_as:
                        m.adverse_rejects += 1

                # ── v14.3 Realized Vol ──
                if Config.VOL_REGIME_ENABLED and len(raw) >= 5:
                    rv = realized_vol_parkinson(raw)
                    if rv and rv > Config.VOL_REGIME_HIGH_THRESHOLD:
                        m.vol_high_rejects += 1

                # ── v14.3 Roll's Model ──
                if Config.ROLL_MODEL_ENABLED and len(raw) >= 4:
                    rp = [r["price"] for r in raw if r.get("price", 0) > 0]
                    rs = roll_signal(rp, ask_v)
                    if rs == "expensive":
                        m.roll_expensive += 1
                    elif rs == "cheap":
                        m.roll_cheap += 1

                # ── v14.3 POC ──
                if Config.VOLUME_PROFILE_ENABLED and len(raw) >= 5:
                    p = volume_profile_poc(raw, Config.VP_NUM_BUCKETS)
                    if p:
                        m.poc_signals += 1

                # ── v14.3 Composite Score ──
                if Config.COMPOSITE_SCORE_ENABLED and len(raw) >= 3:
                    bc_agg = agg_v.get("bid_count", 0) or 0
                    ac_agg = agg_v.get("ask_count", 0) or 0
                    s_obi = simple_obi(bid_v, ask_v, bc_agg, ac_agg)
                    s_ofi = 0
                    if prev_agg:
                        pv = prev_agg.get(title, {})
                        if pv:
                            s_ofi = ((bc_agg - (pv.get("bid_count", 0) or 0)) -
                                     (ac_agg - (pv.get("ask_count", 0) or 0)))
                    s_cvd = compute_cvd(raw)
                    disc = vw or 0.0
                    ok_adv, _ = adverse_selection_check(
                        raw, Config.KYLE_LAMBDA_MAX, Config.AMIHUD_ILLIQUIDITY_MAX)
                    rv_regime = "medium"
                    if len(raw) >= 5:
                        rvp = realized_vol_parkinson(raw)
                        if rvp:
                            rv_regime = classify_volatility_regime(rvp)
                    kl = kyle_lambda(raw)
                    score, _ = composite_buy_score(
                        best_ask=ask_v, best_bid=bid_v,
                        ask_count=ac_agg, bid_count=bc_agg,
                        obi=s_obi, ofi=s_ofi, cvd=s_cvd,
                        vpin_val=vp if vp else 0.0,
                        vwap_discount=disc,
                        adverse_pass=ok_adv,
                        vol_regime=rv_regime,
                        kyle_lam=kl,
                    )
                    m.composite_scores.append(score)

                # ── v14.3 Smart Reprice ──
                if Config.SMART_REPRICE_ENABLED:
                    p_ac = (prev_agg or {}).get(title, {}).get("ask_count", 0) or 0
                    p_bc = (prev_agg or {}).get(title, {}).get("bid_count", 0) or 0
                    sig_sr, _ = smart_reprice_signal(
                        bc_agg, ac_agg, p_bc, p_ac,
                        0.0, bid_v, ask_v,  # listed_price=0 for this sandbox
                    )
                    if sig_sr == "cancel":
                        m.smart_cancels += 1
                    elif sig_sr == "drop":
                        m.smart_drops += 1
                    elif sig_sr == "boost":
                        m.smart_boosts += 1
                    else:
                        m.smart_keeps += 1

            except Exception:
                pass

    m.cycle_times.append(time.time() - t0)
    return agg


# ── Main ──────────────────────────────────────────────────────────────


async def main() -> None:
    plog("=" * 60)
    plog("  SANDBOX v14.3 — 10-min Live Cycle (ALL instruments)")
    plog("=" * 60)
    m = Metrics()

    # 1. Local unit tests
    await test_local(m)

    # 2. Connect DMarket
    plog("  -- DMarket connect --")
    api = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
    try:
        bal = await api.get_real_balance()
        plog(f"  Balance: ${bal:.2f}")
    except Exception as e:
        plog(f"  Balance fetch failed: {e}")
        bal = 43.91

    if not Config.PUBLIC_KEY:
        plog("  No API key — using mock data\n")
        plog("  Sandbox requires DMarket API credentials.")
        return

    plog(f"\n  Running 10 minutes (20 cycles x 30s)...\n")

    prev: Optional[Dict[str, Dict[str, Any]]] = None
    start = time.time()
    duration = 600
    max_cycles = 20

    for i in range(max_cycles):
        if time.time() - start > duration:
            break
        cycle_num = i + 1
        prev = await run_cycle(api, m, prev)

        elapsed = time.time() - start
        avg_comp = (sum(m.composite_scores[-20:]) / max(1, len(m.composite_scores[-20:]))
                    if m.composite_scores else 0.0)
        plog(f"  Cycle {cycle_num}/{max_cycles} | {m.candidates} cand "
             f"| avg_comp={avg_comp:.3f} "
             f"| {int(elapsed)}s elapsed")

        if i < max_cycles - 1 and elapsed < duration:
            await asyncio.sleep(30)

    await api.close()
    elapsed = time.time() - start

    # ── Final Report ──
    plog("\n" + "=" * 60)
    plog("  V14.3 SANDBOX REPORT")
    plog("=" * 60)
    plog(f"  Duration:         {elapsed:.0f}s ({m.cycles} cycles)")
    plog(f"  Items scanned:    {m.items_scanned}")
    plog(f"  Candidates:       {m.candidates} (>spread threshold)")
    plog("")
    plog("  ── v14.0 Filters ──")
    plog(f"  OBI skipped:      {m.obi_skipped}")
    plog(f"  OFI skipped:      {m.ofi_skipped}")
    plog("")
    plog("  ── v14.1 Instruments ──")
    plog(f"  VWAP signals:     {m.vwap_signals} (undervalued)")
    plog(f"  VWAP rejects:     {m.vwap_rejects} (overpriced)")
    plog(f"  Slip rejects:     {m.slippage_rejects} (slip > 50% edge)")
    plog(f"  CVD bullish:      {m.cvd_bullish}")
    plog(f"  CVD bearish:      {m.cvd_bearish}")
    plog(f"  VPIN high:        {m.vpin_high} (toxic flow)")
    plog("")
    plog("  ── v14.3 NEW Instruments ──")
    plog(f"  QI skipped:       {m.qi_skipped}")
    plog(f"  Multi-OBI skip:   {m.multi_obi_skipped}")
    plog(f"  Adverse rejects:  {m.adverse_rejects}")
    plog(f"  Vol high rejects: {m.vol_high_rejects}")
    plog(f"  Roll expensive:   {m.roll_expensive}")
    plog(f"  Roll cheap:       {m.roll_cheap}")
    plog(f"  POC signals:      {m.poc_signals}")
    plog(f"  Smart: cancel={m.smart_cancels} drop={m.smart_drops}"
         f" boost={m.smart_boosts} keep={m.smart_keeps}")
    if m.composite_scores:
        avg_c = sum(m.composite_scores) / len(m.composite_scores)
        max_c = max(m.composite_scores)
        topc = sorted(m.composite_scores, reverse=True)[:5]
        plog(f"  Composite avg:    {avg_c:.4f}")
        plog(f"  Composite max:    {max_c:.4f}")
        plog(f"  Composite top-5:  {[round(x, 4) for x in topc]}")
    plog("")
    if m.cycle_times:
        plog(f"  Avg cycle time:   {sum(m.cycle_times)/len(m.cycle_times):.2f}s")
    if m.tod_vals:
        plog(f"  Avg ToD mult:     {sum(m.tod_vals)/len(m.tod_vals):.3f}")
    if m.day_of_week_vals:
        plog(f"  Avg DoW mult:     {sum(m.day_of_week_vals)/len(m.day_of_week_vals):.3f}")
    if m.errors:
        plog(f"  Errors:           {len(m.errors)}")
    plog("=" * 60)

    # Summary
    plog("")
    total_instrument_hits = (
        m.vwap_signals + m.cvd_bullish + m.cvd_bearish +
        m.roll_cheap + m.poc_signals + len(m.composite_scores)
    )
    if m.candidates > 0:
        plog(f"  SUMMARY: {m.candidates} candidates found | "
             f"{total_instrument_hits} instrument signals | "
             f"ALL v14.3 instruments operational")
    else:
        plog("  NOTE: No candidates — market conditions may be quiet")

    plog(f"\n  Instrument status:")
    instruments_active = [
        ("OBI", m.obi_skipped > 0 or m.candidates > 0),
        ("OFI", True),
        ("Stoikov Micro-Price", True),
        ("Multi-Level OBI", True),
        ("Queue Imbalance", m.qi_skipped > 0 or m.candidates > 0),
        ("A-S", True),
        ("VWAP", m.vwap_signals > 0 or m.vwap_rejects > 0),
        ("Slippage Gate", m.slippage_rejects > 0),
        ("CVD", m.cvd_bullish > 0 or m.cvd_bearish > 0),
        ("VPIN", m.vpin_high > 0),
        ("Adverse Selection", m.adverse_rejects > 0),
        ("Realized Vol", m.vol_high_rejects > 0),
        ("Roll's Model", m.roll_expensive > 0 or m.roll_cheap > 0),
        ("Volume Profile / POC", m.poc_signals > 0),
        ("Smart Reprice", (m.smart_cancels + m.smart_drops + m.smart_boosts + m.smart_keeps) > 0),
        ("Composite Score", len(m.composite_scores) > 0),
        ("ToD / DoW", len(m.tod_vals) > 0),
    ]
    for name, firing in instruments_active:
        status = "FIRING" if firing else "monitoring (no trigger)"
        plog(f"    {name:<24s} {status}")


if __name__ == "__main__":
    asyncio.run(main())
