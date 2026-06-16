"""
Sandbox Test v13.3 — Full Buy → CS2Cap → Sell Cycle (Dry Run).

Fast, robust test of the bot's ability to find and execute profitable
arbitrage opportunities. Runs in <60 seconds using batch API endpoints
and parallel execution.

Features:
- No CS2Cap catalog required (uses /prices/batch, takes hash_names directly)
- Parallel DMarket + CS2Cap calls via asyncio.gather
- Step-level timeouts (no single step blocks >15 seconds)
- Real margin calculation with dynamic fee estimation
- Profitability summary with top opportunities

Run: python -m tests.sandbox_full_cycle
"""

import asyncio
import logging
import os
import sys
import time
from typing import Any, Dict, List, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DRY_RUN"] = "false"  # Allow real market data reads (no buys are executed)
os.environ.setdefault("ENCRYPTION_KEY", "test-key-for-sandbox-reads-only")

from src.config import Config
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.oracle_factory import OracleFactory
from src.api.cs2cap_oracle import CS2CapOracle
from src.db.price_history import price_db

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
# STEP 3: Find Profitable Candidates (batch CS2Cap + spread check)
# =====================================================================
async def step_find_candidates(
    cs2cap: Optional[CS2CapOracle],
    agg_prices: Dict[str, Any],
) -> List[Dict[str, Any]]:
    """Use batch CS2Cap prices to find arbitrage opportunities."""
    log("\n[3/6] 🔍 Finding Profitable Candidates")

    if not agg_prices or not cs2cap:
        log_warn("Missing data — can't evaluate candidates")
        return []

    # Rank by spread-weighted volume
    import math
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
            continue
        spread_pct = spread / best_ask * 100
        volume = ask_cnt + bid_cnt
        # Fee-aware minimum: need spread > expected fee * 2 + 3%
        min_spread = Config.FEE_RATE * 100 * 2 + 3
        if spread_pct < min_spread:
            continue
        score = spread_pct * math.sqrt(max(volume, 1))
        ranked.append((title, best_ask, best_bid, spread_pct, volume, score))

    ranked.sort(key=lambda x: -x[5])
    top = ranked[:20]  # Top 20 most promising
    log_info(f"Top {len(top)} candidates (spread > {Config.FEE_RATE*100*2+3:.0f}% min)")

    if not top:
        log_warn("No candidates meet minimum spread threshold")
        return []

    # Fetch CS2Cap batch prices for top titles (1 HTTP call for all)
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

    # Evaluate each candidate
    candidates = []
    for title, ask, bid, spread_pct, volume, score in top:
        cs_price = cs2cap_prices.get(title, 0)
        dm_buy_price = ask

        # Fee estimate from volume
        from src.api.dmarket_api_client.fees import _FeesMixin
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
            continue

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
        })

    # Sort by margin
    candidates.sort(key=lambda x: -x["margin_pct"])
    log_info(f"Candidates with net profit > 0: {len(candidates)}")

    if candidates:
        log(f"\n  {'Item':<35} {'DM Buy':>7} {'Sell':>7} {'Profit':>7} {'Margin':>7}")
        log(f"  {'─'*35} {'─'*7} {'─'*7} {'─'*7} {'─'*7}")
        for c in candidates[:12]:
            name = c["title"][:33]
            log(
                f"  {name:<35} ${c['dm_buy_price']:>6.2f} "
                f"${c['sell_price']:>6.2f} ${c['profit']:>6.2f} "
                f"{c['margin_pct']:>6.1f}%"
            )
    return candidates


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

        log(
            f"  🛒 {c['title'][:40]} @ ${price:.2f} "
            f"(sell ${c['sell_price']:.2f}, margin {c['margin_pct']:.1f}%)"
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
# MAIN
# =====================================================================
async def run() -> None:
    """Main sandbox test orchestrator."""
    start = time.time()

    log("=" * 60)
    log("  🧪 SANDBOX TEST v13.3 — Buy → CS2Cap → Sell")
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

    # -- Step 3: Find candidates (batch CS2Cap) --
    candidates = await step_find_candidates(cs2cap, agg_prices)
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

    if candidates:
        total_profit = sum(c["profit"] for c in candidates[:10])
        avg_margin = sum(c["margin_pct"] for c in candidates[:10]) / min(len(candidates), 10)
        log(f"\n  💡 *Top 10 candidates:*")
        log(f"     Total potential profit: ${total_profit:.2f}")
        log(f"     Avg margin: {avg_margin:.1f}%")
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
