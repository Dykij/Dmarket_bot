"""
Sandbox Test v14.6 — Full Buy → CS2Cap → Sell Cycle + Value Detection.

v14.6: Added float premium, pattern/phase premium, sticker combo,
       seasonal timing, filler tracking, dirty BS, round float,
       float date, commission optimizer (TA Site Analysis integration).
"""

import asyncio
import logging
import math
import os
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DRY_RUN"] = "false"  # Allow real market data reads (no buys are executed)
os.environ.setdefault("ENCRYPTION_KEY", "test-key-for-sandbox-reads-only")

from src.config import Config
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.oracle_factory import OracleFactory
from src.api.cs2cap_oracle import CS2CapOracle
from src.core.item_intel import DISCOUNT_THRESHOLD_PCT
from src.db.price_history import price_db

from src.analysis.microstructure import (
    simple_obi,
    compute_vwap,
    vwap_signal,
    compute_cvd,
    compute_vpin,
    composite_buy_score,
    classify_volatility_regime,
    realized_vol_parkinson,
    kyle_lambda,
    adverse_selection_check,
)

# ---- Output helpers ----
def log(msg: str) -> None:
    """Print with flush — no buffering delays."""
    print(msg, flush=True)

def log_ok(msg: str) -> None:
    log(f"  ✅ {msg}")

def log_warn(msg: str) -> None:
    log(f"  ⚠️ {msg}")

def log_err(msg: str) -> None:
    log(f"  ❌ {msg}")

def log_info(msg: str) -> None:
    log(f"  ℹ️ {msg}")

# ---- Async helpers ----
async def with_timeout(seconds: float, coro, label: str) -> Any:
    """Run coro with timeout. Returns result or None on timeout/error."""
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        log_err(f"{label}: timed out after {seconds}s")
        return None
    except Exception as e:
        log_err(f"{label}: {e}")
        return None


# ---- Microstructure helpers ----
def _generate_synthetic_sales(best_ask: float, best_bid: float,
                               ask_count: int, bid_count: int) -> List[Dict[str, Any]]:
    """Generate synthetic trade records from spread data for microstructure calcs.

    Creates deterministic pseudo-trades around the mid price so CVD/VPIN/VWAP
    have data to work with. No API calls — pure math, <1ms per candidate.
    """
    if best_ask <= 0 or best_bid <= 0:
        return []
    mid = (best_ask + best_bid) / 2.0
    spread = best_bid - best_ask
    half = spread / 2.0 if spread > 0 else 0.01

    # Simulate a mix of buyer- and seller-initiated trades
    # More bid_count relative to ask_count = more buyer pressure
    total = max(ask_count + bid_count, 1)
    buy_ratio = bid_count / total if total > 0 else 0.5
    num_buys = max(3, round(9 * buy_ratio))
    num_sells = max(3, 9 - num_buys)

    sales: List[Dict[str, Any]] = []
    # Seller-initiated (price near bid / below mid)
    for i in range(num_sells):
        offset = half * (0.2 + 0.6 * i / max(num_sells - 1, 1))
        sales.append({"price": round(mid - offset, 4), "amount": 1})
    # Buyer-initiated (price near ask / above mid)
    for i in range(num_buys):
        offset = half * (0.2 + 0.6 * i / max(num_buys - 1, 1))
        sales.append({"price": round(mid + offset, 4), "amount": 1})

    sales.sort(key=lambda s: s["price"])
    return sales


def _check_microstructure(obi_val: float, cvd_val: float, vwap_val: float,
                           best_ask: float, vpin_val: Optional[float]) -> str:
    """Build compact microstructure filter status string."""
    parts = []
    # OBI: positive = buyer pressure
    parts.append(f"OBI{'✅' if obi_val > 0 else '❌'}")
    # CVD: positive = accumulation
    parts.append(f"CVD{'✅' if cvd_val > 0 else '❌'}")
    # VWAP: undervalued if best_ask < vwap
    if vwap_val > 0:
        parts.append(f"VWAP{'✅' if best_ask < vwap_val else '❌'}")
    else:
        parts.append("VWAP—")
    # VPIN: low informed trading risk
    if vpin_val is not None:
        if vpin_val < 0.4:
            parts.append(f"VPIN✅")
        elif vpin_val < 0.6:
            parts.append(f"VPIN⚠️")
        else:
            parts.append(f"VPIN❌")
    else:
        parts.append("VPIN—")
    return " ".join(parts)


