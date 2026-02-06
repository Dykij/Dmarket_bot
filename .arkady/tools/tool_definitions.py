from typing import List, Dict, Any, Optional

# Gemini Function Definitions for Arkady Swarm Protocol
def get_tool_definitions() -> List[Dict[str, Any]]:
    return [
        {
            "name": "search_items",
            "description": "Search for trading items on DMarket marketplace.",
            "parameters": {
                "type": "object",
                "properties": {
                    "gameId": {"type": "string", "description": "Game ID (e.g., csgo, dota2)."},
                    "limit": {"type": "integer", "description": "Max items to return."},
                    "title": {"type": "string", "description": "Search query/item name."}
                },
                "required": ["gameId"]
            }
        },
        {
            "name": "get_balance",
            "description": "Retrieve current user balance from DMarket.",
            "parameters": {
                "type": "object",
                "properties": {}
            }
        },
        {
            "name": "place_order",
            "description": "Create a buy order on DMarket.",
            "parameters": {
                "type": "object",
                "properties": {
                    "itemId": {"type": "string", "description": "Unique DMarket item ID."},
                    "price": {"type": "number", "description": "Order price in USD."}
                },
                "required": ["itemId", "price"]
            }
        }
    ]
