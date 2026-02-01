"""Wrapper for ArbitrageScanner engine (for backward compatibility)."""

import logging
from typing import Any

from src.dmarket.balance_checker import BalanceChecker
from src.dmarket.scanner.engine import ArbitrageScanner
from src.dmarket.scanner.levels import ARBITRAGE_LEVELS, GAME_IDS


logger = logging.getLogger(__name__)


async def scan_game_for_arbitrage(game: str, mode: str = "medium"):
    scanner = ArbitrageScanner()
    return await scanner.scan_game(game, mode)


async def check_user_balance(api_client: Any, min_required: float = 1.0) -> dict[str, Any]:
    """Check user balance using the BalanceChecker class.

    This is a backward-compatibility wrapper.

    Args:
        api_client: DMarket API client instance
        min_required: Minimum required balance in USD

    Returns:
        Dictionary with balance information
    """
    checker = BalanceChecker(api_client, min_required_balance=min_required)
    return await checker.check_balance()


# Maintain public API
__all__ = [
    "ArbitrageScanner",
    "ARBITRAGE_LEVELS",
    "GAME_IDS",
    "check_user_balance",
    "scan_game_for_arbitrage",
]
