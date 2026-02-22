"""
Script: src/bot/trader.py (The Hands)
Description: Manages Targets (Buying) and Offers (Selling).
Executes orders based on opportunities from the Scanner.
"""

import logging
from typing import Dict

from src.config import Config
from src.utils.api_client import AsyncDMarketClient

logger = logging.getLogger("Trader")

class MarketMaker:
    """
    Places Targets (Bids) and lists purchased items (Asks).
    Handles the actual trading operations.
    """
    
    def __init__(self, client: AsyncDMarketClient):
        self.client = client
        self.dry_run = Config.DRY_RUN
        self.game_id = Config.GAME_ID

    async def place_target(self, opportunity: Dict):
        """Places a Buy Order (Target)."""
        title = opportunity["title"]
        target_price = opportunity["target_price"]
        profit_usd = opportunity["profit"] / 100.0

        # --- Smart Attributes (Float) ---
        attrs = []
        if Config.PREFER_LOW_FLOAT:
            # Determine exterior from title
            exterior_code = None
            if "(Factory New)" in title: exterior_code = "FN"
            elif "(Minimal Wear)" in title: exterior_code = "MW"
            elif "(Field-Tested)" in title: exterior_code = "FT"
            elif "(Well-Worn)" in title: exterior_code = "WW"
            elif "(Battle-Scarred)" in title: exterior_code = "BS"
            
            if exterior_code and exterior_code in Config.FLOAT_CODES:
                # Add preferred float ranges (e.g. FT-0, FT-1)
                # DMarket allows passing a list of values for 'floatPartValue'
                best_floats = Config.FLOAT_CODES[exterior_code]
                for code in best_floats:
                    attrs.append({"Name": "floatPartValue", "Value": code})
                
                # Note: If we add attributes, we might get LESS fills, 
                # but better quality. It's a trade-off.
                # Currently DMarket Target API structure for attributes:
                # "Attrs": [{"Name": "floatPartValue", "Value": "FT-0"}, ...]
                # If we send multiple, does it mean OR? Yes usually.

        if self.dry_run:
            attr_str = f" [Attrs: {attrs}]" if attrs else ""
            logger.info(f"🎯 [SIMULATION] Placed TARGET on '{title}' at ${(target_price/100):.2f}{attr_str}")
            return True
        
        try:
            target_data = {
                "Amount": 1,
                "Price": {"Amount": target_price, "Currency": "USD"},
                "Title": title
            }
            
            if attrs:
                target_data["Attrs"] = attrs

            target_payload = [target_data]
            
            # API Call (Buy)
            response = await self.client.request(
                "POST", 
                "/marketplace-api/v1/user-targets/create", 
                body={"GameID": self.game_id, "Targets": target_payload}
            )
            
            logger.info(f"✅ TARGET ACTIVE: {title} @ ${(target_price/100):.2f} (Profit: ${profit_usd:.2f})")
            return response

        except Exception as e:
            logger.error(f"❌ Target failed on {title}: {e}")
            return False

    async def list_bought_items(self):
        """Checks inventory and lists newly purchased items."""
        # This will be implemented fully once we have inventory logic
        pass

    async def cancel_stale_targets(self):
        """Cancels targets that are no longer profitable."""
        # Risk management logic
        pass
