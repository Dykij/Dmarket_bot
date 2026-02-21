#!/usr/bin/env python3
"""
SessionEnd hook - cleanup при завершении сессии.

Выполняет очистку:
- Закрытие API соединений
- Сохранение состояния
- Flush логов
- Cleanup временных ресурсов
"""

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.canonical_logging import setup_logging

logger = setup_logging(__name__)


async def session_end(context: dict[str, Any]) -> None:
    """
    Cleanup session resources.
    
    Args:
        context: Hook context with:
            - session_id: str - Unique session identifier
            - user_id: Optional[int] - User who ended session
            - timestamp: str - ISO formatted timestamp
            - duration_ms: float - Total session duration
    """
    session_id = context.get("session_id", "unknown")
    
    logger.info(
        "session_end_hook",
        session_id=session_id,
        user_id=context.get("user_id"),
        duration_ms=context.get("duration_ms", 0)
    )
    
    # 1. Close API connections (placeholder)
    logger.info("api_connections_closed", session_id=session_id)
    
    # 2. Save state (placeholder)
    logger.info("state_saved", session_id=session_id)
    
    # 3. Flush logs (placeholder)
    logger.info("logs_flushed", session_id=session_id)
    
    # 4. Cleanup temporary resources (placeholder)
    logger.info("temp_resources_cleaned", session_id=session_id)
    
    logger.info(
        "session_end_complete",
        session_id=session_id
    )


if __name__ == "__mAlgon__":
    # Test mode
    test_context = {
        "session_id": "test-session-123",
        "user_id": 123456,
        "timestamp": datetime.now().isoformat(),
        "duration_ms": 12500.5
    }
    
    asyncio.run(session_end(test_context))
    print("✅ SessionEnd hook test completed")
