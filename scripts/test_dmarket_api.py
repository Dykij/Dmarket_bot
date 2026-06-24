#!/usr/bin/env python3
"""
Diagnostic script: verify DMarket API connectivity and key permissions.

Run before starting the bot in production. Checks:
  1. Balance endpoint (auth + read)
  2. Aggregated prices endpoint (market data)
  3. Market items endpoint (cheapest listings)
  4. User inventory endpoint (auth + inventory read)

Usage:
    .venv/bin/python scripts/test_dmarket_api.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BASE_DIR = str(Path(__file__).resolve().parent.parent)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from dotenv import load_dotenv

load_dotenv(Path(BASE_DIR) / ".env")

from src.api.dmarket_api_client import DMarketAPIClient
from src.config import Config
from src.utils.vault import vault


async def main() -> int:
    print("=" * 60)
    print("DMarket API Diagnostic")
    print("=" * 60)

    pub_key = os.getenv("DMARKET_PUBLIC_KEY", "").strip()
    sec_key = vault.get_dmarket_secret()

    if not pub_key or not sec_key:
        print("ERROR: DMarket API keys not configured in .env")
        return 1

    if pub_key.startswith("ROTATE_ME") or sec_key.startswith("ROTATE_ME"):
        print("ERROR: API keys are placeholders (ROTATE_ME). Insert real keys.")
        return 1

    api = DMarketAPIClient(public_key=pub_key, secret_key=sec_key)

    try:
        # 1. Balance
        print("\n[1/4] Fetching account balance...")
        balance = await api.get_real_balance()
        print(f"  USD balance: ${balance:.2f}")

        # 2. Aggregated prices
        print("\n[2/4] Fetching aggregated prices for CS2...")
        agg = await api.get_aggregated_prices(Config.GAME_ID)
        print(f"  Items returned: {len(agg)}")
        if agg:
            sample = list(agg.items())[:3]
            for title, data in sample:
                print(
                    f"    {title[:40]:40} "
                    f"ask=${data['best_ask']:.2f} bid=${data['best_bid']:.2f} "
                    f"(asks={data['ask_count']} bids={data['bid_count']})"
                )
        else:
            print("  WARNING: empty aggregated prices — bot will skip cycles.")

        # 3. Market items for a sample title
        print("\n[3/4] Fetching cheapest market listings...")
        market_items = await api.get_market_items_v2(Config.GAME_ID, limit=5)
        objects = market_items.get("objects", [])
        print(f"  Listings returned: {len(objects)}")
        for it in objects[:3]:
            title = it.get("title", "?")
            price = int(it.get("price", {}).get("USD", 0)) / 100.0
            print(f"    {title[:40]:40} ${price:.2f}")

        # 4. User inventory
        print("\n[4/4] Fetching user inventory...")
        inv = await api.get_user_inventory(Config.GAME_ID, limit=5)
        inv_objects = inv.get("objects", [])
        print(f"  Inventory items returned: {len(inv_objects)}")

        print("\n" + "=" * 60)
        if len(agg) > 0 and len(objects) > 0:
            print("RESULT: API connectivity OK. Bot should be able to scan.")
            return 0
        else:
            print("RESULT: API connected but no market data. Check keys/rate-limits/IP.")
            return 2

    except Exception as e:
        print(f"\nERROR: {type(e).__name__}: {e}")
        print("RESULT: API call failed. Check keys, network, and DMarket status.")
        return 1
    finally:
        await api.close()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
