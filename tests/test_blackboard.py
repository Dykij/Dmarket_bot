import asyncio
import logging
import sys
import os

# Fix path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.core.blackboard import board

# Setup logging
logging.basicConfig(level=logging.INFO)

async def test_blackboard():
    print("Testing Blackboard Protocol...")
    
    # 1. Load default
    await board.load()
    print(f"Initial Status: {await board.get('system')}")
    
    # 2. Agent Update (Boss sets a target)
    print("Boss adding target...")
    await board.update("strategy", {"active_targets": ["AK-47 | Redline"], "risk_level": "HIGH"})
    
    # 3. Agent Read (Roy checks target)
    strat = await board.get("strategy")
    print(f"Roy sees: {strat}")
    
    # 4. Agent Update (Harper reports threat)
    print("Harper detecting threat...")
    await board.update("security", {"threat_detected": True})
    
    print("Final State Dump:")
    print(board.state)

if __name__ == "__main__":
    asyncio.run(test_blackboard())