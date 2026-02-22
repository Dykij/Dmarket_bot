"""
Script: universal_hft_seller_v3.py
Description: Universal Inventory Seller v3.2 (Looping & Batch V2).
Features:
- Continuous Loop (5 min interval)
- Batch V2 API (offers:batchCreate)
- Dynamic Margins from GameProfiles
- Strict OPUS-MINDSET compliance
"""

import sys
import os
import asyncio
import logging
import requests
import time
import json
from nacl.signing import SigningKey
from pathlib import Path

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.config_manager import ConfigManager
from src.dmarket.api.client import BaseDMarketClient
from src.dmarket.pricing.fee_oracle import fee_oracle
from src.dmarket.pricing.game_profiles import get_profile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HFT_Seller_v3")

GAMES = ['a8db', 'tf2', '9a92', 'rust']

async def main():
    ConfigManager.load()
    pub_key = ConfigManager.get("dmarket_public_key")
    sec_key = ConfigManager.get("dmarket_secret_key")
    
    if not pub_key or not sec_key:
        logger.error("❌ Keys missing in .env")
        return

    logger.info("🟢 HFT Seller v3.2 STARTED. Loop Interval: 5 min.")

    while True:
        try:
            await run_scan_cycle(pub_key, sec_key)
        except Exception as e:
            logger.error(f"Cycle Error: {e}")
        
        logger.info("💤 Sleeping 5 minutes...")
        await asyncio.sleep(300)

async def run_scan_cycle(pub_key, sec_key):
    # 1. Force Sync (Iterate games)
    logger.info("🔄 Forcing Inventory Sync...")
    for game in GAMES:
        await sync_inventory(pub_key, sec_key, game)
    await asyncio.sleep(2)

    total_listed_count = 0

    # 2. Iterate Games
    for game_id in GAMES:
        logger.info(f"🌍 Scanning Game: {game_id.upper()}")
        
        cursor = ""
        page_num = 0
        
        while True:
            page_num += 1
            items, next_cursor = await fetch_inventory_page(pub_key, sec_key, game_id, cursor)
            
            if not items:
                if not next_cursor:
                    break
            
            # 3. Process Items
            items_to_sell = []
            
            for item in items:
                offer = item.get("Offer")
                is_listed = offer and offer.get("OfferID")
                if is_listed:
                    continue
                
                is_tradable = item.get("Tradable", False)
                in_market = item.get("InMarket", False)
                
                if not is_tradable or in_market:
                    continue

                items_to_sell.append(item)

            if items_to_sell:
                logger.info(f"  ⚡ Analyzing {len(items_to_sell)} candidates for sale...")
                count = await process_batch_v2(pub_key, sec_key, items_to_sell, game_id)
                total_listed_count += count

            if not next_cursor:
                break
            
            cursor = next_cursor
            await asyncio.sleep(0.5)

    if total_listed_count > 0:
        logger.info(f"🏁 Cycle Complete. Successfully Listed: {total_listed_count}")
    else:
        logger.info("🏁 Cycle Complete. Nothing new to sell.")

