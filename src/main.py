"""Main entry point for DMarket Telegram Bot.

This module provides the main entry point for running the DMarket Telegram Bot.
The implementation is delegated to src.core.application for modularity.

For the full Application class implementation, see:
    - src/core/application.py - Main Application orchestrator
    - src/core/app_initialization.py - Component initialization
    - src/core/app_lifecycle.py - Lifecycle management
    - src/core/app_notifications.py - Notification handling
    - src/core/app_recovery.py - Trade recovery
    - src/core/app_signals.py - Signal handling
"""

import asyncio
import sys

# Re-export Application and main from core module for backward compatibility
from src.core.application import Application, main

__all__ = ["Application", "main"]


if __name__ == "__main__":
    # Ensure proper event loop policy on Windows
    if sys.platform.startswith("win"):
        import io
        # Force UTF-8 encoding for stdout/stderr to avoid charmap errors in PowerShell
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Run the application
    asyncio.run(main())
