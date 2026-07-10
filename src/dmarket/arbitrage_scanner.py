"""Arbitrage scanner."""
from typing import Any


class ArbitrageScanner:
    def __init__(self, api_client: Any = None, config: Any = None) -> None:
        self.api = api_client
        self.api_client = api_client
        self.config = config

    async def scan_level(self, game: str = "csgo", level: int = 1) -> list[dict[str, Any]]:
        """Scan for arbitrage opportunities at a given level."""
        return []

    async def scan_all_levels(self, game: str = "csgo") -> list[dict[str, Any]]:
        """Scan all levels for arbitrage opportunities."""
        return []
