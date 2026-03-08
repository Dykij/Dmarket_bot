"""Entry point for the DMarket bot application."""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Fix path: use project root relative to this file, not hardcoded D:\\ path
PROJECT_ROOT = Path(__file__).parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def _run_trading_loop() -> None:
    """Inner trading loop — importted lazily to avoid circular imports."""
    from src.bot.main import main as bot_main
    await bot_main()


async def run_bot() -> None:
    """Runs the bot in a safe infinite loop (NO recursion)."""
    retry_delay = 10  # seconds

    while True:
        try:
            logger.info("Starting DMarket trading bot...")
            await _run_trading_loop()
            # If bot_main returns normally (shouldn't happen), restart
            logger.warning("Bot main loop exited unexpectedly. Restarting in %ss...", retry_delay)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user (KeyboardInterrupt).")
            break
        except asyncio.CancelledError:
            logger.info("Bot task cancelled. Shutting down...")
            break
        except Exception as e:
            logger.exception("Bot crashed with error: %s. Restarting in %ss...", e, retry_delay)

        await asyncio.sleep(retry_delay)
        logger.info("Restarting bot...")


def main() -> None:
    """Main entry point with lock file protection."""
    lock_file = Path("bot.lock")

    try:
        # Check for existing lock file (prevent double-start)
        if lock_file.exists():
            try:
                pid_str = lock_file.read_text(encoding="utf-8").strip()
                import psutil
                # pid_exists requires int, not str!
                if pid_str.isdigit() and psutil.pid_exists(int(pid_str)):
                    logger.warning("Bot already running with PID %s. Exiting.", pid_str)
                    sys.exit(1)
                else:
                    logger.warning("Stale lock file found (PID %s not running). Overwriting.", pid_str)
            except Exception as e:
                logger.warning("Could not read lock file: %s. Proceeding.", e)

        # Create lock file with current PID
        lock_file.write_text(str(os.getpid()), encoding="utf-8")

        # Cleanup lock on exit
        import atexit
        def _cleanup() -> None:
            if lock_file.exists():
                lock_file.unlink()
        atexit.register(_cleanup)

        # Start the bot (infinite restart loop, not recursion)
        asyncio.run(run_bot())

    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.exception("Critical startup error: %s", e)
    finally:
        if lock_file.exists():
            lock_file.unlink()


if __name__ == "__main__":
    main()
