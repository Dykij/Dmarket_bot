"""
Sandbox Test v14.3 — Full Buy → CS2Cap → Sell Cycle (Dry Run).

Fast, robust test of the bot's ability to find and execute profitable
arbitrage opportunities. Runs in <60 seconds using batch API endpoints
and parallel execution.

Features:
- No CS2Cap catalog required (uses /prices/batch, takes hash_names directly)
- Parallel DMarket + CS2Cap calls via asyncio.gather
- Step-level timeouts (no single step blocks >15 seconds)
- Real margin calculation with dynamic fee estimation
- Microstructure scoring (OBI, CVD, VPIN, VWAP, composite buy score)
- Bottom-neck detection (what gets filtered and why)
- Profitability summary with top opportunities

Run: python -m tests.sandbox_full_cycle
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

    # ---- Phase 1: Rank by spread-weighted volume, track filters ----
    min_spread = Config.FEE_RATE * 100 * 2 + 3  # fee-aware minimum spread %
    ranked = []
    for title, agg in agg_prices.items():
        best_bid = agg.get("best_bid", 0) or 0
        best_ask = agg.get("best_ask", 0) or 0
        ask_cnt = agg.get("ask_count", 0) or 0
        bid_cnt = agg.get("bid_count", 0) or 0
        if best_bid <= 0 or best_ask <= 0:
            continue
        spread = best_bid - best_ask
        if spread <= 0:
            filtered["spread"].append({
                "title": title, "reason": "negative/zero spread",
                "best_bid": best_bid, "best_ask": best_ask,
            })
            continue
        spread_pct = spread / best_ask * 100
        volume = ask_cnt + bid_cnt

        if spread_pct < min_spread:
            filtered["spread"].append({
                "title": title, "reason": f"spread {spread_pct:.1f}% < min {min_spread:.0f}%",
                "best_bid": best_bid, "best_ask": best_ask, "volume": volume,
            })
            continue

        # Liquidity filter: items with extremely low volume
        if volume < 5:
            filtered["liquidity"].append({
                "title": title, "reason": f"volume={volume} too low",
                "best_ask": best_ask, "best_bid": best_bid, "spread_pct": spread_pct,
            })
            continue

        score = spread_pct * math.sqrt(max(volume, 1))
        ranked.append((title, best_ask, best_bid, spread_pct, volume, score,
                        ask_cnt, bid_cnt))

    ranked.sort(key=lambda x: -x[5])
    top = ranked[:20]  # Top 20 most promising
    log_info(f"Top {len(top)} candidates (spread > {min_spread:.0f}% min)")

    if not top:
        log_warn("No candidates meet minimum spread threshold")
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

    # ---- Phase 3: Evaluate each candidate + microstructure ----
    from src.api.dmarket_api_client.fees import _FeesMixin

    candidates = []
    for item in top:
        title, ask, bid, spread_pct, volume, score, ask_cnt, bid_cnt = item
        cs_price = cs2cap_prices.get(title, 0)
        dm_buy_price = ask

        # Fee estimate from volume
        fee = _FeesMixin._estimate_fee_from_volume(ask_count=volume, bid_count=volume)
        total_fee = fee + Config.WITHDRAWAL_FEE_RATE

        # Estimate sell price: use CS2Cap if available, else DMarket bid
        if cs_price > 0:
            sell_price = cs_price * 0.97  # 3% undercut vs global lowest
            ref = f"CS2Cap=${cs_price:.2f}"
        else:
            sell_price = bid * 0.99
            ref = f"DMarket bid=${bid:.2f}"

        net = sell_price * (1 - total_fee)
        profit = net - dm_buy_price
        margin_pct = (profit / dm_buy_price * 100) if dm_buy_price > 0 else 0

        if profit <= 0 or margin_pct < 1:
            filtered["margin"].append({
                "title": title, "reason": f"profit=${profit:.3f} margin={margin_pct:.1f}%",
                "best_ask": ask, "cs2cap_price": cs_price, "sell_price": sell_price,
            })
            continue

        # ---- Phase 3a: Microstructure scoring ----
        sales = _generate_synthetic_sales(ask, bid, ask_cnt, bid_cnt)
        has_trades = len(sales) >= 3

        # OBI — always computable from agg data
        obi_val = simple_obi(bid, ask, bid_cnt, ask_cnt)

        # VWAP
        if has_trades:
            vwap_val, vwap_vol, _ = compute_vwap(sales)
            vwap_discount_sig = vwap_signal(ask, sales, threshold=0.90)
        else:
            vwap_val = 0.0
            vwap_discount_sig = None

        # CVD
        cvd_val = compute_cvd(sales) if has_trades else 0.0

        # VPIN
        vpin_val = compute_vpin(sales, n_buckets=4) if has_trades else None

        # Kyle lambda
        kyle_lam = kyle_lambda(sales) if has_trades else None

        # Adverse selection
        adverse_pass, adverse_reason = (
            adverse_selection_check(sales) if has_trades
            else (True, "no data")
        )

        # Parkinson volatility → regime
        park_vol = realized_vol_parkinson(sales) if has_trades else None
        vol_regime = classify_volatility_regime(park_vol or 0.15)

        # Composite buy score
        vwap_disc = vwap_discount_sig if vwap_discount_sig is not None else 0.0
        vpin_safe = vpin_val if vpin_val is not None else 0.5
        ofi = (bid_cnt - ask_cnt)  # proxy OFI from order counts

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

        # Microstructure filter flags
        micro_filter = _check_microstructure(obi_val, cvd_val, vwap_val, ask, vpin_val)

        # High-vol filter tracking
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
            # Microstructure fields
            "obi": obi_val,
            "cvd": cvd_val,
            "vwap": round(vwap_val, 4),
            "vpin": vpin_val,
            "vwap_discount": round(vwap_disc, 4),
            "vol_regime": vol_regime,
            "park_vol": round(park_vol, 4) if park_vol else None,
            "kyle_lambda": kyle_lam,
            "adverse_pass": adverse_pass,
            "composite_score": round(comp_score * 100, 1),  # 0-100 scale
            "micro_filter": micro_filter,
        })

    # Sort by composite score then margin
    candidates.sort(key=lambda x: -(x["composite_score"] + x["margin_pct"] * 2))
    log_info(f"Candidates with net profit > 0: {len(candidates)}")
    log_info(f"Filtered — spread: {len(filtered['spread'])}, liquidity: {len(filtered.get('liquidity', []))}, "
             f"margin: {len(filtered['margin'])}, volatility: {len(filtered.get('volatility', []))}")

    if candidates:
        log(f"\n  {'Item':<30} {'Buy':>6} {'Sell':>6} {'Profit':>6} {'Marg':>5} {'Comp':>5} {'Micro Filter'}")
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

    return all_items, titles_seen


# =====================================================================
# STEP 5: Buy Simulation + Inventory
# =====================================================================
async def step_simulate_buy(
    candidates: List[Dict],
    api: DMarketAPIClient,
    balance: float,
) -> int:
    """Simulate buying top candidates into virtual inventory."""
    log("\n[5/6] 🛒 Simulated Buying")

    if not candidates:
        log_warn("No candidates to buy")
        return 0

    # Buy top candidates that fit in budget and inventory caps
    bought = 0
    current_held = 0
    total_cost = 0.0
    max_items = min(Config.MAX_TOTAL_INVENTORY_ITEMS, 30)
    max_value = Config.MAX_TOTAL_INVENTORY_VALUE

    for c in candidates:
        if bought >= 10:
            break
        price = c["dm_buy_price"]
        if price > Config.MAX_SNIPING_PRICE_USD:
            continue
        if total_cost + price > min(balance, max_value):
            continue
        if current_held >= max_items:
            break

        # Add to virtual inventory
        price_db.add_virtual_item(c["title"], price, trade_lock_hours=Config.TRADE_LOCK_HOURS)
        bought += 1
        current_held += 1
        total_cost += price

        cs = c.get("composite_score", 0)
        log(
            f"  🛒 {c['title'][:40]} @ ${price:.2f} "
            f"(sell ${c['sell_price']:.2f}, margin {c['margin_pct']:.1f}%, comp {cs:.0f})"
        )

    log_ok(f"Virtual buys: {bought} items, total cost: ${total_cost:.2f}")
    return bought


# =====================================================================
# STEP 6: Sell Simulation + Final Report
# =====================================================================
async def step_simulate_sell() -> int:
    """Simulate selling idle items via auto-resale."""
    log("\n[6/6] 💰 Simulated Selling")

    idle = price_db.get_virtual_inventory(status="idle", only_unlocked=True)
    if not idle:
        log_warn("No idle items to sell")
        return 0

    listed = 0
    for it in idle[:5]:
        buy_price = it["buy_price"]
        sell_price = round(buy_price * 1.05, 2)
        fee = round(sell_price * Config.FEE_RATE, 4)
        profit = sell_price - buy_price - fee
        log(
            f"  📤 {it['hash_name'][:40]} → list ${sell_price:.2f} "
            f"(profit ${profit:+.2f})"
        )
        listed += 1

    log_ok(f"Ready to list: {listed} items")
    return listed


# =====================================================================
# MICROSTRUCTURE REPORT HELPERS
# =====================================================================
def _print_micro_summary(candidates: List[Dict]) -> None:
    """Print V14.3 Microstructure Summary section."""
    if not candidates:
        return

    obi_buy = sum(1 for c in candidates if c.get("obi", 0) > 0)
    obi_sell = sum(1 for c in candidates if c.get("obi", 0) < 0)
    obi_neutral = sum(1 for c in candidates if c.get("obi", 0) == 0)
    cvd_accum = sum(1 for c in candidates if c.get("cvd", 0) > 0)
    vpin_alert = sum(1 for c in candidates
                     if c.get("vpin") is not None and c["vpin"] > 0.4)
    top_comp = max((c.get("composite_score", 0) for c in candidates), default=0)

    log("\n📊 V14.3 Microstructure Summary")
    log(f"  OBI signals: {obi_buy} buy / {obi_sell} sell / {obi_neutral} neutral")
    log(f"  CVD accumulation: {cvd_accum} items")
    log(f"  VPIN alerts (>0.4): {vpin_alert} items (high informed trading risk)")
    log(f"  Top composite score: {top_comp:.0f}/100")

    # Volatility regime distribution
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

    # Spread-filtered
    spread_items = filtered.get("spread", [])
    if spread_items:
        log(f"  📉 Spread/Margin filtered: {len(spread_items)} items")
        for s in spread_items[:5]:
            reason = s.get("reason", "?")
            log(f"     • {s['title'][:35]} — {reason}")

    # Liquidity-filtered
    liq_items = filtered.get("liquidity", [])
    if liq_items:
        log(f"  💧 Liquidity filtered: {len(liq_items)} items")
        for s in liq_items[:5]:
            log(f"     • {s['title'][:35]} — {s.get('reason', 'low volume')}")

    # Margin-filtered
    margin_items = filtered.get("margin", [])
    if margin_items:
        log(f"  💸 Margin filtered: {len(margin_items)} items")
        for s in margin_items[:5]:
            log(f"     • {s['title'][:35]} — {s.get('reason', '?')}")

    # Volatility-filtered
    vol_items = filtered.get("volatility", [])
    if vol_items:
        log(f"  📈 Volatility filtered: {len(vol_items)} items")
        for s in vol_items[:5]:
            park = s.get("park_vol")
            pv_str = f"park_vol={park:.2f}" if park else "?"
            log(f"     • {s['title'][:35]} — {s.get('vol_regime', 'high')} ({pv_str})")


# =====================================================================
# MAIN
# =====================================================================
async def run() -> None:
    """Main sandbox test orchestrator."""
    start = time.time()

    log("=" * 60)
    log("  🧪 SANDBOX TEST v14.3 — Buy → CS2Cap → Sell + Microstructure")
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

    # -- Step 5: Buy simulation --
    bought = await step_simulate_buy(candidates, api, balance)
    results["bought"] = bought

    # -- Step 6: Sell simulation --
    listed = await step_simulate_sell()
    results["listed"] = listed

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
        ("Profitable Candidates", len(candidates) > 0, len(candidates)),
        ("Market Scan", results.get("items_scanned", 0) > 0, results.get("items_scanned", 0)),
        ("Buy Simulation", bought > 0, bought),
        ("Sell Simulation", listed > 0, listed),
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
    log("=" * 60)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    asyncio.run(run())
