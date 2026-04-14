import asyncio
import logging
import os
import gc
from typing import List, Dict, Any, Optional
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.oracle_factory import OracleFactory
from src.risk.liquidity_manager import LiquidityManager
from src.analytics.rare_valuation import RareValuationEngine
from src.analytics.stickers_evaluator import StickerEvaluator
from src.risk.price_validator import validate_arbitrage_profit, PriceValidationError
from src.db.price_history import price_db
from src.core.event_shield import EventShield

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SnipingBot")

class SnipingLoop:
    """
    Main Autonomous Loop for DMarket Sniping & Re-sale (Async).
    Iteration v7.6: Multi-game Oracles + TVM + Revolving Liquidity.
    """
    
    def __init__(self, client: DMarketAPIClient):
        self.client = client
        self.valuation = RareValuationEngine()
        self.stickers = StickerEvaluator()
        self.event_shield = EventShield()
        self.liquidity = LiquidityManager()
        
        # Phase 7.8: Hybrid scanning state
        self.deep_scan_counter = 0
        
        # Risk factors
        self.buy_budget = 500.0  # Max USD for a single item
        
    @property
    def min_profit_margin(self) -> float:
        """Dynamic margin: base * event multiplier."""
        return 0.05 * self.event_shield.get_margin_multiplier()

    async def start(self):
        self.running = True
        logger.info("Starting DMarket Autonomous Sniping Loop (Async V7.6)...")
        
        # GC Tuning: Disable auto garbage collection and collect manually per cycle
        gc.disable()
        logger.info("Python Garbage Collector set to Manual Mode for lower latency.")

        try:
            while self.running:
                for game_id in self.target_games:
                    await self.run_cycle(game_id)
                
                # Manual garbage collection during the non-critical anti-detection delay
                gc.collect()
                
                # Anti-detection delay (Increased for v7.8 24/7 stability)
                await asyncio.sleep(10) 
        except asyncio.CancelledError:
            logger.info("Sniping loop cancelled.")
        except Exception as e:
            logger.error(f"Critical error in sniping cycle: {e}")
            await asyncio.sleep(30)
        finally:
            await OracleFactory.close_all()
            await self.client.close()

    async def run_cycle(self, game_id: str):
        """
        Oracle Factory + Dynamic Fees + TVM + Persistent Pagination (v7.7/v7.8 Hybrid).
        """
        try:
            # --- PHASE 7.8 HYBRID SCANNING LOGIC ---
            self.deep_scan_counter += 1
            is_fresh_cycle = (self.deep_scan_counter % 5 == 0)
            
            cursor_key = f"dmarket_cursor_{game_id}"
            
            if is_fresh_cycle:
                logger.info(f"🔄 FRESH CYCLE (Page 1) for {game_id} to catch new listings.")
                current_cursor = "" # Force restart
            else:
                current_cursor = price_db.get_state(cursor_key) or ""
            
            logger.info(f"Scanning market for {game_id} (Cursor: {current_cursor or 'START'})...")
            current_balance = await self.client.get_real_balance()
            oracle = OracleFactory.get_oracle(game_id)
            if not oracle:
                return

            try:
                response = await self.client.get_market_items_v2(game_id, limit=100, cursor=current_cursor)
            except Exception as e:
                if "400" in str(e) or "expired" in str(e).lower():
                    logger.warning(f"⚠️ Cursor expired for {game_id}. Resetting scanning state.")
                    price_db.save_state(cursor_key, "")
                    response = await self.client.get_market_items_v2(game_id, limit=100, cursor="")
                else:
                    raise e

            items = response.get("objects", [])
            next_cursor = response.get("cursor", "")
            
            # --- PHASE 7.8: Deep Page Empty Response Guard ---
            if not items and next_cursor and not is_fresh_cycle:
                logger.warning(f"📭 Empty deep page for {game_id}. Resetting to check fresh items.")
                price_db.save_state(cursor_key, "")
                return
            
            # --- Persistence Updates (v7.8) ---
            if not is_fresh_cycle: # Only save cursor if we are doing a deep scan
                if next_cursor:
                    price_db.save_state(cursor_key, next_cursor)
                else:
                    price_db.save_state(cursor_key, "")

            sniping_targets = []
            current_margin = self.min_profit_margin
            
            for item in items:
                title = item.get("title", "")
                item_id = item.get("itemId")
                base_price_cents = int(item.get("price", {}).get("USD", 0))
                base_price = base_price_cents / 100.0
                
                # --- 1. BUDGET & LIQUIDITY ENFORCEMENT ---
                if not self.liquidity.can_spend(base_price, game_id, current_balance):
                    continue
                
                if base_price > self.buy_budget or base_price > current_balance:
                    continue
                
                # --- 2. TREND GUARD ---
                if price_db.is_crashing(title):
                    continue

                # --- 3. VALUATION ---
                attrs = {a.get("name"): a.get("value") for a in item.get("attributes", [])}
                ev = self.valuation.estimate_market_value(base_price, attrs)
                sticker_ev = self.stickers.calculate_added_value(item.get("stickers", []))
                total_ev = ev + sticker_ev
                
                # --- 4. DYNAMIC FEE CHECK ---
                fee_rate = await self.client.get_item_fee(game_id, item_id, base_price_cents)
                
                # --- 5. ORACLE VALIDATION ---
                ref_price = await oracle.get_item_price(title)
                expected_sell = ref_price if ref_price > 0 else total_ev
                
                # --- 6. TVM-AWARE PROFIT VALIDATION ---
                # v7.8 Index Delay Guard: Lower expected sell by 1% for Rust to account for stale SCMM data
                safe_expected_sell = expected_sell * 0.99 if game_id == "rust" else expected_sell
                
                target_buy_price = round(safe_expected_sell * 0.85, 2)
                try:
                    net_margin = validate_arbitrage_profit(
                        buy_price=target_buy_price, 
                        expected_sell_price=safe_expected_sell, 
                        fee_markup=fee_rate, 
                        min_profit_margin=current_margin,
                        lock_days=7
                    )
                except PriceValidationError:
                    continue

                logger.info(f"🎯 TARGET LOCKED: {title} | Buy: ${target_buy_price:.2f} | Adj Margin: {net_margin*100:.1f}%")
                
                # Prepare Target
                target = {
                    "GameID": game_id,
                    "Price": {"Currency": "USD", "Amount": int(target_buy_price * 100)},
                    "Amount": 1,
                    "Attrs": {k: v for k, v in attrs.items() if k in ["floatPartValue", "paintSeed"]}
                }
                sniping_targets.append(target)
                self.liquidity.record_spend(target_buy_price)

            if sniping_targets:
                logger.info(f"🚀 Executing Batch Targets for {len(sniping_targets)} items...")
                await self.client.batch_create_targets(sniping_targets)
                
        except Exception as e:
            logger.error(f"Cycle failed for {game_id}: {e}")

    async def auto_resale(self, inv_mgr):
        """
        Implementation similar to before but using OracleFactory.
        """
        pass

if __name__ == "__main__":
    pass