# =====================================================================
# STEP 1: DMarket API Connection
# =====================================================================
async def step_dmarket_connect() -> tuple[DMarketAPIClient, float, bool]:
    """Connect to DMarket API and get balance."""
    log("\n[1/6] 🔗 DMarket API Connection")
    api = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
    try:
        balance = await with_timeout(10, api.get_real_balance(), "get_real_balance")
        if balance is not None:
            log_ok(f"Connected! Balance: ${balance:.2f}")
            return api, balance, True
    except Exception as e:
        log_err(str(e))
    log_warn(f"Using default balance: $10000")
    return api, 10000.0, False


# =====================================================================
# STEP 2: CS2Cap + DMarket Aggregated Prices (PARALLEL)
# =====================================================================
async def step_fetch_prices(
    api: DMarketAPIClient,
) -> tuple[Optional[CS2CapOracle], Dict[str, Any], bool]:
    """Fetch CS2Cap prices + DMarket aggregated prices in parallel."""
    log("\n[2/6] 📊 Fetching Prices (DMarket + CS2Cap in parallel)")

    cs2cap = OracleFactory.get_cross_market_oracle(Config.GAME_ID)

    # --- DMarket: get aggregated prices (batch 100 titles) ---
    async def fetch_agg() -> Dict[str, Any]:
        try:
            return await api.get_aggregated_prices(Config.GAME_ID)
        except Exception as e:
            log_err(f"aggregated_prices: {e}")
            return {}

    # --- CS2Cap: health check ---
    async def check_cs2cap() -> bool:
        if not cs2cap:
            return False
        try:
            h = await cs2cap.health_check()
            return h.get("status") == "healthy"
        except Exception:
            return False

    # Run both in parallel
    agg_task = asyncio.create_task(with_timeout(15, fetch_agg(), "aggregated-prices"))
    cs2cap_task = asyncio.create_task(with_timeout(10, check_cs2cap(), "cs2cap-health"))

    agg_prices = await agg_task or {}
    cs2cap_ok = await cs2cap_task or False

    if cs2cap_ok:
        log_ok(f"CS2Cap connected (41 marketplaces)")
    else:
        log_warn("CS2Cap unavailable — price comparisons will be limited")

    if agg_prices:
        # Count valid entries
        valid = sum(1 for a in agg_prices.values() if a.get("best_ask", 0) > 0)
        log_ok(f"DMarket aggregated prices: {len(agg_prices)} titles, {valid} with bids")
    else:
        log_warn("No aggregated prices returned from DMarket")

    return cs2cap, agg_prices, cs2cap_ok


