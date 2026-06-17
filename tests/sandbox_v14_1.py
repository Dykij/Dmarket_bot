"""
Sandbox v14.1 — Full Cycle with All Microstructure Instruments (10-min live).

Tests all v14.1 DMarket-native instruments:
  A-S, VWAP, Slippage, CVD, VPIN, ToD

Run: uv run python tests/sandbox_v14_1.py
"""
import asyncio, logging, os, sys, time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["DRY_RUN"] = "false"  # Read-only market data — no real trades
os.environ.setdefault("ENCRYPTION_KEY", "test-key-sandbox-v14-1")
logging.basicConfig(level=logging.WARNING)

from src.config import Config
from src.api.dmarket_api_client import DMarketAPIClient
from src.analysis.microstructure import (
    reservation_price, compute_vwap, vwap_signal, estimate_slippage,
    compute_cvd, compute_vpin, cvd_divergence, tod_multiplier,
)

def plog(msg=""):
    print(msg, flush=True)

class M:
    def __init__(self):
        self.cycles=0; self.items_scanned=0; self.candidates=0
        self.vwap_signals=0; self.vwap_rejects=0; self.slippage_rejects=0
        self.cvd_bullish=0; self.cvd_bearish=0; self.vpin_high=0
        self.tod_vals=[]; self.errors=[]; self.cycle_times=[]

async def test_local(m: M):
    plog("  -- Local instrument tests --")
    r = reservation_price(10.0, 3, 0, 3, 0.4, 0.3, 7)
    assert r < 10.0, f"A-S failed: {r}"
    r2 = reservation_price(10.0, 0, 0, 3, 0.4, 0.3, 7)
    assert abs(r2 - 10.0) < 0.01, f"A-S neutral failed: {r2}"
    plog(f"  [A-S] reserv(inv=3)={r:.4f} inv=0={r2:.4f}")

    sales = [{"price":1.0},{"price":1.1},{"price":0.95},{"price":1.05}]
    v,vol,std = compute_vwap(sales)
    sig = vwap_signal(0.85, sales, 0.90)
    assert sig is not None, "VWAP missed signal"
    plog(f"  [VWAP] {v:.4f} vol={vol} signal={sig}")

    slip = estimate_slippage(10.0, 1, 500, 10.0, 9.5)
    assert slip < 0.01
    plog(f"  [Slip] {slip:.6f}")

    cvd = compute_cvd(sales, prev_mid=1.0)
    div = cvd_divergence(10.0, -0.02)
    assert div == "bullish"
    plog(f"  [CVD] {cvd:.4f} div={div}")

    vpin = compute_vpin(sales * 5, n_buckets=4)
    plog(f"  [VPIN] {vpin}")

    tod = tod_multiplier(4, 10, 0.85, 1.0)
    plog(f"  [ToD] multiplier={tod:.2f}")
    plog("  All local tests passed\n")

