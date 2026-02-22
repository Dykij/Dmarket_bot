import asyncio
import logging
import os
import random
from typing import List, Dict

# Core imports
from src.core.config_manager import ConfigManager
from src.utils.api_circuit_breaker import call_with_circuit_breaker, CircuitBreakerOpen
from src.utils.rate_limiter import DMarketRateLimiter
from src.dmarket.api.client import BaseDMarketClient

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
COMMISSION_FEE = 0.07
MIN_PROFIT_MARGIN = 0.05 # 5% minimum profit
DRY_RUN = True  # Default safety

class TradingBot:
    def __init__(self):
        self.config = ConfigManager()
        self.api = BaseDMarketClient(
            public_key=self.config.get("public_key", ""),
            secret_key=self.config.get("secret_key", "")
        )
        # Auto-detect Dry Run if keys are missing
        if not self.config.get("public_key") or not self.config.get("secret_key"):
            logger.warning("⚠️ No API Keys found. Forcing DRY RUN mode.")
            global DRY_RUN
            DRY_RUN = True

    async def analyze_market(self):
        """
        MAlgon HFT Loop.
        1. Fetch Market Data (Rust)
        2. Calculate OBI (Rust)
        3. Evaluate Profit
        4. Execute (or Dry Run)
        """
        target_items = ["AK-47 | Slate (Field-Tested)", "AWP | Asiimov (Field-Tested)"] # TODO: Load from config
        
        for item_name in target_items:
            try:
                # 1. Fetch Data (Rust Network Layer under the hood)
                # Using a mock URL suffix for now as real endpoint params need construction
                data = await self.api.get_market_items(f"/exchange/v1/market/items?title={item_name}&limit=10&currency=USD")
                
                if not data or "objects" not in data:
                    continue

                offers = data["objects"]
                # Mocking Order Book volumes for OBI calculation (since API doesn't give full book instantly)
                # In prod, we'd aggregate multiple pages or use a different endpoint
                bids_mock = [(float(o["price"]["USD"]) * 0.9, random.randint(1, 10)) for o in offers]
                asks_mock = [(float(o["price"]["USD"]), 1) for o in offers]

                # 2. OBI Calculation (Rust)
                if self.api.rust_client:
                    obi = self.api.rust_client.get_obi(bids_mock, asks_mock)
                else:
                    obi = 0.0 # Fallback

                # 3. Profit Eval
                best_ask = float(offers[0]["price"]["USD"])
                target_sell = best_ask * 1.10 # Algom for +10%
                net_profit = (target_sell * (1 - COMMISSION_FEE)) - best_ask
                margin = net_profit / best_ask

                log_msg = f"Target: {item_name} | Price: ${best_ask} | OBI: {obi:.2f} | Margin: {margin*100:.2f}%"
                
                if margin > MIN_PROFIT_MARGIN and obi > -0.2: # Bullish or Neutral
                    if DRY_RUN:
                        logger.info(f"🔵 [DRY RUN] WOULD BUY: {log_msg}")
                    else:
                        logger.info(f"🟢 [LIVE] BUYING: {log_msg}")
                        # await self.api.create_target(...)
                else:
                    logger.info(f"⚪ SKIP: {log_msg}")

            except CircuitBreakerOpen:
                logger.error("🛑 Circuit Breaker OPEN. Pausing loop.")
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error in loop: {e}")

    async def run(self):
        logger.info(f"🚀 Starting DMarket HFT Bot (Mode: {'DRY RUN' if DRY_RUN else 'LIVE'})")
        while True:
            await self.analyze_market()
            # HFT pacing - Adaptive Limiter handles the micro-sleeps inside api calls
            # ensuring we respect headers. Here we just loop.
            await asyncio.sleep(0.1) 

if __name__ == "__main__":
    bot = TradingBot()
    try:
        asyncio.run(bot.run())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
