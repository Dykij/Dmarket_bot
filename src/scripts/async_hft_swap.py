"""
Script: async_hft_swap.py
Description: Asynchronous HFT Swap & Sell using TaskGroups and AsyncDMarketClient.
Targets: Mann Co. Supply Crate Key (TF2), Tour of Duty Ticket (TF2).
"""

import asyncio
import logging
import os
import sys
import time
from typing import List, Dict

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.utils.api_client import AsyncDMarketClient
from src.core.database import db  # <--- IMPORT DATABASE
from src.core.config_manager import ConfigManager
from dotenv import load_dotenv

load_dotenv(r"D:\Dmarket_bot\.env")

# Setup Logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("AsyncHFT")

# Configuration
GAME_ID = "tf2"
TARGET_ITEMS = [
    "Mann Co. Supply Crate Key",
    "Tour of Duty Ticket"
]

# Min prices (cents) to avoid loss
MIN_PRICES = {
    "Mann Co. Supply Crate Key": 150, 
    "Tour of Duty Ticket": 70
}

async def fetch_market_price(client: AsyncDMarketClient, title: str) -> int:
    """Fetches the lowest market price for an item and RECORDS it."""
    try:
        # Fetch top 1 item sorted by price
        data = await client.request(
            "GET", 
            "/exchange/v1/market/items", 
            params={
                "gameId": GAME_ID, 
                "title": title, 
                "limit": 1, 
                "sortType": "price", 
                "orderBy": "asc", 
                "currency": "USD"
            },
            sign=True
        )
        
        objects = data.get("objects", [])
        if objects:
            price_doc = objects[0].get("price", {})
            if "USD" in price_doc:
                try:
                    price = int(float(price_doc["USD"]))
                    
                    # --- DATA COLLECTION HOOK ---
                    # Record the tick to SQLite for AI training
                    if price > 0:
                        await db.insert_tick(title, price)
                    # ----------------------------
                    
                    return price
                except ValueError:
                    return 0
            
        logger.warning(f"⚠️ No market data for {title}")
        return 0
    except Exception as e:
        logger.error(f"❌ Failed to fetch price for {title}: {e}")
        return 0

def calculate_undercut(market_price: int, min_price: int) -> int:
# ... (rest of the file remains similar)
    """Smart Undercut Logic."""
    if market_price <= 0:
        return 0
        
    # Undercut by 1 cent
    new_price = market_price - 1
    
    # Safety Check
    if new_price < min_price:
        logger.warning(f"🛑 Calculated price {new_price} < Min Price {min_price}. Holding.")
        return 0
        
    return new_price

async def process_item(client: AsyncDMarketClient, item: Dict, offers_batch: List):
    """Analyzes a single item and prepares an offer."""
    title = item.get("title")
    # Debug item structure if needed
    asset_id = item.get("itemId") or item.get("id") or item.get("assetId") # Try multiple keys
    
    if not asset_id and title in TARGET_ITEMS:
        logger.warning(f"⚠️ Missing Asset ID for {title}. Keys: {list(item.keys())}")
        return

    if title not in TARGET_ITEMS:
        return

    logger.info(f"🔍 Analyzing: {title} ({asset_id})")
    
    # Fetch Market Price
    market_price = await fetch_market_price(client, title)
    if market_price == 0:
        return

    # Calculate Price
    min_price = MIN_PRICES.get(title, 0)
    sell_price = calculate_undercut(market_price, min_price)
    
    if sell_price > 0:
        logger.info(f"💡 Strategy: {title} | Market: {market_price}c -> Sell: {sell_price}c")
        # Structure for Marketplace API v2
        offers_batch.append({
            "assetId": asset_id,
            "priceCents": sell_price
        })

async def main():
    # Load Config (Directly from .env via dotenv)
    # ConfigManager.load() # Skipping ConfigManager to avoid potential issues
    
    public_key = os.environ.get("DMARKET_PUBLIC_KEY", "").strip()
    secret_key = os.environ.get("DMARKET_SECRET_KEY", "").strip()

    if not public_key or not secret_key:
        logger.error("❌ API Keys missing in environment!")
        return
        
    logger.info(f"🔑 Public Key Length: {len(public_key)}")
    logger.info(f"🔑 Secret Key Length: {len(secret_key)}")

    logger.info("🚀 STARTING ASYNC SWAP & SELL...")
    start_time = time.time()

    # Init DB
    await db.connect()

    try:
        async with AsyncDMarketClient(public_key, secret_key) as client:
            # 1. Fetch Inventory
            logger.info("📦 Fetching Inventory...")
            inventory_data = await client.get_user_inventory(game=GAME_ID)
            items = inventory_data.get("objects", [])
            logger.info(f"📦 Inventory received: {len(items)} items")

            if not items:
                logger.info("💤 No items to sell.")
                return

            # 2. Analyze Items & Prepare Batch (Concurrency via TaskGroup)
            offers_batch = []
            
            # Python 3.11+ TaskGroup
            if hasattr(asyncio, "TaskGroup"):
                async with asyncio.TaskGroup() as tg:
                    for item in items:
                        tg.create_task(process_item(client, item, offers_batch))
            else:
                # Fallback for older python
                tasks = [process_item(client, item, offers_batch) for item in items]
                await asyncio.gather(*tasks)

            # 3. Execute Batch Offer
            if offers_batch:
                logger.info(f"⚡ Executing Batch Offer ({len(offers_batch)} items)...")
                
                # Using Marketplace API V2 Batch Create
                payload = {"requests": offers_batch}
                
                try:
                    # Note: This endpoint is POST /marketplace-api/v2/offers:batchCreate
                    # It likely requires signing.
                    response = await client.request("POST", "/marketplace-api/v2/offers:batchCreate", body=payload, sign=True)
                    
                    # Check response
                    # Format: { "result": [...], "failed": [...] } or { "offers": [...] }? 
                    # Let's log the full response to be sure.
                    logger.info(f"✅ API Response: {response}")

                except Exception as e:
                    logger.error(f"❌ Batch Transaction Failed: {e}")
            else:
                logger.info("💤 No suitable offers generated.")
    
    finally:
        await db.close()

    duration = time.time() - start_time
    logger.info(f"🏁 OPERATION COMPLETE. Time: {duration:.4f}s")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
