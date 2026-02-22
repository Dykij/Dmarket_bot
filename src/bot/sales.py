"""
Script: src/bot/sales.py (The Closer)
Description: Manages the selling side of the bot.
Autonomously scans inventory and lists items for sale at competitive prices.
"""

import logging
from typing import List, Dict

from src.config import Config
from src.utils.api_client import AsyncDMarketClient

logger = logging.getLogger("Sales")

class SalesManager:
    """
    Handles inventory management and selling.
    Strategy: 
    1. Fetch inventory.
    2. For each item, check current Market Ask price.
    3. List item at (BestAsk - $0.01) to be the cheapest.
    """
    
    def __init__(self, client: AsyncDMarketClient):
        self.client = client
        self.dry_run = Config.DRY_RUN
        self.game_id = Config.GAME_ID

    async def process_inventory(self):
        """
        Main routine: Fetches inventory and lists unlisted items.
        """
        try:
            # 1. Get Inventory
            # The API client needs a method for this, or we use raw request
            response = await self.client.get_user_inventory(game=self.game_id)
            
            items = []
            if "objects" in response:
                items = response["objects"]
            elif "Items" in response:
                items = response["Items"]
            
            # In Dry Run, we mock an item if the real inventory is empty, 
            # to prove the logic works.
            if self.dry_run and not items:
                logger.info("📦 [SIMULATION] Inventory empty. Simulating 1 item (AK-47 Redline) to test sales logic...")
                items = [{
                    "ItemId": "sim_123",
                    "Title": "AK-47 | Redline (Field-Tested)",
                    "InMarket": False
                }]

            if not items:
                return

            # 2. Process Items
            items_to_sell = []
            for item in items:
                # Check different casing from API
                in_market = item.get("inMarket") or item.get("InMarket", False)
                if in_market and not self.dry_run:
                    continue
                
                title = item.get("title") or item.get("Title", "Unknown")
                asset_id = item.get("itemId") or item.get("AssetID") or item.get("ItemId")
                
                # Fetch current market price to undercut
                price_response = await self.client.get_aggregated_prices(names=[title], game=self.game_id)
                
                best_ask_cents = 0
                if "aggregatedPrices" in price_response and len(price_response["aggregatedPrices"]) > 0:
                    market_data = price_response["aggregatedPrices"][0]
                    best_ask_raw = market_data.get("offerBestPrice", 0)
                    
                    if isinstance(best_ask_raw, dict):
                        best_ask_cents = int(best_ask_raw.get("Amount", 0))
                    elif isinstance(best_ask_raw, (int, float, str)):
                        try:
                            best_ask_cents = int(best_ask_raw)
                        except (ValueError, TypeError):
                            best_ask_cents = 0
                
                if best_ask_cents > 0:
                    # Strategy: Undercut by 1 cent
                    sell_price = best_ask_cents - 1
                    
                    items_to_sell.append({
                        "AssetID": asset_id,
                        "Price": {"Amount": sell_price, "Currency": "USD"},
                        "Title": title # For logging
                    })
                else:
                    logger.warning(f"⚠️ Could not find market price for {title}. Skipping list.")

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
                logger.info(f"💰 [SIMULATION] Listing '{title}' for ${price_usd:.2f} (Undercut Best Ask)")
            return

        # Real API Call
        api_payload = []
        for offer in offers:
            # The API expects "AssetID" and "Price" inside "Offers" array
            api_payload.append({
                "AssetID": offer["AssetID"],
                "Price": offer["Price"]
            })

        try:
            # We use request() directly because client wrapper might not match v1.1 perfectly yet
            response = await self.client.request(
                "POST", 
                "/marketplace-api/v1/user-offers/create", 
                body={"GameID": self.game_id, "Offers": api_payload}
            )
            logger.info(f"✅ LISTED {len(offers)} items for sale. Response: {response}")
        except Exception as e:
            logger.error(f"❌ Failed to list items: {e}")
