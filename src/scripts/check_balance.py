import sys
import os
import asyncio
from pathlib import Path

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.config_manager import ConfigManager
from src.dmarket.api.client import BaseDMarketClient

async def check_balance():
    # Load config explicitly
    ConfigManager.load()
    
    # Try different key names
    pub = ConfigManager.get("dmarket_public_key") or ConfigManager.get("dmarket_api_key")
    sec = ConfigManager.get("dmarket_secret_key")
    
    if not pub or not sec or "YOUR_" in pub:
        print("ERROR: API Keys are missing or placeholders in .env")
        # Try reading .env raw just in case
        try:
             with open('.env', 'r') as f:
                 if 'DMARKET_PUBLIC_KEY=' in f.read():
                     print("DEBUG: .env exists and contains key line.")
        except:
             pass
        return

    # Initialize client
    try:
        # BaseDMarketClient expects (public_key, secret_key)
        client = BaseDMarketClient(pub, sec)
        print(f"DEBUG: Client initialized with Public Key ending in ...{pub[-4:] if pub else 'None'}")
    except Exception as e:
        print(f"CRITICAL: Client init failed: {e}")
        return

    try:
        balance = await client.get_balance()
        if "error" in balance:
             print(f"ERROR: {balance['error']}")
             print(f"DEBUG: Full response: {balance}")
        else:
             # DMarket balance response structure: {"usd": "12345"} (cents)
             usd_cents = balance.get("usd", 0)
             try:
                 usd = int(usd_cents) / 100.0
                 print(f"BALANCE_USD: {usd:.2f}")
             except ValueError:
                 print(f"ERROR: Invalid balance format: {usd_cents}")
    except Exception as e:
        print(f"CRITICAL: Balance fetch exception: {e}")

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_balance())
