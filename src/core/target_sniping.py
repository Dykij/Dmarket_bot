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
from src.api.csfloat_oracle import RateLimitException

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SnipingBot")

class SnipingLoop:
    """
    Main Autonomous Loop for DMarket Sniping & Re-sale (Async).
    Iteration v9.0: Sandbox v9.0 (Market Friction + Trade Locks).
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

    @property
    def min_profit_margin(self) -> float:
        """Dynamic margin: base * event multiplier (v7.8)."""
        from src.config import Config
        return (Config.MIN_SPREAD_PCT / 100.0) * event_shield.get_margin_multiplier()

    async def start(self):
        self.running = True
        logger.info(f"Starting DMarket Autonomous Sniping Loop (Async V9.0) | Targets: {self.target_games}")
        
        gc.disable()

        try:
            while self.running:
                for game_id in self.target_games:
                    await self.run_cycle(game_id)
                
                gc.collect()
                
                if self.empty_page_count > 0:
                    delay = min(10 * (self.empty_page_count * 2), 60)
                    logger.info(f"😴 Market appears quiet. Sleeping for {delay}s...")
                else:
                    delay = 10
                
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
        Oracle Factory + Dynamic Fees + TVM + Persistent Pagination (v9.0 Hybrid).
        """
        try:
            self.deep_scan_counter += 1
            is_fresh_cycle = (self.deep_scan_counter % 5 == 0)
            cursor_key = f"dmarket_cursor_{game_id}"
            
            if is_fresh_cycle:
                logger.info(f"🔄 FRESH CYCLE (Page 1) for {game_id} to catch new listings.")
                current_cursor = "" 
            else:
                current_cursor = price_db.get_state(cursor_key) or ""
            
            logger.info(f"Scanning market for {game_id} (Cursor: {current_cursor or 'START'})...")
            current_balance = await self.client.get_real_balance()
            oracle = OracleFactory.get_oracle(game_id)
            if not oracle:
                return

            try:
                from src.config import Config
                await self._simulate_network_latency() # v9.5
                self._maybe_inject_error("get_market_items") # v9.5
                response = await self.client.get_market_items_v2(game_id, limit=Config.BATCH_SIZE, cursor=current_cursor)
            except Exception as e:
                if "400" in str(e) or "expired" in str(e).lower():
                    logger.warning(f"⚠️ Cursor expired for {game_id}. Resetting scanning state.")
                    price_db.save_state(cursor_key, "")
                    response = await self.client.get_market_items_v2(game_id, limit=Config.BATCH_SIZE, cursor="")
                else:
                    raise e

            items = response.get("objects", [])
            next_cursor = response.get("cursor", "")
            
            if not items:
                self.empty_page_count += 1
                if next_cursor and not is_fresh_cycle:
                    logger.warning(f"📭 Empty deep page for {game_id}. Resetting to check fresh items.")
                    price_db.save_state(cursor_key, "")
                return
            
            self.empty_page_count = 0
            
            if not is_fresh_cycle: 
                if next_cursor:
                    price_db.save_state(cursor_key, next_cursor)
                else:
                    price_db.save_state(cursor_key, "")

            sniping_targets = []
            instant_buys = []
            current_margin = self.min_profit_margin
            
            for item in items:
                title = item.get("title", "")
                item_id = item.get("itemId")
                base_price_cents = int(item.get("price", {}).get("USD", 0))
                base_price = base_price_cents / 100.0
                
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
                
                attrs_list = item.get("attributes", [])
                attrs = {a.get("name"): a.get("value") for a in attrs_list}
                item_stickers = item.get("stickers", [])
                ev = self.valuation.estimate_market_value(base_price, attrs)
                sticker_ev = self.stickers.calculate_added_value(item_stickers)
                total_ev = ev + sticker_ev
                
                fee_rate = await self.client.get_item_fee(game_id, item_id, base_price_cents)
                
                try:
                    ref_price = await oracle.get_item_price(title)
                    # Phase 7: Apply Market Scenario Modifier
                    is_sandbox = os.getenv("DRY_RUN", "true").lower() == "true"
                    if is_sandbox:
                        ref_price *= scenario_engine.get_price_modifier()
                except (RateLimitException, Exception) as e:
                    if isinstance(e, RateLimitException) or "429" in str(e):
                        logger.error(f"⚠️ Oracle Rate Limited during {game_id} scan.")
                        self.empty_page_count = 5 
                        return
                    raise e
                
                expected_sell = ref_price if ref_price > 0 else total_ev
                safe_expected_sell = expected_sell * 0.99 if game_id == "rust" else expected_sell
                
                target_buy_price = round(safe_expected_sell * 0.85, 2)
                if target_buy_price < Config.MIN_PRICE_USD:
                    if is_sandbox:
                        price_db.log_decision(title, 'skip', 'Price too low', f"${target_buy_price} < ${Config.MIN_PRICE_USD}")
                    continue

                try:
                    validate_slippage(target_buy_price, base_price, max_slippage_pct=0.02)
                except PriceValidationError as e:
                    if is_sandbox:
                        price_db.log_decision(title, 'skip', 'Slippage guard', str(e))
                    continue

                try:
                    net_margin = validate_arbitrage_profit(
                        buy_price=target_buy_price, 
                        expected_sell_price=safe_expected_sell, 
                        fee_markup=fee_rate, 
                        min_profit_margin=current_margin,
                        lock_days=7
                    )
                except PriceValidationError as e:
                    if is_sandbox:
                        price_db.log_decision(title, 'skip', 'Low profit', str(e))
                    continue

                # Phase 7: Record Potential Profit if we skip due to limits
                if is_sandbox:
                    # If we reached here, it's profitable! 
                    # Now check if we skip due to balance or saturation
                    if base_price > current_balance:
                        price_db.record_missed_opportunity(title, base_price, safe_expected_sell, "Insufficient Balance")
                    
                    held_count = len([x for x in price_db.get_virtual_inventory(status='idle') if x['hash_name'] == title])
                    if held_count >= 5:
                        price_db.record_missed_opportunity(title, base_price, safe_expected_sell, f"Saturation Limit ({held_count})")

                # --- 6. TARGET VS INSTANT BUY DECISION ---
                if base_price <= target_buy_price:
                    buy_offer = {
                        "offerId": item_id,
                        "price": {"amount": str(int(base_price * 100)), "currency": "USD"}
                    }
                    instant_buys.append(buy_offer)
                    continue

                target_attrs = {}
                for k, v in attrs.items():
                    if k in ["floatPartValue", "paintSeed", "phase", "variant"]:
                        target_attrs[k] = v
                if sticker_ev > 0:
                    target_attrs["stickers"] = [s.get("name") for s in item_stickers if s.get("name") in self.stickers.RARE_STICKERS]

                target = {
                    "GameID": game_id, "hash_name": title,
                    "Price": {"Currency": "USD", "Amount": int(target_buy_price * 100)},
                    "Amount": 1, "Attrs": target_attrs
                }
                sniping_targets.append(target)

            # --- EXECUTE INSTANT BUYS ---
            if instant_buys:
                logger.info(f"🔥 Executing INSTANT BUY for {len(instant_buys)} items...")
                await self._simulate_network_latency() # v9.5
                self._maybe_inject_error("buy_items") # v9.5
                await self.client.buy_items(instant_buys)
                for b in instant_buys:
                    title = "Unknown"
                    for itm in (items or []):
                        if itm.get("itemId") == b["offerId"]:
                            title = itm.get("title")
                            break
                    
                    if os.getenv("DRY_RUN", "true").lower() == "true":
                        # Competition Simulation (v9.0)
                        if not self._simulate_competition(0.15):
                            logger.warning(f"🕵️ [SIM] COMPETITION! {title} was sniped by another bot first.")
                            continue
                            
                        # Inventory Saturation Check (v9.5)
                        held_count = len([x for x in price_db.get_virtual_inventory(status='idle') if x['hash_name'] == title])
                        if held_count >= 5:
                            logger.warning(f"🛡️ [SATURATION] Already holding {held_count}x {title}. Skipping instant buy.")
                            continue

                        price_db.add_virtual_item(title, int(b["price"]["amount"])/100.0, trade_lock_hours=168)
                        vwap = price_db.calculate_vwap(title)
                        logger.info(f"📦 [SIM] Item Acquired via SNIPE! VWAP: ${vwap:.2f} | Adding: {title} (7d Lock)")

                    price_db.record_placed_target(b["offerId"], title, int(b["price"]["amount"])/100.0)
                    self.liquidity.record_spend(int(b["price"]["amount"])/100.0)

            # --- EXECUTE TARGETS ---
            if sniping_targets:
                logger.info(f"🚀 Executing Batch Targets for {len(sniping_targets)} items...")
                await self.client.batch_create_targets(sniping_targets)
                for t in sniping_targets:
                    matching_id = None
                    for itm in (items or []):
                        if itm.get("title") == t["hash_name"]:
                            matching_id = itm.get("itemId"); break
                    if matching_id:
                        price_db.record_placed_target(matching_id, t["hash_name"], t["Price"]["Amount"]/100.0)
                        self.liquidity.record_spend(t["Price"]["Amount"]/100.0)

                if os.getenv("DRY_RUN", "true").lower() == "true":
                    import random
                    for t in sniping_targets:
                        can_buy = False
                        for itm in (items or []):
                            listing_price = int(itm.get("price", {}).get("USD", 0)) / 100.0
                            if listing_price <= (t["Price"]["Amount"] / 100.0):
                                can_buy = True; break
                        if can_buy and random.random() < 0.9: 
                            name = t.get("hash_name", "Unknown item")
                            buy_price = t["Price"]["Amount"] / 100.0

                            # Saturation Check (v9.5)
                            held_count = len([x for x in price_db.get_virtual_inventory(status='idle') if x['hash_name'] == name])
                            if held_count >= 5:
                                logger.warning(f"🛡️ [SATURATION] Max limit reached for {name}. Target ignored.")
                                continue

                            if not self._simulate_competition(0.15):
                                logger.warning(f"🕵️ [SIM] COMPETITION! Target fulfillment for {name} failed.")
                                continue
                            price_db.add_virtual_item(name, buy_price, trade_lock_hours=168)
                            logger.info(f"📦 [SIM] Target Sniped! Acquired: {name} @ ${buy_price} (7d Lock)")

            if self.deep_scan_counter % self.resale_cycle_limit == 0:
                await self.auto_resale(game_id)
            
            # Equity Report (v9.5)
            equity = price_db.get_total_equity(current_balance)
            logger.info(f"📈 [EQUITY] Cash: ${equity['cash']:.2f} | Assets: ${equity['assets']:.2f} | TOTAL: ${equity['total']:.2f} (Items: {equity['count']})")
                
            if self.deep_scan_counter % 200 == 0:
                price_db.cleanup_old_targets()

        except Exception as e:
            if "RateLimit" not in str(e):
                logger.error(f"Cycle failed for {game_id}: {e}")

    def _simulate_competition(self, margin: float) -> bool:
        """Sandbox v9.0: Models the probability of being out-sniped by a competitor."""
        import random
        if os.getenv("DRY_RUN", "true").lower() != "true": return True
        if margin > 0.40: fail_chance = 0.90
        elif margin > 0.20: fail_chance = 0.60
        elif margin > 0.10: fail_chance = 0.30
        else: fail_chance = 0.10
        return random.random() >= fail_chance

        return random.random() >= fail_chance

    async def _simulate_network_latency(self, client_type: str = "dmarket"):
        """Sandbox v9.5: Mimics real-world network RTT (Round Trip Time) with Jitter."""
        if os.getenv("DRY_RUN", "true").lower() != "true": return
        import random
        # v10.0: Multi-Latency - Different delays for different services
        if client_type == "csfloat":
            base_lat, jitter = 600, 400 # CSFloat is slower/external
        else:
            base_lat, jitter = 200, 200 # DMarket is core API
            
        delay = (base_lat + random.randint(0, jitter)) / 1000.0
        await asyncio.sleep(delay)

    def _maybe_inject_error(self, method_name: str):
        """Sandbox v9.5: Randomly injects API 429/5xx errors to test resilience."""
        if os.getenv("DRY_RUN", "true").lower() != "true": return
        import random
        # 5% chance of a random API failure
        if random.random() < 0.05:
            error_code = random.choice([429, 500, 502, 503])
            logger.warning(f"🎰 [SIM ERROR] Injected {error_code} for {method_name}!")
            raise Exception(f"Simulated API Error: {error_code}")

    async def auto_resale(self, game_id: str):
        """Scans virtual inventory and lists profitable items (v9.0)."""
        import random
        if os.getenv("DRY_RUN", "true").lower() != "true": return 
        items = price_db.get_virtual_inventory(status='idle', only_unlocked=True)
        locked_count = len(price_db.get_virtual_inventory(status='idle', only_unlocked=False)) - len(items)
        selling_items = price_db.get_virtual_inventory(status='selling')
        if locked_count > 0:
            logger.info(f"⏳ [SIM] Trade Lock: {locked_count} items are currently frozen.")

        for item in selling_items:
            if random.random() < 0.4:
                price_db.update_virtual_status(item['id'], 'sold')
                logger.info(f"💰 [SIM] ITEM SOLD! {item['hash_name']} | Exit Profit logged.")

        if not items: return
        logger.info(f"🔄 Scanning Virtual Inventory for resale ({len(items)} items)...")
        for item in items:
            oracle = OracleFactory.get_oracle(game_id)
            if not oracle: continue
            try:
                current_price = await oracle.get_item_price(item['hash_name'])
                if current_price <= 0: continue
                buy_price = item['buy_price']
                target_sell = round(buy_price * 1.05, 2)
                market_profit = round(current_price * 0.95 - buy_price, 2)
                if current_price >= target_sell:
                    price_db.update_virtual_status(item['id'], 'selling')
                    logger.info(f"🏷️ [SIM] LISTING: {item['hash_name']} | Buy: ${buy_price} | Market: ${current_price} | Est. Net Profit: ${market_profit}")
            except Exception as e:
                logger.debug(f"Resale check failed for {item['hash_name']}: {e}")

if __name__ == "__main__":
    pass
