import logging
import os
from typing import Dict, Optional
from src.api.cs2cap_oracle import CS2CapOracle
from src.api.csfloat_oracle import CSFloatOracle
from src.api.rust_oracle import RustOracle

logger = logging.getLogger("OracleFactory")


class OracleFactory:
    """
    Factory Pattern to provide game-specific pricing oracles.

    CS2: Uses CS2Cap (41 marketplaces) as primary oracle.
          Falls back to CSFloat if CS2CAP_API_KEY is not set.
    Rust: Uses SCMM (rust.scmm.app).

    v14.7: Graceful degradation — when CS2Cap is unavailable (circuit open,
    rate limited, network error), downstream code can fall back to DMarket
    aggregated_prices via OracleFactory.is_degraded().
    """
    _oracles: Dict[str, object] = {}
    _degraded: Dict[str, bool] = {}  # per-game degradation flags

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

        cls._degraded[game_id] = False
        return cls._oracles[game_id]

    @classmethod
    def mark_degraded(cls, game_id: str) -> None:
        """Mark oracle as degraded — downstream should use DMarket fallback."""
        cls._degraded[game_id] = True
        logger.warning(f"[OracleFactory] {game_id} oracle degraded → DMarket fallback")

    @classmethod
    def mark_healthy(cls, game_id: str) -> None:
        """Mark oracle as healthy after recovery."""
        if cls._degraded.get(game_id, False):
            cls._degraded[game_id] = False
            logger.info(f"[OracleFactory] {game_id} oracle recovered")

    @classmethod
    def is_degraded(cls, game_id: str) -> bool:
        """Check if oracle is currently in degraded mode."""
        return cls._degraded.get(game_id, False)

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
