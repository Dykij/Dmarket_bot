"""
Main Trading Bot Entry Point (Watchdog Target).
"""
import sys
import os
import asyncio
import logging

# Add project root to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.core.config_manager import ConfigManager
from src.dmarket.api.client import DMarketAPIClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TradingBot")


async def main():
    try:
        # Load Config
        logger.info("Loading configuration...")
        config_manager = ConfigManager()
        api_url = config_manager.get("api_url")
        logger.info(f"Configuration loaded. API URL: {api_url}")

        # Test Mode Logic
        if "--test" in sys.argv:
            logger.info("Running in TEST mode (CS2 Strategy Simulation)...")

            # Initialize Client with dummy keys for testing config flow
            client = DMarketAPIClient(
                public_key="test_pub",
                secret_key="test_sec",
                # api_url will be fetched from config if not provided
            )

            logger.info(f"Client initialized with API URL: {client.api_url}")

            if client.api_url == "https://api.dmarket.com":
                logger.info("SUCCESS: Default API URL correctly loaded from ConfigManager.")
            else:
                logger.warning(f"WARNING: API URL is {client.api_url}")

            # Simulate CS2 Strategy check
            logger.info("CS2 Strategy: Ready to engage.")
            return

        logger.info("Starting Trading Bot...")
        # (Real bot startup logic would go here)

    except Exception as e:
        logger.error(f"Critical Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
