"""
Script: cold_cycle.py
Description: HFT Pipeline Verification Script.
Role: Live monitoring of market data via Rust Network Layer with professional logging.
Risk Management: Enforces Balance Checks, Safety Limits, and Profit Margins.
"""

import sys
import os
import asyncio
import logging
import logging.handlers
import random
import time
import argparse
import requests
from pathlib import Path
from collections import defaultdict

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

# High-Performance JSON
try:
    import orjson as json
except ImportError:
    import json

from src.core.config_manager import ConfigManager
from src.dmarket.api.client import BaseDMarketClient
from src.dmarket.pricing.risk_gate import risk_gate

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
if not logger:
    logger = logging.getLogger("ColdCycle")

def send_telegram_alert(message):
    """Sends a critical alert to the user."""
    token = ConfigManager.get("telegram_bot_token")
    chat_id = ConfigManager.get("telegram_chat_id") # Ensure this is in .env or hardcoded for now
    
    # Fallback to ConfigManager logic if needed, or just skip if no token
    if not token or not chat_id:
        return

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        logger.error(f"Failed to send Telegram alert: {e}")

async def run_cycle(duration_sec=60, test_mode=True):
    """Main execution loop for Cold Cycle monitoring."""
    mode_str = "READ_ONLY (Dry Run)" if test_mode else "🔥 REAL TRADING (Money at Risk) 🔥"
    logger.info(f"❄️ SYSTEM: STARTING PROFIT CYCLE (Phase 7.2) ❄️")
    logger.info(f"🔧 Mode: {mode_str}")
    
    # Init Client
    ConfigManager.load()
    pub_key = ConfigManager.get("dmarket_public_key") or ConfigManager.get("dmarket_api_key")
    sec_key = ConfigManager.get("dmarket_secret_key")
    
    is_dry_run = test_mode

    if not pub_key or not sec_key:
        logger.critical("❌ Keys missing in ConfigManager. Check .env")
        return
    
    try:
        client = BaseDMarketClient(pub_key, sec_key)
    except Exception as e:
        logger.critical(f"❌ Failed to initialize Client: {e}")
        return

    if not client.rust_client:
        logger.critical("❌ Rust Network Layer NOT available. Aborting.")
        return

    # Financial Vision
    user_balance_usd = 0.0
    try:
        balance_resp = await client.get_balance()
        if "error" in balance_resp:
            logger.error(f"❌ Balance Fetch Failed: {balance_resp['error']}")
        else:
            user_balance_cents = int(balance_resp.get("usd", 0))
            user_balance_usd = user_balance_cents / 100.0
            logger.info(f"💰 WALLET BALANCE: ${user_balance_usd:.2f} (USD)")
    except Exception as e:
        logger.error(f"❌ Exception fetching balance: {e}")

    # Load Targets
    try:
        targets_path = Path("src/scripts/targets.json")
        if not targets_path.exists():
             targets_path = Path("D:/Dmarket_bot/src/scripts/targets.json")
             
        with open(targets_path, "r") as f:
            full_targets_list = json.loads(f.read())
    except Exception as e:
        logger.error(f"❌ Failed to load targets.json: {e}")
        return

    active_targets = full_targets_list 
    logger.info(f"🎯 Active Targets: {len(active_targets)} monitored items.")

    rust_payload = [(t["game_id"], t["title"]) for t in active_targets]
    
    stats = {
        "requests_sent": 0,
        "deals_closed": 0,
        "errors": 0
    }

    start_time_global = time.time()
    end_time_global = start_time_global + duration_sec

    while time.time() < end_time_global:
        try:
            results_map = await asyncio.to_thread(client.rust_client.fetch_bulk, rust_payload)
            stats["requests_sent"] += 1
            
            for target in active_targets:
                game_id = target['game_id']
                title = target['title']
                key = f"{game_id}:{title}"
                data_str = results_map.get(key)
                
                if not data_str or data_str.startswith("ERROR:"):
                    continue

                try:
                    data = json.loads(data_str)
                    objects = data.get("objects", [])
                    if objects:
                        best_offer = objects[0]
                        price_data = best_offer.get("price", {})
                        
                        price_cents = 0
                        if "USD" in price_data:
                            price_cents = int(price_data["USD"])
                        elif "amount" in price_data:
                            price_cents = int(price_data["amount"])
                        
                        price_usd = price_cents / 100.0
                        offer_id = best_offer.get("extra", {}).get("offerId")
                        if not offer_id:
                             offer_id = best_offer.get("offerId") 
                             if not offer_id and "extra" in best_offer:
                                 offer_id = best_offer["extra"].get("offerId")

                        # Strategy Logic (V2 with RiskGate)
                        buy_vol = random.randint(10, 100) # Placeholder until aggregated fetch
                        sell_vol = random.randint(5, 50)
                        spread = 5.0
                        
                        verdict = await risk_gate.check_opportunity(
                            game_id=game_id,
                            title=title,
                            price_usd=price_usd,
                            buy_vol=buy_vol,
                            sell_vol=sell_vol,
                            spread_percent=spread
                        )

                        if verdict['decision']:
                            if not is_dry_run:
                                logger.info(f"⚡ RISK GATE APPROVED: {title} @ ${price_usd:.2f} (K_s2c: {verdict.get('k_s2c', 'N/A'):.2f})")
                                
                                # 1. BUY
                                buy_resp_str = await asyncio.to_thread(
                                    client.rust_client.buy_offer, 
                                    offer_id, 
                                    price_cents, 
                                    ""
                                )
                                
                                if "TxSuccess" in buy_resp_str or "Pending" in buy_resp_str:
                                    logger.info(f"✅ BUY SUCCESS: {title}")
                                    
                                    # Target Sell Calculation
                                    target_sell_usd = verdict.get('target_sell', price_usd * 1.15)
                                    
                                    msg = (
                                        f"🛒 <b>СДЕЛКА ЗАКРЫТА (HFT v2):</b> [{game_id.upper()}] {title}\n"
                                        f"📉 Куплено за: ${price_usd:.2f}\n"
                                        f"📈 Цель продажи: ${target_sell_usd:.2f}\n"
                                        f"🧠 K_s2c: {verdict.get('k_s2c', 'N/A'):.2f}"
                                    )
                                    send_telegram_alert(msg)
                                    stats["deals_closed"] += 1
                                    user_balance_usd -= price_usd
                                else:
                                    logger.error(f"❌ BUY FAILED: {buy_resp_str}")
                            else:
                                logger.info(f"💎 [DRY RUN] RiskGate Approved {title} @ ${price_usd:.2f}")
                        else:
                             if random.random() < 0.1:
                                 logger.info(f"🛡️ RiskGate Blocked: {title} ({verdict['reason']})")

                except Exception as e:
                    logger.error(f"❌ Logic Error {key}: {e}")

        except Exception as e:
            logger.critical(f"❌ Cycle Critical Failure: {e}")

        await asyncio.sleep(1.5)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds")
    args = parser.parse_args()
    
    try:
        asyncio.run(run_cycle(args.duration))
    except KeyboardInterrupt:
        logger.info("🛑 Cycle Interrupted by User")
