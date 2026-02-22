"""
Script: check_targets.py
Description: Check if we accidentally created targets instead of buying.
"""

import sys
import os
import requests
import time
import logging
from nacl.signing import SigningKey
from pathlib import Path

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.config_manager import ConfigManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TargetCheck")

def main():
    ConfigManager.load()
    pub = ConfigManager.get("dmarket_public_key")
    sec = ConfigManager.get("dmarket_secret_key")
    
    path = "/marketplace-api/v1/user-targets?BasicFilters.Status=TargetStatusActive&Limit=100"
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
        items = data.get("Items", [])
        logger.info(f"🎯 Active Targets: {len(items)}")
        for item in items:
            logger.info(f"   - {item.get('Title')} | ${float(item.get('Price', {}).get('Amount', 0))/100} | ID: {item.get('TargetID')}")
    else:
        logger.error(f"Error: {resp.text}")

if __name__ == "__main__":
    main()
