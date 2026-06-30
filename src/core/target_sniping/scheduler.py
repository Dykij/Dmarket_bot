"""
scheduler.py — Main loop scheduler + helpers.

Mixin with start(), _compute_scan_delay(), and _init_cs2cap_cache().
Mixed into `SnipingLoop` (see `core.py`).
"""

from __future__ import annotations

import asyncio
import gc
import logging
import os
import time
from pathlib import Path
from typing import Any, Optional

from src.api.cs2cap_cache import CS2CapCache
from src.api.cs2cap_oracle import CS2CapOracle
from src.api.oracle_factory import OracleFactory
from src.config import Config
from src.core.daily_briefing import DailyBriefingScheduler
from src.risk.fatal_errors import classify
from src.risk.error_reporter import ErrorReporter

logger = logging.getLogger("SnipingBot")


class _SchedulerMixin:
    """Main async loop: start(), scan-delay computation, CS2Cap cache init."""

    # These attributes are set on the instance by SnipingLoop.__init__
    client: Any
    target_games: list
    running: bool
    cs2cap_cache: Optional[CS2CapCache]
    briefing_scheduler: Optional[DailyBriefingScheduler]
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
            f"Starting DMarket Intra-Spread Loop v12.6 | Targets: {self.target_games}"
        )

        gc.set_threshold(700, 10, 5)  # Less aggressive GC, but still enabled

        # v12.4: launch in-memory CS2Cap cache (background refresh task)
        await self._init_cs2cap_cache()

        # v12.5: Launch daily briefing scheduler (background task).
        # Sends a startup briefing after 30s, then one every UTC midnight.
        try:
            self.briefing_scheduler = DailyBriefingScheduler(
                risk=self.risk,
                get_balance=lambda: self.client.get_real_balance(),
            )
            self.briefing_scheduler.start()
        except Exception as e:
            logger.warning(f"[v12.5] Could not start daily briefing scheduler: {e}", exc_info=True)

        # v12.5: Leak detection - sample RSS on every loop. If we grow
        # past 500 MB or >2x the boot-time RSS, the loop is leaking and
        # we should log a warning so the watchdog can decide to restart.
        import psutil
        process = psutil.Process()
        boot_rss_mb = process.memory_info().rss / (1024 * 1024)
        cycle_count = 0

        # v12.5: Watchdog heartbeat. The external watchdog.sh script
        # checks this file; if it stops updating for >5 min, the
        # process is considered hung and gets restarted.
        heartbeat_path = Path(
            os.getenv("WATCHDOG_HEARTBEAT_FILE", "data/watchdog_heartbeat.txt")
        )
        try:
            heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        def _write_heartbeat() -> None:
            try:
                heartbeat_path.write_text(str(int(time.time())), encoding="utf-8")
            except Exception:
                pass

        _write_heartbeat()  # initial

        try:
            while self.running:
                for game_id in self.target_games:
                    await self.run_cycle(game_id)

                cycle_count += 1
                _write_heartbeat()  # per-cycle heartbeat

                # Periodic GC + memory sample (every 10 cycles = ~5 min)
                if cycle_count % 10 == 0:
                    gc.collect()
                    rss_mb = process.memory_info().rss / (1024 * 1024)
                    if rss_mb > 500 or rss_mb > 2 * boot_rss_mb:
                        logger.warning(
                            f"[v12.5 LEAK?] RSS={rss_mb:.1f}MB "
                            f"(boot={boot_rss_mb:.1f}MB). Will restart on next "
                            f"out-of-band error."
                        )
                        # Aggressive GC + drop references
                        gc.collect()
                        gc.collect()

                # v12.5: Self-reflection (every SELF_REFLECTION_INTERVAL cycles).
                # Applies parameter adjustments to the current run.
                try:
                    reflection = await self.self_reflection.maybe_run_reflection(cycle_count)
                    if reflection is not None and reflection.confidence > 0.3:
                        # Apply adjusted spread/risk/vol params to Config
                        # so subsequent candidates see them
                        from src.config import Config
                        new_spread = self.self_reflection.get_adjusted_spread(
                            Config.MIN_SPREAD_PCT, reflection
                        )
                        if new_spread != Config.MIN_SPREAD_PCT:
                            logger.info(
                                f"[v12.5] Self-reflection: MIN_SPREAD_PCT "
                                f"{Config.MIN_SPREAD_PCT:.2f}% → {new_spread:.2f}%"
                            )
                            Config.MIN_SPREAD_PCT = new_spread
                except Exception as e:
                    logger.debug(f"[v12.5] self_reflection error: {e}")

                # v12.5: Quota-aware adaptive scan interval.
                from src.config import Config

                delay = self._compute_scan_delay()
                await asyncio.sleep(delay)
        except asyncio.CancelledError:
            logger.info("Sniping loop cancelled.")
        except Exception as e:
            # v12.6: bubble up fatal errors. The outer supervisor
            # decides whether to retry (transient) or exit (fatal).
            # run_cycle already classified and re-raised fatal ones,
            # so anything landing here is either a transient from
            # outside the cycle, or another fatal from setup. We
            # re-raise and let the supervisor's classifier decide.
            classification = classify(e)
            if classification in ("FATAL", "UNKNOWN"):
                report = ErrorReporter(e, context={
                    "phase": "start",
                    "cycle_count": cycle_count,
                    "boot_rss_mb": f"{boot_rss_mb:.1f}",
                    "current_rss_mb": f"{process.memory_info().rss / (1024*1024):.1f}",
                })
                logger.error(report.format_log())
            else:
                logger.warning(
                    f"[v12.6] Transient start-level error "
                    f"({classification}): {type(e).__name__}: {e}",
                    exc_info=True,
                )
            raise
        finally:
            # v12.5: Stop daily briefing scheduler
            if self.briefing_scheduler is not None:
                try:
                    await self.briefing_scheduler.stop()
                except Exception as e:
                    logger.debug(f"Briefing shutdown error: {e}")
            if self.cs2cap_cache is not None:
                await self.cs2cap_cache.stop()
            await OracleFactory.close_all()
            if self.client:
                await self.client.close()

    def _compute_scan_delay(self) -> float:
        """
        v12.5: Quota-aware adaptive scan interval.

        Strategy:
        - Base: Config.SCAN_INTERVAL (default 30s)
        - If empty page: back off exponentially up to 5 min
        - If CS2Cap quota >80% used: double the delay (slow & steady)
        - If CS2Cap quota >95% used: triple the delay (preserve what's left)
        - If CS2Cap cooldown active: wait out the cooldown
        - If the cache is stale: don't add extra delay (we still have
          the in-memory cache; the hot path doesn't need fresh data to
          do the math).
        """
        from src.config import Config

        delay = float(Config.SCAN_INTERVAL)

        if self.empty_page_count > 0:
            delay = min(delay * self.empty_page_count, 300.0)

        quota_aware = os.getenv("SCAN_INTERVAL_QUOTA_AWARE", "true").lower() in (
            "1", "true", "yes",
        )
        if quota_aware and self.cs2cap_cache is not None:
            try:
                stats = self.cs2cap_cache.stats()
                monthly_limit = max(1, stats.get("monthly_limit", 50000))
                used_pct = (stats.get("monthly_used", 0) * 100.0) / monthly_limit
                cooldown = stats.get("cooldown_remaining_s") or 0.0
                if cooldown > 0:
                    delay = max(delay, cooldown + 5.0)
                    logger.debug(
                        f"[v12.5] CS2Cap cooldown {cooldown:.0f}s — sleeping that long"
                    )
                elif used_pct >= 95.0:
                    delay = min(delay * 3.0, 300.0)
                    if not hasattr(self, "_last_quota_warn") or (
                        time.time() - self._last_quota_warn > 300
                    ):
                        self._last_quota_warn = time.time()
                        logger.warning(
                            f"[v12.5] CS2Cap quota at {used_pct:.1f}% — "
                            f"scan interval tripled to {delay:.0f}s"
                        )
                elif used_pct >= 80.0:
                    delay = min(delay * 2.0, 300.0)
            except Exception as e:
                logger.debug(f"[v12.5] quota-aware check failed: {e}")

        delay = max(
            float(os.getenv("SCAN_INTERVAL_MIN_SECONDS", "30")),
            min(delay, float(os.getenv("SCAN_INTERVAL_MAX_SECONDS", "300"))),
        )
        return delay

    async def _init_cs2cap_cache(self) -> None:
        """
        v12.4: initialise the in-memory CS2Cap cache.

        The cache is fed by a background task (CS2CapCache.start) that
        refreshes the top-100 most-traded titles every CS2CAP_CACHE_TTL_SECONDS.
        The hot path (run_cycle) reads from the cache, so no per-cycle
        CS2Cap HTTP calls are made.
        """
        oracle = OracleFactory.get_oracle(Config.GAME_ID)
        if oracle is None:
            logger.warning(
                "[v12.4] No oracle available for CS2Cap cache; will fall back to per-cycle batch."
            )
            return
        if not isinstance(oracle, CS2CapOracle):
            logger.warning(
                f"[v12.4] Oracle for {Config.GAME_ID} is {type(oracle).__name__}, "
                "not CS2CapOracle; in-memory cache disabled."
            )
            return
        self.cs2cap_cache = CS2CapCache(
            oracle=oracle,
            dmarket_client=self.client,
            game_id=Config.GAME_ID,
        )
        await self.cs2cap_cache.start()
