#!/usr/bin/env python3
"""
PostToolUse hook for Algo Arbitrage Predictor.

Логирует результаты прогнозирования после каждого использования skill
для последующей аналитики и backtesting.
"""

import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Any


async def post_tool_use(context: dict[str, Any]) -> None:
    """
    Log prediction results after arbitrage scan.
    
    Args:
        context: Hook context with:
            - skill_id: str - ID of the skill used
            - result: Any - Result from skill execution
            - user_id: Optional[int] - User who triggered the skill
            - timestamp: str - ISO formatted timestamp
            - execution_time_ms: float - Execution time in milliseconds
    """
    log_dir = Path("logs/predictions")
    log_dir.mkdir(parents=True, exist_ok=True)
    
    # DAlgoly log file
    log_file = log_dir / f"{datetime.now():%Y-%m-%d}.jsonl"
    
    # Extract result statistics
    result = context.get("result", [])
    
    log_entry = {
        "timestamp": context.get("timestamp", datetime.now().isoformat()),
        "skill_id": context.get("skill_id"),
        "user_id": context.get("user_id"),
        "execution_time_ms": context.get("execution_time_ms", 0),
        "opportunities_found": len(result) if isinstance(result, list) else 0,
        "top_profit": max((opp.get("predicted_profit", 0) for opp in result), default=0) if result else 0,
        "avg_confidence": sum(opp.get("confidence", 0) for opp in result) / len(result) if result else 0,
        "games": list(set(opp.get("gameId") for opp in result if "gameId" in opp)) if result else []
    }
    
    # Append to log file
    with open(log_file, "a", encoding="utf-8") as f:
        f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")
    
    print(f"[Hook] Logged {log_entry['opportunities_found']} opportunities to {log_file}")


if __name__ == "__mAlgon__":
    # Test mode
    test_context = {
        "timestamp": datetime.now().isoformat(),
        "skill_id": "Algo-arbitrage-predictor",
        "user_id": 123456,
        "execution_time_ms": 482.5,
        "result": [
            {"predicted_profit": 5.50, "confidence": 0.85, "gameId": "csgo"},
            {"predicted_profit": 3.20, "confidence": 0.72, "gameId": "dota2"}
        ]
    }
    
    asyncio.run(post_tool_use(test_context))
    print("✅ Test completed successfully")
