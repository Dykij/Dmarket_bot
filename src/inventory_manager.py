import logging
from typing import List, Dict, Any
from src.api.dmarket_api_client import DMarketAPIClient

logger = logging.getLogger("InventoryManager")

class InventoryManager:
    """ 
    Manages User's DMarket Inventory for Auto-Resale Tracking.
    Prioritizes items NOT currently on sale to avoid redundant listings.
    """
    def __init__(self, api_client: DMarketAPIClient):
        self.api = api_client
        self.cached_inventory = []

    async def fetch_inventory(self, game_id: str = "a8db") -> List[Dict[str, Any]]:
        """
        Fetches the primary user inventory (items not currently on sale).
        Uses pagination to gather all items.
        """
        inventory = []
        cursor = None
        try:
            while True:
                # Use the new verified user-inventory endpoint
                response = await self.api.get_user_inventory(game_id=game_id, limit=50, cursor=cursor)
                items = response.get("objects", []) # user-inventory returns 'objects' array
                inventory.extend(items)
                
                cursor = response.get("cursor")
                if not cursor or len(items) < 50:
                    break
                    
            self.cached_inventory = inventory
            return inventory
        except Exception as e:
            logger.error(f"Failed to fetch DMarket inventory: {e}")
            return self.cached_inventory

    async def fetch_active_offers(self, game_id: str = "a8db") -> List[Dict[str, Any]]:
        """ Fetches items already listed for sale on DMarket. """
        offers = []
        cursor = None
        try:
            while True:
                response = await self.api.get_user_offers(game_id=game_id, limit=50, cursor=cursor)
                items = response.get("objects", [])
                offers.extend(items)
                cursor = response.get("cursor")
                if not cursor or len(items) < 50:
                    break
            return offers
        except Exception as e:
            logger.error(f"Failed to fetch active offers: {e}")
            return []

    def get_inventory(self) -> List[Dict[str, Any]]:
        """ Returns the last fetched inventory cache. """
        return self.cached_inventory
