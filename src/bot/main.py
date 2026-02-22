"""
Entry Point: src/bot/main.py
The Brain. Launches the HFT system.
Loads Config, connects to DMarket API, and orchestrates scanning and trading.
"""

import asyncio
import logging
import json
import sys

# Add project root to sys.path
sys.path.append("D:\\Dmarket_bot")

from src.config import Config
from src.utils.api_client import AsyncDMarketClient
from src.bot.scanner import MarketScanner
from src.bot.trader import MarketMaker
from src.bot.sales import SalesManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("bot.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("Main")

def load_items_pool():
    try:
        with open("src/data/items_pool.json", "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("❌ src/data/items_pool.json not found!")
        return []

async def main():
    if not Config.PUBLIC_KEY:
        logger.error("❌ API Keys missing in .env")
        return

    logger.info(f"🚀 STARTING CS2 MARKET MAKER (Dry Run: {Config.DRY_RUN})")
    
    # Load Items
    items_pool = load_items_pool()
    if not items_pool:
        logger.error("No items to scan.")
        return
    logger.info(f"📦 Pool: {len(items_pool)} items.")

    async with AsyncDMarketClient(Config.PUBLIC_KEY, Config.SECRET_KEY) as client:
        # Initialize Modules
        scanner = MarketScanner(client)
        trader = MarketMaker(client)
        sales = SalesManager(client)
        
        # Main Loop
        chunk_size = Config.BATCH_SIZE
        
        try:
            while True:
                # 1. SALES CYCLE (Check inventory first to free up capital)
                logger.info("📦 Checking Inventory for new sales...")
                await sales.process_inventory()

                # 2. BUY CYCLE (Place new targets)
                # Iterate over the pool in chunks
                for i in range(0, len(items_pool), chunk_size):
                    batch = items_pool[i:i + chunk_size]
                    logger.info(f"📡 Scanning batch {i//chunk_size + 1} ({len(batch)} items)...")
                    
                    # SCAN
                    opportunities = await scanner.scan(batch)
                    
                    # TRADE (Place Targets)
                    for opp in opportunities:
                        await trader.place_target(opp)
                    
                    # Rate Limit Protection
                    await asyncio.sleep(Config.SCAN_INTERVAL)
                
                logger.info("♻️ Cycle complete. Restarting...")
                await asyncio.sleep(1)

        except KeyboardInterrupt:
            logger.info("🛑 Bot stopped by user.")
        except Exception as e:
            logger.error(f"Critical error: {e}")

if __name__ == "__main__":
    asyncio.run(main())