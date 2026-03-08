import asyncio
import time
import logging
from src.bot.scanner import MarketScanner
from src.utils.api_client import AsyncDMarketClient
from src.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("StressTest")

async def run_stress_test():
    logger.info("🧪 Starting Stress Test: High-Frequency Polling Simulation")
    
    client = AsyncDMarketClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
    scanner = MarketScanner(client)
    
    items_to_scan = [f"Item_{i} (Factory New)" for i in range(100)]
    iterations = 50
    
    logger.info(f"Configuration: {iterations} iterations of {len(items_to_scan)} items each.")
    
    start_time = time.time()
    
    for i in range(iterations):
        if i % 10 == 0:
            logger.info(f"Iter {i}/{iterations}...")
        
        # This will hit the Rust engine fast-path if compiled, otherwise native python
        try:
            results = await scanner.scan(items_to_scan)
        except Exception as e:
            # Catching errors since we might fail authentication or get ratelimits in real life
            pass 
            
    end_time = time.time()
    duration = end_time - start_time
    
    mode = "🦀 RUST CORE" if scanner.rust_poller else "🐍 PYTHON AIOHTTP"
    
    logger.info("✅ Stress Test Complete")
    logger.info(f"Engine Used: {mode}")
    logger.info(f"Total Time: {duration:.2f} seconds")
    logger.info(f"Throughput: {(iterations * len(items_to_scan)) / duration:.2f} items/sec")
    
    await client.session.close()

if __name__ == "__main__":
    asyncio.run(run_stress_test())
