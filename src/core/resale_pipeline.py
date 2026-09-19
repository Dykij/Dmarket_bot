"""
ResalePipeline — Buy cheap on DMarket → Validate price → Sell on DMarket.

Full cycle:
1. Scan DMarket listings for underpriced items
2. Validate against MultiSourceOracle (Market.CSGO + Waxpeer + CSFloat + Steam)
3. Buy items on DMarket
4. Track in virtual inventory
5. List for sale on DMarket at oracle-referenced price + margin
6. Manage inventory (mark items, remember state)

Integrates arXiv improvements:
- Sharpe-adjusted opportunity scoring
- Turnover regularization
- Self-reflection parameter adaptation
- Multi-market price validation
"""

import logging
import time
from typing import Any

from src.analytics.self_reflection import self_reflection
from src.api.dmarket_api_client import DMarketAPIClient
from src.config import Config
from src.db.price_history import price_db
from src.risk.price_validator import PriceValidationError, validate_arbitrage_profit
from src.utils.fee_utils import get_sell_fee_rate

logger = logging.getLogger("ResalePipeline")


class ResalePipeline:
    """
    End-to-end buy-sell pipeline with MultiSourceOracle price intelligence.
    """

    def __init__(self, api_client: DMarketAPIClient, risk=None):
        from src.risk.risk_manager import RiskManager

        self.api = api_client
        self.oracle = None  # Oracle removed — pipeline uses DMarket-internal data only
        self._sell_price_cache: dict[str, tuple[float, float]] = (
            {}
        )  # hash_name -> (price, ts)
        self._risk = risk or RiskManager()

    async def sell_inventory_items(self, max_items: int = 10) -> list[dict[str, Any]]:
        """
        List trade-unlocked items for sale on DMarket.

        Phase 5 optimization: replaces per-item oracle calls and per-item
        DMarket create_offer calls with two batched calls:
          1. Oracle /prices/batch for all unique titles in 1 call
          2. DMarket batch_create_offers_v2 for all items in 1 call
        """
        items = await price_db.run_in_thread(
            price_db.get_virtual_inventory, status="idle", only_unlocked=True
        )
        if not items:
            return []

        # Slice the candidate set first — we only price-check the first
        # max_items to keep oracle usage bounded.
        candidates = items[:max_items]
        unique_titles = list({it["hash_name"] for it in candidates})

        cs_prices = await self._fetch_reference_prices(unique_titles)
        ready_to_list = self._build_ready_to_list(candidates, cs_prices)

        if not ready_to_list:
            return []

        if Config.DRY_RUN:
            return await self._handle_dry_run(ready_to_list, cs_prices)

        asset_by_title = await self._lookup_asset_ids()
        return await self._execute_batch_listing(ready_to_list, asset_by_title)

    async def _fetch_reference_prices(
        self, unique_titles: list[str]
    ) -> dict[str, float]:
        cs_prices: dict[str, float] = {}
        try:
            agg = await self.api.get_aggregated_prices(
                Config.GAME_ID, titles=unique_titles
            )
            cs_prices = {
                title: data.get("best_bid", 0.0)
                for title, data in agg.items()
                if data.get("best_bid", 0) > 0
            }
        except Exception as e:
            logger.debug(f"[RESALE] Aggregated prices fetch failed: {e}")
        return cs_prices

    def _build_ready_to_list(
        self, candidates: list[dict[str, Any]], cs_prices: dict[str, float]
    ) -> list[tuple[Any, float, float]]:
        target_margin = (
            Config.MIN_SPREAD_PCT / 100.0
            + get_sell_fee_rate()
            + Config.WITHDRAWAL_FEE_RATE
        )
        ready_to_list: list[tuple[Any, float, float]] = []
        for item in candidates:
            title = item["hash_name"]
            buy_price = item["buy_price"]
            reference_price = cs_prices.get(title, 0.0)
            if reference_price <= 0:
                reference_price = buy_price * (1 + target_margin)

            sell_price = self._calculate_sell_price(
                buy_price=buy_price,
                reference_price=reference_price,
                fee_rate=get_sell_fee_rate(),
            )
            net_after_sell = sell_price * (1 - get_sell_fee_rate())
            profit_pct = ((net_after_sell - buy_price) / buy_price) * 100
            if profit_pct < Config.MIN_SPREAD_PCT:
                logger.debug(
                    f"Skipping {title}: profit {profit_pct:.1f}% < {Config.MIN_SPREAD_PCT}%"
                )
                continue
            ready_to_list.append((item, sell_price, profit_pct))
        return ready_to_list

    async def _handle_dry_run(
        self, ready_to_list: list[tuple[Any, float, float]], cs_prices: dict[str, float]
    ) -> list[dict[str, Any]]:
        listed: list[dict[str, Any]] = []
        for item, sell_price, profit_pct in ready_to_list:
            title = item["hash_name"]
            buy_price = item["buy_price"]
            await price_db.run_in_thread(
                price_db.update_virtual_status, item["id"], "selling"
            )
            logger.info(
                f"[SIM] LISTED: {title} @ ${sell_price:.2f} | "
                f"Bought: ${buy_price:.2f} | Oracle: ${cs_prices.get(title, 0):.2f} | "
                f"Profit: {profit_pct:.1f}%"
            )
            listed.append(
                {
                    "title": title,
                    "sell_price": sell_price,
                    "buy_price": buy_price,
                    "profit_pct": profit_pct,
                    "status": "listed_sim",
                }
            )
        return listed

    async def _lookup_asset_ids(self) -> dict[str, str]:
        asset_by_title: dict[str, str] = {}
        try:
            inv_resp = await self.api.get_user_inventory(Config.GAME_ID)
            for obj in inv_resp.get("objects") or inv_resp.get("items") or []:
                title = obj.get("title", "")
                asset_id = obj.get("assetId") or obj.get("itemId") or ""
                if title and asset_id:
                    asset_by_title[title] = asset_id

            cursor = None
            for _ in range(5):
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
            logger.error(f"Failed to enumerate assets for lookup: {e}", exc_info=True)
        return asset_by_title

    async def _execute_batch_listing(
        self,
        ready_to_list: list[tuple[Any, float, float]],
        asset_by_title: dict[str, str],
    ) -> list[dict[str, Any]]:
        batch_payload: list[dict[str, Any]] = []
        plan: list[tuple[Any, float, float]] = []
        for item, sell_price, profit_pct in ready_to_list:
            title = item["hash_name"]
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

        try:
            result = await self.api.batch_create_offers_v2(batch_payload)
        except Exception as e:
            logger.error(f"batch_create_offers_v2 failed: {e}", exc_info=True)
            return []

        offer_id_by_asset: dict[str, str] = {}
        for entry in result.get("offers") or result.get("items") or []:
            aid = entry.get("assetId") or entry.get("asset_id") or ""
            oid = entry.get("id") or entry.get("offerId") or entry.get("offer_id") or ""
            if aid and oid:
                offer_id_by_asset[aid] = oid

        listed: list[dict[str, Any]] = []
        for item, sell_price, profit_pct in plan:
            title = item["hash_name"]
            buy_price = item["buy_price"]
            asset_id = asset_by_title.get(title, "")
            await price_db.run_in_thread(
                price_db.update_virtual_status, item["id"], "selling"
            )
            offer_id = offer_id_by_asset.get(asset_id, "")
            logger.info(
                f"LISTED: {title} @ ${sell_price:.2f} | "
                f"Bought: ${buy_price:.2f} | Profit: {profit_pct:.1f}%"
            )
            listed.append(
                {
                    "title": title,
                    "sell_price": sell_price,
                    "buy_price": buy_price,
                    "profit_pct": profit_pct,
                    "status": "listed",
                    "offer_id": offer_id,
                }
            )
        return listed

    # =================================================================
    # 3. PRICE CALCULATION
    # =================================================================

    def _calculate_sell_price(
        self,
        buy_price: float,
        reference_price: float,
        fee_rate: float,
    ) -> float:
        """
        Calculate optimal sell price on DMarket.
        Strategy: use reference price, ensure minimum profit margin after fees.
        """
        if reference_price <= 0:
            return buy_price * 1.10  # Fallback: 10% margin

        target_sell = reference_price

        # Ensure minimum profit after fees
        min_sell_for_profit = (
            buy_price * (1 + float(Config.MIN_SPREAD_PCT) / 100.0) / (1 - fee_rate)
        )
        target_sell = max(target_sell, min_sell_for_profit)

        # Don't exceed reference price by more than 10%
        max_allowed = reference_price * 1.10
        target_sell = min(target_sell, max_allowed)

        return round(target_sell, 2)

    # =================================================================
    # 4. INVENTORY MANAGEMENT
    # =================================================================

    async def get_inventory_status(self) -> dict[str, Any]:
        """
        Get full inventory status: virtual + real DMarket inventory.
        """
        # Virtual inventory (tracked items)
        virtual_idle = await price_db.run_in_thread(
            price_db.get_virtual_inventory, status="idle", only_unlocked=False
        )
        virtual_selling = await price_db.run_in_thread(
            price_db.get_virtual_inventory, status="selling"
        )
        virtual_sold = await price_db.run_in_thread(
            price_db.get_virtual_inventory, status="sold"
        )

        # Real DMarket inventory
        real_inventory = []
        real_offers = []
        try:
            real_inventory = (await self.api.get_user_inventory(Config.GAME_ID)).get(
                "objects", []
            )
            real_offers = (await self.api.get_user_offers(Config.GAME_ID)).get(
                "objects", []
            )
        except Exception as e:
            logger.debug(f"Failed to fetch real inventory: {e}")

        return {
            "virtual": {
                "idle": len(virtual_idle),
                "selling": len(virtual_selling),
                "sold": len(virtual_sold),
                "total_value": sum(
                    i["buy_price"] for i in virtual_idle + virtual_selling
                ),
            },
            "real": {
                "inventory": len(real_inventory),
                "active_offers": len(real_offers),
            },
            "items": [
                {
                    "title": i["hash_name"],
                    "buy_price": i["buy_price"],
                    "status": i["status"],
                    "acquired": time.ctime(i["acquired_at"]),
                }
                for i in (virtual_idle + virtual_selling)[:10]
            ],
        }

    # =================================================================
    # 5. TURNOVER
    # =================================================================

    _turnover_mm: Any = None

    def _get_turnover_penalty(self) -> float:
        """Calculate turnover penalty from today's trade count."""
        if self._turnover_mm is None:
            from src.strategies.market_maker import MarketMaker

            self._turnover_mm = MarketMaker()
        return self._turnover_mm.calculate_turnover_penalty()

    async def close(self):
        pass  # Oracle removed — no resources to close
