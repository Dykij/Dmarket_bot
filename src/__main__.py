"""Entry point for the DMarket bot application."""

import asyncio
import logging
import os
import sys

# v15.5: uvloop — 2-4x faster event loop (Linux/macOS)
try:
    import uvloop
    uvloop.install()
except ImportError:
    pass  # fallback to default asyncio event loop
from logging.handlers import RotatingFileHandler
from pathlib import Path

# Fix path: use project root relative to this file, not hardcoded D:\\ path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ----------------------------------------------------------------------------
# Single-source-of-truth logging configuration (v12.5)
# ----------------------------------------------------------------------------
# The previous version called logging.basicConfig() here AND
# autonomous_scanner.setup_logging() added another handler to root, so every
# log message was emitted twice (234 KB / 30 min of duplicated text).
#
# Now: __main__ owns the logging setup. autonomous_scanner.setup_logging() is
# a no-op (it was historically called for side effects from the scanner
# module; we keep the function so the symbol still exists for back-compat).
# ----------------------------------------------------------------------------
LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_TO_FILE = os.getenv("LOG_TO_FILE", "true").lower() == "true"
LOG_FILE = PROJECT_ROOT / "logs" / "bot_24_7.log"
LOG_FILE_MAX_BYTES = int(os.getenv("LOG_FILE_MAX_BYTES", str(10 * 1024 * 1024)))
LOG_FILE_BACKUP_COUNT = int(os.getenv("LOG_FILE_BACKUP_COUNT", "5"))


def _configure_logging() -> None:
    """Configure root logger with exactly one console + one rotating file handler.

    Idempotent — safe to call multiple times (replaces existing handlers).

    v12.5: installs a SecurityAuditor log filter on every handler so
    any log line that contains a leaked secret is REDACTED before it
    hits disk or stdout. Belt-and-suspenders defense — even if some
    other code path accidentally logs an API key, it won't make it
    to the log file or the Telegram notifier.
    """
    root = logging.getLogger()
    root.setLevel(LOG_LEVEL)

    # Remove any pre-existing handlers (avoid duplication on restart / reload).
    for h in list(root.handlers):
        root.removeHandler(h)

    formatter = logging.Formatter(LOG_FORMAT)

    # v12.5: Security filter — scrubs secrets from every log line.
    try:
        from src.risk.security_auditor import SecurityAuditor
        security_filter = SecurityAuditor.as_logging_filter()
    except Exception:
        security_filter = None

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    console.setLevel(LOG_LEVEL)
    if security_filter is not None:
        console.addFilter(security_filter)
    root.addHandler(console)

    if LOG_TO_FILE:
        try:
            LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            rotating = RotatingFileHandler(
                LOG_FILE,
                maxBytes=LOG_FILE_MAX_BYTES,
                backupCount=LOG_FILE_BACKUP_COUNT,
                encoding="utf-8",
            )
            rotating.setFormatter(formatter)
            rotating.setLevel(LOG_LEVEL)
            if security_filter is not None:
                rotating.addFilter(security_filter)
            root.addHandler(rotating)
        except Exception as e:
            # Don't crash the bot if disk is full or perms are bad; just
            # warn once and continue with console logging.
            print(f"WARNING: could not open log file {LOG_FILE}: {e}", file=sys.stderr)

    # Reduce noise from third-party libs (aiohttp access logs are spammy).
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)


_configure_logging()
logger = logging.getLogger(__name__)

# v15.6: Module-level shutdown flag for graceful shutdown
_shutdown_requested = False


async def _run_trading_loop() -> None:
    """Inner trading loop — imported lazily to avoid circular imports."""
    from src.core.autonomous_scanner import run_autonomous_scanner as bot_main
    try:
        await bot_main()
    except SystemExit:
        # v15.6: Catch SystemExit from fatal_exit() and re-raise
        # so run_bot() can handle it gracefully
        raise
    except asyncio.CancelledError:
        # v15.6: Catch CancelledError and re-raise
        raise