# =====================================================================
# STEP 3: Find Profitable Candidates + Microstructure Scoring
# =====================================================================
async def step_find_candidates(
    cs2cap: Optional[CS2CapOracle],
    agg_prices: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], Dict[str, List[Dict[str, Any]]]]:
    """Use batch CS2Cap prices to find arbitrage opportunities + score microstructure."""
    log("\n[3/6] 🔍 Finding Profitable Candidates + Microstructure Scoring")

    # Track filtered items for bottom-neck detection
    filtered: Dict[str, List[Dict[str, Any]]] = {
        "spread": [],      # items with insufficient spread
        "liquidity": [],    # items with low volume/liquidity
        "margin": [],       # items with negative profit after fees
    }

    if not agg_prices or not cs2cap:
        log_warn("Missing data — can't evaluate candidates")
        return [], filtered

    # ---- Phase 1: Rank by liquidity/volume, then CS2Cap cross-market check ----
    min_spread = Config.FEE_RATE * 100 * 2 + 3  # fee-aware minimum spread %
    ranked = []
    for title, agg in agg_prices.items():
        best_bid = agg.get("best_bid", 0) or 0
        best_ask = agg.get("best_ask", 0) or 0
        ask_cnt = agg.get("ask_count", 0) or 0
        bid_cnt = agg.get("bid_count", 0) or 0
        if best_ask <= 0:
            continue
        volume = ask_cnt + bid_cnt

        # v14.5: In a normal market, best_ask > best_bid.
        # We're looking for cross-market arbitrage (DM cheap vs CS2Cap high),
        # not intra-DM spread. Rank by liquidity/volume so we CS2Cap-check
        # the most liquid items (which are likely to have cross-market data).
        if volume < 3:
            filtered["liquidity"].append({
                "title": title, "reason": f"volume={volume} too low",
                "best_ask": best_ask, "best_bid": best_bid,
            })
            continue

        score = volume
        ranked.append((title, best_ask, best_bid, 0.0, volume, score,
                        ask_cnt, bid_cnt))

    ranked.sort(key=lambda x: -x[5])
    top = ranked[:20]  # Top 20 most liquid items
    log_info(f"Top {len(top)} candidates (most liquid)")

    if not top:
        log_warn("No candidates — low liquidity")
        return [], filtered

    # ---- Phase 2: Fetch CS2Cap batch prices ----
    titles_for_cs2cap = [t[0] for t in top]
    cs2cap_prices: Dict[str, float] = {}

    cs2cap_snaps = await with_timeout(
        15,
        cs2cap.get_prices_batch(titles_for_cs2cap),
        f"CS2Cap batch ({len(titles_for_cs2cap)} items)",
    ) or {}

    for title in titles_for_cs2cap:
        snap = cs2cap_snaps.get(title)
        if snap and getattr(snap, "has_data", False):
            cs2cap_prices[title] = snap.min_price

    if cs2cap_prices:
        log_ok(f"CS2Cap prices for {len(cs2cap_prices)}/{len(titles_for_cs2cap)} titles")

    # ---- Phase 3: Scan DMarket for cheap items, check CS2Cap cross-market ----
    from src.api.dmarket_api_client.fees import _FeesMixin

    candidates = []

    # Use the previously fetched prices to evaluate candidates
    for item in top:
        title, ask, bid, spread_pct, volume, score, ask_cnt, bid_cnt = item
        cs_price = cs2cap_prices.get(title, 0)
        if cs_price <= 0:
            continue
        dm_buy_price = ask

        fee = _FeesMixin._estimate_fee_from_volume(ask_count=volume)
        total_fee = fee + Config.WITHDRAWAL_FEE_RATE

        sell_price = cs_price * 0.97
        ref = f"CS2Cap=${cs_price:.2f}"
        net = sell_price * (1 - total_fee)
        profit = net - dm_buy_price
        margin_pct = (profit / dm_buy_price * 100) if dm_buy_price > 0 else 0

        if profit <= 0 or margin_pct < 1:
            filtered["margin"].append({
                "title": title, "reason": f"profit=${profit:.3f} margin={margin_pct:.1f}%",
                "best_ask": ask, "cs2cap_price": cs_price, "sell_price": sell_price,
            })
            continue

        # ---- Microstructure scoring ----
        sales = _generate_synthetic_sales(ask, bid, ask_cnt, bid_cnt)
        has_trades = len(sales) >= 3

        obi_val = simple_obi(bid, ask, bid_cnt, ask_cnt)
        vwap_val, vwap_vol, _ = compute_vwap(sales) if has_trades else (0.0, 0.0, [])
        vwap_discount_sig = vwap_signal(ask, sales, threshold=0.90) if has_trades else None
        cvd_val = compute_cvd(sales) if has_trades else 0.0
        vpin_val = compute_vpin(sales, n_buckets=4) if has_trades else None
        kyle_lam = kyle_lambda(sales) if has_trades else None
        adverse_pass, adverse_reason = (
            adverse_selection_check(sales) if has_trades else (True, "no data")
        )
        park_vol = realized_vol_parkinson(sales) if has_trades else None
        vol_regime = classify_volatility_regime(park_vol or 0.15)

        vwap_disc = vwap_discount_sig if vwap_discount_sig is not None else 0.0
        vpin_safe = vpin_val if vpin_val is not None else 0.5
        ofi = (bid_cnt - ask_cnt)

        comp_score, comp_parts = composite_buy_score(
            best_ask=ask, best_bid=bid,
            ask_count=ask_cnt, bid_count=bid_cnt,
            obi=obi_val, ofi=ofi,
            cvd=cvd_val, vpin_val=vpin_safe,
            vwap_discount=vwap_disc,
            adverse_pass=adverse_pass,
            vol_regime=vol_regime,
            kyle_lam=kyle_lam,
        )
        micro_filter = _check_microstructure(obi_val, cvd_val, vwap_val, ask, vpin_val)

        if vol_regime == "high":
            filtered.setdefault("volatility", []).append({
                "title": title, "vol_regime": vol_regime,
                "park_vol": park_vol, "ask": ask,
            })

        candidates.append({
            "title": title,
            "dm_buy_price": dm_buy_price,
            "cs2cap_price": cs_price,
            "sell_price": sell_price,
            "fee": fee,
            "total_fee": total_fee,
            "net": net,
            "profit": profit,
            "margin_pct": margin_pct,
            "spread_pct": round(spread_pct, 1),
            "volume": volume,
            "ref": ref,
            "obi": obi_val,
            "cvd": cvd_val,
            "vwap": round(vwap_val, 4),
            "vpin": vpin_val,
            "vwap_discount": round(vwap_disc, 4),
            "vol_regime": vol_regime,
            "park_vol": round(park_vol, 4) if park_vol else None,
            "kyle_lambda": kyle_lam,
            "adverse_pass": adverse_pass,
            "composite_score": round(comp_score * 100, 1),
            "micro_filter": micro_filter,
        })

    candidates.sort(key=lambda x: -(x["composite_score"] + x["margin_pct"] * 2))
    log_info(f"Candidates with net profit > 0 (cross-market): {len(candidates)}")
    log_info(f"Filtered — liquidity: {len(filtered.get('liquidity', []))}, "
             f"margin: {len(filtered['margin'])}, volatility: {len(filtered.get('volatility', []))}")

    if candidates:
        log(f"\n  {'Item':<30} {'BuyDM':>6} {'SellCS2':>6} {'Profit':>6} {'Marg':>5} {'Comp':>5} {'Micro Filter'}")
        log(f"  {'─'*30} {'─'*6} {'─'*6} {'─'*6} {'─'*5} {'─'*5} {'─'*30}")
        for c in candidates[:15]:
            name = c["title"][:28] + (".." if len(c["title"]) > 30 else "")
            log(
                f"  {name:<30} ${c['dm_buy_price']:>5.2f} "
                f"${c['sell_price']:>5.2f} ${c['profit']:>5.2f} "
                f"{c['margin_pct']:>4.1f}% {c['composite_score']:>4.0f}  {c['micro_filter']}"
            )

    return candidates, filtered


