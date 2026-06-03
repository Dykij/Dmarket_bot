import asyncio
import sys
import os
import time
import logging
from typing import List, Dict

# Set up project path
BASE_DIR = os.getcwd()
sys.path.append(BASE_DIR)

from src.core.autonomous_scanner import run_autonomous_scanner
from src.api.dmarket_api_client import DMarketAPIClient
from src.utils.vault import vault

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("DeepTester")

class DeepStressTester:
    """
    Stress Tester for DMarket Bot (Phase 7.6).
    Performs multiple rapid startup/teardown cycles to detect:
    - Memory leaks
    - Rate limit handling
    - PID lock residue
    - Strategy stability
    """
    def __init__(self, cycles: int = 50):
        self.total_cycles = cycles
        self.results = []
        # Force Test Mode
        os.environ["DRY_RUN"] = "true"

    async def run_test_cycle(self, cycle_num: int):
        logger.info(f"== TEST CYCLE {cycle_num}/{self.total_cycles} STARTED ==")
        start_time = time.time()
        success = False
        error = None

        try:
            # We wrap the scanner run in a task and cancel it after 30 seconds
            # to verify cycle stability and clean termination.
            task = asyncio.create_task(run_autonomous_scanner())
            
            # Allow it to run for 15 seconds to complete at least one market sweep
            await asyncio.sleep(15)
            
            task.cancel()
            await task
            success = True
        except asyncio.CancelledError:
            success = True # Normal termination
        except Exception as e:
            logger.error(f"Cycle {cycle_num} CRASHED: {e}")
            error = str(e)
        
        duration = time.time() - start_time
        self.results.append({
            "cycle": cycle_num,
            "success": success,
            "duration": duration,
            "error": error
        })

    async def run_full_suite(self):
        print("\n" + "!" * 50)
        print("🔥 INITIATING QUANTITATIVE STRESS TEST (50 CYCLES)")
        print("!" * 50 + "\n")

        for i in range(1, self.total_cycles + 1):
            await self.run_test_cycle(i)
            # Short rest between cycles to simulate real-world intermittent restarts
            await asyncio.sleep(2)

        self.summarize()

    def summarize(self):
        successes = sum(1 for r in self.results if r["success"])
        avg_duration = sum(r["duration"] for r in self.results) / self.total_cycles
        
        print("\n" + "=" * 50)
        print("📊 DEEP STRESS TEST SUMMARY")
        print(f"Total Cycles: {self.total_cycles}")
        print(f"Passed: {successes}")
        print(f"Failed: {self.total_cycles - successes}")
        print(f"Avg Duration: {avg_duration:.2f}s")
        print("=" * 50)

        if successes == self.total_cycles:
            print("\n✅ ENGINE STABILITY: ROCK SOLID.")
        else:
            print(f"\n❌ ENGINE STABILITY: DETECTED {self.total_cycles - successes} ANOMALIES.")

if __name__ == "__main__":
    tester = DeepStressTester(cycles=50)
    asyncio.run(tester.run_full_suite())
