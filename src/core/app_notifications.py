"""
app_notifications.py — Notification management.
"""

from typing import Any


class NotificationManager:
    """Manages notification delivery."""

    def __init__(self, app: Any = None, bot: Any = None, config: Any = None) -> None:
        self.app = app
        self.bot = bot or (getattr(app, "bot", None) if app else None)
        self.config = config or (getattr(app, "config", None) if app else None)

    def get_admin_users(self) -> list[int]:
        """Get list of admin user IDs."""
        return self._get_admin_users()

    def _get_admin_users(self) -> list[int]:
        """Get admin users from config.security."""
        cfg = self.config
        if cfg:
            security = getattr(cfg, "security", None)
            if security:
                admins = getattr(security, "admin_users", None)
                if admins:
                    return list(admins)
                allowed = getattr(security, "allowed_users", None)
                if allowed:
                    return [allowed[0]]
            admins = getattr(cfg, "admin_users", None)
            if admins:
                return list(admins)
        return []

    async def handle_critical_shutdown(self, reason: str = "") -> None:
        """Send critical shutdown notification."""
        try:
            from src.telegram.notifier import notifier
            msg = f"🔴 <b>CRITICAL SHUTDOWN</b>\n{reason}" if reason else "🔴 <b>CRITICAL SHUTDOWN</b>\nNo reason specified"
            await notifier.custom(msg, severity="critical")
        except Exception as e:
            import logging
            logging.getLogger("NotificationManager").error(f"Failed to send critical shutdown notification: {e}")
