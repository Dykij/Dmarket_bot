"""
Target Sniping v12.0 — Strategy A: Intra-DMarket Spread Arbitrage.

The bot:
1. Scans DMarket for items (50 per batch)
2. Fetches aggregated prices (best_bid, best_ask) for those items
3. Filters: best_bid > best_ask * 1.05 (5%+ spread)
4. CS2Cap oracle validates the spread is real (not a stale data spike)
5. If profitable: buy at best_ask, list at best_bid - 0.01
6. Periodically reprices unsold items

No more BUFF163-csfloat comparison (that strategy never worked).
"""

import asyncio
import logging
import os
import gc
import time
from typing import List, Dict, Any, Optional

from src.api.dmarket_api_client import DMarketAPIClient
from src.api.oracle_factory import OracleFactory
from src.risk.liquidity_manager import LiquidityManager
from src.analytics.rare_valuation import RareValuationEngine
from src.analytics.stickers_evaluator import StickerEvaluator
from src.risk.price_validator import validate_arbitrage_profit, validate_volatility, validate_slippage, PriceValidationError
from src.db.price_history import price_db
from src.core.event_shield import event_shield
from src.core.sandbox_scenarios import scenario_engine
from src.api.cs2cap_oracle import RateLimitException

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SnipingBot")


class SnipingLoop:
    """
    Main Autonomous Loop for DMarket Sniping & Re-sale (v12.0 Intra-Spread).
    """

    def __init__(self, client: DMarketAPIClient):
        self.client = client
        self.valuation = RareValuationEngine()
        self.stickers = StickerEvaluator()
        self.liquidity = LiquidityManager()
        self.inventory_mgr = None

        from src.config import Config
        self.target_games = [Config.GAME_ID]

        self.deep_scan_counter = 0
        self.buy_budget = Config.MAX_PRICE_USD
        self.running = False
        self.empty_page_count = 0
        self.resale_cycle_limit = 10
        self.reprice_counter = 0

    @property
    def min_profit_margin(self) -> float:
        """Dynamic margin: base * event multiplier (v7.8)."""
        from src.config import Config
        return (Config.MIN_SPREAD_PCT / 100.0) * event_shield.get_margin_multiplier()

    async def start(self):
        self.running = True
        logger.info(f"Starting DMarket Intra-Spread Loop v12.0 | Targets: {self.target_games}")

        gc.disable()

        try:
            while self.running:
                for game_id in self.target_games:
                    await self.run_cycle(game_id)

                gc.collect()

                if self.empty_page_count > 0:
                    delay = min(10 * (self.empty_page_count * 2), 60)
                    logger.info(f"Market appears quiet. Sleeping for {delay}s...")
                else:
                    delay = 5  # Faster than v9.0 — Strategy A needs more data

                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            logger.info("Sniping loop cancelled.")
        except Exception as e:
            logger.error(f"Critical error in sniping cycle: {e}")
            await asyncio.sleep(30)
        finally:
            await OracleFactory.close_all()
            if self.client:
                await self.client.close()

    async def run_cycle(self, game_id: str):
        """
        v12.0 Strategy A: Intra-DMarket Spread.
        1. Scan 50 items
        2. Get aggregated prices (best_bid, best_ask)
        3. Filter: 5%+ spread
        4. Validate with CS2Cap oracle
        5. Buy at ask, list at bid - 0.01
        """
        try:
            self.deep_scan_counter += 1
            self.reprice_counter += 1
            is_fresh_cycle = (self.deep_scan_counter % 5 == 0)
            cursor_key = f"dmarket_cursor_{game_id}"

            if is_fresh_cycle:
                logger.info(f"FRESH CYCLE (Page 1) for {game_id} to catch new listings.")
                current_cursor = ""
            else:
                current_cursor = price_db.get_state(cursor_key) or ""

            logger.info(f"Scanning {game_id} (Cursor: {current_cursor or 'START'})...")
            current_balance = await self.client.get_real_balance()
            oracle = OracleFactory.get_oracle(game_id)
            if not oracle:
                return

            # --- Step 1: Scan market ---
            try:
                from src.config import Config
                await self._simulate_network_latency()
                self._maybe_inject_error("get_market_items")
                response = await self.client.get_market_items_v2(game_id, limit=Config.BATCH_SIZE, cursor=current_cursor)
            except Exception as e:
                if "400" in str(e) or "expired" in str(e).lower():
                    logger.warning(f"Cursor expired for {game_id}. Resetting.")
                    price_db.save_state(cursor_key, "")
                    response = await self.client.get_market_items_v2(game_id, limit=Config.BATCH_SIZE, cursor="")
                else:
                    raise e

            items = response.get("objects", [])
            next_cursor = response.get("cursor", "")

            if not items:
                self.empty_page_count += 1
                if next_cursor and not is_fresh_cycle:
                    logger.warning(f"Empty deep page for {game_id}. Resetting.")
                    price_db.save_state(cursor_key, "")
                return

            self.empty_page_count = 0

            if not is_fresh_cycle:
                if next_cursor:
                    price_db.save_state(cursor_key, next_cursor)
                else:
                    price_db.save_state(cursor_key, "")

            # --- Step 2: Get aggregated prices for all items ---
            titles = [item.get("title", "") for item in items if item.get("title")]
            await self._simulate_network_latency()
            self._maybe_inject_error("get_aggregated_prices")
            agg_prices = await self.client.get_aggregated_prices(game_id, titles)

            # --- Step 3: Filter and validate ---
            sniping_targets = []
            instant_buys = []
            current_margin = self.min_profit_margin

            for item in items:
                title = item.get("title", "")
                item_id = item.get("itemId")
                base_price_cents = int(item.get("price", {}).get("USD", 0))
                base_price = base_price_cents / 100.0

                if not title or not item_id or base_price <= 0:
                    continue

                if price_db.has_target_been_placed(item_id):
                    continue

                from src.config import Config
                if base_price < Config.MIN_PRICE_USD:
                    continue
                if base_price > self.buy_budget or base_price > current_balance:
                    continue

                max_risk_price = current_balance * (Config.MAX_POSITION_RISK_PCT / 100.0)
                if base_price > max_risk_price:
                    continue

                if not self.liquidity.can_spend(base_price, game_id, current_balance):
                    continue

                if price_db.is_crashing(title):
                    continue

                history = price_db.get_recent_prices(title, days=14)
                prices_only = [p for p, _ in history]
                try:
                    validate_volatility(prices_only)
                except PriceValidationError:
                    continue

                # --- Strategy A: bid-ask spread analysis ---
                agg = agg_prices.get(title, {})
                best_bid = agg.get("best_bid", 0.0)
                best_ask = agg.get("best_ask", 0.0)
                ask_count = agg.get("ask_count", 0)
                bid_count = agg.get("bid_count", 0)

                if best_ask <= 0 or best_bid <= 0:
                    continue
                if ask_count < 1 or bid_count < 1:
                    continue  # No real demand

                # Spread check: best_bid > best_ask * 1.05
                if best_bid <= best_ask * (1 + Config.INTRA_MIN_SPREAD_PCT / 100.0):
                    continue

                # CS2Cap oracle validation (sanity check)
                try:
                    cs_price = await oracle.get_item_price(title)
                    is_sandbox = os.getenv("DRY_RUN", "true").lower() == "true"
                    if is_sandbox:
                        cs_price *= scenario_engine.get_price_modifier()
                except (RateLimitException, Exception) as e:
                    if isinstance(e, RateLimitException) or "429" in str(e):
                        logger.error(f"Oracle rate limited during {game_id} scan.")
                        self.empty_page_count = 5
                        return
                    raise e

                # CS2Cap reference: ensure oracle price is not way below our buy
                # (this would mean the item is genuinely overvalued on DMarket)
                if cs_price > 0 and base_price > cs_price * 1.5:
                    # DMarket price is 50%+ above BUFF163 — likely overpriced, skip
                    if is_sandbox:
                        price_db.log_decision(title, 'skip', 'DMarket overpriced vs BUFF163', f"DM=${base_price} BUFF=${cs_price}")
                    continue

                # Calculate profit: list at best_bid - 0.01
                list_price = round(best_bid - Config.INTRA_LIST_DISCOUNT, 2)

                # v12.0 Phase 1.2: Float Premium (FN-0, FT-0, FN)
                attrs_list = item.get("attributes", [])
                attrs = {a.get("name"): a.get("value") for a in attrs_list}
                float_premium = self._calculate_float_premium(attrs)
                if float_premium > 1.0:
                    list_price = round(list_price * float_premium, 2)
                    if is_sandbox:
                        logger.debug(f"Float premium {float_premium:.2f}x applied to {title}")

                if list_price < base_price * 1.02:
                    # Less than 2% gross — too thin after fees
                    continue

                # v12.0 Phase 1.1: Low-Fee Filter (prefer low-fee items)
                fee_rate = await self.client.get_item_fee(game_id, item_id, base_price_cents)
                cached_low_fee = price_db.get_low_fee_rate(title)
                if cached_low_fee is not None and cached_low_fee < fee_rate:
                    # Use the lower cached rate (it might differ slightly from dynamic)
                    fee_rate = min(fee_rate, cached_low_fee)

                try:
                    net_margin = validate_arbitrage_profit(
                        buy_price=base_price,
                        expected_sell_price=list_price,
                        fee_markup=fee_rate,
                        min_profit_margin=current_margin,
                        lock_days=7
                    )
                except PriceValidationError as e:
                    if os.getenv("DRY_RUN", "true").lower() == "true":
                        price_db.log_decision(title, 'skip', 'Low profit', str(e))
                    continue

                if os.getenv("DRY_RUN", "true").lower() == "true":
                    if base_price > current_balance:
                        price_db.record_missed_opportunity(title, base_price, list_price, "Insufficient Balance")
                    held_count = len([x for x in price_db.get_virtual_inventory(status='idle') if x['hash_name'] == title])
                    if held_count >= 5:
                        price_db.record_missed_opportunity(title, base_price, list_price, f"Saturation Limit ({held_count})")

                # --- Decide: instant buy vs target ---
                # For intra-spread strategy, we typically instant-buy
                # (the spread exists right now, may not in 5 minutes)
                attrs_list = item.get("attributes", [])
                attrs = {a.get("name"): a.get("value") for a in attrs_list}

                buy_offer = {
                    "offerId": item_id,
                    "price": {"amount": str(int(base_price * 100)), "currency": "USD"}
                }
                instant_buys.append({
                    "buy_offer": buy_offer,
                    "title": title,
                    "item_id": item_id,
                    "base_price": base_price,
                    "list_price": list_price,
                    "best_bid": best_bid,
                    "best_ask": best_ask,
                })

            # --- Execute instant buys ---
            if instant_buys:
                logger.info(f"Executing INSTANT BUY for {len(instant_buys)} items (Strategy A)...")
                await self._simulate_network_latency()
                self._maybe_inject_error("buy_items")
                buy_payloads = [item["buy_offer"] for item in instant_buys]
                await self.client.buy_items(buy_payloads)

                for item_data in instant_buys:
                    title = item_data["title"]
                    item_id = item_data["item_id"]
                    base_price = item_data["base_price"]
                    list_price = item_data["list_price"]

                    if os.getenv("DRY_RUN", "true").lower() == "true":
                        if not self._simulate_competition(0.15):
                            logger.warning(f"[SIM] COMPETITION! {title} was sniped by another bot first.")
                            continue

                        held_count = len([x for x in price_db.get_virtual_inventory(status='idle') if x['hash_name'] == title])
                        if held_count >= 5:
                            logger.warning(f"[SATURATION] Already holding {held_count}x {title}. Skipping.")
                            continue

                        price_db.add_virtual_item(title, base_price, trade_lock_hours=168)
                        vwap = price_db.calculate_vwap(title)
                        logger.info(f"[SIM] SNIPED! {title} @ ${base_price} → list ${list_price} (spread: {item_data['best_bid']-item_data['best_ask']:.2f}, VWAP: ${vwap:.2f})")

                    price_db.record_placed_target(item_id, title, base_price)
                    self.liquidity.record_spend(base_price)

            if self.deep_scan_counter % self.resale_cycle_limit == 0:
                await self.auto_resale(game_id)

            # Periodic repricing
            if self.reprice_counter % 60 == 0:  # Every ~60 cycles
                await self.reprice_unsold_offers(game_id)

            # v12.0 Phase 1.1: Refresh low-fee cache every 100 cycles
            if self.deep_scan_counter % 100 == 0:
                await self._refresh_low_fee_cache(game_id)

            # Equity report
            equity = price_db.get_total_equity(current_balance)
            logger.info(f"[EQUITY] Cash: ${equity['cash']:.2f} | Assets: ${equity['assets']:.2f} | TOTAL: ${equity['total']:.2f} (Items: {equity['count']})")

            if self.deep_scan_counter % 200 == 0:
                price_db.cleanup_old_targets()

        except Exception as e:
            if "RateLimit" not in str(e):
                logger.error(f"Cycle failed for {game_id}: {e}")

    def _simulate_competition(self, margin: float) -> bool:
        """Sandbox v9.0: Models the probability of being out-sniped by a competitor."""
        import random
        if os.getenv("DRY_RUN", "true").lower() != "true":
            return True
        if margin > 0.40:
            fail_chance = 0.90
        elif margin > 0.20:
            fail_chance = 0.60
        elif margin > 0.10:
            fail_chance = 0.30
        else:
            fail_chance = 0.10
        return random.random() >= fail_chance

    async def _simulate_network_latency(self, client_type: str = "dmarket"):
        """Sandbox v9.5: Mimics real-world network RTT (Round Trip Time) with Jitter."""
        if os.getenv("DRY_RUN", "true").lower() != "true":
            return
        import random
        if client_type == "cs2cap":
            base_lat, jitter = 600, 400
        else:
            base_lat, jitter = 200, 200
        delay = (base_lat + random.randint(0, jitter)) / 1000.0
        await asyncio.sleep(delay)

    def _maybe_inject_error(self, method_name: str):
        """Sandbox v9.5: Randomly injects API 429/5xx errors to test resilience."""
        if os.getenv("DRY_RUN", "true").lower() != "true":
            return
        import random
        if random.random() < 0.05:
            error_code = random.choice([429, 500, 502, 503])
            logger.warning(f"[SIM ERROR] Injected {error_code} for {method_name}!")
            raise Exception(f"Simulated API Error: {error_code}")

    async def auto_resale(self, game_id: str):
        """
        v12.0: Scans virtual inventory and lists items at best_bid - 0.01.
        """
        import random
        if os.getenv("DRY_RUN", "true").lower() != "true":
            return
        items = price_db.get_virtual_inventory(status='idle', only_unlocked=True)
        locked_count = len(price_db.get_virtual_inventory(status='idle', only_unlocked=False)) - len(items)
        selling_items = price_db.get_virtual_inventory(status='selling')

        if locked_count > 0:
            logger.info(f"Trade Lock: {locked_count} items are currently frozen.")

        for item in selling_items:
            if random.random() < 0.4:
                price_db.update_virtual_status(item['id'], 'sold')
                logger.info(f"[SIM] ITEM SOLD! {item['hash_name']} | Exit Profit logged.")

        if not items:
            return
        logger.info(f"Scanning Virtual Inventory for resale ({len(items)} items)...")
        for item in items:
            oracle = OracleFactory.get_oracle(game_id)
            if not oracle:
                continue
            try:
                current_price = await oracle.get_item_price(item['hash_name'])
                if current_price <= 0:
                    continue
                buy_price = item['buy_price']
                target_sell = round(buy_price * 1.05, 2)
                market_profit = round(current_price * 0.95 - buy_price, 2)
                if current_price >= target_sell:
                    price_db.update_virtual_status(item['id'], 'selling')
                    logger.info(f"[SIM] LISTING: {item['hash_name']} | Buy: ${buy_price} | Market: ${current_price} | Est. Net Profit: ${market_profit}")
            except Exception as e:
                logger.debug(f"Resale check failed for {item['hash_name']}: {e}")

    async def reprice_unsold_offers(self, game_id: str):
        """
        v12.0: Reprice items that have been listed > REPRICE_AFTER_HOURS.
        In production: call client.edit_offer(); in DRY_RUN: log only.
        """
        from src.config import Config
        if os.getenv("DRY_RUN", "true").lower() != "true":
            return
        selling_items = price_db.get_virtual_inventory(status='selling')
        if not selling_items:
            return
        cutoff = time.time() - (Config.REPRICE_AFTER_HOURS * 3600)
        stale = [it for it in selling_items if it['acquired_at'] < cutoff]
        if stale:
            logger.info(f"[REPRICE] {len(stale)} items pending repricing (>{Config.REPRICE_AFTER_HOURS}h listed)")

    # ------------------------------------------------------------------
    # v12.0 Phase 1.1: Low-fee cache
    # ------------------------------------------------------------------
    async def _refresh_low_fee_cache(self, game_id: str):
        """Refresh the low-fee items cache from DMarket (24h TTL)."""
        age = price_db.low_fee_cache_age_seconds()
        if age is not None and age < 86400:
            return  # Fresh enough
        try:
            await self._simulate_network_latency()
            self._maybe_inject_error("get_low_fee_items")
            items = await self.client.get_low_fee_items(game_id)
            if items:
                price_db.save_low_fee_items(items)
                logger.info(f"[LOW-FEE] Cached {len(items)} low-fee items (refreshed)")
        except Exception as e:
            logger.debug(f"Low-fee cache refresh failed: {e}")

    # ------------------------------------------------------------------
    # v12.0 Phase 1.2: Float Premium
    # ------------------------------------------------------------------
    @staticmethod
    def _calculate_float_premium(attrs: Dict[str, Any]) -> float:
        """
        Returns a price multiplier based on item's float value.

        Float ranges (CS2):
        - FN-0: 0.00 - 0.01  (best) → 1.20x
        - FN:   0.00 - 0.07   → 1.10x
        - MW:   0.07 - 0.15   → 1.00x
        - FT-0: 0.15 - 0.18   → 1.15x
        - FT:   0.15 - 0.38   → 1.00x
        - WW:   0.38 - 0.45   → 0.95x
        - BS:   0.45 - 1.00   → 0.90x

        Returns 1.0 (no premium) if float not available.
        """
        try:
            float_str = attrs.get("floatPartValue")
            if not float_str:
                return 1.0
            float_val = float(float_str)
        except (ValueError, TypeError):
            return 1.0

        if float_val < 0.01:
            return 1.20  # FN-0
        if float_val < 0.07:
            return 1.10  # FN
        if 0.15 <= float_val <= 0.18:
            return 1.15  # FT-0
        if 0.38 <= float_val < 0.45:
            return 0.95  # WW
        if float_val >= 0.45:
            return 0.90  # BS
        return 1.0  # MW / regular FT


if __name__ == "__main__":
    pass