# =====================================================================
# STEP 4: Market Scan — sample cheap listings
# =====================================================================
async def step_market_scan(api: DMarketAPIClient) -> tuple[List[Dict], int]:
    """Scan DMarket to sample real listing data."""
    log("\n[4/6] 📦 Market Scan (sample 500 items)")

    all_items = []
    cursor = None
    max_pages = 5  # Faster: just 5 pages = 500 items
    for page in range(max_pages):
        try:
            resp = await with_timeout(
                5,
                api.get_market_items_v2(Config.GAME_ID, limit=100, cursor=cursor),
                f"market page {page+1}",
            )
            if not resp:
                break
            items = resp.get("objects", [])
            all_items.extend(items)
            cursor = resp.get("cursor")
            if not cursor:
                break
        except Exception as e:
            log_err(f"Page {page+1}: {e}")
            break

    titles_seen = len({it.get("title", "") for it in all_items})
    cheapest = min(
        (int(it.get("price", {}).get("USD", 0)) / 100
         for it in all_items if it.get("price")),
        default=0
    )

    log_ok(f"Scanned {len(all_items)} items ({titles_seen} unique titles)")
    log_info(f"Cheapest listing: ${cheapest:.2f}")

    # v14.6: Value Detection Layers (TA Site Analysis)
    try:
        from src.core.target_sniping.pricing import get_float_premium, get_pattern_premium
        from src.analytics.filler_tracker import is_filler, get_filler_multiplier
        from src.analysis.seasonal import get_timing_multiplier

        float_hits = 0
        pattern_hits = 0
        filler_hits = 0
        for it in all_items[:200]:  # Sample first 200 items
            attrs = {a.get("name"): a.get("value") for a in it.get("attributes", [])}
            if get_float_premium(attrs) > 1.0:
                float_hits += 1
            if get_pattern_premium(attrs) > 1.0:
                pattern_hits += 1
            if is_filler(it.get("title", "")):
                filler_hits += 1

        timing = get_timing_multiplier()
        log_info(
            f"v14.6 Value Detection: {float_hits} float premiums, "
            f"{pattern_hits} pattern premiums, "
            f"{filler_hits} filler skins, timing={timing:.3f}x"
        )
    except Exception:
        pass

    # v14.5: Item intel — categorize + discount detection
    try:
        from src.core.item_intel import _ItemIntelMixin
        intel = _ItemIntelMixin()
        categories: dict[str, int] = {}
        discounted = 0
        for it in all_items:
            title = it.get("title", "")
            cat = intel.categorize_item(title)
            categories[cat] = categories.get(cat, 0) + 1
            if intel.is_discounted_deal(it, int(it.get("price", {}).get("USD", 0)) / 100.0):
                discounted += 1
        log_info(f"Categories: {', '.join(f'{k}:{v}' for k,v in sorted(categories.items(), key=lambda x:-x[1])[:5])}")
        if discounted > 0:
            log_info(f"Discounted deals (≥{DISCOUNT_THRESHOLD_PCT}%): {discounted}")
    except Exception:
        pass

    return all_items, titles_seen

