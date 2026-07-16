"""
app_signals.py — Signal handling for graceful shutdown.
"""

import asyncio
import signal
from collections.abc import Callable


class SignalHandler:
    """Handles OS signals for graceful shutdown."""

    def __init__(self, shutdown_callback: Callable) -> None:
        self._shutdown_callback = shutdown_callback
        self._shutdown_event = asyncio.Event()

    @property
    def shutdown_event(self) -> asyncio.Event:
        """Returns the shutdown event."""
        return self._shutdown_event

    def setup(self) -> None:
        """Register signal handlers for SIGINT and SIGTERM."""
        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

    def _handle_signal(self, signum: int, _frame: object) -> None:
        """Handle received signal."""
        self._shutdown_event.set()
        if self._shutdown_callback:
            self._shutdown_callback()
