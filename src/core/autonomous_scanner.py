"""
Autonomous DMarket Scanner v3.2 — Pure Script / Math Pipeline.

Pipeline:
  1. DMarketAPIClient initialization.
  2. InventoryManager initialization.
  3. Start the Target Sniping Loop (Math based).

v12.6 changes (Phase 5: hard error policy):
- Distinct exit codes (1=generic, 2=config, 3=auth, 4=db, 5=logic, 6=unknown).
- Fatal vs transient errors. The bot no longer restarts on bugs in our
  code (KeyError, AttributeError, etc.) — those exit immediately so the
  user sees a clean stack trace and the watchdog does not loop them.
- Transient errors (network blips, rate limits) still retry with
  exponential backoff, but the backoff is bounded.
- A single ErrorReporter is used for log + Telegram; same context block.
- The "self.target_games" bug in the startup notification is fixed (use
  Config.GAME_ID or a module-level constant).

v12.5 changes:
- setup_logging() is now a no-op (logging is owned by src.__main__).
- Exponential backoff capped at 5 min, resets on first successful run.
- Quota-aware: if the inner loop already handles the rate-limit guard,
  we just sleep longer between restarts when monthly usage is high.
- psutil: log memory + fd count on every restart, useful for spotting
  leaks that the inner loop's RSS check would miss.
- Sends a Telegram alert on every restart (best-effort, non-blocking).
"""

import asyncio
import os
import sys
import logging
import time
from dotenv import load_dotenv
from pathlib import Path

BASE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from src.api.dmarket_api_client import DMarketAPIClient  # noqa: E402
from src.inventory_manager import InventoryManager  # noqa: E402
from src.utils.vault import vault  # noqa: E402
from src.risk.fatal_errors import (  # noqa: E402
    AuthError,
    ConfigError,
    classify,
)
from src.risk.error_reporter import ErrorReporter, _write_exit_state, fatal_exit  # noqa: E402


def setup_logging() -> None:
    """No-op stub for back-compat. Logging is configured in src.__main__."""
    return None


logger = logging.getLogger("AutonomousScanner")

# Phase 1: Feature-flag selection between v12.0 and legacy v10.0 loops.
_USE_V12 = os.getenv("USE_V12_LOOP", "true").lower() == "true"
if _USE_V12:
    from src.core.target_sniping.core import SnipingLoop
    logger.info("🔀 Using SnipingLoop v12.0 (batched endpoints + selective CS2Cap)")
else:
    from src.core.target_sniping import SnipingLoop
    logger.warning("⚠️  Using legacy v10.0 SnipingLoop (per-item CS2Cap, quota-heavy)")


def _format_process_stats() -> str:
    """Memory / FD stats — useful for spotting leaks on restart."""
    try:
        import psutil
        p = psutil.Process()
        mi = p.memory_info()
        fds = len(p.open_files())
        return (
            f"RSS={mi.rss/1024/1024:.1f}MB "
            f"VMS={mi.vms/1024/1024:.1f}MB "
            f"open_fds={fds} "
            f"threads={p.num_threads()}"
        )
    except Exception:
        return "(psutil unavailable)"


async def _send_startup_notification(target_games: list) -> None:
    """
    Best-effort Telegram notification that the bot is up.
    Never raises — the bot must start even if Telegram is down.
    """
    try:
        from src.telegram.notifier import notifier

        mode = (
            "🧪 DRY_RUN" if os.getenv("DRY_RUN", "true").lower() == "true" else "💸 LIVE"
        )
        await notifier.custom(
            f"🟢 <b>DMarket bot started</b>\n"
            f"Mode: {mode}\n"
            f"Targets: {target_games}\n"
            f"{_format_process_stats()}",
            severity="info",
        )
    except Exception as e:
        logger.debug(f"startup notification failed: {e}")


