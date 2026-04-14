import asyncio
import logging
import os
import gc
from typing import List, Dict, Any, Optional
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.csfloat_oracle import CSFloatOracle, RateLimitException
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
    Includes Trend Guard (anti-crash) and Event Shield (calendar awareness).
    """
    
    def __init__(self, client: DMarketAPIClient):
        self.client = client
        oracle_key = os.getenv("CSFLOAT_API_KEY", "")
        self.oracle = CSFloatOracle(api_key=oracle_key)
        self.valuation = RareValuationEngine()
        self.stickers = StickerEvaluator()
        self.event_shield = EventShield()
        
        # Focusing strictly on CS2 (a8db) and Rust.
        self.target_games = ["a8db", "rust"] 
        self.running = False
        
        # Risk factors
        self.base_min_profit_margin = 0.05  # 5% minimum net profit on capital
        self.buy_budget = 500.0  # Max USD for a single item
        
    @property
    def min_profit_margin(self) -> float:
        """Dynamic margin: base * event multiplier."""
        return self.base_min_profit_margin * self.event_shield.get_margin_multiplier()

    async def start(self):
        self.running = True
        logger.info("Starting DMarket Autonomous Sniping Loop (Async V4.0)...")
        
        # Log active events
        active_events = self.event_shield.get_active_events()
        if active_events:
            for ev in active_events:
                icon = "⚠️" if ev["effect"] == "caution" else "💰"
                logger.info(f"{icon} ACTIVE EVENT: {ev['name']} ({ev['effect'].upper()}) — margin x{ev.get('margin_multiplier', 1.0)}")
        else:
            logger.info("📅 No active CS2 events. Running with base margin (5%).")
        
        logger.info(f"📊 Effective margin requirement: {self.min_profit_margin*100:.1f}%")
        
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
            await self.oracle.close()
            await self.client.close()

    async def run_cycle(self, game_id: str):
        """
        One cycle: Scan Market -> Analyze -> Trend Guard -> Event Shield -> Oracle -> Target.
        """
        logger.info(f"Scanning market for opportunities in {game_id}...")
        response = await self.client.get_market_items_v2(game_id, limit=100)
        items = response.get("objects", [])
        
        sniping_targets = []
        current_margin = self.min_profit_margin
        
        for item in items:
            item_id = item.get("itemId")
            base_price = float(item.get("price", {}).get("USD", 0)) / 100.0
            title = item.get("title", "")
            
            # Skip if above budget
            if base_price > self.buy_budget:
                continue
            
            # --- EVENT SHIELD: Category Risk Check ---
            if self.event_shield.is_category_risky(title):
                logger.info(f"🛡️ EVENT SHIELD: Skipping {title} — risky category during active event.")
                continue

            # --- TREND GUARD: Crash Detection ---
            if price_db.is_crashing(title):
                trend = price_db.get_price_trend(title)
                logger.warning(f"📉 TREND GUARD: {title} is CRASHING (trend={trend}). Skipping to avoid loss.")
                continue
            
            # 2. Performance Rare Valuation
            attrs = {a.get("name"): a.get("value") for a in item.get("attributes", [])}
            sticker_list = item.get("stickers", [])
            
            # Calculate Estimated Value (EV) built-in
            ev = self.valuation.estimate_market_value(base_price, attrs)
            sticker_ev = self.stickers.calculate_added_value(sticker_list)
            
            total_ev = ev + sticker_ev
            
            # 3. Smart Market Making logic: Target Sniping
            # Limit Buy order at 85% of market EV
            target_buy_price = round(total_ev * 0.85, 2)
            
            # Verify mathematically that limit order yields net profit > min_profit_margin
            try:
                net_margin = validate_arbitrage_profit(
                    buy_price=target_buy_price, 
                    expected_sell_price=total_ev, 
                    fee_markup=0.05, 
                    min_profit_margin=current_margin
                )
            except PriceValidationError:
                continue

            # 3.5. EXTERNAL ORACLE (CSFloat Validation) for CS2 items only!
            if game_id == "a8db":
                try:
                    csfloat_price = await self.oracle.get_item_price(title)
                    if csfloat_price > 0:
                        # Re-validate with CSFloat true price
                        try:
                            net_margin = validate_arbitrage_profit(
                                buy_price=target_buy_price, 
                                expected_sell_price=csfloat_price, 
                                fee_markup=0.05, 
                                min_profit_margin=current_margin
                            )
                        except PriceValidationError:
                            logger.info(f"⏭ Skip {title}: CSFloat Oracle ref price ${csfloat_price} invalidates EV ${total_ev}.")
                            continue
                except RateLimitException:
                    logger.warning("Skipping Oracle for this target due to API Limit penalty.")
                except Exception as e:
                    logger.error(f"Oracle failure on {title}: {e}")
                    
            logger.info(f"🎯 TARGET LOCKED: {title} | Buy: ${target_buy_price:.2f} | Margin: {net_margin*100:.1f}% | Req: {current_margin*100:.1f}%")
            
            # Prepare Target for Batch Creation
            target = {
                "GameID": game_id,
                "Price": {"Currency": "USD", "Amount": int(target_buy_price * 100)},
                "Amount": 1,
                "Attrs": {
                    "floatPartValue": attrs.get("floatPartValue") if attrs.get("floatPartValue") else None,
                    "paintSeed": attrs.get("paintSeed") if attrs.get("paintSeed") else None
                }
            }
            # Clean none attrs
            target["Attrs"] = {k: v for k, v in target["Attrs"].items() if v is not None}
            
            sniping_targets.append(target)
            
        # 4. Async Batch Execution
        if sniping_targets:
            logger.info(f"🚀 Executing Batch Targets for {len(sniping_targets)} items...")
            try:
                res = await self.client.batch_create_targets(sniping_targets)
                logger.info(f"Target Batch Result: {res.get('status')}")
            except Exception as e:
                logger.error(f"Batch execution failed: {e}")

    async def auto_resale(self, inv_mgr):
        """
        Моментальный реселл на DMarket.
        Checks bought items via InventoryManager and immediately lists them for EV/CSFloat price.
        """
        logger.info("Running parallel Auto-Resale module...")
        try:
            # Fetch user inventory securely through InventoryManager pagination
            inventory = await inv_mgr.fetch_inventory(game_id="a8db")
            if not inventory:
                logger.info("No items in inventory to resell.")
                return

            sell_targets = []
            for item in inventory:
                title = item.get("title")
                item_id = item.get("itemId")
                
                # Check cache or CSFloat
                csfloat_price = await self.oracle.get_item_price(title)
                
                if csfloat_price > 0:
                    # Undercut CSFloat price by 1 cent or match it
                    sell_price = round(csfloat_price - 0.01, 2)
                    
                    sell_targets.append({
                        "itemId": item_id,
                        "price": {"amount": int(sell_price * 100), "currency": "USD"}
                    })
                    logger.info(f"💼 Preparing to sell {title} for ${sell_price}")

            if sell_targets:
                logger.info(f"📤 Dispatching {len(sell_targets)} items to market...")
                res = await self.client.make_request("POST", "/exchange/v1/user/offers/create", body={"Offers": sell_targets})
                logger.info(f"Resale Batch Result: {res}")
                
        except Exception as e:
            logger.error(f"Auto-Resale failed: {e}")

if __name__ == "__main__":
    pass