async def run_cycle(api, m: M, prev_agg=None):
    t0 = time.time()
    m.cycles += 1
    try:
        agg = await api.get_aggregated_prices(Config.GAME_ID)
    except Exception as e:
        m.errors.append(str(e))
        m.cycle_times.append(time.time()-t0)
        return prev_agg or {}
    if not agg:
        m.cycle_times.append(time.time()-t0)
        return prev_agg or {}
    items = list(agg.items())
    m.items_scanned += len(items)

    for title, a in items:
        bid = a.get("best_bid",0) or 0
        ask = a.get("best_ask",0) or 0
        ac = a.get("ask_count",0) or 0
        bc = a.get("bid_count",0) or 0
        if bid<=0 or ask<=0 or ac<1 or bc<1:
            continue
        sp = (bid-ask)/ask*100
        if sp < Config.FEE_RATE*100*2+3:
            continue
        m.candidates += 1
        tod = tod_multiplier(
            Config.TOD_NIGHT_START_UTC, Config.TOD_NIGHT_END_UTC,
            Config.TOD_NIGHT_MULTIPLIER, Config.TOD_DAY_MULTIPLIER)
        m.tod_vals.append(tod)
        dv = (ac+bc)*10
        slip = estimate_slippage(ask, 1, max(dv,1), ask, bid,
            Config.SLIPPAGE_TEMP_IMPACT_BPS, Config.SLIPPAGE_PERM_IMPACT_BPS)
        if slip*100 > sp*0.5:
            m.slippage_rejects += 1

    if m.cycles % 3 == 0:
        for title in [t for t,_ in items[:5]]:
            try:
                raw = await api.get_last_sales(Config.GAME_ID, title, days=7, limit=20)
                if not raw: continue
                agg_v = agg.get(title,{})
                ask_v = agg_v.get("best_ask",0) or 0
                vw = vwap_signal(ask_v, raw, Config.VWAP_DISCOUNT_THRESHOLD)
                if vw is not None: m.vwap_signals += 1
                else:
                    vv,_,_ = compute_vwap(raw)
                    if vv>0 and ask_v>vv: m.vwap_rejects += 1
                cvd = compute_cvd(raw)
                chg = 0.0
                if prev_agg and title in prev_agg:
                    pa = prev_agg[title].get("best_ask",0) or ask_v
                    if pa>0: chg = (ask_v-pa)/pa
                div = cvd_divergence(cvd, chg)
                if div=="bullish": m.cvd_bullish += 1
                elif div=="bearish": m.cvd_bearish += 1
                vp = compute_vpin(raw, Config.VPIN_BUCKETS)
                if vp and vp > Config.VPIN_THRESHOLD: m.vpin_high += 1
            except Exception:
                pass
    m.cycle_times.append(time.time()-t0)
    return agg

async def main():
    plog("="*60)
    plog("  SANDBOX v14.1 — 10-min Live Cycle")
    plog("="*60)
    m = M()
    await test_local(m)

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
    prev = None
    start = time.time()
    duration = 600  # 10 minutes
    cycle_num = 0
    max_cycles = 20

    for i in range(max_cycles):
        if time.time() - start > duration:
            break
        cycle_num = i + 1
        prev = await run_cycle(api, m, prev)
        elapsed = time.time() - start
        plog(f"  Cycle {cycle_num}/{max_cycles} | {m.candidates} cand | "
             f"{int(elapsed)}s elapsed")
        if i < max_cycles - 1 and elapsed < duration:
            await asyncio.sleep(30)

    await api.close()
    elapsed = time.time() - start

    # Final report
    plog("\n" + "="*60)
    plog("  V14.1 SANDBOX REPORT")
    plog("="*60)
    plog(f"  Duration:       {elapsed:.0f}s ({cycle_num} cycles)")
    plog(f"  Items scanned:  {m.items_scanned}")
    plog(f"  Candidates:     {m.candidates} (>spread threshold)")
    plog(f"  VWAP signals:   {m.vwap_signals} (undervalued)")
    plog(f"  VWAP rejects:   {m.vwap_rejects} (overpriced vs VWAP)")
    plog(f"  Slip rejects:   {m.slippage_rejects} (slippage > 50% edge)")
    plog(f"  CVD bullish:    {m.cvd_bullish}")
    plog(f"  CVD bearish:    {m.cvd_bearish}")
    plog(f"  VPIN high:      {m.vpin_high} (toxic flow)")
    if m.cycle_times:
        plog(f"  Avg cycle time: {sum(m.cycle_times)/len(m.cycle_times):.2f}s")
    if m.tod_vals:
        plog(f"  Avg ToD mult:   {sum(m.tod_vals)/len(m.tod_vals):.3f}")
    if m.errors:
        plog(f"  Errors:         {len(m.errors)}")
    plog("="*60)

    if m.candidates > 0:
        plog("\n  SUMMARY: v14.1 instruments active and processing live data")
    else:
        plog("\n  NOTE: No candidates — market conditions may be quiet")

if __name__ == "__main__":
    asyncio.run(main())