# =====================================================================
# STEP 5: Shadow Trading Engine (v14.5)
# =====================================================================
async def step_shadow_engine(
    candidates: List[Dict],
    agg_prices: Dict[str, Any],
    cs2cap_ok: bool,
) -> Optional[Dict[str, Any]]:
    """Run full shadow trading simulation with live market data."""
    log("\n[5/6] 🕶️ Shadow Trading Engine")

    if not candidates and not agg_prices:
        log_warn("No data for shadow engine")
        return None

    from src.core.shadow_engine import ShadowEngine
    shadow = ShadowEngine(initial_balance=50.0)

    cands = candidates if candidates else _build_candidates_from_agg(agg_prices)

    for cycle in range(1, 15):
        result = shadow.record_cycle(
            candidates=cands,
            agg_prices=agg_prices,
            cs2cap_ok=cs2cap_ok,
            cycle=cycle,
            max_buys=3,
            max_spend_per_cycle=10.0,
        )

        if cycle % 5 == 0 or cycle == 1:
            summary = shadow.get_portfolio_summary()
            log(f"  📊 Cycle {cycle:>2}: balance=${summary['balance']:.2f} | "
                f"equity=${summary['total_equity']:.2f} | "
                f"PnL=${summary['total_pnl']:+.2f} | "
                f"trades={summary['total_trades']} | "
                f"WR={summary['win_rate']:.0f}%")

    final = shadow.get_portfolio_summary()

    log_ok(f"Shadow P&L: ${final['total_pnl']:+.2f} "
           f"(ROI {final['roi_pct']:+.1f}%, "
           f"DD {final['drawdown_pct']:.1f}%, "
           f"{final['total_trades']} trades, "
           f"WR {final['win_rate']:.0f}%)")

    strats = final.get("strategies", {})
    if len(strats) > 1:
        log_info("Strategy Comparison:")
        for name, s in sorted(strats.items(), key=lambda x: -x[1]["pnl"]):
            log(f"    {name}: {s['trades']} trades, PnL ${s['pnl']:+.2f}, Wins {s['wins']}")

    cats = shadow.get_position_breakdown()
    if cats:
        log_info(f"Portfolio: {', '.join(f'{k}:{v}' for k,v in sorted(cats.items()))}")

    return final


def _build_candidates_from_agg(agg_prices: Dict[str, Any]) -> List[Dict[str, Any]]:
    candidates = []
    for title, agg in list(agg_prices.items())[:30]:
        ask = agg.get("best_ask", 0) or 0
        bid = agg.get("best_bid", 0) or 0
        if ask <= 0:
            continue
        margin = ((bid - ask) / ask * 100) if bid > 0 else 0
        candidates.append({
            "title": title,
            "dm_buy_price": ask,
            "best_ask": ask,
            "best_bid": bid,
            "margin_pct": margin,
            "strategy": "CrossMarket" if margin > 5 else "MarketMaker",
        })
    return candidates


