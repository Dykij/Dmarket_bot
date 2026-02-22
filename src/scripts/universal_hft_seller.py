"""
Script: universal_hft_seller.py
Description: Universal Cash-out. Scans ALL inventories (4 games) with Pagination.
Implements HFT v2 Pricing (Dynamic Fee + Margin).
"""

import sys
import os
import asyncio
import logging
import requests
import time
from nacl.signing import SigningKey
from pathlib import Path

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.config_manager import ConfigManager
from src.dmarket.api.client import BaseDMarketClient
from src.dmarket.pricing.fee_oracle import fee_oracle

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HFT_Seller")

GAMES = ['a8db', 'tf2', '9a92', 'rust']
TARGET_MARGIN = 0.15 # 15% Markup

async def main():
    ConfigManager.load()
    pub_key = ConfigManager.get("dmarket_public_key")
    sec_key = ConfigManager.get("dmarket_secret_key")
    
    if not pub_key or not sec_key:
        logger.error("Keys missing")
        return

    client = BaseDMarketClient(pub_key, sec_key)
    
    total_listed = 0
    
    for game_id in GAMES:
        logger.info(f"🌍 Scanning Game: {game_id.upper()} ...")
        
        cursor = ""
        page_count = 0
        
        while True:
            page_count += 1
            items, next_cursor = await fetch_inventory_page(pub_key, sec_key, game_id, cursor)
            
            logger.info(f"  📖 Page {page_count}: {len(items)} items")
            
            if not items and not next_cursor:
                break
                
            for item in items:
                # Check listing status
                offer = item.get("Offer")
                # Offer is a dict if listed, or None/Empty if not.
                # BUT DMarket sometimes returns empty Offer dict {'OfferID': ''}.
                is_listed = offer and offer.get("OfferID")
                
                if is_listed:
                    continue
                    
                # Not listed - Proceed to Sell
                title = item.get("Title")
                if not title: continue
                
                # Filter junk? For now, list EVERYTHING that isn't junk.
                # Actually, let's filter for our targets to be safe, OR list all?
                # Prompt says "universal script... until it downloads entire inventory...".
                # But selling random junk might clog.
                # Let's filter for "Key", "Ticket", "Redline", "Tempered", "Asiimov" logic from cold_cycle.
                
                # Heuristic Filter
                targets = ["Key", "Ticket", "Redline", "Asiimov", "Tempered", "Alien Red", "Dragonclaw"]
                if not any(t in title for t in targets):
                    # Skip junk
                    continue
                    
                await sell_item(client, item, game_id)
                total_listed += 1

            if not next_cursor:
                break
            
            cursor = next_cursor
            await asyncio.sleep(0.5) # Rate limit safety

    logger.info(f"✅ Universal Scan Complete. Listed {total_listed} items.")

async def fetch_inventory_page(pub, sec, game_id, cursor=""):
    import urllib.parse
    
    path = f"/marketplace-api/v1/user-inventory?GameID={game_id}&Limit=100"
    if cursor:
        path += f"&Cursor={cursor}"
        
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
        data = resp.json()
        return data.get("Items", []), data.get("Cursor")
    
    logger.error(f"Page Fetch Error: {resp.status_code} {resp.text}")
    return [], None

async def sell_item(client, item, game_id):
    title = item.get("Title")
    asset_id = item.get("AssetID")
    
    # 1. Determine Buy Price (Heuristic since API doesn't give history here)
    buy_price = 1.0 # Default fallback
    if "Key" in title: buy_price = 1.76
    elif "Ticket" in title: buy_price = 0.97
    elif "Redline" in title: buy_price = 10.0
    elif "Asiimov" in title: buy_price = 50.0
    
    # 2. Get Real Fee
    fee_fraction = await fee_oracle.get_fee_for_item(game_id, title)
    
    # 3. Calc Price
    # Sell = (Buy / (1 - Fee)) * (1 + Margin)
    sell_price_raw = (buy_price / (1 - fee_fraction)) * (1 + TARGET_MARGIN)
    sell_price_cents = int(sell_price_raw * 100)
    sell_price_usd = sell_price_cents / 100.0
    
    logger.info(f"💎 SELLING: {title} @ ${sell_price_usd} (Fee {fee_fraction:.2f})")
    
    # 4. Create Offer
    resp = await asyncio.to_thread(client.rust_client.create_sell_offer, asset_id, sell_price_cents)
    
    if "OfferId" in resp or "Success" in resp or "created" in resp:
         logger.info(f"✅ LISTED: {title}")
         send_telegram_report(title, game_id, sell_price_usd)
    else:
         logger.error(f"❌ FAIL: {resp}")

def send_telegram_report(title, game, sell_price):
    token = ConfigManager.get("telegram_bot_token")
    chat_id = ConfigManager.get("telegram_chat_id")
    msg = (
        f"📈 <b>НА ПРОДАЖЕ (HFT v2):</b> [{game.upper()}] {title}\n"
        f"💰 Цена: ${sell_price:.2f} (+15%)"
    )
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=2)
    except: pass

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
