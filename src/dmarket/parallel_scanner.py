"""Parallel arbitrage scanner for multi-game scanning with asyncio.gather.

This module enables:
- Parallel scanning across multiple games
- Parallel scanning across multiple arbitrage levels
- Batch processing for large datasets
- Optimized API usage with concurrent requests
"""

import asyncio
from typing import Any

import structlog

from src.dmarket.scanner.engine import ArbitrageScanner
from src.interfaces import IDMarketAPI


logger = structlog.get_logger(__name__)


class ParallelScanner:
    """Scanner with parallel execution across games and levels."""

    def __init__(
        self,
        api_client: IDMarketAPI,
        max_concurrent_scans: int = 5,
    ) -> None:
        """Initialize parallel scanner.

        Args:
            api_client: DMarket API client
            max_concurrent_scans: Maximum concurrent scan operations
        """
        self.api_client = api_client
        self.max_concurrent_scans = max_concurrent_scans
        self.semaphore = asyncio.Semaphore(max_concurrent_scans)

        logger.info(
            "parallel_scanner_initialized",
            max_concurrent_scans=max_concurrent_scans,
        )

    async def scan_game_level(
        self,
        game: str,
        level: str,
        max_items: int = 10,
    ) -> list[dict[str, Any]]:
        """Scan single game/level combination with semaphore.

        Args:
            game: Game code (csgo, dota2, tf2, rust)
            level: Arbitrage level (low, medium, high)
            max_items: Maximum items to return

        Returns:
            List of arbitrage opportunities
        """
        async with self.semaphore:
            logger.info(
                "scanning_game_level",
                game=game,
                level=level,
                max_items=max_items,
            )

            try:
                scanner = ArbitrageScanner(api_client=self.api_client)
                results = await scanner.scan_game(
                    game=game,
                    mode=level,
                    max_items=max_items,
                )

                logger.info(
                    "scan_completed",
                    game=game,
                    level=level,
                    opportunities_found=len(results),
                )

                return results

            except Exception as e:
                logger.error(
                    "scan_failed",
                    game=game,
                    level=level,
                    error=str(e),
                    exc_info=True,
                )
                return []

    async def scan_multiple_games(
        self,
        games: list[str],
        level: str = "medium",
        max_items_per_game: int = 10,
    ) -> dict[str, list[dict[str, Any]]]:
        """Scan multiple games in parallel.

        Args:
            games: List of game codes
            level: Arbitrage level for all games
            max_items_per_game: Max items per game

        Returns:
            Dict mapping game code to opportunities list
        """
        logger.info(
            "parallel_multi_game_scan_started",
            games=games,
            level=level,
            max_items_per_game=max_items_per_game,
        )

        # Create tasks for all games
        tasks = [self.scan_game_level(game, level, max_items_per_game) for game in games]

        # Execute in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build results dict
        results_dict = {}
        for game, result in zip(games, results, strict=False):
            if isinstance(result, Exception):
                logger.error(
                    "game_scan_exception",
                    game=game,
                    error=str(result),
                )
                results_dict[game] = []
            else:
                results_dict[game] = result

        total_opportunities = sum(len(v) for v in results_dict.values())
        logger.info(
            "parallel_multi_game_scan_completed",
            total_opportunities=total_opportunities,
            games_scanned=len(games),
        )

        return results_dict

    async def scan_multiple_levels(
        self,
        game: str,
        levels: list[str],
        max_items_per_level: int = 10,
    ) -> dict[str, list[dict[str, Any]]]:
        """Scan multiple arbitrage levels in parallel for one game.

        Args:
            game: Game code
            levels: List of levels (low, medium, high)
            max_items_per_level: Max items per level

        Returns:
            Dict mapping level to opportunities list
        """
        logger.info(
            "parallel_multi_level_scan_started",
            game=game,
            levels=levels,
            max_items_per_level=max_items_per_level,
        )

        tasks = [self.scan_game_level(game, level, max_items_per_level) for level in levels]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        results_dict = {}
        for level, result in zip(levels, results, strict=False):
            if isinstance(result, Exception):
                logger.error(
                    "level_scan_exception",
                    game=game,
                    level=level,
                    error=str(result),
                )
                results_dict[level] = []
            else:
                results_dict[level] = result

        total_opportunities = sum(len(v) for v in results_dict.values())
        logger.info(
            "parallel_multi_level_scan_completed",
            game=game,
            total_opportunities=total_opportunities,
            levels_scanned=len(levels),
        )

        return results_dict

    async def scan_matrix(
        self,
        games: list[str],
        levels: list[str],
        max_items_per_combination: int = 5,
    ) -> dict[tuple[str, str], list[dict[str, Any]]]:
        """Scan all combinations of games and levels in parallel.

        Args:
            games: List of game codes
            levels: List of arbitrage levels
            max_items_per_combination: Max items per game/level combo

        Returns:
            Dict mapping (game, level) tuple to opportunities
        """
        logger.info(
            "parallel_matrix_scan_started",
            games=games,
            levels=levels,
            total_combinations=len(games) * len(levels),
            max_items_per_combination=max_items_per_combination,
        )

        # Create all combinations
        tasks = []
        combinations = []
        for game in games:
            for level in levels:
                tasks.append(self.scan_game_level(game, level, max_items_per_combination))
                combinations.append((game, level))

        # Execute all in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Build results dict
        results_dict = {}
        for (game, level), result in zip(combinations, results, strict=False):
            if isinstance(result, Exception):
                logger.error(
                    "combination_scan_exception",
                    game=game,
                    level=level,
                    error=str(result),
                )
                results_dict[game, level] = []
            else:
                results_dict[game, level] = result

        total_opportunities = sum(len(v) for v in results_dict.values())
        logger.info(
            "parallel_matrix_scan_completed",
            total_opportunities=total_opportunities,
            combinations_scanned=len(combinations),
        )

        return results_dict


# Example usage
async def example_parallel_scan():
    """Example of parallel scanning."""
    from src.dmarket.dmarket_api import DMarketAPI

    api = DMarketAPI(public_key="test", secret_key="test")
    parallel_scanner = ParallelScanner(api_client=api, max_concurrent_scans=5)

    # Scan multiple games at once
    games = ["csgo", "dota2", "rust", "tf2"]
    results = await parallel_scanner.scan_multiple_games(
        games=games, level="medium", max_items_per_game=10
    )

    for game, opportunities in results.items():
        print(f"{game}: {len(opportunities)} opportunities")

    # Scan all levels for CS:GO
    levels_results = await parallel_scanner.scan_multiple_levels(
        game="csgo", levels=["low", "medium", "high"], max_items_per_level=5
    )

    for level, opportunities in levels_results.items():
        print(f"CS:GO {level}: {len(opportunities)} opportunities")

    # Scan full matrix (all games x all levels)
    matrix_results = await parallel_scanner.scan_matrix(
        games=["csgo", "dota2"],
        levels=["low", "medium"],
        max_items_per_combination=3,
    )

    for (game, level), opportunities in matrix_results.items():
        print(f"{game} {level}: {len(opportunities)} opportunities")
