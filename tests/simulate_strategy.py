import asyncio
import os
import sys
import time
import logging
from datetime import datetime

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.api.dmarket_api_client import DMarketAPIClient
from src.core.target_sniping import SnipingLoop
from src.utils.vault import vault

# Force Sandbox Mode
os.environ["DRY_RUN"] = "true"

logging.basicConfig(level=logging.INFO, format='%(asctime)s - 🧪 [SANDBOX] - %(levelname)s - %(message)s')
logger = logging.getLogger("StrategySimulator")

async def run_simulation(duration_minutes: int = 10):
    """
    Runs the Sniping Strategy on real-time market data without spending money.
    Analyzes potential profitability including Resale.
    """
    from src.db.price_history import price_db
    logger.info(f"Starting Strategy Simulation for {duration_minutes} minutes...")
    
    # --- Pre-simulation: Clear virtual inventory to have clean data ---
    with price_db.conn:
        price_db.conn.execute("DELETE FROM virtual_inventory")

    # Initialize API and Bot
    pub_key = os.getenv("DMARKET_PUBLIC_KEY", "sim_key")
    sec_key = vault.get_dmarket_secret() or "0" * 64
    
    api = DMarketAPIClient(public_key=pub_key, secret_key=sec_key)
    bot = SnipingLoop(api)
    
    start_time = time.time()
    end_time = start_time + (duration_minutes * 60)
    
    # Start the bot in a background task
    bot_task = asyncio.create_task(bot.start())
    
    logger.info("Simulation running. Monitoring for 'TARGET LOCKED' and 'ITEM SOLD' events...")
    
    try:
        while time.time() < end_time:
            elapsed = int(time.time() - start_time)
            mins, secs = divmod(elapsed, 60)
            if elapsed % 60 == 0:
                logger.info(f"Simulation Progress: {mins}m {secs}s / {duration_minutes}m")
            await asyncio.sleep(10)
            
    except KeyboardInterrupt:
        logger.info("Simulation manually stopped.")
    finally:
        logger.info("Stopping Simulation Engine...")
        bot.running = False
        await bot_task
        await api.close()
        
    logger.info("--- SIMULATION COMPLETE ---")
    
    # --- FINAL PROFITABILITY REPORT (v7.8) ---
    idle = price_db.get_virtual_inventory('idle')
    selling = price_db.get_virtual_inventory('selling')
    sold = price_db.get_virtual_inventory('sold')
    
    total_acquired = len(idle) + len(selling) + len(sold)
    total_buy_cost = sum(i['buy_price'] for i in (idle + selling + sold))
    # For simulation, we assume sold items realized 5% profit as per auto_resale logic
    realized_revenue = sum(i['buy_price'] * 1.05 for i in sold)
    
    print("\n" + "="*50)
    print("📊 FINAL SANDBOX PERFORMANCE REPORT (10 min)")
    print("="*50)
    print(f"Items Acquired:    {total_acquired}")
    print(f"Items Sold:        {len(sold)}")
    print(f"Items On Sale:      {len(selling)}")
    print(f"Total Buy Cost:    ${total_buy_cost:.2f}")
    print(f"Realized Revenue:  ${realized_revenue:.2f}")
    print(f"Net Profit (Est):  ${(realized_revenue - sum(i['buy_price'] for i in sold)):.2f}")
    print("="*50 + "\n")
    
    generate_report_metadata()

def generate_report_metadata():
    report_file = os.path.join(os.path.dirname(__file__), "..", "PROFITABILITY_REPORT.md")
    with open(report_file, "w") as f:
        f.write(f"# Strategy Profitability Report - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n")
        f.write("## Simulation Metadata\n")
        f.write("- **Mode**: Sandbox (Dry Run)\n")
        f.write("- **Strategy**: Target Sniping v7.8\n")
        f.write("- **Oracle**: Multi-Game Factory (CSFloat/SCMM)\n\n")
        f.write("## Observations\n")
        f.write("Check `logs/bot_24_7.log` for specific 'TARGET LOCKED' entries captured during this run.\n")

if __name__ == "__main__":
    asyncio.run(run_simulation(duration_minutes=10))
