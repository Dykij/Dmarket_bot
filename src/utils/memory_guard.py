"""Memory Guard - Автоматическая защита от переполнения памяти."""

import os
import sys

import psutil
from telegram.ext import Application, ContextTypes

from src.utils.canonical_logging import get_logger

logger = get_logger(__name__)


class MemoryGuard:
    """Monitor system resources and perform safety reboot if limits exceeded."""

    def __init__(self, memory_limit_mb: int = 512, check_interval_sec: int = 60):
        self.limit_mb = memory_limit_mb
        self.interval = check_interval_sec
        self.running = False
        self._task = None

    async def _check_memory(self, context: ContextTypes.DEFAULT_TYPE = None):
        """Internal check function."""
        try:
            process = psutil.Process(os.getpid())
            mem_info = process.memory_info()
            current_mb = mem_info.rss / 1024 / 1024

            logger.debug(f"Memory check: {current_mb:.1f}MB / {self.limit_mb}MB")

            if current_mb > self.limit_mb:
                logger.critical(
                    f"MEMORY OVERFLOW: {current_mb:.1f}MB > {self.limit_mb}MB. REBOOTING..."
                )

                # Notify users via Telegram if context is available
                if context and context.bot:
                    try:
                        # You might want to broadcast to admins here if you have their IDs
                        pass
                    except Exception as e:
                        logger.error(f"Failed to notify before reboot: {e}")

                # Save state (if implemented)
                # await self.save_state()

                # RESTART
                logger.warning("Initiating emergency restart...")
                # sys.executable is the python interpreter
                # sys.argv are the arguments passed to the script
                # execv replaces the current process immediately
                os.execv(sys.executable, [sys.executable] + sys.argv)

        except Exception as e:
            logger.error(f"MemoryGuard check failed: {e}")

    def start(self, application: Application):
        """Start the monitoring loop using job queue."""
        if self.running:
            return

        logger.info(
            f"Starting MemoryGuard. Limit: {self.limit_mb}MB. Interval: {self.interval}s"
        )

        # Use job queue for periodic checks
        if application.job_queue:
            application.job_queue.run_repeating(
                self._check_memory,
                interval=self.interval,
                first=10,  # First check after 10s
                name="memory_guard_check",
            )
            self.running = True
        else:
            logger.error("JobQueue not available for MemoryGuard!")


# Global instance
memory_guard = MemoryGuard(memory_limit_mb=768)  # 768MB limit
