"""
Bot: Trident (CS2 Market Maker)
Version: 1.0.0 (Clean Slate)
Strategy: Spread Capture (>7%)
Game: CS2 Only (a8db)

Modules:
1. Scanner: Finds profitable items.
2. OrderManager: Places/Updates Buy Targets.
3. SalesManager: Lists inventory for sale.
"""

import asyncio
import os
import logging
import json
from dotenv import load_dotenv
import sys

# Add project root
sys.path.append("D:\\Dmarket_bot")
from src.utils.api_client import AsyncDMarketClient

# Configuration
GAME_ID = "a8db"  # CS2
MIN_SPREAD_PCT = 7.0
MAX_PRICE_USD = 15.0  # Conservative limit
DRY_RUN = True  # Safety First

# Load environment variables
load_dotenv()
PUBLIC_KEY = os.getenv("DMARKET_PUBLIC_KEY")
SECRET_KEY = os.getenv("DMARKET_SECRET_KEY")

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("trident.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Trident")

class TridentBot:
    def __init__(self):
        self.client = None
        self.items_pool = self.load_items()
        self.active_targets = {}  # {title: price_cents}

    def load_items(self):
        try:
            with open("src/data/items_pool.json", "r") as f:
                items = json.load(f)
                logger.info(f"📦 Loaded {len(items)} items from pool.")
                return items
        except FileNotFoundError:
            logger.error("❌ items_pool.json missing!")
            return []

    async def start(self):
        if not PUBLIC_KEY:
            logger.critical("❌ API Keys missing!")
            return

        self.client = await AsyncDMarketClient(PUBLIC_KEY, SECRET_KEY).__aenter__()
        logger.info("🔱 Trident Bot Started (CS2 Market Maker)")
        logger.info(f"   Mode: {'SIMULATION' if DRY_RUN else 'LIVE TRADING'}")
        
        try:
            # Run loops concurrently
            await asyncio.gather(
                self.scanner_loop(),
                self.sales_loop()
            )
        except asyncio.CancelledError:
            logger.info("🛑 Bot stopping...")
        finally:
            await self.client.__aexit__(None, None, None)

    async def scanner_loop(self):
        """Scans market and places buy targets."""
        while True:
            logger.info("📡 Scanning market...")
            
            # Process in chunks of 20
            chunk_size = 20
            for i in range(0, len(self.items_pool), chunk_size):
                chunk = self.items_pool[i:i + chunk_size]
                await self.process_batch(chunk)
                await asyncio.sleep(1)

            logger.info("💤 Scan complete. Sleeping 60s...")
            await asyncio.sleep(60)

    async def process_batch(self, items):
        try:
            response = await self.client.get_aggregated_prices(names=items)
            if "aggregatedPrices" not in response:
                return

            for item in response["aggregatedPrices"]:
                title = item.get("title", "Unknown")
                
                # Parse Prices
                bid_raw = item.get("orderBestPrice", 0)
                ask_raw = item.get("offerBestPrice", 0)
                
                bid_cents = int(bid_raw) if bid_raw else 0
                ask_cents = int(ask_raw) if ask_raw else 0
                
                if bid_cents == 0 or ask_cents == 0:
                    continue

                # Analyze Spread
                ask_usd = ask_cents / 100.0
                bid_usd = bid_cents / 100.0
                
                if ask_usd > MAX_PRICE_USD:
                    continue

                spread_pct = ((ask_usd - bid_usd) / ask_usd) * 100
                
                if spread_pct >= MIN_SPREAD_PCT:
                    target_price = bid_cents + 1
                    
                    # Log opportunity
                    profit = (ask_cents * 0.93) - target_price
                    if profit > 0:
                        logger.info(f"💎 FOUND: {title} | Spread: {spread_pct:.1f}% | Est. Profit: ${(profit/100):.2f}")
                        
                        if not DRY_RUN:
                            # TODO: Place Real Target
                            pass
                        else:
                            logger.info(f"   [SIM] Placed Target @ ${(target_price/100):.2f}")

        except Exception as e:
            logger.error(f"Batch Error: {e}")

    async def sales_loop(self):
        """Monitors inventory and lists items for sale."""
        while True:
            # In simulation, we just log that we are checking
            # In live, we would fetch inventory and create offers
            # logger.info("💰 Checking inventory for sales...")
            await asyncio.sleep(120)  # Check every 2 mins

if __name__ == "__main__":
    bot = TridentBot()
    try:
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        pass