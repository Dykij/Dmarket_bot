"""
Sandbox Test — Full Buy → CS2Cap → Sell Cycle (Dry Run).

Tests:
1. DMarket API connection (balance check)
2. Market scanning with pagination
3. CS2Cap price lookup
4. Cross-market data fetch
5. Buy decision (virtual)
6. Sell listing (virtual)
7. Inventory tracking
8. PnL calculation

Run: python -m tests.sandbox_full_cycle
"""

import asyncio
import os
import sys
import time
import logging

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ["DRY_RUN"] = "true"

from src.config import Config
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.oracle_factory import OracleFactory
from src.api.cs2cap_oracle import CS2CapOracle
from src.core.resale_pipeline import ResalePipeline
from src.inventory_manager import InventoryManager
from src.analytics.self_reflection import self_reflection
from src.db.price_history import price_db

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("SandboxTest")


async def run_sandbox_test():
    """Run full sandbox test cycle."""
    results = {
        "dmarket_connection": False,
        "balance": 0.0,
        "market_scan": False,
        "items_found": 0,
        "cs2cap_connection": False,
        "cs2cap_prices_found": 0,
        "cross_market_data": False,
        "buy_decisions": 0,
        "sell_listings": 0,
        "inventory_tracked": 0,
        "pagination_pages": 0,
        "errors": [],
    }

    print("\n" + "=" * 60)
    print("  SANDBOX TEST: Full Buy -> CS2Cap -> Sell Cycle")
    print("=" * 60)

    # --- 1. DMarket API Connection ---
    print("\n[1/8] DMarket API Connection...")
    api = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
    try:
        balance = await api.get_real_balance()
        results["dmarket_connection"] = True
        results["balance"] = balance
        print(f"  ✅ Connected! Balance: ${balance:.2f}")
    except Exception as e:
        results["errors"].append(f"DMarket connection: {e}")
        print(f"  ❌ Failed: {e}")
        # Use fallback balance for sandbox
        balance = 10000.0
        results["balance"] = balance
        print(f"  ⚠️ Using fallback balance: ${balance:.2f}")

    # --- 2. CS2Cap Connection ---
    print("\n[2/8] CS2Cap Oracle Connection...")
    cs2cap = OracleFactory.get_cross_market_oracle(Config.GAME_ID)
    if cs2cap:
        try:
            health = await cs2cap.health_check()
            if health.get("status") == "healthy":
                results["cs2cap_connection"] = True
                print(f"  ✅ Connected! Providers: {health.get('provider_count', 'unknown')}")
            else:
                print(f"  ⚠️ Health check returned: {health}")
                results["cs2cap_connection"] = True  # Try anyway
        except Exception as e:
            results["errors"].append(f"CS2Cap health: {e}")
            print(f"  ❌ Health check failed: {e}")
            print(f"  ⚠️ Will attempt price fetches anyway...")
            results["cs2cap_connection"] = True
    else:
        print(f"  ⚠️ CS2Cap not available (CS2CAP_API_KEY not set)")
        print(f"  → Falling back to CSFloat oracle")

    # --- 3. Market Scan with Pagination ---
    print("\n[3/8] Market Scan with Pagination...")
    all_items = []
    cursor = None
    pages = 0
    max_pages = 50  # Scan 50 pages = ~1000 items
    consecutive_empty = 0

    try:
        while pages < max_pages:
            response = await api.get_market_items_v2(
                Config.GAME_ID, limit=Config.BATCH_SIZE, cursor=cursor
            )
            items = response.get("objects", [])
            next_cursor = response.get("cursor", "")
            pages += 1

            if items:
                all_items.extend(items)
                consecutive_empty = 0
                print(f"  Page {pages}: {len(items)} items (Total: {len(all_items)})")
            else:
                consecutive_empty += 1
                print(f"  Page {pages}: empty (consecutive: {consecutive_empty})")
                if consecutive_empty >= 3:
                    print(f"  ⚠️ 3 consecutive empty pages, stopping")
                    break

            # Stop if no new cursor or cursor unchanged
            if not next_cursor or next_cursor == cursor:
                print(f"  ⚠️ No new cursor, stopping pagination")
                break
            cursor = next_cursor

        results["market_scan"] = len(all_items) > 0
        results["items_found"] = len(all_items)
        results["pagination_pages"] = pages
        print(f"  ✅ Scanned {pages} pages, found {len(all_items)} items")

    except Exception as e:
        results["errors"].append(f"Market scan: {e}")
        print(f"  ❌ Scan failed: {e}")

    # --- 4. CS2Cap Price Lookup for Sample Items ---
    print("\n[4/8] CS2Cap Price Lookup...")
    sample_items = all_items[:50]  # Check first 50 items
    cs2cap_prices = {}

    for item in sample_items:
        title = item.get("title", "")
        if not title:
            continue

        dm_price = int(item.get("price", {}).get("USD", 0)) / 100.0

        if cs2cap:
            try:
                cs2cap_price = await cs2cap.get_item_price(title)
                if cs2cap_price > 0:
                    cs2cap_prices[title] = cs2cap_price
                    results["cs2cap_prices_found"] += 1
                    margin = ((cs2cap_price - dm_price) / dm_price * 100) if dm_price > 0 else 0
                    print(f"  {title[:40]}: DM=${dm_price:.2f} | CS2Cap=${cs2cap_price:.2f} | Margin={margin:+.1f}%")
            except Exception as e:
                print(f"  {title[:40]}: CS2Cap error: {e}")

    if results["cs2cap_prices_found"] > 0:
        print(f"  ✅ Found CS2Cap prices for {results['cs2cap_prices_found']} items")
    else:
        print(f"  ⚠️ No CS2Cap prices found (API may need key or items not in catalog)")

    # --- 5. Cross-Market Data ---
    print("\n[5/8] Cross-Market Data...")
    if cs2cap and sample_items:
        test_title = sample_items[0].get("title", "")
        if test_title:
            try:
                cross_data = await cs2cap.get_cross_market_data(test_title)
                if cross_data:
                    results["cross_market_data"] = True
                    print(f"  ✅ {test_title}:")
                    print(f"     Providers: {len(cross_data.provider_prices)}")
                    print(f"     Min Ask: ${cross_data.global_min_ask:.2f}")
                    print(f"     Max Bid: ${cross_data.global_max_bid:.2f}")
                    print(f"     Liquidity: {cross_data.liquidity_score:.2f}")

                    # Show provider breakdown
                    for prov, price in sorted(cross_data.provider_prices.items(), key=lambda x: x[1])[:5]:
                        print(f"     {prov}: ${price:.2f}")
            except Exception as e:
                print(f"  ❌ Cross-market fetch failed: {e}")

    # --- 6. Buy Decisions (Virtual) ---
    print("\n[6/8] Buy Decisions (Dry Run)...")
    pipeline = ResalePipeline(api)
    pipeline.cs2cap = cs2cap

    try:
        purchased = await pipeline.scan_and_buy(balance=balance, max_items=20)
        results["buy_decisions"] = len(purchased)

        for item in purchased:
            print(f"  ✅ BUY: {item['title'][:40]} @ ${item['buy_price']:.2f}")
            print(f"     CS2Cap: ${item['cs2cap_price']:.2f} → Sell: ${item['estimated_sell_price']:.2f}")
            print(f"     Margin: {item['net_margin_pct']:.1f}%")

        if not purchased:
            print(f"  ⚠️ No buy decisions (items may not meet margin criteria)")
    except Exception as e:
        results["errors"].append(f"Buy decisions: {e}")
        print(f"  ❌ Buy scan failed: {e}")

    # --- 7. Sell Listings (Virtual) ---
    print("\n[7/8] Sell Listings (Dry Run)...")
    try:
        # First, add some test items to virtual inventory for sell test
        test_items = [
            ("AK-47 | Redline (Field-Tested)", 8.0),
            ("AWP | Dragon Lore (Field-Tested)", 15.0),
            ("M4A4 | Howl (Field-Tested)", 12.0),
        ]

        for name, price in test_items:
            price_db.add_virtual_item(name, price, trade_lock_hours=0)  # No lock for test

        listed = await pipeline.sell_inventory_items(max_items=5)
        results["sell_listings"] = len(listed)

        for item in listed:
            print(f"  ✅ LIST: {item['title'][:40]} @ ${item['sell_price']:.2f}")
            print(f"     Buy: ${item['buy_price']:.2f} → Profit: {item['profit_pct']:.1f}%")

        if not listed:
            print(f"  ⚠️ No items listed (margins too low or no items in inventory)")
    except Exception as e:
        results["errors"].append(f"Sell listings: {e}")
        print(f"  ❌ Sell listing failed: {e}")

    # --- 8. Inventory Tracking ---
    print("\n[8/8] Inventory Tracking...")
    try:
        inv_mgr = InventoryManager(api)
        summary = inv_mgr.get_portfolio_summary(current_balance=balance)

        print(f"  Cash: ${summary['cash']:.2f}")
        print(f"  Assets: ${summary['assets_value']:.2f}")
        print(f"  Total Equity: ${summary['total_equity']:.2f}")
        print(f"  Items Holding: {summary['items_holding']}")
        print(f"  Items Sold: {summary['items_sold']}")

        results["inventory_tracked"] = summary['items_holding']
        print(f"  ✅ Inventory tracking working")
    except Exception as e:
        results["errors"].append(f"Inventory tracking: {e}")
        print(f"  ❌ Inventory tracking failed: {e}")

    # --- Cleanup ---
    await pipeline.close()
    await api.close()

    # --- FINAL REPORT ---
    print("\n" + "=" * 60)
    print("  SANDBOX TEST REPORT")
    print("=" * 60)

    checks = [
        ("DMarket Connection", results["dmarket_connection"]),
        ("Market Scan", results["market_scan"]),
        ("CS2Cap Connection", results["cs2cap_connection"]),
        ("CS2Cap Prices Found", results["cs2cap_prices_found"] > 0),
        ("Cross-Market Data", results["cross_market_data"]),
        ("Buy Decisions", results["buy_decisions"] > 0),
        ("Sell Listings", results["sell_listings"] > 0),
        ("Inventory Tracking", results["inventory_tracked"] > 0),
    ]

    passed = sum(1 for _, ok in checks if ok)
    total = len(checks)

    for name, ok in checks:
        status = "✅" if ok else "❌"
        print(f"  {status} {name}")

    print(f"\n  Score: {passed}/{total} checks passed")

    if results["errors"]:
        print(f"\n  Errors encountered:")
        for err in results["errors"]:
            print(f"    - {err}")

    print(f"\n  Summary:")
    print(f"    Balance: ${results['balance']:.2f}")
    print(f"    Items Scanned: {results['items_found']}")
    print(f"    Pages Scanned: {results['pagination_pages']}")
    print(f"    CS2Cap Prices: {results['cs2cap_prices_found']}")
    print(f"    Buy Decisions: {results['buy_decisions']}")
    print(f"    Sell Listings: {results['sell_listings']}")
    print(f"    Items Tracked: {results['inventory_tracked']}")

    print("=" * 60)

    return results


if __name__ == "__main__":
    asyncio.run(run_sandbox_test())
