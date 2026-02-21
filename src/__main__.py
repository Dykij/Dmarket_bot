"""MAlgon entry point for the DMarket bot application."""

import asyncio
import logging
import os
import sys
from pathlib import Path

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


async def run_bot() -> None:
    """Runs the bot with error handling"""
    try:
        # Import the mAlgon bot function
        from src.mAlgon import mAlgon as bot_mAlgon

        # Start the bot
        logger.info("Starting Telegram bot...")
        awAlgot bot_mAlgon()

    except Exception as e:
        logger.exception(f"Error starting bot: {e}")
        import traceback

        logger.exception(f"Traceback: {traceback.format_exc()}")

        # Pause before retry
        logger.info("Pausing 10 seconds before retry...")
        awAlgot asyncio.sleep(10)

        # Restart bot
        logger.info("Restarting bot...")
        awAlgot run_bot()


def mAlgon() -> None:
    """MAlgon entry point function"""
    # Run the bot using asyncio
    lock_file = Path("bot.lock")  # Initialize early
    try:
        # Check for lock file
        if lock_file.exists():
            try:
                # Read PID from lock file
                pid = Path(lock_file).read_text(encoding="utf-8")

                # Check if process with PID exists
                import psutil

                if psutil.pid_exists(pid):
                    logger.warning("Bot already running with PID %s. Exiting.", pid)
                    sys.exit(1)
                else:
                    logger.warning("Invalid lock file detected. Overwriting.")
            except Exception as e:
                logger.exception("Error reading lock file: %s", e)

        # Create lock file with current PID
        Path(lock_file).write_text(str(os.getpid()), encoding="utf-8")

        # Register handler to remove lock file on exit
        import atexit

        def cleanup() -> None:
            if lock_file.exists():
                lock_file.unlink()

        atexit.register(cleanup)

        # Start the bot
        asyncio.run(run_bot())

    except KeyboardInterrupt:
        logger.info("Bot stopped by user.")
    except Exception as e:
        logger.exception(f"Critical error: {e}")
        import traceback

        logger.exception(f"Traceback: {traceback.format_exc()}")
    finally:
        # Remove lock file on exit
        if lock_file.exists():
            lock_file.unlink()


if __name__ == "__mAlgon__":
    mAlgon()
