import os
from typing import Dict, Optional
from src.api.csfloat_oracle import CSFloatOracle
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

        if game_id == "a8db": # CS2
            api_key = os.getenv("CSFLOAT_API_KEY", "")
            cls._oracles[game_id] = CSFloatOracle(api_key=api_key)
        elif game_id == "rust":
            cls._oracles[game_id] = RustOracle()
        else:
            # Fallback or generic
            return None
            
        return cls._oracles[game_id]

    @classmethod
    async def close_all(cls):
        for oracle in cls._oracles.values():
            if hasattr(oracle, "close"):
                await oracle.close()
        cls._oracles.clear()
