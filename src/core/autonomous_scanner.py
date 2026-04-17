"""
Autonomous DMarket Scanner v3.1 — Pure Script / Math Pipeline.

Pipeline:
  1. DMarketAPIClient initialization.
  2. InventoryManager initialization.
  3. Start the Target Sniping Loop (Math based).
"""

import asyncio
import os
import sys
import logging
import time
from logging.handlers import RotatingFileHandler
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.api.dmarket_api_client import DMarketAPIClient
from src.inventory_manager import InventoryManager
from src.core.target_sniping import SnipingLoop
from src.utils.vault import vault

def setup_logging():
    """Configures rotating file logs (v7.7) to prevent disk overflow."""
    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    log_file = os.path.join(BASE_DIR, "logs", "bot_24_7.log")
    os.makedirs(os.path.dirname(log_file), exist_ok=True)

    # 10MB per file, keep 5 backups
    handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
    handler.setFormatter(log_formatter)
    handler.setLevel(logging.INFO)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(handler)
    
    # Also log to console
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(log_formatter)
    root_logger.addHandler(console_handler)

setup_logging()
logger = logging.getLogger("AutonomousScanner")

async def run_autonomous_scanner():
    """Main Entry with Infinite Autonomy Loop (v7.7/7.8)."""
    retry_delay = 5
    
    while True:
        try:
            # Re-initialize vault and environment each major restart
            for env_candidate in [os.path.join(os.getcwd(), ".env"), os.path.join(BASE_DIR, ".env")]:
                if os.path.isfile(env_candidate):
                    load_dotenv(dotenv_path=env_candidate)
                    vault.re_initialize()
                    break
            
            pub_key = os.environ.get("DMARKET_PUBLIC_KEY", "").strip()
            sec_key = vault.get_dmarket_secret()
            
            if not pub_key or not sec_key:
                logger.error("No API keys found. Retrying in 30s...")
                await asyncio.sleep(30)
                continue

            api = DMarketAPIClient(public_key=pub_key, secret_key=sec_key)
            inventory_mgr = InventoryManager(api)
            bot = SnipingLoop(api)
            bot.inventory_mgr = inventory_mgr # Link the manager
            
            logger.info("🚀 QUANTITATIVE ENGINE v7.8 (24/7 Deep Scan Active)")
            await bot.start()
            
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"⚠️ CRITICAL ENGINE CRASH: {e}")
            await asyncio.sleep(retry_delay)
            retry_delay = min(retry_delay * 2, 3600)

if __name__ == "__main__":
    try:
        asyncio.run(run_autonomous_scanner())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
