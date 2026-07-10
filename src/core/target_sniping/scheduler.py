"""
scheduler.py — Main loop scheduler + helpers (v14.9).

Mixin with start() and _compute_scan_delay().
Mixed into `SnipingLoop` (see `core.py`).

v14.9 Improvements (based on PythonHub best practices):
- Structured concurrency with asyncio.TaskGroup
- Graceful shutdown with proper task cancellation
- Structured error context in ErrorReporter
- Clean resource lifecycle management
- Removed CS2Cap cache (replaced by MultiSourceOracle)
"""

from __future__ import annotations

import asyncio
import contextlib
import gc
import logging
import os
import time
from pathlib import Path
from typing import Any

from src.api.oracle_factory import OracleFactory
from src.config import Config
from src.core.daily_briefing import DailyBriefingScheduler
from src.risk.error_reporter import ErrorReporter
from src.risk.fatal_errors import classify

logger = logging.getLogger("SnipingBot")


class _SchedulerMixin:
    """Main async loop: start() and scan-delay computation."""

    # These attributes are set on the instance by SnipingLoop.__init__
    client: Any
    target_games: list
    running: bool
    briefing_scheduler: DailyBriefingScheduler | None
    deep_scan_counter: int
    empty_page_count: int
    risk: Any
    self_reflection: Any
    pump_detector: Any
    _last_quota_warn: float

    async def run_cycle(self, game_id: str) -> None: ...

    async def start(self) -> None:
        self.running = True
        logger.info(
            f"Starting DMarket Intra-Spread Loop v14.9 | Targets: {self.target_games}"
        )

        gc.set_threshold(700, 10, 5)  # Less aggressive GC, but still enabled

        # v14.9: Use TaskGroup for structured concurrency
        # All background tasks managed in a single group for clean shutdown
        try:
            async with asyncio.TaskGroup() as tg:
                # Launch daily briefing scheduler
                try:
                    self.briefing_scheduler = DailyBriefingScheduler(
                        risk=self.risk,
                        get_balance=lambda: self.client.get_real_balance(),
                    )
                    # Briefing runs as a background task within the group
                    tg.create_task(
                        self._run_briefing_with_lifecycle(),
                        name="daily_briefing",
                    )
                except Exception as e:
                    logger.warning(
                        f"[v14.9] Could not start daily briefing scheduler: {e}",
                        exc_info=True,
                    )

                # Leak detection - sample RSS on every loop
                import psutil
                process = psutil.Process()
                boot_rss_mb = process.memory_info().rss / (1024 * 1024)
                cycle_count = 0

                # Watchdog heartbeat
                heartbeat_path = Path(
                    os.getenv("WATCHDOG_HEARTBEAT_FILE", "data/watchdog_heartbeat.txt")
                )
                with contextlib.suppress(Exception):
                    heartbeat_path.parent.mkdir(parents=True, exist_ok=True)

                def _write_heartbeat() -> None:
                    with contextlib.suppress(Exception):
                        heartbeat_path.write_text(str(int(time.time())), encoding="utf-8")

                _write_heartbeat()  # initial

                # Main trading loop
                while self.running:
                    for game_id in self.target_games:
                        await self.run_cycle(game_id)

                    cycle_count += 1
                    _write_heartbeat()

                    # Periodic GC + memory sample (every 10 cycles)
                    if cycle_count % 10 == 0:
                        gc.collect()
                        rss_mb = process.memory_info().rss / (1024 * 1024)
                        if rss_mb > 500 or rss_mb > 2 * boot_rss_mb:
                            logger.warning(
                                f"[v14.9 LEAK?] RSS={rss_mb:.1f}MB "
                                f"(boot={boot_rss_mb:.1f}MB). Will restart on next "
                                f"out-of-band error."
                            )
                            gc.collect()
                            gc.collect()

                    # Self-reflection (every SELF_REFLECTION_INTERVAL cycles)
                    try:
                        reflection = await self.self_reflection.maybe_run_reflection(cycle_count)
                        if reflection is not None and reflection.confidence > 0.3:
                            new_spread = self.self_reflection.get_adjusted_spread(
                                Config.MIN_SPREAD_PCT, reflection
                            )
                            if new_spread != Config.MIN_SPREAD_PCT:
                                logger.info(
                                    f"[v14.9] Self-reflection: MIN_SPREAD_PCT "
                                    f"{Config.MIN_SPREAD_PCT:.2f}% -> {new_spread:.2f}%"
                                )
                                Config.MIN_SPREAD_PCT = new_spread
                    except Exception as e:
                        logger.debug(f"[v14.9] self_reflection error: {e}")

                    # Quota-aware adaptive scan interval
                    delay = self._compute_scan_delay()
                    await asyncio.sleep(delay)

        except* asyncio.CancelledError:
            logger.info("Sniping loop cancelled (TaskGroup shutdown).")
        except* Exception as eg:
            # v14.9: TaskGroup aggregates exceptions from all tasks
            for exc in eg.exceptions:
                classification = classify(exc)
                if classification in ("FATAL", "UNKNOWN"):
                    report = ErrorReporter(exc, context={
                        "phase": "taskgroup",
                        "cycle_count": cycle_count if 'cycle_count' in dir() else 0,
                        "boot_rss_mb": f"{boot_rss_mb:.1f}" if 'boot_rss_mb' in dir() else "unknown",
                    })
                    logger.error(report.format_log())
                else:
                    logger.warning(
                        f"[v14.9] Transient TaskGroup error "
                        f"({classification}): {type(exc).__name__}: {exc}",
                        exc_info=True,
                    )
            raise
        finally:
            # Clean shutdown of all resources
            await self._shutdown_resources()

    async def _run_briefing_with_lifecycle(self) -> None:
        """v14.9: Run daily briefing with proper lifecycle management."""
        if self.briefing_scheduler is None:
            return
        try:
            self.briefing_scheduler.start()
            # Keep the task alive until cancelled
            while self.running:
                await asyncio.sleep(60)
        except asyncio.CancelledError:
            logger.debug("Briefing task cancelled.")
        finally:
            with contextlib.suppress(Exception):
                await self.briefing_scheduler.stop()

    async def _shutdown_resources(self) -> None:
        """v14.9: Clean shutdown of all resources."""
        logger.info("Shutting down resources...")
        with contextlib.suppress(Exception):
            await OracleFactory.close_all()
        if self.client:
            with contextlib.suppress(Exception):
                await self.client.close()
        logger.info("Resources shutdown complete.")

    def _compute_scan_delay(self) -> float:
        """
        v14.9: Adaptive scan interval.

        Strategy:
        - Base: Config.SCAN_INTERVAL (default 30s)
        - If empty page: back off exponentially up to 5 min
        """
        from src.config import Config

        delay = float(Config.SCAN_INTERVAL)

        if self.empty_page_count > 0:
            delay = min(delay * self.empty_page_count, 300.0)

        delay = max(
            float(os.getenv("SCAN_INTERVAL_MIN_SECONDS", "30")),
            min(delay, float(os.getenv("SCAN_INTERVAL_MAX_SECONDS", "300"))),
        )
        return delay

