"""
Verification Script for Sandbox v9.0 features.
Tests Competition (Ghost Buyers) and Trade Lock logic.
"""

import asyncio
import os
import time
import logging
from src.db.price_history import price_db
from src.core.target_sniping import SnipingLoop
from src.api.dmarket_api_client import DMarketAPIClient

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("TestV9")

async def test_v9_features():
    os.environ["DRY_RUN"] = "true"
    client = DMarketAPIClient("pub", "sec")
    bot = SnipingLoop(client)
    
    logger.info("="*50)
    logger.info("🧪 TESTING SANDBOX V9.0: MARKET FRICTION")
    logger.info("="*50)
    
    # 1. Test Trade Lock Implementation
    logger.info("📝 Step 1: Purchasing an item with 7-day Trade Lock...")
    price_db.add_virtual_item("AK-47 | Slate (FT)", 5.0, trade_lock_hours=168)
    
    inv_all = price_db.get_virtual_inventory(status='idle', only_unlocked=False)
    inv_unlocked = price_db.get_virtual_inventory(status='idle', only_unlocked=True)
    
    logger.info(f"📊 Total items: {len(inv_all)} | Unlocked items: {len(inv_unlocked)}")
    if len(inv_all) > len(inv_unlocked):
        logger.info("✅ SUCCESS: Trade Lock is working. Item is hidden from resale.")
    else:
        logger.error("❌ FAILURE: Trade Lock failed to hide the item.")

    # 2. Test Competition Modeling
    logger.info("\n📝 Step 2: Testing Competition (Ghost Buyers) for High Margin items...")
    high_margin = 0.45 # 45% profit should trigger 90% competition fail
    fails = 0
    total = 20
    for _ in range(total):
        if not bot._simulate_competition(high_margin):
            fails += 1
            
    fail_rate = (fails / total) * 100
    logger.info(f"📊 Competition Results (Margin {high_margin*100}%): {fails}/{total} sniped by rivals ({fail_rate}%).")
    if fail_rate > 70:
        logger.info("✅ SUCCESS: Competition modeling correctly repelled high-margin snipes.")
    else:
        logger.error("❌ FAILURE: Competition is too weak for high-margin deals.")

    logger.info("\n="*50)
    logger.info("🏁 V9.0 VERIFICATION COMPLETE")
    logger.info("="*50)

if __name__ == "__main__":
    asyncio.run(test_v9_features())
