"""Filter + cross-market target pipeline test (uses live DMarket + Oracle)."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from src.config import Config
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.oracle_factory import OracleFactory
from src.api.multi_source_oracle import MultiSourceOracle
from src.core.limit_orders import _LimitOrderMixin
from src.core.target_sniping.filter import _FilterMixin
from src.core.target_sniping.underpriced import fetch_low_fee_titles, is_dmarket_underpriced
from src.core.limit_orders import _LimitOrderMixin
from src.risk.liquidity_manager import LiquidityManager
from src.utils.vault import vault

from tests.sandbox_comprehensive.common import (
    log,
    log_err,
    log_info,
    log_ok,
    log_warn,
    with_timeout,
)

if TYPE_CHECKING:
    from tests.sandbox_comprehensive.common import SandboxMetrics


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


async def _check_connectivity(
    dmarket: DMarketAPIClient,
    oracle: Optional[MultiSourceOracle],
    metrics: "SandboxMetrics",
) -> tuple[Dict[str, Any], bool]:
    """Check DMarket + Oracle connectivity and fetch aggregated prices."""
    log("\n[PIPELINE] API connectivity")

    balance = await with_timeout(10, dmarket.get_real_balance(), "dmarket balance")
    if balance is not None:
        metrics.dmarket_connected = True
        metrics.balance = balance
        log_ok(f"DMarket balance: ${balance:.2f}")
    else:
        log_warn("DMarket balance fetch failed, using $10000")
        metrics.balance = 10000.0

    agg_prices = await with_timeout(15, dmarket.get_aggregated_prices(Config.GAME_ID), "aggregated prices")
    if not agg_prices:
        log_err("No aggregated prices — aborting pipeline")
        return {}, False

    metrics.agg_titles = len(agg_prices)
    metrics.agg_with_bids = sum(1 for a in agg_prices.values() if a.get("best_ask", 0) > 0)
    log_ok(f"DMarket aggregated: {metrics.agg_titles} titles, {metrics.agg_with_bids} with asks")

    oracle_ok = False
    if oracle is not None:
        try:
            h = await with_timeout(10, oracle.health_check(), "oracle health")
            oracle_ok = bool(h and h.get("status") == "healthy")
        except Exception as e:
            log_warn(f"Oracle health check failed: {e}")

    metrics.oracle_connected = oracle_ok
    if oracle_ok:
        log_ok("Oracle connected")
    else:
        log_warn("Oracle not available — cross-market targets disabled")

    return agg_prices, oracle_ok


async def _fetch_listings(
    dmarket: DMarketAPIClient,
    agg_prices: Dict[str, Any],
    metrics: "SandboxMetrics",
) -> tuple[List[Dict[str, Any]], Dict[str, float]]:
    """Fetch cheapest listing per top title + optional price-range scan."""
    log("\n[PIPELINE] Fetching listings")

    top_titles = sorted(
        agg_prices.keys(),
        key=lambda t: agg_prices[t].get("ask_count", 0) + agg_prices[t].get("bid_count", 0),
        reverse=True,
    )[: Config.AGG_SCAN_TOP_N]

    items: List[Dict[str, Any]] = []
    seen_ids = set()
    sem = asyncio.Semaphore(2)

    async def fetch_one(title: str) -> List[Dict[str, Any]]:
        async with sem:
            try:
                resp = await dmarket.get_market_items_v2(
                    Config.GAME_ID,
                    limit=Config.LISTINGS_FETCH_LIMIT,
                    title=title,
                )
                await asyncio.sleep(0.2)
                return resp.get("objects", [])
            except Exception as e:
                log_err(f"fetch {title}: {e}")
                return []

    listings_per_title = await asyncio.gather(*[fetch_one(t) for t in top_titles])
    for title, listings in zip(top_titles, listings_per_title):
        for lst in sorted(listings, key=lambda x: int(x.get("price", {}).get("USD", 0))):
            item_id = lst.get("itemId", "")
            if item_id and item_id not in seen_ids:
                seen_ids.add(item_id)
                items.append(lst)
                break

    log_info(f"Top-title cheapest listings: {len(items)}")

    if Config.PRICE_RANGE_SCAN_ENABLED:
        log_info("Price-range scan enabled")
        pr_items: List[Dict[str, Any]] = []
        cursor = ""
        for _page in range(Config.PRICE_RANGE_MAX_PAGES):
            params: Dict[str, Any] = {
                "limit": 100,
                "priceFrom": str(int(Config.PRICE_RANGE_MIN_USD * 100)),
                "priceTo": str(int(Config.PRICE_RANGE_MAX_USD * 100)),
            }
            if cursor:
                params["cursor"] = cursor
            try:
                resp = await dmarket.get_market_items_v2(Config.GAME_ID, **params)
            except Exception as e:
                log_err(f"price-range page: {e}")
                break
            page_items = resp.get("objects", [])
            if not page_items:
                break
            pr_items.extend(page_items)
            await asyncio.sleep(0.3)
            cursor = resp.get("cursor", "")
            if not cursor:
                break

        by_title: Dict[str, Dict[str, Any]] = {}
        for it in pr_items:
            title = it.get("title", "")
            if not title:
                continue
            price_cents = int(it.get("price", {}).get("USD", 0))
            prev_cents = int(by_title.get(title, {}).get("price", {}).get("USD", 0))
            if title not in by_title or price_cents < prev_cents:
                by_title[title] = it

        new = 0
        for it in by_title.values():
            if it.get("itemId", "") not in seen_ids:
                seen_ids.add(it.get("itemId", ""))
                items.append(it)
                new += 1
        log_info(f"Price-range unique listings added: {new}")

    # --- v14.8.1 Low-fee items secondary scan ---
    if Config.LOW_FEE_ITEMS_SCAN_ENABLED:
        log_info("Low-fee items scan enabled")
        low_fee_map = await fetch_low_fee_titles(dmarket, Config.GAME_ID)
        if low_fee_map:
            log_info(f"  Low-fee titles: {len(low_fee_map)}")
            lf_titles = list(low_fee_map.keys())[: Config.LOW_FEE_ITEMS_SCAN_LIMIT]
            sem = asyncio.Semaphore(2)

            async def fetch_low_fee_one(title: str) -> List[Dict[str, Any]]:
                async with sem:
                    try:
                        resp = await dmarket.get_market_items_v2(
                            Config.GAME_ID,
                            limit=Config.LISTINGS_FETCH_LIMIT,
                            title=title,
                        )
                        await asyncio.sleep(0.2)
                        return resp.get("objects", [])
                    except Exception as e:
                        log_err(f"low-fee fetch {title}: {e}")
                        return []

            lf_listings_per_title = await asyncio.gather(
                *[fetch_low_fee_one(t) for t in lf_titles]
            )
            lf_added = 0
            for title, listings in zip(lf_titles, lf_listings_per_title):
                for lst in sorted(
                    listings,
                    key=lambda x: int(x.get("price", {}).get("USD", 0)),
                ):
                    item_id = lst.get("itemId", "")
                    if item_id and item_id not in seen_ids:
                        seen_ids.add(item_id)
                        lst["_low_fee_rate"] = low_fee_map.get(title, 0.05)
                        items.append(lst)
                        lf_added += 1
                        break
            log_info(f"  Low-fee unique listings added: {lf_added}")

    metrics.listings_fetched = len(items)
    return items, low_fee_map


async def _fetch_oracle_snapshots(
    oracle: Optional[MultiSourceOracle],
    titles: List[str],
) -> tuple[Dict[str, float], Dict[str, float]]:
    """Fetch Oracle ask/bid snapshots for titles."""
    asks: Dict[str, float] = {}
    bids: Dict[str, float] = {}
    if oracle is None:
        return asks, bids
    try:
        if hasattr(oracle, "get_prices_batch"):
            asks = await oracle.get_prices_batch(titles)
        if hasattr(oracle, "get_bids_batch"):
            bids = await oracle.get_bids_batch(titles)
        log_info(f"Oracle snapshots: {len(asks)} asks, {len(bids)} bids")
    except Exception as e:
        log_warn(f"Oracle batch failed: {e}")
    return asks, bids


async def _run_filters(
    dmarket: DMarketAPIClient,
    items: List[Dict[str, Any]],
    agg_prices: Dict[str, Any],
    cs_asks: Dict[str, float],
    cs_bids: Dict[str, float],
    metrics: "SandboxMetrics",
    low_fee_map: Dict[str, float],
) -> None:
    """Run filter pipeline on fetched listings and count results."""
    log("\n[PIPELINE] Running filter pipeline")

    liquidity = LiquidityManager()
    dummy = _DummySnipingLoop(dmarket, liquidity, metrics.balance)

    candidate_ids = [
        it.get("itemId") for it in items
        if it.get("itemId") and int(it.get("price", {}).get("USD", 0)) > 0
    ]
    item_id_to_title = {
        it["itemId"]: it["title"]
        for it in items if it.get("itemId") and it.get("title")
    }
    title_volume = {
        t: agg.get("ask_count", 0) + agg.get("bid_count", 0)
        for t, agg in agg_prices.items()
    }

    bulk_fees = await with_timeout(
        30,
        dmarket.get_item_fee_bulk(Config.GAME_ID, candidate_ids, title_volume=title_volume, item_id_to_title=item_id_to_title),
        "bulk fees",
    )
    if bulk_fees is None:
        bulk_fees = {}

    # Fetch Oracle snapshots for aggregated titles AND low-fee titles
    # so low-fee candidates have cross-market reference data.
    low_fee_titles = list(low_fee_map.keys()) if Config.LOW_FEE_ITEMS_SCAN_ENABLED else []
    all_agg_titles = list(agg_prices.keys())[:100]
    snapshot_titles = list(dict.fromkeys(all_agg_titles + low_fee_titles))[:200]
    oracle = OracleFactory.get_oracle(Config.GAME_ID)
    cs_asks_full, cs_bids_full = await _fetch_oracle_snapshots(oracle, snapshot_titles)
    metrics.oracle_asks = len(cs_asks_full)
    metrics.oracle_bids = len(cs_bids_full)

    instant = 0
    cross = 0
    for it in items:
        item_id = it.get("itemId", "")
        title = it.get("title", "")
        if not item_id or not title:
            continue

        agg = agg_prices.get(title, {})
        best_bid = agg.get("best_bid", 0) or 0
        best_ask = agg.get("best_ask", 0) or 0
        current_margin = ((best_bid - best_ask) / best_ask * 100) if best_ask > 0 else 0.0

        try:
            result = await dummy._evaluate_candidate(
                item=it,
                game_id=Config.GAME_ID,
                oracle=oracle,
                agg_prices=agg_prices,
                bulk_fees=bulk_fees,
                current_balance=metrics.balance,
                current_margin=current_margin,
                cs_snapshots=cs_asks_full,
                cs_bids=cs_bids_full,
                saturation_counts={},
                effective_balance=max(0.0, metrics.balance - Config.BALANCE_RESERVE_USD),
                dynamic_max_price=min(
                    Config.MAX_SNIPING_PRICE_USD,
                    metrics.balance * Config.MAX_SNIPING_PRICE_BALANCE_FRACTION,
                ),
            )
        except Exception as e:
            log_err(f"filter {title}: {e}")
            continue

        if not result:
            continue

        strategy = result.get("strategy", "unknown")
        metrics.filter_reasons[strategy] = metrics.filter_reasons.get(strategy, 0) + 1

        if strategy == "cross_market":
            cross += 1
            log_ok(f"Cross candidate: {title[:40]} @ ${result.get('base_price', 0):.2f}")
        elif strategy == "intra_spread":
            instant += 1
            log_ok(f"Instant candidate: {title[:40]} @ ${result.get('base_price', 0):.2f}")
        elif strategy == "dmarket_underpriced":
            metrics.dmarket_underpriced += 1
            ref = result.get("dm_underpriced_ref", 0.0)
            log_ok(f"DMarket underpriced: {title[:40]} @ ${result.get('base_price', 0):.2f} (ref ${ref:.2f})")

        if it.get("_low_fee_rate") is not None:
            metrics.low_fee_candidates += 1

    # Separate cross-market buy target placement simulation
    limit_mixin = _LimitOrderMixin()
    limit_mixin.client = dmarket
    cross_targets = await limit_mixin._execute_cross_market_targets(
        game_id=Config.GAME_ID,
        agg_prices=agg_prices,
        cs_snapshots=cs_asks_full,
        current_balance=metrics.balance,
    )
    cross += cross_targets
    if cross_targets:
        log_ok(f"Cross-market targets that would be placed: {cross_targets}")

    metrics.instant_candidates = instant
    metrics.cross_market_targets = cross


async def run_pipeline_test(metrics: "SandboxMetrics") -> None:
    """Main entry point for the pipeline phase."""
    log("\n" + "=" * 70)
    log("  PIPELINE TEST — Filter + Cross-Market Targets")
    log("=" * 70)
    log_info(f"Config: MIN_SPREAD_PCT={Config.MIN_SPREAD_PCT}% STRICT_MICROSTRUCTURE={Config.STRICT_MICROSTRUCTURE_FILTERS}")

    pub_key = Config.PUBLIC_KEY
    sec_key = vault.get_dmarket_secret() or Config.SECRET_KEY
    if not pub_key or not sec_key:
        log_err("DMarket API keys not configured — skipping pipeline")
        return

    dmarket = DMarketAPIClient(public_key=pub_key, secret_key=sec_key)
    oracle = OracleFactory.get_oracle(Config.GAME_ID)

    try:
        agg_prices, _oracle_ok = await _check_connectivity(dmarket, oracle, metrics)
        if not agg_prices:
            return

        items, low_fee_map = await _fetch_listings(dmarket, agg_prices, metrics)
        if not items:
            log_warn("No listings fetched — skipping filter run")
            return

        await _run_filters(dmarket, items, agg_prices, {}, {}, metrics, low_fee_map)
    finally:
        await dmarket.close()
        await OracleFactory.close_all()
