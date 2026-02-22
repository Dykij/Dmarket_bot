"""
Script: reprice_inventory.py
Description: Repricing module for active offers.
Use case: Update prices for items ALREADY on sale using v2 logic.
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
from src.dmarket.pricing.game_profiles import get_profile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Repricer")

async def main():
    ConfigManager.load()
    pub = ConfigManager.get("dmarket_public_key")
    sec = ConfigManager.get("dmarket_secret_key")
    
    if not pub or not sec:
        logger.error("Keys missing")
        return

    # 1. Fetch Active Offers
    # GET /marketplace-api/v1/user-offers?Status=OfferStatusActive&Limit=50
    offers = await fetch_active_offers(pub, sec)
    logger.info(f"📋 Active Offers: {len(offers)} found.")
    
    updates = []
    
    for offer in offers:
        title = offer.get("Title")
        offer_id = offer.get("OfferID")
        game_id = offer.get("GameID")
        
        if not title or not offer_id:
            continue
            
        # Filter for our targets
        if "Key" not in title and "Ticket" not in title:
            continue
            
        logger.info(f"🔎 Analyzing: {title} (ID: {offer_id})")
        
        # 2. V2 Pricing
        # Buy Price Heuristic
        buy_price = 1.76 if "Key" in title else 0.97
        
        fee_fraction = await fee_oracle.get_fee_for_item(game_id, title)
        target_margin = 0.15
        
        sell_price_raw = (buy_price / (1 - fee_fraction)) * (1 + target_margin)
        sell_price_cents = int(sell_price_raw * 100)
        sell_price_usd = sell_price_cents / 100.0
        
        current_price_data = offer.get("Price", {})
        current_price = float(current_price_data.get("Amount", 0)) / 100
        
        if abs(current_price - sell_price_usd) < 0.01:
            logger.info(f"✅ Price OK: ${current_price} (Target: ${sell_price_usd})")
            continue
            
        logger.info(f"🔄 Repricing: ${current_price} -> ${sell_price_usd} (Fee {fee_fraction:.2f})")
        
        updates.append({
            "OfferID": offer_id,
            "Price": {
                "Amount": sell_price_cents,
                "Currency": "USD"
            }
        })
        
    if updates:
        await execute_batch_update(pub, sec, updates)
    else:
        logger.info("No updates needed.")

async def fetch_active_offers(pub, sec):
    # Check ALL statuses
    path = "/marketplace-api/v1/user-offers?Limit=100" # Default status includes multiple? Or need to specify?
    # Spec says Status default is OfferStatusDefault.
    # Enum: Default, Active, Sold, Inactive, In_transfer.
    # Let's try to fetch active and in_transfer explicitly? Or just list all if possible.
    # We can't list all in one go maybe.
    # Let's try Status=OfferStatusDefault (usually means Active?).
    # Let's try NO status param.
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

async def execute_batch_update(pub, sec, updates):
    # POST /marketplace-api/v1/user-offers/edit
    path = "/marketplace-api/v1/user-offers/edit"
    body_json = {"Offers": updates}
    body_str = json.dumps(body_json, separators=(',', ':')) # Minimal JSON for signature?
    # Reqwest/Requests usually adds spaces? DMarket is strict.
    # Python requests json parameter adds spaces? No, default is usually separate.
    # Let's use string body for signing correctness.
    
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
    
    logger.info(f"🚀 Sending Batch Update: {len(updates)} items")
    resp = requests.post(f"https://api.dmarket.com{path}", data=body_str, headers=headers)
    
    if resp.status_code == 200:
        logger.info(f"✅ BATCH SUCCESS: {resp.json()}")
        
        # Telemetry
        for up in updates:
            title = "Item" # Simplified
            price = up["Price"]["Amount"] / 100
            send_telegram_report(title, price)
    else:
        logger.error(f"❌ BATCH FAILED: {resp.text}")

def send_telegram_report(title, price):
    token = ConfigManager.get("telegram_bot_token")
    chat_id = ConfigManager.get("telegram_chat_id")
    msg = f"🔄 <b>ЦЕНА ОБНОВЛЕНА (HFT v2):</b>\n💰 Новая цена: ${price:.2f}"
    requests.post(f"https://api.telegram.org/bot{token}/sendMessage", json={"chat_id": chat_id, "text": msg, "parse_mode": "HTML"})

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
