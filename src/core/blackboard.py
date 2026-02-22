"""
Blackboard Pattern (Shared State Orchestration).
Standard Operating Procedure (SOP) for Agent Sync.

Storage: data/blackboard.json
Locking: Asyncio Lock + File Lock
"""

import json
import asyncio
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger("Blackboard")

STATE_FILE = Path("D:/Dmarket_bot/data/blackboard.json")

DEFAULT_STATE = {
    "system": {
        "status": "IDLE",
        "last_update": 0,
        "mode": "HFT"
    },
    "strategy": {
        "active_targets": [],
        "min_margin": 0.05,
        "risk_level": "LOW"
    },
    "network": {
        "requests_per_minute": 0,
        "errors_last_hour": 0,
        "proxy_status": "CLEAN"
    },
    "security": {
        "keys_verified": False,
        "threat_detected": False
    }
}

class Blackboard:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Blackboard, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self.file_path = STATE_FILE
        self._lock = asyncio.Lock()
        self.state = DEFAULT_STATE.copy()
        self._initialized = True
        
        # Ensure dir exists
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

    async def load(self):
        """Load state from disk."""
        async with self._lock:
            if not self.file_path.exists():
                await self._save_unsafe()
                return
            
            try:
                content = self.file_path.read_text(encoding="utf-8")
                if content:
                    self.state = json.loads(content)
            except Exception as e:
                logger.error(f"Failed to load blackboard: {e}")
                self.state = DEFAULT_STATE.copy()

    async def update(self, section: str, data: Dict[str, Any]):
        """Update a specific section safely."""
        async with self._lock:
            if section not in self.state:
                self.state[section] = {}
            
            self.state[section].update(data)
            self.state["system"]["last_update"] = time.time()
            await self._save_unsafe()

    async def get(self, section: str) -> Dict[str, Any]:
        return self.state.get(section, {})

    async def _save_unsafe(self):
        """Internal save (lock already held)."""
        try:
            # Atomic write
            temp = self.file_path.with_suffix(".tmp")
            temp.write_text(json.dumps(self.state, indent=2), encoding="utf-8")
            if self.file_path.exists():
                self.file_path.unlink()
            temp.rename(self.file_path)
        except Exception as e:
            logger.error(f"Failed to save blackboard: {e}")

# Global Instance
board = Blackboard()