async def run_bot() -> None:
    """Runs the bot in a safe infinite loop (NO recursion).

    v15.6: Improved graceful shutdown — properly cancels all pending tasks
    on SIGTERM to avoid 'Task was destroyed but it is pending!' errors.
    """
    from src.config import Config

    retry_delay = 5
    max_retry_delay = 300  # Cap backoff at 5 minutes
    consecutive_crashes = 0

    # Honor the safe-default from .env; refuse to start in production mode
    # if the env is misconfigured.
    if not Config.DRY_RUN and os.getenv("ENVIRONMENT", "development") == "development":
        logger.warning(
            "DRY_RUN=false in a development environment. Forcing DRY_RUN=true. "
            "Set ENVIRONMENT=production to allow live trading."
        )
        os.environ["DRY_RUN"] = "true"
        Config.DRY_RUN = True

    # v12.7: Optional HTTP /healthz + /readyz + /metrics server. Starts
    # only when HEALTH_PORT is set in the env. Defaults OFF so we don't
    # expose the port to the network unless an operator wants it. The
    # watchdog can then curl /readyz instead of reading the heartbeat
    # file.
    from src.utils.health_server import (
        health_state,
        start_health_server,
        stop_health_server,
    )
    from src.utils.health_server import (
        is_enabled as health_server_enabled,
    )
    health_runner = None
    if health_server_enabled():
        health_runner = await start_health_server()
    health_state.set_shutting_down(False)

    # v14.5: Config hot-reload — watch .env for changes
    from src.utils.config_watcher import config_watcher as _cfg_watcher
    await _cfg_watcher.start()

    # v14.5: Live shadow mode (paper trading alongside real bot)
    from src.core.live_shadow import live_shadow as _shadow
    _shadow.start()

    # v15.6: Graceful shutdown helper — cancel all pending tasks
    async def _graceful_shutdown() -> None:
        """Cancel all pending asyncio tasks and wait for them to finish."""
        try:
            logger.info("Graceful shutdown: cancelling pending tasks...")
            # Get all tasks except the current one
            current_task = asyncio.current_task()
            tasks = [t for t in asyncio.all_tasks() if t is not current_task and not t.done()]
            if tasks:
                logger.info(f"Cancelling {len(tasks)} pending tasks...")
                for task in tasks:
                    task.cancel()
                # Wait for all tasks to finish with timeout
                try:
                    await asyncio.wait(tasks, timeout=10.0, return_when=asyncio.ALL_COMPLETED)
                except asyncio.TimeoutError:
                    logger.warning("Some tasks did not finish within 10s timeout")
                except Exception as e:
                    logger.debug(f"Error waiting for tasks: {e}")
            logger.info("Graceful shutdown complete.")
        except RuntimeError as e:
            # Event loop is already closed — can't cancel tasks
            logger.debug(f"Graceful shutdown skipped (event loop closing): {e}")
        except Exception as e:
            logger.debug(f"Graceful shutdown error: {e}")

    try:
        while True:
            # v15.6: Check shutdown flag
            if _shutdown_requested:
                logger.info("Shutdown requested. Exiting cleanly...")
                break

            try:
                logger.info("Starting DMarket trading bot...")
                await _run_trading_loop()
                # If bot_main returns normally (shouldn't happen), restart
                logger.warning(
                    "Bot main loop exited unexpectedly. Restarting in %ss...",
                    retry_delay,
                )
                consecutive_crashes = 0
                retry_delay = 5  # reset after successful run
            except KeyboardInterrupt:
                logger.info("Bot stopped by user (KeyboardInterrupt).")
                break
            except asyncio.CancelledError:
                logger.info("Bot task cancelled. Shutting down gracefully...")
                await _graceful_shutdown()
                break
            except SystemExit as e:
                logger.info(f"SystemExit({e.code}). Shutting down...")
                await _graceful_shutdown()
                raise  # Re-raise to exit the loop
            except Exception as e:
                consecutive_crashes += 1
                logger.exception(
                    "Bot crashed with error: %s. Restarting in %ss (crash #%d)...",
                    e,
                    retry_delay,
                    consecutive_crashes,
                )
                # Exponential backoff capped at 5 min; reset on first success
                retry_delay = min(retry_delay * 2, max_retry_delay)

            await asyncio.sleep(retry_delay)
            logger.info("Restarting bot...")
    finally:
        # v15.6: Graceful shutdown — cancel pending tasks
        await _graceful_shutdown()
        # Mark as shutting down BEFORE stopping the server so the
        # endpoint reports 503 during the brief drain window (lets
        # any monitoring dashboard know the bot is going down).
        health_state.set_shutting_down(True)
        if health_runner is not None:
            await stop_health_server(health_runner)
        await _cfg_watcher.stop()
        _shadow.stop()


