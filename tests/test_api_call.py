import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.dmarket.api.client import BaseDMarketClient
from src.dmarket.api.market import MarketMixin

# Load environment variables
load_dotenv()

class TestClient(BaseDMarketClient, MarketMixin):
    """Test client combining base logic and market mixin."""
    pass

async def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    public_key = os.getenv("DMARKET_PUBLIC_KEY")
    secret_key = os.getenv("DMARKET_SECRET_KEY")

    if not public_key or not secret_key:
        print("ERROR: API keys not found in .env")
        return

    print(f"Initializing client with Public Key: {public_key[:4]}...{public_key[-4:]}")
    
    client = TestClient(public_key=public_key, secret_key=secret_key)
    
    try:
        print("Fetching top 5 CS2 items...")
        # Using specific params to get popular items
        response = await client.get_market_items(
            game="csgo",  # DMarket uses 'a8db' which is mapped from 'csgo'/'cs2'
            limit=5,
            sort="price", # Cheapest first usually implies high volume or just trash, let's try default
            currency="USD"
        )
        
        # Check if response is Pydantic model or dict (it should be dict based on market.py return type hint, 
        # but the decorator might return the model if configured so. 
        # Wait, the decorator in market.py returns dict[str, Any] per type hint, 
        # but let's see what actually comes back.)
        
        if isinstance(response, dict):
             objects = response.get("objects", [])
             print(f"Success! Received {len(objects)} items.")
             for item in objects:
                 # item might be a dict or a Pydantic object depending on validation wrapper
                 if hasattr(item, "title"):
                     print(f"- {item.title} (${item.price})")
                 else:
                     print(f"- {item.get('title')} (${item.get('price', {}).get('USD', 'N/A')})")
        else:
             print("Response type:", type(response))
             print(response)

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await client._close_client()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass

