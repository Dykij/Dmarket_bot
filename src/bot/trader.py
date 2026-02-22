"""
Script: src/bot/trader.py (The Hands)
Description: Manages Targets (Buying) and Offers (Selling).
Executes orders based on opportunities from the Scanner.
"""

import logging
from typing import List, Dict

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

        if self.dry_run:
            logger.info(f"🎯 [SIMULATION] Placed TARGET on '{title}' at ${(target_price/100):.2f}")
            return True
        
        try:
            target_payload = [{
                "Amount": 1,
                "Price": {"Amount": target_price, "Currency": "USD"},
                "Title": title
            }]
            
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
