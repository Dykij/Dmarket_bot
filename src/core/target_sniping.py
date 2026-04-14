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
        
        # Focusing strictly on CS2 (a8db) and Rust.
        self.target_games = ["a8db", "rust"] 
        self.running = False
        
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
                
                # Anti-detection delay
                await asyncio.sleep(5) 
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
        Oracle Factory + Dynamic Fees + TVM + Liquidity Enforcements.
        """
        logger.info(f"Scanning market for opportunities in {game_id}...")
        
        try:
            current_balance = await self.client.get_real_balance()
            logger.info(f"💵 Current Sniper Balance: ${current_balance:.2f}")
            
            oracle = OracleFactory.get_oracle(game_id)
            if not oracle:
                logger.warning(f"No oracle found for game {game_id}")
                return

            response = await self.client.get_market_items_v2(game_id, limit=100)
            items = response.get("objects", [])
            
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
                # Assume 7-day hold for all items (V7.6 standard)
                target_buy_price = round(expected_sell * 0.85, 2)
                try:
                    net_margin = validate_arbitrage_profit(
                        buy_price=target_buy_price, 
                        expected_sell_price=expected_sell, 
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
