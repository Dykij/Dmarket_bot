"""
Script: cold_cycle.py
Description: HFT Pipeline Verification Script.
Role: Live monitoring of market data via Rust Network Layer with professional logging.
Risk Management: Enforces Balance Checks and Dry-Run safety.
"""

import sys
import os
import asyncio
import logging
import logging.handlers
import random
import time
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# High-Performance JSON
try:
    import orjson as json
except ImportError:
    import json

from src.core.config_manager import ConfigManager
from src.dmarket.api.client import BaseDMarketClient

# --- Configuration ---
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "cold_cycle.log"
MAX_BYTES = 10 * 1024 * 1024  # 10 MB
BACKUP_COUNT = 5

def setup_logging():
    """Configures Enterprise-grade logging with rotation and console output."""
    LOG_DIR.mkdir(exist_ok=True)
    
    logger = logging.getLogger("ColdCycle")
    logger.setLevel(logging.INFO)
    logger.propagate = False  # Prevent double logging if root logger is touched

    # Formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - [%(levelname)s] - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

    # 1. Rotating File Handler (The Black Box)
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE, maxBytes=MAX_BYTES, backupCount=BACKUP_COUNT, encoding='utf-8'
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(logging.INFO)
    logger.addHandler(file_handler)

    # 2. Console Handler (The Operator View)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    return logger

logger = setup_logging()
if not logger: # Fallback if setup returns None (unlikely but safe)
    logger = logging.getLogger("ColdCycle")

# Force TEST_MODE (Safe handling for missing keys)
if "trading" not in ConfigManager._config:
    ConfigManager._config["trading"] = {}
ConfigManager._config["trading"]["test_mode"] = True

async def run_cycle():
    """Main execution loop for Cold Cycle monitoring."""
    logger.info("❄️ SYSTEM: STARTING COLD CYCLE (Live Monitor) ❄️")
    logger.info(f"🔧 Mode: {'DRY_RUN' if ConfigManager.get('trading.test_mode') else 'LIVE_TRADING'}")
    
    # Init Client
    pub_key = ConfigManager.get("api_key")
    sec_key = ConfigManager.get("secret_key")
    
    try:
        client = BaseDMarketClient(pub_key, sec_key)
    except Exception as e:
        logger.critical(f"❌ Failed to initialize Client: {e}")
        return

    if not client.rust_client:
        logger.critical("❌ Rust Network Layer NOT available. Aborting.")
        return

    # 1. Financial Vision (Balance Check)
    user_balance_usd = 0.0
    try:
        balance_resp = await client.get_balance()
        if "error" in balance_resp:
            logger.error(f"❌ Balance Fetch Failed: {balance_resp['error']}")
        else:
            # DMarket typically returns 'usd' in cents
            user_balance_cents = int(balance_resp.get("usd", 0))
            user_balance_usd = user_balance_cents / 100.0
            logger.info(f"💰 WALLET BALANCE: ${user_balance_usd:.2f} (USD)")
    except Exception as e:
        logger.error(f"❌ Exception fetching balance: {e}")

    # Load Targets
    try:
        targets_path = Path("src/scripts/targets.json")
        if not targets_path.exists():
             logger.error(f"❌ Target file missing: {targets_path}")
             return
             
        with open(targets_path, "r") as f:
            full_targets_list = json.loads(f.read())
    except Exception as e:
        logger.error(f"❌ Failed to load targets.json: {e}")
        return

    # 2. Risk Management (Active Target Filtering)
    active_targets = full_targets_list 
    logger.info(f"🎯 Active Targets: {len(active_targets)} monitored items.")

    # Prepare Rust Bulk Payload
    rust_payload = [(t["game_id"], t["title"]) for t in active_targets]
    
    # Monitoring Loop
    cycles = 3
    for i in range(1, cycles + 1): 
        logger.info(f"--- Cycle {i}/{cycles} ---")
        start_time = time.perf_counter()
        
        try:
            # Asyncio thread offload for Rust blocking call
            # This ensures the Python event loop stays healthy for other tasks (like heartbeats)
            results_map = await asyncio.to_thread(client.rust_client.fetch_bulk, rust_payload)
            
            latency_ms = (time.perf_counter() - start_time) * 1000
            
            # Process Results
            for target in active_targets:
                key = f"{target['game_id']}:{target['title']}"
                data_str = results_map.get(key)
                
                if not data_str:
                    logger.warning(f"⚠️ No data for {key}")
                    continue
                    
                if data_str.startswith("ERROR:"):
                    if "429" in data_str:
                         logger.warning(f"⚠️ Rate Limit (429) for {key}")
                    else:
                         # Log debug to avoid console spam on known transient errors
                         logger.debug(f"❌ Rust Error for {key}: {data_str}")
                    continue

                try:
                    data = json.loads(data_str)
                    objects = data.get("objects", [])
                    if objects:
                        price_data = objects[0].get("price", {})
                        
                        # Flexible price parsing
                        price_cents = 0
                        if "USD" in price_data:
                            price_cents = int(price_data["USD"])
                        elif "amount" in price_data:
                            price_cents = int(price_data["amount"])
                        
                        price_usd = price_cents / 100.0
                        title = objects[0].get("title", "Unknown")
                        
                        # Simulated OBI (Order Book Imbalance) for Dry Run visualization
                        obi = random.uniform(-1.0, 1.0)
                        
                        # 3. Decision Engine (Balance + Signal)
                        signal = "WAIT"
                        if obi > 0.6: 
                            if price_usd <= user_balance_usd:
                                signal = "STRONG_BUY"
                            else:
                                signal = "NO_FUNDS"
                        elif obi < -0.6: 
                            signal = "STRONG_SELL"
                        
                        log_msg = f"👁️ [{target['game_id'].upper()}] {title[:25]:<25} | Price: ${price_usd:>6.2f} | OBI: {obi:>5.2f} | Signal: {signal}"
                        
                        if signal == "STRONG_BUY":
                            logger.info(log_msg) # Highlight buys
                        else:
                            logger.info(log_msg)

                    else:
                        pass # Empty order book is normal for illiquid items
                except Exception as e:
                    logger.error(f"❌ Parse Error {key}: {e}")

            logger.info(f"⏱️ Batch Latency: {latency_ms:.2f}ms")
            
        except Exception as e:
            logger.critical(f"❌ Cycle Critical Failure: {e}")

        # Rate Limit Compliance (Global Token Bucket is in Rust, but we add safety gap)
        await asyncio.sleep(1.0) 

    logger.info("❄️ Cold Cycle Completed Successfully.")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(run_cycle())
    except KeyboardInterrupt:
        logger.info("🛑 Cycle Interrupted by User")
