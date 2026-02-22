import sys
import os
import asyncio
import logging
import requests
from pathlib import Path

# Add project root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from src.core.config_manager import ConfigManager
from src.scripts.cold_cycle import run_cycle

# Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("LiveLauncher")

def send_startup_msg():
    ConfigManager.load()
    token = ConfigManager.get("telegram_bot_token") or os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = ConfigManager.get("telegram_chat_id") or os.getenv("TELEGRAM_CHAT_ID")
    
    if not token or not chat_id:
        logger.error("❌ Telegram Token or Chat ID missing!")
        return False

    msg = "🟢 <b>DMARKET HFT BOT: БОЕВОЙ РЕЖИМ АКТИВИРОВАН.</b>\n🚀 ПОИСК ЦЕЛЕЙ (CS2, Dota2, TF2, Rust)\n💰 Бюджет: $15.00\n🛡 Лимит предмета: $5.00"
    
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg, "parse_mode": "HTML"}
    
    try:
        resp = requests.post(url, json=payload, timeout=5)
        if resp.status_code == 200:
            logger.info("✅ Telegram Startup Message Sent")
            return True
        else:
            logger.error(f"❌ Telegram Error: {resp.text}")
            return False
    except Exception as e:
        logger.error(f"❌ Telegram Exception: {e}")
        return False

async def main():
    # 1. Send Telemetry
    send_startup_msg()
    
    # 2. Force Live Mode
    # Use update mechanism or direct access via settings if possible
    # But ConfigManager is a shim.
    # Let's bypass ConfigManager for setting flag if needed or just rely on env?
    # Better: Update settings directly
    from src.utils.config import settings
    settings.dry_run = False
    
    logger.info("💀 LIVE TRADING ENABLED. NO DRY RUN.")
    
    # 3. Run Cycle (180 seconds, test_mode=False)
    await run_cycle(duration_sec=180, test_mode=False)

if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
