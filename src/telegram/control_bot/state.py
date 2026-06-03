"""
state.py — Configuration, access control, and bot state.

Contains:
- `_load_config()` — validate and load TELEGRAM_BOT_TOKEN + TELEGRAM_ADMIN_ID from .env
- `_TOKEN`, `_ADMIN_ID` — module-level config constants
- `is_admin(user_id)` — access control check
- `BotState` — thread-safe state container for the sniping loop + DMarket client
- `state` — singleton instance of BotState

Imported as: from src.telegram.control_bot import state, is_admin, BotState, _TOKEN, _ADMIN_ID
"""

import asyncio
import logging
import os
from typing import Optional

from src.api.dmarket_api_client import DMarketAPIClient
from src.config import Config
from src.core.target_sniping import SnipingLoop

logger = logging.getLogger("TelegramControl.state")


# ============================================================
# Configuration loading
# ============================================================
def _load_config() -> tuple[Optional[str], Optional[int]]:
    """Load token + admin id; returns (token, admin_id) or raises ValueError."""
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    admin_id_str = os.getenv("TELEGRAM_ADMIN_ID")

    if not token or token.strip() == "":
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env!")
    if not admin_id_str or admin_id_str.strip() == "":
        raise ValueError("TELEGRAM_ADMIN_ID not set in .env!")
    try:
        admin_id = int(admin_id_str)
    except (TypeError, ValueError):
        raise ValueError(f"TELEGRAM_ADMIN_ID must be numeric, got: {admin_id_str!r}")
    return token.strip(), admin_id


# Module-level: validate eagerly, expose constants. Never sys.exit() — just log.
try:
    _TOKEN, _ADMIN_ID = _load_config()
    logger.info(f"Configuration loaded (admin_id={_ADMIN_ID})")
except Exception as e:
    logger.error(f"Configuration error: {e}")
    logger.error(
        "Please create a .env file with TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_ID"
    )
    _TOKEN = ""
    _ADMIN_ID = 0


# ============================================================
# Access control
# ============================================================
def is_admin(user_id: int) -> bool:
    """Only the configured admin can control the bot."""
    return user_id == _ADMIN_ID


# ============================================================
# BotState — thread-safe state container
# ============================================================
class BotState:
    """Container for the sniping loop + flags with a single asyncio.Lock.

    Manages:
    - is_running: True when the sniping loop is active
    - sniping_loop: the SnipingLoop instance
    - sniping_task: the asyncio.Task running the loop
    - client: shared DMarketAPIClient (reused by PANIC to avoid duplicate calls)

    All mutations go through `lock` for thread safety.
    """

    def __init__(self) -> None:
        self.lock = asyncio.Lock()
        self.sniping_loop: Optional[SnipingLoop] = None
        self.sniping_task: Optional[asyncio.Task] = None
        self.is_running: bool = False
        self.client: Optional[DMarketAPIClient] = None

    async def start(self) -> bool:
        """Start the sniping loop. Returns True if started, False if already running."""
        async with self.lock:
            if self.is_running:
                return False
            from src.utils.vault import vault
            secret = (
                vault.get_dmarket_secret()
                if hasattr(vault, "get_dmarket_secret")
                else Config.SECRET_KEY
            )
            self.client = DMarketAPIClient(Config.PUBLIC_KEY, secret)
            self.sniping_loop = SnipingLoop(client=self.client)
            self.is_running = True
            self.sniping_task = asyncio.create_task(self.sniping_loop.start())
            return True

    async def stop(self) -> bool:
        """Stop the sniping loop. Returns True if stopped, False if not running."""
        async with self.lock:
            if not self.is_running:
                return False
            self.is_running = False
            if self.sniping_task:
                self.sniping_task.cancel()
                try:
                    await self.sniping_task
                except asyncio.CancelledError:
                    pass
                self.sniping_task = None
            if self.client:
                try:
                    await self.client.close()
                except Exception:
                    logger.exception("Error closing client")
                self.client = None
            self.sniping_loop = None
            return True

    async def status(self) -> dict:
        """Return a snapshot of current state."""
        async with self.lock:
            return {
                "is_running": self.is_running,
                "has_task": self.sniping_task is not None,
                "has_client": self.client is not None,
            }


# Module-level singleton (used by handlers and lifecycle)
state = BotState()
