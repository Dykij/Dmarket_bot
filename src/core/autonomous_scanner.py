"""
Autonomous DMarket Scanner v3.1 — Pure Script / Math Pipeline.

Pipeline:
  1. DMarketAPIClient initialization.
  2. InventoryManager initialization.
  3. Start the Target Sniping Loop (Math based, no LLMs).
"""

import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

BASE_DIR = "/mnt/d/Dmarket_bot" if sys.platform != "win32" else "D:/Dmarket_bot"
sys.path.append(BASE_DIR)

from src.api.dmarket_api_client import DMarketAPIClient
from src.inventory_manager import InventoryManager
from src.core.target_sniping import SnipingLoop
from src.utils.vault import vault

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("AutonomousScanner")

async def run_autonomous_scanner():
    print("\n" + "=" * 50)
    print("🚀 ZAПУСК АВТОНОМНОГО СКАННЕРА DMARKET v3.1")
    print("   (Target Sniping + Pure Math, No LLM)")
    print("=" * 50 + "\n")

    # Try multiple .env locations
    for env_candidate in [
        os.path.join(BASE_DIR, "config", ".env"),
        os.path.join(BASE_DIR, ".env"),
    ]:
        if os.path.isfile(env_candidate):
            load_dotenv(dotenv_path=env_candidate)
            break

    api = None
    inv_mgr = None
    
    pub_key = os.environ.get("DMARKET_PUBLIC_KEY", "").strip()
    sec_key = vault.get_dmarket_secret()
    
    if pub_key and sec_key and len(sec_key) >= 64:
        logger.info("Keys loaded via Vault, initializing DMarket API Client...")
        api = DMarketAPIClient(public_key=pub_key, secret_key=sec_key)
        inv_mgr = InventoryManager(api)
    else:
        logger.warning("API keys not found or invalid! Proceeding without placing real mock orders.")
        # Minimal skeleton setup or mock if need be.
        return

    # Phase B: Balance + Inventory Checks periodically or initially
    try:
        balance = await api.get_real_balance()
        logger.info(f"💵 Real Account Balance: ${balance:.2f}")
    except Exception as e:
        logger.error(f"Failed to get balance: {e}")

    if inv_mgr:
        # Pre-fetch initially
        await inv_mgr.fetch_inventory()
        inventory = inv_mgr.get_inventory()
        if inventory:
            logger.info(f"📦 Found {len(inventory)} items in inventory.")
        else:
            logger.info("📭 Inventory is empty.")

    # Phase A: Target Sniping Loop
    logger.info("Initiating Target Sniping Engine...")
    bot = SnipingLoop(api)
    
    async def continuous_resale():
        while bot.running:
            await bot.auto_resale(inv_mgr)
            await asyncio.sleep(60)  # Check inventory every minute
    
    # Start the async loop and auto-resale concurrently
    try:
        await asyncio.gather(
            bot.start(),
            continuous_resale()
        )
    except Exception as e:
        logger.error(f"Scanner crashed: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(run_autonomous_scanner())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