def main() -> None:
    """Main entry point with lock file protection."""
    import atexit
    import hashlib
    import signal
    import time
    lock_file = PROJECT_ROOT / "bot.lock"
    our_pid = os.getpid()

    try:
        # Check for existing lock file (prevent double-start)
        if lock_file.exists():
            try:
                content = lock_file.read_text(encoding="utf-8").strip()
                lines = content.split("\n")
                pid_str = lines[0].strip()
                stored_hash = lines[2].strip() if len(lines) > 2 else ""

                # v12.9: Integrity check — verify the stored hash
                expected_hash = hashlib.sha256(
                    f"{pid_str}\n".encode()
                ).hexdigest()[:16]
                if stored_hash and stored_hash != expected_hash:
                    logger.warning(
                        "Lock file integrity check FAILED (tampered?). Overwriting."
                    )
                else:
                    import psutil
                    if pid_str.isdigit() and psutil.pid_exists(int(pid_str)):
                        other_pid = int(pid_str)
                        if other_pid == our_pid:
                            logger.warning("Lock file points to our own PID; reusing.")
                        else:
                            try:
                                p = psutil.Process(other_pid)
                                cmd = " ".join(p.cmdline()[:3]) if p.cmdline() else "?"
                                logger.error(
                                    "Bot already running with PID %s (%s). Exiting.",
                                    other_pid, cmd,
                                )
                            except (psutil.NoSuchProcess, psutil.AccessDenied):
                                logger.error(
                                    "Bot already running with PID %s. Exiting.",
                                    other_pid,
                                )
                            sys.exit(1)
            except Exception as e:
                logger.warning("Could not read lock file: %s. Proceeding.", e)

        # Create lock file with current PID + start time + integrity hash
        integrity_hash = hashlib.sha256(
            f"{our_pid}\n".encode()
        ).hexdigest()[:16]
        lock_file.write_text(
            f"{our_pid}\n{int(time.time())}\n{integrity_hash}\n",
            encoding="utf-8",
        )
        lock_file.chmod(0o600)

        def _cleanup() -> None:
            try:
                if lock_file.exists():
                    current = lock_file.read_text(encoding="utf-8").split("\n")[0].strip()
                    if current == str(our_pid):
                        lock_file.unlink()
            except OSError as e:
                logger.debug(f"Lock file cleanup failed: {e}")

        atexit.register(_cleanup)

        # Signal handlers for graceful shutdown
        # v15.6: Cancel the current task to trigger graceful shutdown
        def _signal_handler(signum, _frame):  # noqa: ARG001
            global _shutdown_requested
            logger.info("Received signal %s, shutting down gracefully...", signum)
            _shutdown_requested = True
            _cleanup()
            # Cancel the current task to break out of the event loop
            try:
                current = asyncio.current_task()
                if current and not current.done():
                    current.cancel()
            except RuntimeError:
                # No event loop running
                pass

        signal.signal(signal.SIGTERM, _signal_handler)
        signal.signal(signal.SIGINT, _signal_handler)

        # Start the bot (infinite restart loop, not recursion)
        asyncio.run(run_bot())

    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.exception("Critical startup error: %s", e)
    finally:
        try:
            if lock_file.exists():
                current = lock_file.read_text(encoding="utf-8").split("\n")[0].strip()
                if current == str(our_pid):
                    lock_file.unlink()
        except OSError as e:
            logger.debug(f"Final lock cleanup failed: {e}")


if __name__ == "__main__":
    main()
