"""
state.py — Configuration, access control, and bot state.

Contains:
- `_load_config()` — validate and load TELEGRAM_BOT_TOKEN + TELEGRAM_ADMIN_IDS from .env
- `_TOKEN`, `_ADMIN_IDS` — module-level config constants (set of ints)
- `is_admin(user_id)` — access control check
- `BotState` — thread-safe state container for the sniping loop + DMarket client
- `state` — singleton instance of BotState

Supports multiple admin IDs via TELEGRAM_ADMIN_IDS (comma-separated)
with TELEGRAM_ADMIN_ID as legacy fallback.

Imported as: from src.telegram.control_bot import state, is_admin, BotState, _TOKEN, _ADMIN_IDS
"""

import asyncio
import contextlib
import logging
import os

from src.api.dmarket_api_client import DMarketAPIClient
from src.config import Config

# Phase 1: Feature-flag selection (mirrors autonomous_scanner.py).
# v12.0 SnipingLoop = batched DMarket endpoints + selective oracle top-K.
# Legacy v10.0 = per-item oracle, exceeds Starter 50K/month quota.
if os.getenv("USE_V12_LOOP", "true").lower() == "true":
    from src.core.target_sniping.core import SnipingLoop
else:
    from src.core.target_sniping import SnipingLoop

logger = logging.getLogger("TelegramControl.state")


# ============================================================
# Configuration loading
# ============================================================
def _load_config() -> tuple[str | None, set[int]]:
    """Load token + admin ids; returns (token, admin_ids_set).

    Reads TELEGRAM_ADMIN_IDS (comma-separated) and TELEGRAM_CHAT_ID
    (legacy single ID). All valid IDs are merged into the admin set.

    Raises ValueError if token is missing or no valid admin ID found.
    """
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    admin_ids: set[int] = set()

    # Read comma-separated admin IDs (primary)
    admin_ids_str = os.getenv("TELEGRAM_ADMIN_IDS", "")
    for part in admin_ids_str.split(","):
        part = part.strip()
        if part:
            try:
                admin_ids.add(int(part))
            except (TypeError, ValueError):
                logger.warning(f"Ignoring non-numeric TELEGRAM_ADMIN_IDS entry: {part!r}")

    # Legacy single admin ID (fallback)
    legacy_id_str = os.getenv("TELEGRAM_ADMIN_ID", "")
    if legacy_id_str and legacy_id_str.strip():
        try:
            admin_ids.add(int(legacy_id_str.strip()))
        except (TypeError, ValueError):
            logger.warning(f"Ignoring non-numeric TELEGRAM_ADMIN_ID: {legacy_id_str!r}")

    if not token or token.strip() == "":
        raise ValueError("TELEGRAM_BOT_TOKEN not set in .env!")
    if not admin_ids:
        raise ValueError(
            "No valid admin IDs found. "
            "Set TELEGRAM_ADMIN_IDS (comma-separated) or TELEGRAM_ADMIN_ID in .env!"
        )
    return token.strip(), admin_ids


# Module-level: validate eagerly, expose constants. Never sys.exit() — just log.
try:
    _TOKEN, _ADMIN_IDS = _load_config()
    logger.info(f"Configuration loaded (admins={len(_ADMIN_IDS)})")
except Exception as e:
    logger.error(f"Configuration error: {e}", exc_info=True)
    logger.error(
        "Please create a .env file with TELEGRAM_BOT_TOKEN and "
        "TELEGRAM_ADMIN_IDS (comma-separated) or TELEGRAM_ADMIN_ID"
    )
    _TOKEN = ""
    _ADMIN_IDS = {0}


# ============================================================
# Access control
# ============================================================
def is_admin(user_id: int) -> bool:
    """Check if user is in the configured admin set.

    Supports multiple admin IDs via TELEGRAM_ADMIN_IDS (comma-separated)
    and legacy TELEGRAM_ADMIN_ID for backward compatibility.
    """
    return user_id in _ADMIN_IDS


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
        self.sniping_loop: SnipingLoop | None = None
        self.sniping_task: asyncio.Task | None = None
        self.is_running: bool = False
        self.client: DMarketAPIClient | None = None

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
            self.client = DMarketAPIClient(Config.PUBLIC_KEY, secret)  # type: ignore[arg-type]
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
                with contextlib.suppress(asyncio.CancelledError):
                    await self.sniping_task
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
