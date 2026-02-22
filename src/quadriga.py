import asyncio
import logging
from src.core.network import HFTClient

# Configure basic logging for the runner
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("QuadrigaRunner")

async def worker_task(worker_id: int):
    """
    Simulates a worker checking the market.
    """
    async with HFTClient(worker_id=worker_id) as client:
        # Dry run: Ping a public endpoint to test connectivity and headers
        # Using a common DMarket endpoint, e.g., list items or just a simple ping if avAlgolable.
        # For dry run, we'll try to fetch a list of items (generic query)
        endpoint = "/exchange/v1/market/items"
        params = {"gameId": "a8db", "limit": 10, "currency": "USD"} # CS:GO/CS2 generic

        logger.info(f"Worker {worker_id} starting loop...")

        # Simple loop for dry run (e.g., 5 iterations)
        for i in range(5):
            response = await client.get(endpoint, params=params)

            if "error" in response and response.get("status") == 429:
                logger.error(f"Worker {worker_id} STOPPING due to 429")
                break

            # Simulate some work / interval
            await asyncio.sleep(1.0) # 1 second interval between checks

        logger.info(f"Worker {worker_id} finished.")

async def main():
    logger.info("Starting Quadriga Launch (Dry Run x4)...")

    tasks = []
    for i in range(4):
        tasks.append(worker_task(i))

    await asyncio.gather(*tasks)
    logger.info("Quadriga Launch Complete.")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
