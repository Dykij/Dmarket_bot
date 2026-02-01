"""Wrapper for ArbitrageScanner engine (for backward compatibility)."""

from src.dmarket.scanner.engine import ArbitrageScanner
import logging

logger = logging.getLogger(__name__)

async def scan_game_for_arbitrage(game: str, mode: str = "medium"):
    scanner = ArbitrageScanner()
    return await scanner.scan_game(game, mode)

# Maintain public API
__all__ = ["ArbitrageScanner", "scan_game_for_arbitrage"]
