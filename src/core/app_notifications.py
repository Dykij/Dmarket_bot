"""Application notifications module.

This module handles crash and critical shutdown notifications.
"""

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.core.application import Application

logger = logging.getLogger(__name__)


class NotificationManager:
    """Handles application crash and shutdown notifications."""

    def __init__(self, app: "Application") -> None:
        """Initialize notification manager.

        Args:
            app: Application instance

        """
        self.app = app

    async def handle_critical_shutdown(self, reason: str) -> None:
        """Handle critical shutdown event.

        Args:
            reason: Reason for critical shutdown

        """
        from src.telegram_bot.notifier import send_critical_shutdown_notification

        logger.critical(f"CRITICAL SHUTDOWN TRIGGERED: {reason}")

        if not self.app.bot or not self.app.config:
            return

        admin_users = self._get_admin_users()
        consecutive_errors = (
            self.app.state_manager.consecutive_errors if self.app.state_manager else 0
        )

        for user_id in admin_users:
            try:
                await send_critical_shutdown_notification(
                    bot=self.app.bot.bot,
                    user_id=int(user_id),
                    reason=reason,
                    details={"consecutive_errors": consecutive_errors},
                )
                logger.info(f"Critical shutdown notification sent to {user_id}")
            except Exception as e:
                logger.exception(
                    f"Failed to send shutdown notification to {user_id}: {e}"
                )

    async def send_crash_notifications(
        self,
        error: Exception,
        traceback_text: str,
    ) -> None:
        """Send crash notifications to all administrators.

        Args:
            error: Exception that caused the crash
            traceback_text: Full traceback string

        """
        from src.telegram_bot.notifier import send_crash_notification

        if not self.app.bot or not self.app.config:
            return

        admin_users = self._get_admin_users()

        for user_id in admin_users:
            try:
                await send_crash_notification(
                    bot=self.app.bot.bot,
                    user_id=int(user_id),
                    error_type=type(error).__name__,
                    error_message=str(error),
                    traceback_str=traceback_text,
                )
                logger.info(f"Crash notification sent to user {user_id}")
            except Exception as e:
                logger.exception(f"Failed to send crash notification to {user_id}: {e}")

    def _get_admin_users(self) -> list:
        """Get list of admin users from config."""
        admin_users = []
        if hasattr(self.app.config.security, "admin_users"):
            admin_users = self.app.config.security.admin_users

        if not admin_users and hasattr(self.app.config.security, "allowed_users"):
            admin_users = self.app.config.security.allowed_users[:1]

        return admin_users
