"""Application signals handling module.

This module handles OS signals for graceful shutdown.
"""

import asyncio
import logging
import signal
from collections.abc import Callable

logger = logging.getLogger(__name__)


class SignalHandler:
    """Handler for OS signals (SIGINT, SIGTERM, SIGQUIT)."""

    def __init__(self, shutdown_callback: Callable[[], None]) -> None:
        """Initialize signal handler.

        Args:
            shutdown_callback: Callback to invoke on shutdown signal

        """
        self._shutdown_callback = shutdown_callback
        self._shutdown_event = asyncio.Event()

    def setup(self) -> None:
        """Setup signal handlers for graceful shutdown."""

        def signal_handler(sig: int, frame: object) -> None:
            _ = frame  # Unused but required by signal.signal protocol
            logger.info(f"Received signal {sig}")
            self._shutdown_callback()
            self._shutdown_event.set()

        # Register signal handlers
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        # Windows doesn't have SIGQUIT
        if hasattr(signal, "SIGQUIT"):
            signal.signal(signal.SIGQUIT, signal_handler)

    @property
    def shutdown_event(self) -> asyncio.Event:
        """Get shutdown event."""
        return self._shutdown_event
