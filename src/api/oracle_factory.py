import os
from typing import Dict, Optional
from src.api.cs2cap_oracle import CS2CapOracle
from src.api.csfloat_oracle import CSFloatOracle
from src.api.rust_oracle import RustOracle

class OracleFactory:
    """
    Factory Pattern to provide game-specific pricing oracles.

    CS2: Uses CS2Cap (41 marketplaces) as primary oracle.
          Falls back to CSFloat if CS2CAP_API_KEY is not set.
    Rust: Uses SCMM (rust.scmm.app).
    """
    _oracles: Dict[str, object] = {}

    @classmethod
    def get_oracle(cls, game_id: str):
        if game_id in cls._oracles:
            return cls._oracles[game_id]

        if game_id == "a8db":  # CS2
            cs2cap_key = os.getenv("CS2CAP_API_KEY", "")
            if cs2cap_key:
                cls._oracles[game_id] = CS2CapOracle(api_key=cs2cap_key)
            else:
                csfloat_key = os.getenv("CSFLOAT_API_KEY", "")
                cls._oracles[game_id] = CSFloatOracle(api_key=csfloat_key)
        elif game_id == "rust":
            cls._oracles[game_id] = RustOracle()
        else:
            return None

        return cls._oracles[game_id]

    @classmethod
    def get_cross_market_oracle(cls, game_id: str) -> Optional[CS2CapOracle]:
        """Get CS2Cap oracle specifically for cross-market data (CS2 only)."""
        if game_id == "a8db":
            oracle = cls.get_oracle(game_id)
            if isinstance(oracle, CS2CapOracle):
                return oracle
        return None

    @classmethod
    async def close_all(cls):
        for oracle in cls._oracles.values():
            if hasattr(oracle, "close"):
                await oracle.close()
        cls._oracles.clear()
