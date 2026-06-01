"""
Oracle Factory (v12.0) — Provides game-specific pricing oracles.

CS2Cap Oracle (BUFF163 + 41 markets) replaces CSFloat (deprecated/closed).
"""

import os
from typing import Dict, Optional

from src.api.cs2cap_oracle import CS2CapOracle
from src.api.rust_oracle import RustOracle


class OracleFactory:
    """
    Factory Pattern to provide game-specific pricing oracles.
    """
    _oracles: Dict[str, object] = {}

    @classmethod
    def get_oracle(cls, game_id: str):
        if game_id in cls._oracles:
            return cls._oracles[game_id]

        if game_id == "a8db":  # CS2
            api_key = os.getenv("CS2C_API_KEY", "")
            tier = os.getenv("CS2C_TIER", "free").lower()
            cls._oracles[game_id] = CS2CapOracle(api_key=api_key, tier=tier)
        elif game_id == "rust":
            cls._oracles[game_id] = RustOracle()
        else:
            return None

        return cls._oracles[game_id]

    @classmethod
    async def close_all(cls):
        for oracle in cls._oracles.values():
            if hasattr(oracle, "close"):
                await oracle.close()
        cls._oracles.clear()
