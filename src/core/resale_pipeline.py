"""
ResalePipeline — Buy cheap on DMarket → Check CS2Cap → Sell on DMarket.

Full cycle:
1. Scan DMarket listings for underpriced items
2. Validate against CS2Cap (41 marketplaces)
3. Buy items on DMarket
4. Track in virtual inventory
5. List for sale on DMarket at CS2Cap-referenced price + margin
6. Manage inventory (mark items, remember state)

Integrates arXiv improvements:
- Sharpe-adjusted opportunity scoring
- Turnover regularization
- Self-reflection parameter adaptation
- Multi-market price validation
"""

import asyncio
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from src.api.dmarket_api_client import DMarketAPIClient
from src.api.cs2cap_oracle import CS2CapOracle, CrossMarketData
from src.api.oracle_factory import OracleFactory
from src.config import Config
from src.db.price_history import price_db
from src.risk.price_validator import validate_arbitrage_profit, validate_slippage, PriceValidationError
from src.analytics.self_reflection import self_reflection

logger = logging.getLogger("ResalePipeline")


class ResalePipeline:
    """
    End-to-end buy-sell pipeline with CS2Cap price intelligence.
    """

    def __init__(self, api_client: DMarketAPIClient):
        self.api = api_client
        self.cs2cap = OracleFactory.get_cross_market_oracle(Config.GAME_ID)
        self._sell_price_cache: Dict[str, Tuple[float, float]] = {}  # hash_name -> (price, ts)

    # =================================================================
    # 1. SCAN & BUY — Find cheap items on DMarket
    # =================================================================

    async def scan_and_buy(
        self,
        balance: float,
        max_items: int = 10,
    ) -> List[Dict[str, Any]]:
        """
        Scan DMarket for underpriced items, validate against CS2Cap, buy.
        Returns list of purchased items.
        """
        purchased = []
        cursor = None
        pages_scanned = 0
        max_pages = 20  # Safety limit for pagination

        while pages_scanned < max_pages:
            response = await self.api.get_market_items_v2(
                Config.GAME_ID, limit=Config.BATCH_SIZE, cursor=cursor
            )
            items = response.get("objects", [])
            next_cursor = response.get("cursor", "")

            if not items:
                break

            for item in items:
                if len(purchased) >= max_items:
                    return purchased

                result = await self._evaluate_and_buy(item, balance)
                if result:
                    purchased.append(result)
                    balance -= result["buy_price"]

            pages_scanned += 1

            if not next_cursor or next_cursor == cursor:
                break
            cursor = next_cursor

        return purchased

    async def _evaluate_and_buy(
        self, item: Dict[str, Any], balance: float
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluate a single DMarket item: check CS2Cap price → decide to buy.
        """
        item_id = item.get("itemId", "")
        title = item.get("title", "")
        price_cents = int(item.get("price", {}).get("USD", 0))
        buy_price = price_cents / 100.0

        # Basic filters
        if buy_price < Config.MIN_PRICE_USD or buy_price > Config.MAX_PRICE_USD:
            return None
        if buy_price > balance:
            return None
        if price_db.has_target_been_placed(item_id):
            return None

        # Check CS2Cap for reference price
        cs2cap_price = 0.0
        cross_data: Optional[CrossMarketData] = None

        if self.cs2cap:
            try:
                cs2cap_price = await self.cs2cap.get_item_price(title)
                cross_data = await self.cs2cap.get_cross_market_data(title)
                # NOTE (Phase 8): get_market_indicators (RSI/MACD) is a
                # Quant-tier feature. On Starter/Pro it always returns None
                # — was being awaited per item for nothing. Removed.
            except Exception as e:
                logger.debug(f"CS2Cap fetch failed for {title}: {e}")

        if cs2cap_price <= 0:
            return None

        # Calculate margin: CS2Cap best price vs DMarket buy price
        # We'll sell on DMarket at ~CS2Cap price (or slightly below to undercut)
        estimated_sell_price = cs2cap_price * 0.98  # Slight undercut for faster sale
        fee_rate = await self.api.get_item_fee(Config.GAME_ID, item_id, price_cents)

        # Turnover penalty
        turnover_penalty = self._get_turnover_penalty()

        # Self-reflection adjusted spread
        reflection = self_reflection._cached_result
        adjusted_min_spread = Config.MIN_SPREAD_PCT
        if reflection and reflection.confidence > 0.3:
            adjusted_min_spread += reflection.recommended_spread_adjustment

        # Validate profitability
        try:
            net_margin = validate_arbitrage_profit(
                buy_price=buy_price,
                expected_sell_price=estimated_sell_price,
                fee_markup=fee_rate,
                min_profit_margin=adjusted_min_spread / 100.0,
                lock_days=7,
            )
        except PriceValidationError:
            return None

        # NOTE (Phase 8): get_market_indicators (RSI) is a Quant-tier
        # CS2Cap feature. On Starter/Pro it always returned None, so this
        # block was effectively dead code — removed together with the call.

        # Execute buy
        buy_offer = {
            "offerId": item_id,
            "price": {"amount": str(price_cents), "currency": "USD"}
        }
        result = await self.api.buy_items([buy_offer])
        is_dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

        # Record in virtual inventory
        price_db.add_virtual_item(title, buy_price, trade_lock_hours=168)
        price_db.record_placed_target(item_id, title, buy_price)

        # Calculate sell price based on CS2Cap
        sell_price = self._calculate_sell_price(
            buy_price=buy_price,
            cs2cap_price=cs2cap_price,
            cross_data=cross_data,
            fee_rate=fee_rate,
        )

        status = "purchased_sim" if is_dry_run else "purchased"
        log_prefix = "[SIM] " if is_dry_run else ""

        logger.info(
            f"{log_prefix}BOUGHT: {title} @ ${buy_price:.2f} | "
            f"CS2Cap: ${cs2cap_price:.2f} -> Sell target: ${sell_price:.2f} | "
            f"Margin: {net_margin*100:.1f}%"
        )

        return {
            "item_id": item_id,
            "title": title,
            "buy_price": buy_price,
            "cs2cap_price": cs2cap_price,
            "estimated_sell_price": sell_price,
            "net_margin_pct": net_margin * 100,
            "fee_rate": fee_rate,
            "turnover_penalty": turnover_penalty,
            "status": status,
        }

    # =================================================================
    # 2. SELL — List purchased items on DMarket
    # =================================================================

    async def sell_inventory_items(self, max_items: int = 10) -> List[Dict[str, Any]]:
        """
        List trade-unlocked items for sale on DMarket.

        Phase 5 optimization: replaces per-item CS2Cap calls and per-item
        DMarket create_offer calls with two batched calls:
          1. CS2Cap /prices/batch for all unique titles in 1 call
          2. DMarket batch_create_offers_v2 for all items in 1 call
        """
        items = price_db.get_virtual_inventory(status='idle', only_unlocked=True)
        if not items:
            return []

        # Slice the candidate set first — we only price-check the first
        # max_items to keep CS2Cap usage bounded.
        candidates = items[:max_items]
        unique_titles = list({it['hash_name'] for it in candidates})

        # --- 1. CS2Cap batch (1 call for all unique titles) ---
        cs_prices: Dict[str, float] = {}
        if self.cs2cap and unique_titles:
            try:
                snapshots = await self.cs2cap.get_prices_batch(unique_titles)
                cs_prices = {
                    title: snap.min_price
                    for title, snap in snapshots.items()
                    if snap.has_data
                }
            except AttributeError:
                # Fallback for CSFloat fallback oracle (no batch endpoint)
                for title in unique_titles:
                    try:
                        p = await self.cs2cap.get_item_price(title)
                        if p > 0:
                            cs_prices[title] = p
                    except Exception as e:
                        logger.debug(f"CS2Cap fallback price check failed for {title}: {e}")
            except Exception as e:
                logger.debug(f"CS2Cap batch price check failed: {e}")

        # --- 2. Build the list of (item, sell_price) that pass the
        #    profitability filter. ---
        ready_to_list: List[Tuple[Dict[str, Any], float, float]] = []  # (item, sell_price, profit_pct)
        for item in candidates:
            title = item['hash_name']
            buy_price = item['buy_price']
            cs2cap_price = cs_prices.get(title, 0.0)
            if cs2cap_price <= 0:
                continue

            sell_price = self._calculate_sell_price(
                buy_price=buy_price,
                cs2cap_price=cs2cap_price,
                cross_data=None,
                fee_rate=Config.FEE_RATE,
            )
            net_after_sell = sell_price * (1 - Config.FEE_RATE)
            profit_pct = ((net_after_sell - buy_price) / buy_price) * 100
            if profit_pct < Config.MIN_SPREAD_PCT:
                logger.debug(
                    f"Skipping {title}: profit {profit_pct:.1f}% < {Config.MIN_SPREAD_PCT}%"
                )
                continue
            ready_to_list.append((item, sell_price, profit_pct))

        if not ready_to_list:
            return []

        listed: List[Dict[str, Any]] = []
        is_dry_run = os.getenv("DRY_RUN", "true").lower() == "true"

        if is_dry_run:
            # DRY_RUN: no real DMarket call — just update status + log
            for item, sell_price, profit_pct in ready_to_list:
                title = item['hash_name']
                buy_price = item['buy_price']
                price_db.update_virtual_status(item['id'], 'selling')
                logger.info(
                    f"[SIM] LISTED: {title} @ ${sell_price:.2f} | "
                    f"Bought: ${buy_price:.2f} | CS2Cap: ${cs_prices.get(title, 0):.2f} | "
                    f"Profit: {profit_pct:.1f}%"
                )
                listed.append({
                    "title": title,
                    "sell_price": sell_price,
                    "buy_price": buy_price,
                    "profit_pct": profit_pct,
                    "status": "listed_sim",
                })
            return listed

        # --- 3. PRODUCTION: lookup asset_ids and batch-list in 1 call ---
        # We need each item's asset_id to call batch_create_offers_v2.
        # Paginate DMarket user_offers to find them (one pass, not per-item).
        asset_by_title: Dict[str, str] = {}
        try:
            cursor = None
            for _ in range(10):  # safety cap
                resp = await self.api.get_user_offers(
                    Config.GAME_ID, limit=100, cursor=cursor
                )
                for obj in resp.get("items") or resp.get("objects") or []:
                    title = obj.get("title", "")
                    asset_id = obj.get("assetId") or obj.get("itemId") or ""
                    if title and asset_id and title not in asset_by_title:
                        asset_by_title[title] = asset_id
                cursor = resp.get("cursor")
                if not cursor:
                    break
        except Exception as e:
            logger.error(f"Failed to enumerate offers for asset lookup: {e}")

        batch_payload: List[Dict[str, Any]] = []
        plan: List[Tuple[Dict[str, Any], float, float]] = []
        for item, sell_price, profit_pct in ready_to_list:
            title = item['hash_name']
            asset_id = asset_by_title.get(title)
            if not asset_id:
                logger.warning(
                    f"No asset_id for {title} in user_offers — "
                    f"skipping batch listing (item may not be on DMarket yet)"
                )
                continue
            batch_payload.append({"asset_id": asset_id, "price_usd": sell_price})
            plan.append((item, sell_price, profit_pct))

        if not batch_payload:
            return []

        # 1 batch call for all offers
        try:
            result = await self.api.batch_create_offers_v2(batch_payload)
        except Exception as e:
            logger.error(f"batch_create_offers_v2 failed: {e}")
            return []

        # Update statuses + collect results.
        # The v2 endpoint returns {"offers": [{"offerId": "...", "assetId": "...", ...}]}
        # or {"items": [...]} depending on schema. We just iterate and
        # flip status for each item we sent.
        offer_id_by_asset: Dict[str, str] = {}
        for entry in (result.get("offers") or result.get("items") or []):
            aid = entry.get("assetId") or entry.get("asset_id") or ""
            oid = entry.get("offerId") or entry.get("offer_id") or ""
            if aid and oid:
                offer_id_by_asset[aid] = oid

        for (item, sell_price, profit_pct) in plan:
            title = item['hash_name']
            buy_price = item['buy_price']
            asset_id = asset_by_title.get(title, "")
            price_db.update_virtual_status(item['id'], 'selling')
            offer_id = offer_id_by_asset.get(asset_id, "")
            logger.info(
                f"LISTED: {title} @ ${sell_price:.2f} | "
                f"Bought: ${buy_price:.2f} | Profit: {profit_pct:.1f}%"
            )
            listed.append({
                "title": title,
                "sell_price": sell_price,
                "buy_price": buy_price,
                "profit_pct": profit_pct,
                "status": "listed",
                "offer_id": offer_id,
            })

        return listed

    # =================================================================
    # 3. PRICE CALCULATION
    # =================================================================

    def _calculate_sell_price(
        self,
        buy_price: float,
        cs2cap_price: float,
        cross_data: Optional[CrossMarketData],
        fee_rate: float,
    ) -> float:
        """
        Calculate optimal sell price on DMarket based on CS2Cap data.
        Strategy: undercut CS2Cap min by 2% for faster sale,
        but ensure minimum profit margin.
        """
        if cs2cap_price <= 0:
            return buy_price * 1.10  # Fallback: 10% margin

        # Base: slightly below CS2Cap min ask
        target_sell = cs2cap_price * 0.98

        # Check cross-market data for better pricing
        if cross_data and cross_data.global_max_bid > 0:
            # If there's a buy order above our target, price to fill it
            if cross_data.global_max_bid > target_sell * 0.95:
                target_sell = min(target_sell, cross_data.global_max_bid * 0.99)

        # Ensure minimum profit after fees
        min_sell_for_profit = buy_price * (1 + Config.MIN_SPREAD_PCT / 100.0) / (1 - fee_rate)
        target_sell = max(target_sell, min_sell_for_profit)

        # Don't exceed CS2Cap price (no point listing much higher)
        # But if min margin requires higher price, allow up to 10% above CS2Cap
        max_allowed = cs2cap_price * 1.10
        target_sell = min(target_sell, max_allowed)

        return round(target_sell, 2)

    # =================================================================
    # 4. INVENTORY MANAGEMENT
    # =================================================================

    async def get_inventory_status(self) -> Dict[str, Any]:
        """
        Get full inventory status: virtual + real DMarket inventory.
        """
        # Virtual inventory (tracked items)
        virtual_idle = price_db.get_virtual_inventory(status='idle', only_unlocked=False)
        virtual_selling = price_db.get_virtual_inventory(status='selling')
        virtual_sold = price_db.get_virtual_inventory(status='sold')

        # Real DMarket inventory
        real_inventory = []
        real_offers = []
        try:
            real_inventory = (await self.api.get_user_inventory(Config.GAME_ID)).get("objects", [])
            real_offers = (await self.api.get_user_active_offers(Config.GAME_ID)).get("objects", [])
        except Exception as e:
            logger.debug(f"Failed to fetch real inventory: {e}")

        return {
            "virtual": {
                "idle": len(virtual_idle),
                "selling": len(virtual_selling),
                "sold": len(virtual_sold),
                "total_value": sum(i['buy_price'] for i in virtual_idle + virtual_selling),
            },
            "real": {
                "inventory": len(real_inventory),
                "active_offers": len(real_offers),
            },
            "items": [
                {
                    "title": i['hash_name'],
                    "buy_price": i['buy_price'],
                    "status": i['status'],
                    "acquired": time.ctime(i['acquired_at']),
                }
                for i in (virtual_idle + virtual_selling)[:10]
            ],
        }

    # =================================================================
    # 5. TURNOVER
    # =================================================================

    def _get_turnover_penalty(self) -> float:
        """Calculate turnover penalty from today's trade count."""
        from src.strategies.market_maker import MarketMaker
        mm = MarketMaker()
        return mm.calculate_turnover_penalty()

    async def close(self):
        if self.cs2cap:
            await self.cs2cap.close()
