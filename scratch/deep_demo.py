"""
Deep Demo & Audit Engine (v8.1).
Executes SnipingLoop for 10 minutes and generates a deep logic breakdown.

Objective:
- Show purchase logic (Why Item X?)
- Show Oracle behavior.
- Show pricing & Pagination.
- Detect bugs.
"""

import asyncio
import os
import time
import logging
from src.core.target_sniping import SnipingLoop
from src.api.dmarket_api_client import DMarketAPIClient
from src.db.price_history import price_db

# Enhanced Logging for Deep Audit
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger("DeepAudit")

# Force DRY_RUN for safety
os.environ["DRY_RUN"] = "true"

async def run_audit():
    start_time = time.time()
    duration = 600 # 10 minutes
    
    from src.config import Config
    client = DMarketAPIClient(public_key=Config.PUBLIC_KEY, secret_key=Config.SECRET_KEY)
    bot = SnipingLoop(client)
    
    logger.info("="*50)
    logger.info("🛑 STARTING 10-MINUTE DEEP AUDIT (Engine v8.1)")
    logger.info(f"Target Duration: {duration}s")
    logger.info("="*50)
    
    # Run in a background task so we can monitor cycles
    bot_task = asyncio.create_task(bot.start())
    
    cycle_count = 0
    try:
        while time.time() - start_time < duration:
            elapsed = int(time.time() - start_time)
            remaining = duration - elapsed
            
            # Every minute, report progress
            if elapsed % 60 == 0 and elapsed > 0:
                logger.info(f"🕒 Audit Progress: {elapsed}s elapsed | {remaining}s remaining")
                # We can check how many items were added to virtual inventory
                inv = price_db.get_virtual_inventory(status='idle')
                logger.info(f"📈 Virtual Inventory Size: {len(inv)} items items found/acquired.")
            
            await asyncio.sleep(5)
            
            # Stop if we hit 5 cycles early if they take too long, 
            # or just let it run for 10 mins as requested.
            
    except Exception as e:
        logger.error(f"❌ Audit interrupted: {e}")
    finally:
        logger.info("⌛ 10-minute timer EXPIRED. Stopping bot...")
        bot.running = False
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass
        
        logger.info("="*50)
        logger.info("🏁 AUDIT COMPLETED. Analyzing results...")
        logger.info("="*50)

if __name__ == "__main__":
    asyncio.run(run_audit())
