"""
Monte Carlo & Ultimate Stress Test (Sandbox v10.0).
Simulates a 'Black Swan' event and analyzes Profit Leak vs Safety.
"""

import asyncio
import os
import logging
from src.core.target_sniping import SnipingLoop
from src.api.dmarket_api_client import DMarketAPIClient
from src.core.sandbox_scenarios import scenario_engine
from src.db.price_history import price_db

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MonteCarlo")

async def run_ultimate_audit():
    os.environ["DRY_RUN"] = "true"
    client = DMarketAPIClient("pub", "sec")
    bot = SnipingLoop(client)
    
    # 1. Create Baseline Snapshot
    price_db.backup_state("pre_stress")
    
    logger.info("="*60)
    logger.info("🦅 STARTING ULTIMATE EAGLE-EYE AUDIT v10.0")
    logger.info("="*60)
    
    # 2. Normal Market Phase (2 cycles)
    logger.info("🌤️ PHASE 1: Normal Market Conditions...")
    scenario_engine.reset()
    for _ in range(2):
        await bot.run_cycle("a8db") # CS2

    # 3. BLACK SWAN ATTACK (-30% crash)
    logger.info("\n🚨 PHASE 2: TRIGGERING BLACK SWAN EVENT!")
    scenario_engine.trigger_black_swan()
    for _ in range(2):
        await bot.run_cycle("a8db")

    # 4. Analytics: Profit Leak Report
    logger.info("\n" + "="*60)
    logger.info("📊 FINAL ANALYTICS REPORT (v10.0)")
    logger.info("="*60)
    
    with price_db.state_conn:
        leaks = price_db.state_conn.execute("SELECT COUNT(*) as count, SUM(expected_sell - price) as lost FROM missed_opportunities").fetchone()
        decisions = price_db.state_conn.execute("SELECT decision, COUNT(*) as count FROM decision_logs GROUP BY decision").fetchall()
        
    logger.info(f"💡 PROFIT LEAK: {leaks['count']} opportunities missed | Potential Lost: ${leaks['lost'] or 0.0:.2f}")
    logger.info("🧠 SELF-REFLECTION SUMMARY:")
    for d in decisions:
        logger.info(f"   - {d['decision'].upper()}: {d['count']} times")
        
    equity = price_db.get_total_equity(43.91) # Assuming start balance
    logger.info(f"💹 FINAL EQUITY: ${equity['total']:.2f} (Assets: ${equity['assets']:.2f})")
    
    # 5. Restore State (Clean up for next real run)
    price_db.restore_state("pre_stress")
    logger.info("="*60)
    logger.info("🏁 AUDIT COMPLETE: State has been restored.")
    logger.info("="*60)

if __name__ == "__main__":
    asyncio.run(run_ultimate_audit())
