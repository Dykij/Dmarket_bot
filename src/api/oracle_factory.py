"""
oracle_factory.py — Factory Pattern for pricing oracles.

CS2: Uses MultiSourceOracle (Market.CSGO + Waxpeer + CSFloat + Steam).
Rust: Uses SCMM (rust.scmm.app).

v15.0: MultiSourceOracle — free unified price beacon using
Market.CSGO, Waxpeer, CSFloat, and Steam APIs. No paid subscriptions.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("OracleFactory")


class OracleFactory:
    """
    Factory Pattern to provide game-specific pricing oracles.
    Always uses MultiSourceOracle (free, no CS2Cap dependency).
    """

    _oracles: dict[str, Any] = {}
    _multi_source: Any = None
    _degraded: dict[str, bool] = {}

    @classmethod
    def get_oracle(cls, game_id: str) -> Any:
        if game_id in cls._oracles:
            return cls._oracles[game_id]

        if game_id == "a8db":  # CS2
            cls._oracles[game_id] = cls._get_multi_source()
            logger.info(
                "[OracleFactory] Using MultiSourceOracle "
                "(Market.CSGO + Waxpeer + CSFloat + Steam)"
            )
        elif game_id == "rust":
            from src.api.rust_oracle import RustOracle
            cls._oracles[game_id] = RustOracle()
        else:
            return None

        cls._degraded[game_id] = False
        return cls._oracles[game_id]

    @classmethod
    def _get_multi_source(cls) -> Any:
        """Get or create the MultiSourceOracle singleton."""
        if cls._multi_source is None:
            from src.api.multi_source_oracle import multi_source_oracle
            cls._multi_source = multi_source_oracle
        return cls._multi_source

    @classmethod
    def get_multi_source(cls) -> Any:
        """Get the MultiSourceOracle singleton."""
        return cls._get_multi_source()

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
    def get_cross_market_oracle(cls, game_id: str) -> Any:
        """Get oracle for cross-market data."""
        if game_id == "a8db":
            return cls.get_oracle(game_id)
        return None

    @classmethod
    def oracle_type(cls, game_id: str = "a8db") -> str:
        """Return human-readable oracle type for logging/Telegram."""
        oracle = cls._oracles.get(game_id)
        if oracle is None:
            return "none"
        type_name = type(oracle).__name__
        if "MultiSource" in type_name:
            return "MultiSource (Market.CSGO+Waxpeer+CSFloat+Steam, free)"
        if "RustOracle" in type_name:
            return "Rust SCMM"
        return type_name

    @classmethod
    async def close_all(cls) -> None:
        for oracle in cls._oracles.values():
            if hasattr(oracle, "close"):
                await oracle.close()
        cls._oracles.clear()
        if cls._multi_source and hasattr(cls._multi_source, "close"):
            await cls._multi_source.close()
            cls._multi_source = None