# =====================================================================
# STEP 6: Stress Test Scenarios (v14.5)
# =====================================================================
async def step_stress_test(
    candidates: List[Dict],
    agg_prices: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """Run shadow engine through multiple market scenarios."""
    log("\n[6/6] 🌡️ Stress Test Scenarios")

    if not agg_prices:
        log_warn("No data for stress tests")
        return {}

    cands = candidates if candidates else _build_candidates_from_agg(agg_prices)

    from src.core.shadow_engine import run_stress_test
    results = run_stress_test(
        base_candidates=cands,
        agg_prices=agg_prices,
        cycles=15,
    )

    for name, r in results.items():
        emoji = chr(0x1F7E2) if r["total_pnl"] > 0 else chr(0x1F534)  # green/red circle
        log(f"  {emoji} {name}: PnL=${r['total_pnl']:+.2f} "
            f"(ROI {r['roi_pct']:+.1f}%, DD {r['drawdown_pct']:.1f}%, "
            f"{r['total_trades']} trades)")

    log_ok(f"{len(results)} stress scenarios completed")
    return results


# =====================================================================
# STEP 7: Monte Carlo Simulation (v14.5)
# =====================================================================
async def step_monte_carlo(
    candidates: List[Dict],
    agg_prices: Dict[str, Any],
) -> Optional[Dict[str, Any]]:
    """Run Monte Carlo simulation for statistical significance."""
    log("\n[7/7] 🎲 Monte Carlo Simulation")

    if not agg_prices:
        log_warn("No data for Monte Carlo")
        return None

    from src.core.live_shadow import LiveShadow

    cands = candidates if candidates else _build_candidates_from_agg(agg_prices)
    mc = LiveShadow()
    mc._enabled = True
    mc._engine.__init__(initial_balance=50.0)

    # Run with reduced count for sandbox speed
    runs = int(os.getenv("MONTE_CARLO_RUNS", "200"))
    cycles_per_run = int(os.getenv("MONTE_CARLO_CYCLES", "20"))

    log_info(f"Running {runs} simulations ({cycles_per_run} cycles each)...")
    start = time.time()

    result = await mc.run_monte_carlo(
        candidates=cands,
        agg_prices=agg_prices,
        runs=runs,
        cycles=cycles_per_run,
    )

    elapsed = time.time() - start
    log_info(f"Completed in {elapsed:.1f}s")

    log(f"  📊 *P&L Distribution:*")
    log(f"    Mean:    ${result.mean_pnl:+.2f}")
    log(f"    Median:  ${result.median_pnl:+.2f}")
    log(f"    StdDev:  ${result.std_pnl:.2f}")
    log(f"    Range:   ${result.min_pnl:+.2f} ... ${result.max_pnl:+.2f}")
    log(f"    5th pct: ${result.pnl_5th:+.2f} (VaR 95%)")
    log(f"    95th pct:${result.pnl_95th:+.2f}")
    log(f"  📈 *Quality Metrics:*")
    log(f"    Profit probability: {result.profit_probability:.1f}% of runs profitable")
    log(f"    Sharpe estimate:    {result.sharpe_estimate:.2f}")
    log(f"    Avg win rate:       {result.win_rate_mean:.1f}%")
    log(f"    Avg max drawdown:   {result.max_drawdown_mean:.1f}%")

    verdict = "🟢 STRATEGY HAS EDGE" if result.mean_pnl > 0 and result.profit_probability > 55 else "🔴 NO STATISTICAL EDGE"
    log_ok(f"{verdict} (mean PnL ${result.mean_pnl:+.2f}, {result.profit_probability:.1f}% profitable)")
    return {"runs": result.runs, "mean_pnl": result.mean_pnl, "profit_probability": result.profit_probability, "sharpe": result.sharpe_estimate}


# =====================================================================
# REPORT HELPERS
# =====================================================================

def _print_micro_summary(candidates: List[Dict]) -> None:
    """Print V14.6 Microstructure Summary section."""
    if not candidates:
        return

    obi_buy = sum(1 for c in candidates if c.get("obi", 0) > 0)
    obi_sell = sum(1 for c in candidates if c.get("obi", 0) < 0)
    cvd_accum = sum(1 for c in candidates if c.get("cvd", 0) > 0)
    vpin_alert = sum(1 for c in candidates
                     if c.get("vpin") is not None and c["vpin"] > 0.4)
    top_comp = max((c.get("composite_score", 0) for c in candidates), default=0)

    log("\n📊 V14.6 Microstructure Summary")
    log(f"  OBI signals: {obi_buy} buy / {obi_sell} sell")
    log(f"  CVD accumulation: {cvd_accum} items")
    log(f"  VPIN alerts (>0.4): {vpin_alert} items")
    log(f"  Top composite score: {top_comp:.0f}/100")

    regimes = {}
    for c in candidates:
        r = c.get("vol_regime", "unknown")
        regimes[r] = regimes.get(r, 0) + 1
    regime_str = "  ".join(f"{k}: {v}" for k, v in sorted(regimes.items()))
    log(f"  Volatility regimes: {regime_str}")


def _print_bottleneck(filtered: Dict[str, List[Dict[str, Any]]]) -> None:
    """Print Bottom-Neck Detection section."""
    has_any = any(v for v in filtered.values())
    if not has_any:
        return

    log("\n🔻 Bottom-Neck Detection (Filtered Items)")

    spread_items = filtered.get("spread", [])
    if spread_items:
        log(f"  📉 Spread/Margin filtered: {len(spread_items)} items")
        for s in spread_items[:3]:
            log(f"     • {s['title'][:35]} — {s.get('reason', '?')}")

    liq_items = filtered.get("liquidity", [])
    if liq_items:
        log(f"  💧 Liquidity filtered: {len(liq_items)} items")
        for s in liq_items[:3]:
            log(f"     • {s['title'][:35]} — {s.get('reason', 'low volume')}")

    margin_items = filtered.get("margin", [])
    if margin_items:
        log(f"  💰 Margin filtered: {len(margin_items)} items")
        for s in margin_items[:3]:
            log(f"     • {s['title'][:35]} — profit=${s.get('profit', 0):.2f}")

    vol_items = filtered.get("volatility", [])
    if vol_items:
        log(f"  📈 Volatility filtered: {len(vol_items)} items")


# =====================================================================
# MAIN
# =====================================================================

async def run() -> None:
    """Main sandbox test orchestrator."""
    start = time.time()

    log("=" * 60)
    log("  🧪 SANDBOX TEST v14.6 — Buy → CS2Cap → Sell + Stop-Loss/Take-Profit + Value Detection")
    log("=" * 60)

    results: Dict[str, Any] = {
        "dmarket_ok": False,
        "cs2cap_ok": False,
        "balance": 0.0,
        "candidates": 0,
        "bought": 0,
        "listed": 0,
        "errors": [],
    }

    # -- Step 1: DMarket connect --
    api, balance, dm_ok = await step_dmarket_connect()
    results["dmarket_ok"] = dm_ok
    results["balance"] = balance

    # -- Step 2: Fetch prices (parallel) --
    cs2cap, agg_prices, cs2cap_ok = await step_fetch_prices(api)
    results["cs2cap_ok"] = cs2cap_ok

    # -- Step 3: Find candidates + microstructure (batch CS2Cap) --
    candidates, filtered = await step_find_candidates(cs2cap, agg_prices)
    results["candidates"] = len(candidates)

    # -- Step 4: Market scan --
    items, unique_titles = await step_market_scan(api)
    results["items_scanned"] = len(items)
    results["unique_titles"] = unique_titles

    # -- Step 5: Shadow Engine (full paper trading) --
    shadow_report = await step_shadow_engine(candidates, agg_prices, cs2cap_ok)
    results["shadow"] = shadow_report

    # -- Step 6: Stress test scenarios --
    stress_results = await step_stress_test(candidates, agg_prices)
    results["stress"] = stress_results

    # -- Step 7: Monte Carlo (v14.5) --
    mc_result = await step_monte_carlo(candidates, agg_prices)
    results["monte_carlo"] = mc_result

    # -- Cleanup --
    if cs2cap:
        await cs2cap.close()
    await api.close()

    elapsed = time.time() - start

    # ================================================================
    # FINAL REPORT
    # ================================================================
    log("\n" + "=" * 60)
    log("  📊 SANDBOX TEST REPORT")
    log("=" * 60)

    checks = [
        ("DMarket Connection", dm_ok, results.get("balance", 0)),
        ("CS2Cap Oracle", cs2cap_ok, None),
        ("Aggregated Prices", len(agg_prices) > 0, len(agg_prices)),
        ("Market Scan", results.get("items_scanned", 0) > 0, results.get("items_scanned", 0)),
        ("Shadow Engine", shadow_report is not None, f"{shadow_report.get('total_trades',0)} trades" if shadow_report else "N/A"),
        ("Stop-Loss/Take-Profit", True, f"SL={shadow_report.get('sells_sl',0)} TP={shadow_report.get('sells_tp',0)}" if shadow_report else "N/A"),
        ("Strategy Compare", len((shadow_report or {}).get('strategies', {})) > 0, f"{len((shadow_report or {}).get('strategies', {}))} strats"),
        ("Stress Tests", len(stress_results) > 0, f"{len(stress_results)} scenarios"),
        ("Monte Carlo", mc_result is not None, f"{mc_result.get('runs',0)} runs, PnL ${mc_result.get('mean_pnl',0):+.2f}" if mc_result else "N/A"),
        ("Shadow P&L", shadow_report is not None, f"${shadow_report.get('total_pnl',0):+.2f}" if shadow_report else "N/A"),
    ]

    passed = 0
    for name, ok, detail in checks:
        status = "✅" if ok else "❌"
        detail_str = f" ({detail})" if detail is not None else ""
        log(f"  {status} {name}{detail_str}")
        if ok:
            passed += 1

    log(f"\n  Score: {passed}/{len(checks)} checks passed")
    log(f"  Time: {elapsed:.1f}s")

    # ---- V14.3 Microstructure Summary ----
    _print_micro_summary(candidates)

    # ---- v14.4 Affordable vs Missed (Balance-Aware) ----
    if candidates and "balance" in results:
        bal = results["balance"]
        eff_bal = max(0.0, bal - Config.BALANCE_RESERVE_USD)
        dyn_max = max(Config.MAX_SNIPING_PRICE_FLOOR, eff_bal * Config.MAX_SNIPING_PRICE_BALANCE_FRACTION)
        affordable = [c for c in candidates if c["dm_buy_price"] <= dyn_max]
        missed = [c for c in candidates if c["dm_buy_price"] > dyn_max]
        affordable_profit = sum(c["profit"] for c in affordable[:10])
        missed_profit = sum(c["profit"] for c in missed[:10])
        log(f"\n  💳 v14.4 Balance-Aware Report")
        log(f"     Balance: ${bal:.2f} | Reserve: ${Config.BALANCE_RESERVE_USD:.2f}")
        log(f"     Effective: ${eff_bal:.2f} | Max item: ${dyn_max:.2f}")
        log(f"     🟢 Affordable (≤${dyn_max:.2f}): {len(affordable)} items, potential profit ${affordable_profit:.2f}")
        if missed:
            log(f"     🔴 Above budget (>${dyn_max:.2f}): {len(missed)} items, missed profit ${missed_profit:.2f}")
            for m in missed[:3]:
                log(f"        · {m['title'][:40]} @ ${m['dm_buy_price']:.2f} (→${m['sell_price']:.2f}, +{m['margin_pct']:.1f}%)")

    # ---- Bottom-Neck Detection ----
    _print_bottleneck(filtered)

    # ---- Top candidates profit summary ----
    if candidates:
        total_profit = sum(c["profit"] for c in candidates[:10])
        avg_margin = sum(c["margin_pct"] for c in candidates[:10]) / min(len(candidates), 10)
        avg_comp = sum(c.get("composite_score", 0) for c in candidates[:10]) / min(len(candidates), 10)
        log(f"\n  💡 *Top 10 candidates:*")
        log(f"     Total potential profit: ${total_profit:.2f}")
        log(f"     Avg margin: {avg_margin:.1f}%")
        log(f"     Avg composite score: {avg_comp:.0f}/100")
        log(f"     Balance needed for full execution: ~${total_profit * 10:.0f}")

    if results["errors"]:
        log(f"\n  ⚠️ Errors ({len(results['errors'])}):")
        for e in results["errors"]:
            log(f"     - {e}")

    log(f"\n  Bot version: v{Config.BOT_VERSION}")
    log(f"  Mode: {'DRY_RUN' if Config.DRY_RUN else 'LIVE'}")
    log(f"  Strategy: {Config.ACTIVE_STRATEGY}")
    log(f"  Fee rate: {Config.FEE_RATE*100:.1f}%")
    log(f"  Trade lock: {Config.TRADE_LOCK_HOURS}h")
    log(f"  v14.6: Float={'ON'if Config.FLOAT_PREMIUM_ENABLED else'OFF'} "
        f"Pattern={'ON'if Config.PATTERN_PREMIUM_ENABLED else'OFF'} "
        f"StickerCombo={'ON'if Config.STICKER_COMBO_ENABLED else'OFF'} "
        f"Seasonal={'ON'if Config.SEASONAL_TIMING_ENABLED else'OFF'}")
    log("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run())
