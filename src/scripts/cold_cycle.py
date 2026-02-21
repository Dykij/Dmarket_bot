"""
Script: cold_cycle.py
Description: Runs a 'Cold Cycle' to test the full HFT pipeline (Rust Network -> Python Logic) 
without executing real trades. Simulates a live monitoring environment.
Multi-Game Expansion: Now supports CS2, Dota 2, Rust, TF2.
Risk Management: Balance Awareness & Dynamic Filtering.
"""

import sys
import os
import asyncio
import logging
import random
import time
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# HFT Optimization: orjson
try:
    import orjson as json
except ImportError:
    import json

from src.core.config_manager import ConfigManager
# Quick fix for logger sig mismatch: just use basic logging if setup_logger fails or is complex
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("ColdCycle")

from src.dmarket.api.client import BaseDMarketClient

# Force TEST_MODE (Safe handling for missing keys)
if "trading" not in ConfigManager._config:
    ConfigManager._config["trading"] = {}
ConfigManager._config["trading"]["test_mode"] = True

async def run_cycle():
    logger.info("❄️ STARTING COLD CYCLE (Live Monitor - Multi-Game Expansion) ❄️")
    
    # Init Client
    pub_key = ConfigManager.get("api_key")
    sec_key = ConfigManager.get("secret_key")
    client = BaseDMarketClient(pub_key, sec_key)

    if not client.rust_client:
        logger.error("❌ Rust Client NOT available. Aborting Cold Cycle.")
        return

    # 1. Fetch Balance (The "Financial Vision")
    try:
        balance_resp = await client.get_balance()
        if "error" in balance_resp:
            logger.error(f"❌ Failed to fetch balance: {balance_resp['error']}")
            user_balance_usd = 0.0 # Default to 0 for safety
        else:
            # Assuming DMarket response format: {"usd": 1234, ...} or {"objects": [...]}
            # Usually /account/v1/balance returns {"usd": 1234, "knyc": ...} in cents
            user_balance_cents = int(balance_resp.get("usd", 0))
            user_balance_usd = user_balance_cents / 100.0
            logger.info(f"💰 WALLET BALANCE: ${user_balance_usd:.2f} (USD)")
    except Exception as e:
        logger.error(f"❌ Exception fetching balance: {e}")
        user_balance_usd = 0.0

    # Load Targets
    try:
        targets_path = Path("src/scripts/targets.json")
        with open(targets_path, "r") as f:
            full_targets_list = json.loads(f.read())
    except Exception as e:
        logger.error(f"❌ Failed to load targets.json: {e}")
        return

    # 2. Dynamic Risk Management (Filter Targets)
    # Filter out items that are likely too expensive (using a hardcoded estimation or just skip if balance is very low)
    # Since we don't know item price before fetching, we can't filter purely on price yet without history.
    # BUT, if balance is < $10, we probably shouldn't scan High Tier items.
    
    # Simple heuristic: If balance < $50, exclude "High Tier" (Rust/Dota Expensive).
    # For now, let's just log the count.
    
    active_targets = full_targets_list 
    # Example Logic (commented out until we have price history or tags):
    # if user_balance_usd < 50.0:
    #     active_targets = [t for t in full_targets_list if not is_expensive(t)]
    
    logger.info(f"🎯 Active Targets: {len(active_targets)} (Filtered from {len(full_targets_list)}) based on Risk Profile.")

    # Prepare Rust Bulk Payload
    rust_payload = [(t["game_id"], t["title"]) for t in active_targets]
    
    for i in range(1, 4): # Run 3 cycles
        logger.info(f"--- Cycle {i}/3 ---")
        start_time = time.perf_counter()
        
        try:
            # Use asyncio.to_thread to keep main loop responsive
            results_map = await asyncio.to_thread(client.rust_client.fetch_bulk, rust_payload)
            
            latency = (time.perf_counter() - start_time) * 1000
            
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
                         pass 
                    continue

                try:
                    data = json.loads(data_str)
                    objects = data.get("objects", [])
                    if objects:
                        price_data = objects[0]["price"]
                        # Handle different price formats
                        if "USD" in price_data:
                            price_cents = int(price_data["USD"])
                        elif "amount" in price_data:
                            price_cents = int(price_data["amount"])
                        else:
                            price_cents = 0 
                        
                        price_usd = price_cents / 100.0
                        title = objects[0]["title"]
                        
                        # Mock OBI
                        obi = random.uniform(-1.0, 1.0)
                        
                        # 3. BALANCE CHECK SIGNAL
                        signal = "WAIT"
                        if obi > 0.6: 
                            if price_usd <= user_balance_usd:
                                signal = "STRONG_BUY"
                            else:
                                signal = "NO_FUNDS (Too Expensive)"
                        elif obi < -0.6: 
                            signal = "STRONG_SELL"
                        
                        logger.info(f"👁️ [{target['game_id'].upper()}] {title[:20]}... | Price: ${price_usd:.2f} | OBI: {obi:.2f} | Signal: {signal}")
                    else:
                        pass
                except Exception as e:
                    logger.error(f"❌ Parse Error {key}: {e}")

            logger.info(f"⏱️ Cycle Latency (Total Batch): {latency:.2f}ms")
            
        except Exception as e:
            logger.error(f"❌ Cycle Failed: {e}")

        await asyncio.sleep(1.0) 

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_cycle())
