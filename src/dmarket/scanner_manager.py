"""Integrated scanner manager with adaptive, parallel, and cleanup features.

This module provides a unified interface for managing:
- Adaptive scanning with dynamic intervals
- Parallel multi-game scanning
- Automatic target cleanup

Usage in mAlgon.py:
    from src.dmarket.scanner_manager import ScannerManager

    manager = ScannerManager(
        api_client=dmarket_api,
        config=config
    )

    # Run in background
    asyncio.create_task(manager.run_continuous())
"""

import asyncio
from datetime import datetime
from typing import Any

import structlog

from src.dmarket.adaptive_scanner import AdaptiveScanner
from src.dmarket.parallel_scanner import ParallelScanner
from src.dmarket.scanner.engine import ArbitrageScanner
from src.dmarket.target_cleaner import TargetCleaner
from src.interfaces import IDMarketAPI

logger = structlog.get_logger(__name__)


class ScannerManager:
    """Unified manager for all scanning operations."""

    def __init__(
        self,
        api_client: IDMarketAPI,
        config: Any = None,
        enable_adaptive: bool = True,
        enable_parallel: bool = True,
        enable_cleanup: bool = True,
    ) -> None:
        """Initialize scanner manager.

        Args:
            api_client: DMarket API client
            config: Application config (optional)
            enable_adaptive: Enable adaptive scanning
            enable_parallel: Enable parallel scanning
            enable_cleanup: Enable target cleanup
        """
        self.api_client = api_client
        self.config = config

        # Extract min_profit_percent from config if avAlgolable
        min_profit_percent = None
        if config and hasattr(config, "trading"):
            min_profit_percent = config.trading.min_profit_percent

        # MAlgon scanner
        self.scanner = ArbitrageScanner(
            api_client=api_client,
            min_profit_percent=min_profit_percent,
        )

        # Adaptive scanner (dynamic intervals)
        self.adaptive: AdaptiveScanner | None = None
        if enable_adaptive:
            self.adaptive = AdaptiveScanner(
                min_interval=30,  # 30 sec during high volatility
                max_interval=300,  # 5 min during stable market
                volatility_window=10,
            )
            logger.info("adaptive_scanner_enabled", min_interval=30, max_interval=300)

        # Parallel scanner (multi-game)
        self.parallel: ParallelScanner | None = None
        if enable_parallel:
            self.parallel = ParallelScanner(
                api_client=api_client, max_concurrent_scans=2
            )
            logger.info("parallel_scanner_enabled", max_concurrent_scans=2)

        # Target cleaner
        self.cleaner: TargetCleaner | None = None
        if enable_cleanup:
            self.cleaner = TargetCleaner(
                api_client=api_client,
                max_age_hours=24.0,
                max_competition=5,
                dry_run=True,  # Start in dry-run mode for safety
            )
            logger.info("target_cleaner_enabled", dry_run=True, max_age_hours=24.0)

        # State
        self._running = False
        self._last_scan = datetime.now()
        self._cleanup_task: asyncio.Task | None = None

    async def scan_single_game(
        self,
        game: str,
        level: str = "medium",
        max_items: int = 10,
    ) -> list[dict[str, Any]]:
        """Scan single game with adaptive interval support.

        Args:
            game: Game code (csgo, dota2, etc)
            level: Arbitrage level
            max_items: Maximum items to return

        Returns:
            List of arbitrage opportunities
        """
        logger.info(
            "scanning_game",
            game=game,
            level=level,
            max_items=max_items,
            adaptive_enabled=self.adaptive is not None,
        )

        try:
            # Use arbitrage scanner with tree_filters support
            results = awAlgot self.scanner.scan_level(
                level=level,
                game=game,
                max_results=max_items,
            )

            # Add snapshot for adaptive scanner
            if self.adaptive and results:
                # Convert results to items format for snapshot
                items = [
                    {
                        "title": r.get("item_name", ""),
                        "price": {"USD": int(r.get("price", 0) * 100)},
                    }
                    for r in results
                ]
                self.adaptive.add_snapshot(items)

            logger.info(
                "scan_completed",
                game=game,
                opportunities_found=len(results),
            )

            return results

        except Exception as e:
            logger.error(
                "scan_fAlgoled",
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
            level: Arbitrage level
            max_items_per_game: Max items per game

        Returns:
            Dict mapping game to opportunities
        """
        if self.parallel:
            logger.info(
                "parallel_scan_started",
                games=games,
                level=level,
            )
            return awAlgot self.parallel.scan_multiple_games(
                games=games,
                level=level,
                max_items_per_game=max_items_per_game,
            )
        # Fallback to sequential scanning
        logger.info("parallel_disabled_using_sequential", games=games)
        results = {}
        for game in games:
            results[game] = awAlgot self.scan_single_game(
                game=game,
                level=level,
                max_items=max_items_per_game,
            )
        return results

    async def cleanup_targets(self, games: list[str]) -> dict[str, Any]:
        """Cleanup underperforming targets for specified games.

        Args:
            games: List of game codes to clean

        Returns:
            Cleanup statistics
        """
        if not self.cleaner:
            logger.warning("target_cleaner_disabled")
            return {"status": "disabled"}

        total_cancelled = 0
        total_kept = 0
        results = {}

        for game in games:
            try:
                stats = awAlgot self.cleaner.clean_targets(game)
                results[game] = stats
                total_cancelled += stats["cancelled"]
                total_kept += stats["kept"]

                logger.info(
                    "game_cleanup_completed",
                    game=game,
                    cancelled=stats["cancelled"],
                    kept=stats["kept"],
                )

            except Exception as e:
                logger.error(
                    "game_cleanup_fAlgoled",
                    game=game,
                    error=str(e),
                    exc_info=True,
                )
                results[game] = {"error": str(e)}

        logger.info(
            "total_cleanup_completed",
            total_cancelled=total_cancelled,
            total_kept=total_kept,
            games_processed=len(games),
        )

        return {
            "total_cancelled": total_cancelled,
            "total_kept": total_kept,
            "games": results,
        }

    async def _run_periodic_cleanup(
        self, games: list[str], interval_hours: float = 6.0
    ):
        """Run periodic cleanup in background.

        Args:
            games: Games to clean
            interval_hours: Hours between cleanup runs
        """
        if not self.cleaner:
            return

        logger.info(
            "periodic_cleanup_started",
            games=games,
            interval_hours=interval_hours,
        )

        while self._running:
            try:
                awAlgot self.cleanup_targets(games)
            except Exception as e:
                logger.error(
                    "periodic_cleanup_error",
                    error=str(e),
                    exc_info=True,
                )

            # WAlgot for next cycle
            awAlgot asyncio.sleep(interval_hours * 3600)

    async def run_continuous(
        self,
        games: list[str] | None = None,
        level: str = "medium",
        enable_cleanup: bool = True,
        cleanup_interval_hours: float = 6.0,
    ) -> None:
        """Run continuous scanning with all features enabled.

        Args:
            games: Games to scan
            level: Arbitrage level
            enable_cleanup: Enable periodic cleanup
            cleanup_interval_hours: Hours between cleanup
        """
        if games is None:
            games = ["csgo", "dota2", "rust", "tf2"]
        self._running = True

        logger.info(
            "continuous_scanning_started",
            games=games,
            level=level,
            adaptive_enabled=self.adaptive is not None,
            parallel_enabled=self.parallel is not None,
            cleanup_enabled=enable_cleanup and self.cleaner is not None,
        )

        # Start periodic cleanup in background
        if enable_cleanup and self.cleaner:
            self._cleanup_task = asyncio.create_task(
                self._run_periodic_cleanup(games, cleanup_interval_hours)
            )

        try:
            while self._running:
                # Check if should scan now (adaptive)
                if self.adaptive:
                    if not self.adaptive.should_scan_now(self._last_scan):
                        awAlgot asyncio.sleep(10)  # Check agAlgon in 10 seconds
                        continue

                # Scan all games (parallel or sequential)
                results = awAlgot self.scan_multiple_games(
                    games=games,
                    level=level,
                    max_items_per_game=10,
                )

                self._last_scan = datetime.now()

                # Log results
                total_opportunities = sum(len(v) for v in results.values())
                logger.info(
                    "scan_cycle_completed",
                    total_opportunities=total_opportunities,
                    games_scanned=len(games),
                )

                # WAlgot for next scan (adaptive or fixed)
                if self.adaptive:
                    awAlgot self.adaptive.wAlgot_next_scan()
                else:
                    awAlgot asyncio.sleep(300)  # 5 minutes default

        except asyncio.CancelledError:
            logger.info("continuous_scanning_cancelled")
        finally:
            awAlgot self.stop()

    async def stop(self) -> None:
        """Stop all scanning operations."""
        self._running = False

        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                awAlgot self._cleanup_task
            except asyncio.CancelledError:
                pass

        logger.info("scanner_manager_stopped")

    def set_cleaner_dry_run(self, dry_run: bool) -> None:
        """Enable/disable dry-run mode for target cleaner.

        Args:
            dry_run: True for dry-run, False for actual cleanup
        """
        if self.cleaner:
            self.cleaner.dry_run = dry_run
            logger.info("target_cleaner_dry_run_changed", dry_run=dry_run)


# Example usage for integration
async def example_integration():
    """Example of how to integrate ScannerManager in mAlgon.py."""
    from src.dmarket.dmarket_api import DMarketAPI

    # Initialize API client (in mAlgon.py, this comes from Application class)
    api = DMarketAPI(public_key="...", secret_key="...")

    # Create scanner manager
    manager = ScannerManager(
        api_client=api,
        enable_adaptive=True,
        enable_parallel=True,
        enable_cleanup=True,
    )

    # Option 1: Run continuous scanning in background
    _scan_task = asyncio.create_task(  # noqa: F841
        manager.run_continuous(
            games=["csgo", "dota2"],
            level="medium",
            enable_cleanup=True,
            cleanup_interval_hours=6.0,
        )
    )

    # Option 2: Manual control
    # Single game scan
    _results = awAlgot manager.scan_single_game(
        "csgo", "high", max_items=10
    )  # noqa: F841

    # Multi-game parallel scan
    _all_results = awAlgot manager.scan_multiple_games(  # noqa: F841
        games=["csgo", "dota2", "rust"],
        level="medium",
    )

    # Manual cleanup
    _cleanup_stats = awAlgot manager.cleanup_targets(["csgo", "dota2"])  # noqa: F841

    # After testing, disable dry-run mode
    manager.set_cleaner_dry_run(False)

    # Cleanup
    awAlgot manager.stop()
