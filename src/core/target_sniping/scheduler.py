"""
scheduler.py — Main loop scheduler + helpers (v14.9).

Mixin with start() and _compute_scan_delay().
Mixed into `SnipingLoop` (see `core.py`).

v14.9 Improvements (based on PythonHub best practices):
- Structured concurrency with asyncio.TaskGroup
- Graceful shutdown with proper task cancellation
- Structured error context in ErrorReporter
- Clean resource lifecycle management
- Removed paid oracle cache (replaced by MultiSourceOracle)
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
            f"Starting DMarket Intra-Spread Loop {Config.BOT_VERSION} | Targets: {self.target_games}"
        )

        gc.set_threshold(700, 10, 5)  # More frequent gen2 GC (default: 700, 10, 10)

        # v14.9: Use TaskGroup for structured concurrency
        # All background tasks managed in a single group for clean shutdown
        try:
            async with asyncio.TaskGroup() as tg:
                tg.create_task(self._run_maintenance_loop())
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
                        f"[{Config.BOT_VERSION}] Could not start daily briefing scheduler: {e}",
                        exc_info=True,
                    )

                # v16.3: Telegram reporter — automated reports
                from src.telegram.notifier import notifier
                from src.telegram_reporter import TelegramReporter
                from src.db.price_history import price_db

                reporter = TelegramReporter(
                    notifier=notifier,
                    price_db=price_db,
                    intervals={
                        "hourly": Config.REPORT_INTERVAL_HOURLY,
                        "cron": Config.REPORT_INTERVAL_CRON,
                        "daily": Config.REPORT_INTERVAL_DAILY,
                        "weekly": Config.REPORT_INTERVAL_WEEKLY,
                    },
                    get_stats=lambda: self._reporter_stats(),
                )

                # Leak detection - sample RSS on every loop
                import psutil
                process = psutil.Process()
                boot_rss_mb = process.memory_info().rss / (1024 * 1024)
                cycle_count = 0
                import time as _time
                _cycle_start = _time.monotonic()

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
                    _cycle_start = _time.monotonic()
                    for game_id in self.target_games:
                        try:
                            await self.run_cycle(game_id)
                        except Exception as e:
                            logger.error(f"[CYCLE] run_cycle failed for {game_id}: {e}", exc_info=True)
                            await asyncio.sleep(5)  # Brief pause before retry

                    cycle_count += 1
                    _write_heartbeat()

                    # v16.3: Record cycle stats for Telegram reporter
                    try:
                        cycle_time = _time.monotonic() - _cycle_start
                        reporter.record_cycle(
                            balance=getattr(self, '_last_balance', 0.0),
                            listings=getattr(self, '_last_listings', 0),
                            candidates=getattr(self, '_last_candidates', 0),
                            errors_429=getattr(self, '_last_429', 0),
                            cycle_time=cycle_time,
                            drawdown=getattr(self, '_last_drawdown', 0.0),
                        )
                        # Check and send reports every 3 cycles
                        if cycle_count % 3 == 0:
                            await reporter.check_and_send_reports()
                    except Exception as e:
                        logger.debug(f"[Reporter] record/check error: {e}")

                    # Periodic GC + memory sample (every 10 cycles)
                    if cycle_count % 10 == 0:
                        gc.collect()
                        rss_mb = process.memory_info().rss / (1024 * 1024)
                        if rss_mb > 500 or rss_mb > 2 * boot_rss_mb:
                            logger.warning(
                                f"[{Config.BOT_VERSION} LEAK?] RSS={rss_mb:.1f}MB "
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
                                    f"[{Config.BOT_VERSION}] Self-reflection: MIN_SPREAD_PCT "
                                    f"{Config.MIN_SPREAD_PCT:.2f}% -> {new_spread:.2f}%"
                                )
                                Config.MIN_SPREAD_PCT = new_spread
                    except Exception as e:
                        logger.debug(f"[{Config.BOT_VERSION}] self_reflection error: {e}")

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
                        "cycle_count": cycle_count if 'cycle_count' in locals() else 0,
                        "boot_rss_mb": f"{boot_rss_mb:.1f}" if 'boot_rss_mb' in locals() else "unknown",
                    })
                    logger.error(report.format_log())
                else:
                    logger.warning(
                        f"[{Config.BOT_VERSION}] Transient TaskGroup error "
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

    def _reporter_stats(self) -> dict[str, Any]:
        """Collect stats for TelegramReporter from current bot state."""
        stats: dict[str, Any] = {}
        try:
            # Rate limiter
            if hasattr(self, 'client') and hasattr(self.client, 'rate_limiter_status'):
                rl = self.client.rate_limiter_status()
                mon = rl.get("_monitoring", {})
                stats["rate_limiter_margin"] = f"{mon.get('current_safety_margin', 0):.2f}"
                stats["total_429"] = mon.get("total_429", 0)
            # Risk state
            if hasattr(self, 'risk') and self.risk:
                rs = self.risk.get_state()
                stats["drawdown"] = rs.current_drawdown_pct
                stats["daily_trades"] = rs.daily_trade_count
        except Exception as e:
            logger.debug(f"[Reporter] stats collection error: {e}")
        return stats
    async def _run_maintenance_loop(self) -> None:
        """Periodic SQLite maintenance and state backup (every 8 hours)."""
        from src.db.price_history import price_db
        from pathlib import Path
        import subprocess
        
        while self.running:
            await asyncio.sleep(8 * 3600)  # ~8 hours
            
            # 1. DB Maintenance
            try:
                await price_db.run_in_thread(price_db.wal_checkpoint)
                await price_db.run_in_thread(price_db.optimize)
                await price_db.run_in_thread(price_db.cleanup_old_prices, days=30)
                await price_db.run_in_thread(price_db.cleanup_old_trades, days=90)
                logger.info("[DB] Background WAL checkpoint + optimize + cleanup complete")
            except Exception as e:
                logger.warning(f"[DB] Background maintenance failed: {e}")

            # 2. Git state backup using worktree (safe for concurrent running bot)
            def _do_backup() -> None:
                branch = "dryrun-state"
                worktree_dir = "/tmp/dmarket-dryrun-state-worktree"
                try:
                    import shutil
                    if Path(worktree_dir).exists():
                        shutil.rmtree(worktree_dir, ignore_errors=True)
                        subprocess.run(["git", "worktree", "prune"], capture_output=True)

                    res = subprocess.run(["git", "worktree", "add", "-B", branch, worktree_dir, "origin/master"], capture_output=True)
                    if res.returncode != 0:
                        subprocess.run(["git", "worktree", "add", "-B", branch, worktree_dir], capture_output=True)

                    wt_data = Path(worktree_dir) / "data"
                    wt_data.mkdir(parents=True, exist_ok=True)
                    
                    db_files = ["data/dmarket_state.db", "data/dmarket_history.db", "data/dmarket_trading.db"]
                    for f in db_files:
                        src = Path(f)
                        if src.exists():
                            shutil.copy2(src, wt_data / src.name)
                            if Path(f"{src}-wal").exists():
                                shutil.copy2(f"{src}-wal", wt_data / f"{src.name}-wal")
                            if Path(f"{src}-shm").exists():
                                shutil.copy2(f"{src}-shm", wt_data / f"{src.name}-shm")

                    import time
                    msg = f"state-backup ts={int(time.time())}"
                    subprocess.run(["git", "add", "data/*.db*"], cwd=worktree_dir, capture_output=True)
                    subprocess.run(["git", "commit", "-m", msg, "--allow-empty"], cwd=worktree_dir, capture_output=True)
                    subprocess.run(["git", "push", "origin", branch, "--force"], cwd=worktree_dir, capture_output=True)
                    logger.info("[STATE-BACKUP] Background commit successful")
                except Exception as e:
                    logger.warning(f"[STATE-BACKUP] Background commit failed: {e}")
                finally:
                    if Path(worktree_dir).exists():
                        shutil.rmtree(worktree_dir, ignore_errors=True)
                    subprocess.run(["git", "worktree", "prune"], capture_output=True)

            try:
                await asyncio.get_event_loop().run_in_executor(None, _do_backup)
            except Exception as e:
                logger.warning(f"[STATE-BACKUP] Executor failed: {e}")

