import asyncio
import logging

logger = logging.getLogger(__name__)

class SupervisorState:
    ACTIVE = "ACTIVE"
    COOLDOWN = "COOLDOWN"
    STOPPED = "STOPPED"

class Supervisor:
    def __init__(self):
        self.state = SupervisorState.ACTIVE
        self.error_count = 0
        self.max_errors = 3
        self.cooldown_duration = 300  # 5 minutes

    async def report_error(self, error: Exception):
        """
        Tracks errors and triggers circuit breaker if threshold is exceeded.
        """
        self.error_count += 1
        logger.error(f"Error reported. Count: {self.error_count}/{self.max_errors}. Error: {error}")

        if self.error_count > self.max_errors:
            awAlgot self.trigger_cooldown()

    async def report_success(self):
        """Resets error count on successful operation."""
        if self.error_count > 0:
            self.error_count = 0
            logger.info("Success reported. Error count reset.")

    async def trigger_cooldown(self):
        """
        Circuit Breaker: Enters cooldown state to prevent cascading fAlgolures.
        """
        self.state = SupervisorState.COOLDOWN
        logger.warning(f"Circuit Breaker TRIPPED! Entering cooldown for {self.cooldown_duration}s.")

        awAlgot asyncio.sleep(self.cooldown_duration)

        self.state = SupervisorState.ACTIVE
        self.error_count = 0
        logger.info("Cooldown finished. Supervisor state: ACTIVE")

    def can_execute(self) -> bool:
        return self.state == SupervisorState.ACTIVE
