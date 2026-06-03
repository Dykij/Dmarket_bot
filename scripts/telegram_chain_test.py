import asyncio
import os
import sys
import traceback
from typing import List

# Ensure we import from project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.csfloat_oracle import CSFloatOracle
from src.inventory_manager import InventoryManager
from src.risk.price_validator import validate_arbitrage_profit, PriceValidationError
from src.config import Config

load_dotenv()

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
CSFLOAT_API_KEY = os.getenv("CSFLOAT_API_KEY")

async def send_to_telegram(message: str):
    try:
        from aiogram import Bot
        bot = Bot(token=TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message, parse_mode="Markdown")
        await bot.session.close()
    except Exception as e:
        print(f"Failed to send to Telegram: {e}")

async def run_chain_test():
    errors: List[str] = []
    report = ["🚀 **DMarket -> CSFloat -> DMarket Test Chain Initiated**"]
    
    # 1. Initialization
    report.append("\n**1. Initialization**")
    try:
        dm_api = DMarketAPIClient(os.getenv("DMARKET_PUBLIC_KEY"), os.getenv("DMARKET_SECRET_KEY"))
        cs_api = CSFloatOracle(CSFLOAT_API_KEY)
        inv_mgr = InventoryManager(dm_api)
        report.append("✅ APIs initialized successfully.")
    except Exception as e:
        errors.append(f"Init Error: {e}\n{traceback.format_exc()}")
        report.append("❌ APIs initialization failed.")
        await finalize_report(report, errors)
        return

    # 2. Scanning DMarket (Buy Phase)
    report.append("\n**2. Scanning DMarket (Buy Target)**")
    test_item = "AK-47 | Redline (Field-Tested)"
    dm_best_price = 0.0
    try:
        dm_resp = await dm_api.get_market_items_v2("a8db", title=test_item, limit=1)
        dm_objects = dm_resp.get("objects", [])
        if not dm_objects:
            errors.append(f"DMarket Scan Error: {test_item} not found.")
            report.append(f"❌ '{test_item}' not found on DMarket.")
        else:
            dm_best_price = float(dm_objects[0].get("price", {}).get("USD", 0)) / 100.0
            report.append(f"✅ Found '{test_item}' Best Price: ${dm_best_price:.2f}")
    except Exception as e:
        errors.append(f"DMarket API Error: {e}\n{traceback.format_exc()}")
        report.append("❌ Failed to scan DMarket.")

    # 3. Checking Oracle (CSFloat Evaluation)
    report.append("\n**3. CSFloat Oracle (Price Evaluation)**")
    cs_price = 0.0
    try:
        cs_price = await cs_api.get_item_price(test_item)
        if cs_price <= 0:
            errors.append("CSFloat Oracle Error: Price returned 0 or not found.")
            report.append("❌ Oracle could not determine a reliable price.")
        else:
            report.append(f"✅ Oracle Price: ${cs_price:.2f}")
    except Exception as e:
        errors.append(f"CSFloat Oracle Error: {e}\n{traceback.format_exc()}")
        report.append("❌ Failed to query Oracle.")

    # 4. Profit Validation
    report.append("\n**4. Quantitative Validation**")
    try:
        if dm_best_price > 0 and cs_price > 0:
            # Check if buying at DM and selling at CSFloat is feasible based on our 5% margin
            margin = validate_arbitrage_profit(dm_best_price, cs_price, fee_markup=0.05, min_profit_margin=0.05)
            report.append(f"✅ Arbitrage Validated! Net Margin: {margin*100:.1f}%")
        else:
            errors.append("Quantitative Validation Skipped due to previous errors getting prices.")
            report.append("⚠️ Validation skipped.")
    except PriceValidationError as e:
        # Note: Since this is a live market, it's very possible there's no arbitrage right now for specifically this item.
        # This is expected and not practically a code error, but we log the constraint logic working.
        report.append(f"⚠️ Validation rejected (Expected market condition): {e}")
    except Exception as e:
        errors.append(f"Validation Error: {e}\n{traceback.format_exc()}")
        report.append("❌ Validation logic crashed.")

    # 5. Inventory Checking (Sell Phase simulation)
    report.append("\n**5. DMarket Inventory (Resell Phase)**")
    try:
        inventory = await inv_mgr.fetch_inventory(game_id="a8db")
        count = len(inventory) if inventory else 0
        report.append(f"✅ Inventory fetched successfully. Found {count} items.")
    except Exception as e:
        errors.append(f"Inventory Error: {e}\n{traceback.format_exc()}")
        report.append("❌ Failed to fetch inventory.")

    # Closing
    await dm_api.close()
    await cs_api.close()

    await finalize_report(report, errors)

async def finalize_report(report, errors):
    report.append("\n**📋 Error Report**")
    if errors:
        report.append(f"⚠️ **Found {len(errors)} errors during chain execution:**")
        # Truncate traces if too long for Telegram
        for idx, err in enumerate(errors, 1):
            err_msg = err[:500] + "..." if len(err) > 500 else err
            report.append(f"*{idx}.* `{err_msg}`")
    else:
        report.append("✅ **No execution errors encountered!** The chain ran smoothly.")

    final_message = "\n".join(report)
    print("Testing output meant for Telegram:\n" + "="*40 + "\n" + final_message + "\n" + "="*40)
    await send_to_telegram(final_message)


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_chain_test())

