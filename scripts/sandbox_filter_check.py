#!/usr/bin/env python3
"""
Sandbox filter check — evaluate how many DMarket candidates pass the
configured filters without making real purchases.

Run after changing .env to validate filter looseness/tightness.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

BASE_DIR = str(Path(__file__).resolve().parent.parent)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ["DRY_RUN"] = "true"

from src.api.dmarket_api_client import DMarketAPIClient
from src.api.oracle_factory import OracleFactory
from src.config import Config
from src.core.limit_orders import _LimitOrderMixin
from src.core.target_sniping.filter import _FilterMixin
from src.risk.liquidity_manager import LiquidityManager
from src.utils.vault import vault


class _DummySnipingLoop(_FilterMixin):
    """Minimal stand-in for SnipingLoop to run _evaluate_candidate."""

    def __init__(self, client, liquidity, buy_budget):
        self.client = client
        self.liquidity = liquidity
        self.buy_budget = buy_budget
        self._oracle_price_cache = {}
        self.risk = None
        self._diag_cycle_id = -1

    def _skip_if_locked(self, item_id: str, title: str) -> bool:
        return False

    def _calculate_float_premium(self, attrs: dict) -> float:
        return 1.0

    def is_dirty_bs(self, attrs: dict) -> bool:
        return False


async def main() -> int:
    print("=" * 70)
    print("Sandbox Filter Check")
    print("=" * 70)
    print(f"DRY_RUN: {Config.DRY_RUN}")
    print(f"MIN_SPREAD_PCT: {Config.MIN_SPREAD_PCT}%")
    print(f"INTRA_MIN_SPREAD_PCT: {Config.INTRA_MIN_SPREAD_PCT}%")
    print(f"WITHDRAWAL_FEE_RATE: {Config.WITHDRAWAL_FEE_RATE * 100:.2f}%")
    print(f"STRICT_MICROSTRUCTURE_FILTERS: {Config.STRICT_MICROSTRUCTURE_FILTERS}")
    print(f"OBI_ENABLED: {Config.OBI_ENABLED}")
    print(f"OFI_ENABLED: {Config.OFI_ENABLED}")
    print(f"PRICE_RANGE_SCAN_ENABLED: {Config.PRICE_RANGE_SCAN_ENABLED}")
    print(f"MIN_BID_ASK_COUNT: {Config.MIN_BID_ASK_COUNT}")
    print(f"MIN_TOTAL_SALES: {Config.MIN_TOTAL_SALES}")
    print("-" * 70)

    pub_key = os.getenv("DMARKET_PUBLIC_KEY", "").strip()
    sec_key = vault.get_dmarket_secret()

    if not pub_key or not sec_key:
        print("ERROR: DMarket API keys not configured")
        return 1

    client = DMarketAPIClient(public_key=pub_key, secret_key=sec_key)
    oracle = OracleFactory.get_oracle(Config.GAME_ID)
    liquidity = LiquidityManager()

    try:
        balance = await client.get_real_balance()
        print(f"Balance: ${balance:.2f}")

        print("\n[1/3] Fetching aggregated prices (top-100 by volume)...")
        agg_prices = await client.get_aggregated_prices(Config.GAME_ID)
        print(f"  Got {len(agg_prices)} aggregated price entries")

        if not agg_prices:
            print("ERROR: no aggregated prices — bot cannot scan")
            return 2

        top_titles = sorted(
            agg_prices.keys(),
            key=lambda t: agg_prices[t].get("ask_count", 0) + agg_prices[t].get("bid_count", 0),
            reverse=True,
        )[: Config.AGG_SCAN_TOP_N]

        print(f"\n[2/3] Fetching cheapest listings for top-{len(top_titles)} titles...")
        items: list[dict] = []
        sem = asyncio.Semaphore(2)

        async def fetch_one(title: str) -> list[dict]:
            async with sem:
                try:
                    resp = await client.get_market_items_v2(
                        Config.GAME_ID, limit=Config.LISTINGS_FETCH_LIMIT, title=title
                    )
                    # Pacing to respect DMarket public endpoint rate limits.
                    await asyncio.sleep(0.2)
                    return resp.get("objects", [])
                except Exception as e:
                    print(f"  fetch failed for {title}: {e}")
                    return []

        listings_per_title = await asyncio.gather(*[fetch_one(t) for t in top_titles])
        seen_ids = set()
        for title, listings in zip(top_titles, listings_per_title):
            for lst in sorted(
                listings,
                key=lambda x: int(x.get("price", {}).get("USD", 0)),
            ):
                item_id = lst.get("itemId", "")
                if item_id and item_id not in seen_ids:
                    seen_ids.add(item_id)
                    items.append(lst)
                    break

        print(f"  Got {len(items)} unique cheapest listings")

        if Config.PRICE_RANGE_SCAN_ENABLED:
            print("\n[2b/3] Fetching price-range scan listings...")
            pr_items: list[dict] = []
            cursor = ""
            for page in range(Config.PRICE_RANGE_MAX_PAGES):
                params: dict = {
                    "limit": 100,
                    "priceFrom": str(int(Config.PRICE_RANGE_MIN_USD * 100)),
                    "priceTo": str(int(Config.PRICE_RANGE_MAX_USD * 100)),
                }
                if cursor:
                    params["cursor"] = cursor
                try:
                    resp = await client.get_market_items_v2(Config.GAME_ID, **params)
                except Exception as e:
                    print(f"  price-range page failed: {e}")
                    break
                page_items = resp.get("objects", [])
                if not page_items:
                    break
                pr_items.extend(page_items)
                await asyncio.sleep(0.3)
                cursor = resp.get("cursor", "")
                if not cursor:
                    break

            by_title: dict[str, dict] = {}
            for it in pr_items:
                title = it.get("title", "")
                if not title:
                    continue
                price_cents = int(it.get("price", {}).get("USD", 0))
                if title not in by_title or price_cents < int(by_title[title].get("price", {}).get("USD", 0)):
                    by_title[title] = it

            new = 0
            for it in by_title.values():
                if it.get("itemId", "") not in seen_ids:
                    seen_ids.add(it.get("itemId", ""))
                    items.append(it)
                    new += 1
            print(f"  Added {new} unique price-range listings (total {len(items)})")

        print("\n[3/3] Running filter pipeline (no real buys)...")

        # Bulk fees
        candidate_ids = [
            it.get("itemId") for it in items if it.get("itemId") and int(it.get("price", {}).get("USD", 0)) > 0
        ]
        item_id_to_title = {it["itemId"]: it["title"] for it in items if it.get("itemId") and it.get("title")}
        title_volume = {
            t: agg.get("ask_count", 0) + agg.get("bid_count", 0)
            for t, agg in agg_prices.items()
        }
        bulk_fees = await client.get_item_fee_bulk(
            Config.GAME_ID, candidate_ids, title_volume=title_volume, item_id_to_title=item_id_to_title
        )

        # Oracle snapshots for all aggregated-price titles so cross-market
        # targets and filter validation have reference prices.
        cs_snapshots: dict = {}
        cs_bids: dict = {}
        all_agg_titles = list(agg_prices.keys())[:100]
        if oracle is not None:
            try:
                if hasattr(oracle, "get_prices_batch"):
                    cs_snapshots = await oracle.get_prices_batch(all_agg_titles)
                if hasattr(oracle, "get_bids_batch"):
                    cs_bids = await oracle.get_bids_batch(all_agg_titles)
                print(f"  Oracle snapshots: {len(cs_snapshots)} asks, {len(cs_bids)} bids")
            except Exception as e:
                print(f"  Oracle batch failed: {e}")

        loop = _DummySnipingLoop(client, liquidity, Config.MAX_PRICE_USD)
        current_margin = Config.MIN_SPREAD_PCT / 100.0

        results: list[dict] = []
        reasons: dict[str, int] = {}

        for item in items:
            title = item.get("title", "")
            try:
                result = await loop._evaluate_candidate(
                    item=item,
                    game_id=Config.GAME_ID,
                    oracle=oracle,
                    agg_prices=agg_prices,
                    bulk_fees=bulk_fees,
                    current_balance=balance,
                    current_margin=current_margin,
                    cs_snapshots=cs_snapshots,
                    cs_bids=cs_bids,
                    saturation_counts={},
                    effective_balance=max(0.0, balance - Config.BALANCE_RESERVE_USD),
                    dynamic_max_price=min(Config.MAX_SNIPING_PRICE_USD, balance * Config.MAX_SNIPING_PRICE_BALANCE_FRACTION),
                )
                if result:
                    results.append(
                        {
                            "title": title,
                            "base_price": result["base_price"],
                            "list_price": result["list_price"],
                            "best_bid": result["best_bid"],
                            "best_ask": result["best_ask"],
                            "strategy": result["strategy"],
                        }
                    )
                else:
                    reasons["filtered"] = reasons.get("filtered", 0) + 1
            except Exception as e:
                reasons[f"error:{type(e).__name__}"] = reasons.get(f"error:{type(e).__name__}", 0) + 1

        print("\n" + "=" * 70)
        print(f"RESULTS: {len(results)} candidates passed all filters out of {len(items)} items")
        print("=" * 70)

        if results:
            print("\nTop candidates:")
            top_results = sorted(results, key=lambda x: x["list_price"] - x["base_price"], reverse=True)[:10]
            for r in top_results:
                spread = r["best_bid"] - r["best_ask"]
                margin = ((r["list_price"] - r["base_price"]) / r["base_price"] * 100) if r["base_price"] > 0 else 0
                print(
                    f"  {r['title'][:40]:40} "
                    f"buy=${r['base_price']:.2f} list=${r['list_price']:.2f} "
                    f"spread=${spread:.2f} margin={margin:.1f}% [{r['strategy']}]"
                )
        else:
            print("\nNo candidates passed. Filters are still too strict or market has no edges.")

        print("\nFilter outcome distribution:")
        for k, v in sorted(reasons.items(), key=lambda x: -x[1]):
            print(f"  {k}: {v}")

        # Cross-market target simulation
        print("\n[4/3] Simulating cross-market buy targets (DMarket ask > Oracle ask)...")
        limit_mixin = _LimitOrderMixin()
        limit_mixin.client = client
        cross_targets = await limit_mixin._execute_cross_market_targets(
            game_id=Config.GAME_ID,
            agg_prices=agg_prices,
            cs_snapshots=cs_snapshots,
            current_balance=balance,
        )
        print(f"  Cross-market targets that would be placed: {cross_targets}")

        print("\n" + "=" * 70)
        if results or cross_targets:
            print(
                f"RESULTS: {len(results)} instant candidates + "
                f"{cross_targets} cross-market target(s) out of {len(items)} items"
            )
        else:
            print("RESULTS: 0 instant candidates and 0 cross-market targets.")
        print("=" * 70)

        return 0 if (results or cross_targets) else 3

    finally:
        await client.close()
        await OracleFactory.close_all()


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
