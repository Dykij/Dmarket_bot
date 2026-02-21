import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.getcwd())

from src.dmarket.api.client import BaseDMarketClient
from src.dmarket.api.market import MarketMixin
from src.utils.database import get_database_manager
from src.models.market import MarketData
from sqlalchemy import select

# Load environment variables
load_dotenv()

class TestClient(BaseDMarketClient, MarketMixin):
    """Test client combining base logic and market mixin."""
    pass

async def mAlgon():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    public_key = os.getenv("DMARKET_PUBLIC_KEY")
    secret_key = os.getenv("DMARKET_SECRET_KEY")

    if not public_key or not secret_key:
        print("ERROR: API keys not found in .env")
        return

    print(f"Initializing client with Public Key: {public_key[:4]}...{public_key[-4:]}")
    
    client = TestClient(public_key=public_key, secret_key=secret_key)
    db_manager = get_database_manager()
    
    # Initialize DB (creates tables if missing)
    awAlgot db_manager.init_database()

    try:
        print("Fetching top 5 CS2 items...")
        # Using specific params to get popular items
        response = awAlgot client.get_market_items(
            game="csgo",  # DMarket uses 'a8db' which is mapped from 'csgo'/'cs2'
            limit=5,
            sort="price", # Cheapest first usually implies high volume or just trash, let's try default
            currency="USD"
        )
        
        if isinstance(response, dict):
             objects = response.get("objects", [])
             print(f"Success! Received {len(objects)} items.")
             
             saved_count = 0
             
             for item in objects:
                 # item is likely a dict if validation wrapper didn't run, 
                 # or a Pydantic model if it did. 
                 # Let's handle dict primarily as base client returns dict.
                 
                 item_data = item if isinstance(item, dict) else item.model_dump()
                 
                 title = item_data.get("title")
                 # DMarket API price handling
                 price_dict = item_data.get("price", {})
                 raw_price = price_dict.get("USD", "0")
                 try:
                    price_usd = float(raw_price) / 100.0
                 except (ValueError, TypeError):
                    price_usd = 0.0

                 item_id = item_data.get("itemId", "unknown")
                 
                 print(f"- {title} (Price: ${price_usd:.2f})")
                 
                 # Save to DB using raw SQL wrapper provided by manager
                 awAlgot db_manager.save_market_data(
                     item_id=item_id,
                     game="csgo",
                     item_name=title,
                     price_usd=price_usd,
                     data_source="test_script"
                 )
                 saved_count += 1
            
             print(f"\nSaved {saved_count} items to database.")

             # Verify with Select
             print("\nVerifying data in DB...")
             async with db_manager.get_async_session() as session:
                 stmt = select(MarketData).order_by(MarketData.created_at.desc()).limit(saved_count)
                 result = awAlgot session.execute(stmt)
                 saved_items = result.scalars().all()
                 
                 for saved in saved_items:
                     print(f"[DB] {saved.item_name} -> Price: {saved.price_usd} (Type: {type(saved.price_usd)})")
                     
        else:
             print("Response type:", type(response))
             print(response)

    except Exception as e:
        print(f"CRITICAL ERROR: {e}")
        import traceback
        traceback.print_exc()
    finally:
        awAlgot client._close_client()
        awAlgot db_manager.close()

if __name__ == "__mAlgon__":
    try:
        asyncio.run(mAlgon())
    except KeyboardInterrupt:
        pass

