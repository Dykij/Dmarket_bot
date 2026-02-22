"""
Script: src/bot/sales.py (v2 - Wall Breaker & Decay)
Description: Manages the selling side of the bot.
Autonomously scans inventory and lists items for sale using 'Wall Breaker' logic.
Tracks time-in-inventory for 'Smart Decay' pricing.
"""

import logging
import time
from typing import List, Dict

from src.config import Config
from src.utils.api_client import AsyncDMarketClient

logger = logging.getLogger("Sales")

class SalesManager:
    """
    Handles inventory management and selling.
    Strategy: 
    1. Fetch inventory.
    2. Check Market Depth (top 5 asks).
    3. Apply Wall Breaker Logic:
       - If gap between 1st & 2nd ask > WALL_BREAKER_PCT -> Price at (2nd Ask - $0.01).
       - Else -> Price at (1st Ask - $0.01).
    4. Apply Inventory Decay (if item stuck > 24h).
    """
    
    def __init__(self, client: AsyncDMarketClient):
        self.client = client
        self.dry_run = Config.DRY_RUN
        self.game_id = Config.GAME_ID
        self.wall_breaker_threshold = Config.WALL_BREAKER_PCT
        
        # Local cache for tracking item age (since DMarket inventory doesn't easily show listing age)
        # { asset_id: timestamp_first_seen }
        self.inventory_tracker = {}

    async def process_inventory(self):
        """
        Main routine: Fetches inventory and lists unlisted items.
        """
        try:
            # 1. Get Inventory
            response = await self.client.get_user_inventory(game=self.game_id)
            
            items = []
            if "objects" in response:
                items = response["objects"]
            elif "Items" in response:
                items = response["Items"]
            
            # Simulation Logic
            if self.dry_run and not items:
                logger.info("📦 [SIMULATION] Inventory empty. Simulating 'Glock-18 | Moonrise' for Wall Breaker test...")
                items = [{
                    "ItemId": "sim_glock_123",
                    "Title": "Glock-18 | Moonrise (Field-Tested)",
                    "InMarket": False
                }]

            if not items:
                return

            # Update Inventory Tracker (Age)
            current_time = time.time()
            active_ids = set()
            
            items_to_sell = []
            
            for item in items:
                asset_id = item.get("itemId") or item.get("AssetID") or item.get("ItemId")
                title = item.get("title") or item.get("Title", "Unknown")
                in_market = item.get("inMarket") or item.get("InMarket", False)
                
                active_ids.add(asset_id)
                if asset_id not in self.inventory_tracker:
                    self.inventory_tracker[asset_id] = current_time # New item detected
                
                # If already listed, check if price needs decay (Repricing logic would go here)
                if in_market and not self.dry_run:
                    # TODO: Implement active repricing based on age
                    age_hours = (current_time - self.inventory_tracker[asset_id]) / 3600
                    if age_hours > Config.INVENTORY_DECAY_HOURS:
                        logger.info(f"⏳ Item {title} is stale ({age_hours:.1f}h). Considering price decay...")
                    continue
                
                # FETCH MARKET DEPTH (Not just aggregated price, but actual listings)
                # To see the "Wall", we need at least top 2-3 offers.
                # The aggregated endpoint gives best price, but maybe we can infer or use offers endpoint.
                # Standard endpoint: /exchange/v1/market/items?title=...&limit=5&sort=price&order=asc
                
                market_response = await self.client.get_market_items(title=title, limit=5)
                
                top_asks = []
                if "objects" in market_response:
                    for market_item in market_response["objects"]:
                        price_obj = market_item.get("price", {})
                        if "USD" in price_obj:
                             top_asks.append(int(price_obj["USD"]))
                
                if not top_asks:
                    logger.warning(f"⚠️ No market data for {title}. Skipping.")
                    continue
                
                best_ask = top_asks[0]
                second_ask = top_asks[1] if len(top_asks) > 1 else best_ask
                
                # --- STRATEGY: WALL BREAKER ---
                target_ask = best_ask
                
                gap_pct = ((second_ask - best_ask) / best_ask) * 100
                
                if gap_pct > self.wall_breaker_threshold:
                    # Gap is huge! Don't be stupid and undercut the cheap guy.
                    # Let the cheap guy sell, we target the second guy.
                    target_ask = second_ask
                    logger.info(f"🧱 WALL BREAKER: {title} | Gap {gap_pct:.1f}% > {self.wall_breaker_threshold}% | Targeting 2nd Ask (${second_ask/100}) instead of 1st (${best_ask/100})")
                else:
                    # Gap is small, standard undercut
                    target_ask = best_ask
                
                # Final Price Calculation (Undercut selected target by 1 cent)
                sell_price = target_ask - 1
                
                # --- STRATEGY: INVENTORY DECAY (For new listings of old items) ---
                age_hours = (current_time - self.inventory_tracker[asset_id]) / 3600
                if age_hours > Config.INVENTORY_DECAY_HOURS:
                    decay_mult = 1.0 - (Config.DECAY_RATE_PCT / 100.0)
                    sell_price = int(sell_price * decay_mult)
                    logger.info(f"📉 DECAY APPLIED: {title} is old ({age_hours:.1f}h). Lowering price to ${sell_price/100}")

                items_to_sell.append({
                    "AssetID": asset_id,
                    "Price": {"Amount": sell_price, "Currency": "USD"},
                    "Title": title
                })

            # Cleanup tracker
            # remove IDs that are no longer in inventory
            for tracked_id in list(self.inventory_tracker.keys()):
                if tracked_id not in active_ids:
                    del self.inventory_tracker[tracked_id]

            # 3. Execute Sell Orders
            if items_to_sell:
                await self.create_offers(items_to_sell)

        except Exception as e:
            logger.error(f"Inventory process failed: {e}")

    async def create_offers(self, offers: List[Dict]):
        """
        Creates sell offers (listings).
        """
        if self.dry_run:
            for offer in offers:
                price_usd = offer["Price"]["Amount"] / 100.0
                title = offer.get("Title", "Unknown")
                logger.info(f"💰 [SIMULATION] Listing '{title}' for ${price_usd:.2f}")
            return

        # Real API Call
        api_payload = []
        for offer in offers:
            api_payload.append({
                "AssetID": offer["AssetID"],
                "Price": offer["Price"]
            })

        try:
            response = await self.client.request(
                "POST", 
                "/marketplace-api/v1/user-offers/create", 
                body={"GameID": self.game_id, "Offers": api_payload}
            )
            logger.info(f"✅ LISTED {len(offers)} items for sale. Response: {response}")
        except Exception as e:
            logger.error(f"❌ Failed to list items: {e}")