async def sync_inventory(pub, sec, game_id):
    path = "/marketplace-api/v1/user-inventory/sync"
    
    # OPUS-MINDSET: Map internal game IDs to Swagger Enums
    game_enum = game_id
    if game_id == "a8db": game_enum = "CSGO"
    elif game_id == "9a92": game_enum = "Dota2"
    elif game_id == "tf2": game_enum = "TF2"
    elif game_id == "rust": game_enum = "Rust"
    
    body_json = {
        "Type": "Inventory",
        "GameID": game_enum
    }
    body_str = json.dumps(body_json, separators=(',', ':'))
    
    ts = str(int(time.time()))
    msg = f"POST{path}{body_str}{ts}"
    
    secret_bytes = bytes.fromhex(sec)
    seed = secret_bytes[:32]
    signing_key = SigningKey(seed)
    sig = signing_key.sign(msg.encode('utf-8')).signature.hex()
    
    headers = {
        "X-Api-Key": pub,
        "X-Request-Sign": f"dmar ed25519 {sig}",
        "X-Sign-Date": ts,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    try:
        resp = requests.post(f"https://api.dmarket.com{path}", data=body_str, headers=headers)
        if resp.status_code == 200:
            pass # Silent success
        else:
            logger.warning(f"  ⚠️ Sync Failed ({game_id}): {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Sync Exception: {e}")

async def fetch_inventory_page(pub, sec, game_id, cursor=""):
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
    
    try:
        resp = requests.get(f"https://api.dmarket.com{path}", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            return data.get("Items", []), data.get("Cursor")
        else:
            logger.error(f"  ❌ Fetch Error {resp.status_code}: {resp.text}")
            return [], None
    except Exception as e:
        logger.error(f"Fetch Exception: {e}")
        return [], None

async def process_batch_v2(pub, sec, items, game_id):
    """
    Uses POST /marketplace-api/v2/offers:batchCreate
    Body: { "requests": [ { "assetId": "...", "priceCents": 123 }, ... ] }
    """
    requests_payload = []
    
    profile = get_profile(game_id)
    target_margin = profile.sell_margin
    
    for item in items:
        asset_id = item.get("AssetID")
        title = item.get("Title")
        
        if not asset_id or not title: continue
        
        # Heuristic Price logic
        mp = item.get("MarketPrice", {}).get("Amount")
        if not mp:
            sug = item.get("suggestedPrice", {}).get("USD")
            if sug:
                mp = int(float(sug) * 100)
        
        if not mp:
            continue
            
        ref_price_cents = mp
        fee_fraction = await fee_oracle.get_fee_for_item(game_id, title)
        
        sell_price_raw = (ref_price_cents / (1 - fee_fraction)) * (1 + target_margin)
        sell_price_cents = int(sell_price_raw)
        sell_price_usd = sell_price_cents / 100.0
        
        logger.info(f"    💎 Pricing {title}: Ref ${ref_price_cents/100} -> Sell ${sell_price_usd} (Fee {fee_fraction:.2f}, Margin {target_margin})")
        
        requests_payload.append({
            "assetId": asset_id,
            "priceCents": sell_price_cents
        })
        
    if not requests_payload:
        return 0

    # Send Batch V2
    path = "/marketplace-api/v2/offers:batchCreate"
    body_json = {"requests": requests_payload}
    body_str = json.dumps(body_json, separators=(',', ':'))
    
    ts = str(int(time.time()))
    msg = f"POST{path}{body_str}{ts}"
    
    secret_bytes = bytes.fromhex(sec)
    seed = secret_bytes[:32]
    signing_key = SigningKey(seed)
    sig = signing_key.sign(msg.encode('utf-8')).signature.hex()
    
    headers = {
        "X-Api-Key": pub,
        "X-Request-Sign": f"dmar ed25519 {sig}",
        "X-Sign-Date": ts,
        "Content-Type": "application/json",
        "Accept": "application/json"
    }
    
    listed_count = 0
    try:
        resp = requests.post(f"https://api.dmarket.com{path}", data=body_str, headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            # V2 response: { "offers": [...], "failed": [...] }
            success_count = len(data.get("offers", []))
            failed_count = len(data.get("failed", []))
            
            logger.info(f"  🚀 Batch V2: {success_count} Success, {failed_count} Failed")
            
            if success_count > 0:
                listed_count = success_count
                send_telegram_summary(listed_count, game_id, target_margin, fee_fraction)
                
            if failed_count > 0:
                logger.warning(f"  ⚠️ Failures: {data.get('failed')}")
                
        else:
            logger.error(f"  ❌ Batch V2 List Failed: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.error(f"Batch Exception: {e}")
        
    return listed_count

def send_telegram_summary(count, game, margin, fee):
    token = ConfigManager.get("telegram_bot_token")
    chat_id = ConfigManager.get("telegram_chat_id")
    msg = f"🛒 <b>ЛОВУШКА РАССТАВЛЕНА:</b>\nВыставлено {count} предметов в игре {game.upper()}.\nПрайсинг: HFT v2 (Маржа {margin*100:.0f}%)"
    try:
        requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}, timeout=2)
    except: pass

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
