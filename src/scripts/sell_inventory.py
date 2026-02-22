"""
Script: sell_inventory.py
Description: Cash-out logic. Scans inventory, calculates v2 pricing, and lists items.
"""

import sys
import os
import asyncio
import logging
import requests
from pathlib import Path

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.config_manager import ConfigManager
from src.dmarket.api.client import BaseDMarketClient
from src.dmarket.pricing.fee_oracle import fee_oracle
from src.dmarket.pricing.game_profiles import get_profile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CashOut")

async def main():
    ConfigManager.load()
    pub_key = ConfigManager.get("dmarket_public_key")
    sec_key = ConfigManager.get("dmarket_secret_key")
    
    if not pub_key or not sec_key:
        logger.error("Keys missing")
        return

    client = BaseDMarketClient(pub_key, sec_key)
    
    # 1. Fetch Inventory with GameID=a8db
    logger.info("🌊 Fetching CS2 Inventory (GameID=a8db)...")
    items = await fetch_game_inventory(pub_key, sec_key, "a8db")
    logger.info(f"📦 Inventory: {len(items)} items found.")
    
    # 2. Filter Targets
    targets = ["Mann Co.", "Key", "Ticket", "Redline"] # Broad filter
    
    found_count = 0
    for item in items:
        title = item.get("Title")
        if not title: continue
        
        is_target = any(t in title for t in targets)
        
        if is_target:
            logger.info(f"🎯 Target Found: {title}")
            await sell_item(client, item)
            found_count += 1

async def fetch_game_inventory(pub, sec, game_id):
    from nacl.signing import SigningKey
    import time
    
    path = f"/marketplace-api/v1/user-inventory?GameID={game_id}&Limit=100"
    ts = str(int(time.time()))
    msg = f"GET{path}{ts}"
    
    secret_bytes = bytes.fromhex(sec)
    seed = secret_bytes[:32]
    signing_key = SigningKey(seed)
    sig = signing_key.sign(msg.encode('utf-8')).signature.hex()
    
    headers = {
        "X-Api-Key": pub,
        "X-Request-Sign": f"dmar ed25519 {sig}",
        "X-Sign-Date": ts,
        "Content-Type": "application/json"
    }
    
    resp = requests.get(f"https://api.dmarket.com{path}", headers=headers)
    if resp.status_code == 200:
        return resp.json().get("Items", [])
    logger.error(f"Fetch Error: {resp.status_code} {resp.text}")
    return []

def send_telegram_report(title, game, buy, sell, margin, fee):
    token = ConfigManager.get("telegram_bot_token")
    chat_id = ConfigManager.get("telegram_chat_id")
    msg = (
        f"📈 <b>НА ПРОДАЖЕ:</b> [{game.upper()}] {title}\n"
        f"📉 Куплено: ${buy:.2f}\n"
        f"📈 Выставлено: ${sell:.2f}\n"
        f"(Маржа: {margin*100:.0f}%, Комиссия: {fee*100:.1f}%)"
    )
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})

async def sell_item(client, item):
    title = item.get("Title")
    offer = item.get("Offer")
    
    # Correct check: Offer must exist AND have a valid OfferID
    is_listed = offer and offer.get("OfferID")
    
    if is_listed: 
        logger.info(f"  -> Skipping {title} (Already listed: {offer.get('OfferID')})")
        return

    game_id = item.get("GameID")
    asset_id = item.get("AssetID")
    
    # Heuristic Pricing
    buy_price = 0.0
    if "Key" in title: buy_price = 1.76
    elif "Ticket" in title: buy_price = 0.97
    else: buy_price = 1.0
    
    # Get fee
    fee_fraction = await fee_oracle.get_fee_for_item(game_id, title)
    
    # Pricing v2
    target_margin = 0.15
    sell_price_raw = (buy_price / (1 - fee_fraction)) * (1 + target_margin)
    sell_price_cents = int(sell_price_raw * 100)
    sell_price_usd = sell_price_cents / 100.0
    
    logger.info(f"🚀 Creating Offer: {title} for {sell_price_cents} cents (${sell_price_usd})")
    
    # Execute
    resp = await asyncio.to_thread(client.rust_client.create_sell_offer, asset_id, sell_price_cents)
    
    if "OfferId" in resp or "Success" in resp or "created" in resp or "offers" in resp:
         logger.info(f"✅ LISTED SUCCESS: {title}")
         send_telegram_report(title, game_id, buy_price, sell_price_usd, target_margin, fee_fraction)
    else:
         logger.error(f"❌ LIST FAILED: {resp}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
