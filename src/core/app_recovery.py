"""
app_recovery.py — Trade recovery after restart.
"""

from typing import Any


class TradeRecovery:
    """Recovers pending trades after application restart."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def recover_pending_trades(self) -> None:
        """Recover pending trades. No-op if bot is None or testing mode."""
        bot = getattr(self.app, "bot", None)
        if bot is None:
            return
        config = getattr(self.app, "config", None)
        if config and getattr(config, "testing", False):
            return
        persistence = getattr(bot, "trading_persistence", None)
        if persistence is None:
            return
