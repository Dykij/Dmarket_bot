"""
app_lifecycle.py — Application lifecycle management.
"""

from typing import Any


class ApplicationLifecycle:
    """Manages application startup and shutdown."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def start_services(self) -> None:
        """Start configured services."""
        pass

    async def shutdown(self, timeout: float = 5.0) -> None:
        """Graceful shutdown."""
        await self._stop_scanner()

    async def _stop_scanner(self) -> None:
        """Stop scanner manager."""
        scanner = getattr(self.app, "scanner_manager", None)
        if scanner and hasattr(scanner, "stop"):
            await scanner.stop()