async def run_autonomous_scanner() -> None:
    """
    Main entry with restart-on-transient-error loop.

    v12.6 error policy:
    - TRANSIENT errors (network, CB) → exponential backoff, retry.
    - FATAL errors (config, auth, db corruption, our code bugs) →
      log with full context, send Telegram, exit with distinct code.
    - The watchdog checks the exit code and skips restart on codes
      ≥ 1. So a fatal error stops the bot once and the user sees
      a clean traceback instead of a tight crash loop.
    """
    base_retry = 5
    max_retry = 300
    retry_delay = base_retry
    consecutive_transient = 0
    started_at = time.time()
    successful_cycles = 0

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

    while True:
        _write_heartbeat()
        try:
            # Re-initialize vault and environment each major restart.
            for env_candidate in (
                os.path.join(os.getcwd(), ".env"),
                os.path.join(BASE_DIR, ".env"),
            ):
                if os.path.isfile(env_candidate):
                    load_dotenv(dotenv_path=env_candidate, override=False)
                    vault.re_initialize()
                    break

            pub_key = os.environ.get("DMARKET_PUBLIC_KEY", "").strip()
            sec_key = vault.get_dmarket_secret()

            if not pub_key or not sec_key or pub_key.startswith("ROTATE_ME"):
                raise ConfigError(
                    "API keys not configured (placeholders detected in .env?). "
                    "Edit .env and insert real keys."
                )

            api = DMarketAPIClient(public_key=pub_key, secret_key=sec_key)
            inventory_mgr = InventoryManager(api)
            bot = SnipingLoop(api)
            bot.inventory_mgr = inventory_mgr

            logger.info(
                f"🚀 QUANTITATIVE ENGINE v12.6 (24/7 Deep Scan Active) | "
                f"{_format_process_stats()}"
            )

            # Send startup notification (uses the actual target list).
            await _send_startup_notification(bot.target_games)

            # Run the inner loop. It blocks until cancelled or until
            # it raises. Transient cycle errors are handled inside
            # the inner loop's own try/except. Anything that bubbles
            # up to here is treated by the classifier.
            await bot.start()
            successful_cycles += 1
            consecutive_transient = 0
            retry_delay = base_retry
            logger.info(
                f"[v12.6] Inner loop returned cleanly. Stats: "
                f"uptime={time.time() - started_at:.0f}s "
                f"successes={successful_cycles}"
            )

        except asyncio.CancelledError:
            logger.info("Engine cancelled by supervisor. Exiting cleanly.")
            _write_exit_state(0, KeyboardInterrupt(), context={"reason": "cancelled"})
            return
        except KeyboardInterrupt:
            logger.info("Engine interrupted. Exiting.")
            _write_exit_state(0, KeyboardInterrupt(), context={"reason": "interrupted"})
            return
        except ConfigError as e:
            # Config is a fatal error: no point in retrying. The user
            # must edit .env and restart manually.
            fatal_exit(e, context={
                "phase": "startup",
                "uptime_s": int(time.time() - started_at),
                "process": _format_process_stats(),
            })
        except AuthError as e:
            fatal_exit(e, context={
                "phase": "startup",
                "uptime_s": int(time.time() - started_at),
                "process": _format_process_stats(),
            })
        except Exception as e:
            classification = classify(e)
            if classification == "FATAL" or classification == "UNKNOWN":
                # Our code bug, db corruption, or unknown — STOP.
                # The watchdog will not restart (non-zero exit).
                fatal_exit(e, context={
                    "phase": "runtime",
                    "uptime_s": int(time.time() - started_at),
                    "consecutive_transient": consecutive_transient,
                    "successful_cycles": successful_cycles,
                    "process": _format_process_stats(),
                })
            else:
                # Transient: exponential backoff, then retry.
                consecutive_transient += 1
                report = ErrorReporter(e, context={
                    "phase": "runtime",
                    "consecutive_transient": consecutive_transient,
                    "next_retry_in_s": retry_delay,
                    "process": _format_process_stats(),
                })
                logger.warning(report.format_log())
                if consecutive_transient == 1:
                    # Send a Telegram ping on first transient — not a
                    # panic, just a heads-up. Subsequent transients
                    # are silent (Telegram could spam).
                    asyncio.create_task(report.send_telegram())
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, max_retry)


if __name__ == "__main__":
    try:
        asyncio.run(run_autonomous_scanner())
    except KeyboardInterrupt:
        print("\nShutdown complete.")
