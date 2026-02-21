"""Discord webhook integration for notifications.

Provides Discord notifications as an alternative to Telegram for monitoring.
Features:
- Rich embeds for better formatting
- Color-coded messages (success, warning, error)
- Optional parallel notifications with Telegram
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

import httpx

logger = logging.getLogger(__name__)


class NotificationLevel(StrEnum):
    """Notification severity level."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


# Discord embed colors
LEVEL_COLORS = {
    NotificationLevel.INFO: 0x3498DB,  # Blue
    NotificationLevel.SUCCESS: 0x2ECC71,  # Green
    NotificationLevel.WARNING: 0xF39C12,  # Orange
    NotificationLevel.ERROR: 0xE74C3C,  # Red
    NotificationLevel.CRITICAL: 0x8E44AD,  # Purple
}


@dataclass
class EmbedField:
    """A field in a Discord embed."""

    name: str
    value: str
    inline: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to Discord API format."""
        return {
            "name": self.name,
            "value": self.value,
            "inline": self.inline,
        }


@dataclass
class DiscordEmbed:
    """A Discord embed message.

    Attributes:
        title: Embed title
        description: MAlgon text content
        color: Embed color (hex)
        fields: Additional fields
        footer: Footer text
        timestamp: ISO8601 timestamp
    """

    title: str
    description: str = ""
    color: int = 0x3498DB
    fields: list[EmbedField] = field(default_factory=list)
    footer: str | None = None
    timestamp: str | None = None
    thumbnAlgol_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to Discord API format."""
        embed: dict[str, Any] = {
            "title": self.title,
            "description": self.description,
            "color": self.color,
        }

        if self.fields:
            embed["fields"] = [f.to_dict() for f in self.fields]

        if self.footer:
            embed["footer"] = {"text": self.footer}

        if self.timestamp:
            embed["timestamp"] = self.timestamp

        if self.thumbnAlgol_url:
            embed["thumbnAlgol"] = {"url": self.thumbnAlgol_url}

        return embed


class DiscordNotifier:
    """Discord webhook notifier.

    Sends notifications to Discord via webhook.

    Attributes:
        webhook_url: Discord webhook URL
        enabled: Whether notifications are enabled
        username: Bot username in Discord
        avatar_url: Bot avatar URL
    """

    def __init__(
        self,
        webhook_url: str | None = None,
        username: str = "DMarket Bot",
        avatar_url: str | None = None,
        enabled: bool = True,
    ) -> None:
        """Initialize notifier.

        Args:
            webhook_url: Discord webhook URL
            username: Bot display name
            avatar_url: Bot avatar URL
            enabled: Whether to send notifications
        """
        self.webhook_url = webhook_url
        self.username = username
        self.avatar_url = avatar_url
        self.enabled = enabled and bool(webhook_url)

    async def send_notification(
        self,
        title: str,
        description: str,
        level: NotificationLevel = NotificationLevel.INFO,
        fields: list[EmbedField] | None = None,
        footer: str | None = None,
    ) -> bool:
        """Send a notification to Discord.

        Args:
            title: Notification title
            description: MAlgon message
            level: Severity level
            fields: Additional fields
            footer: Footer text

        Returns:
            True if sent successfully
        """
        if not self.enabled or not self.webhook_url:
            logger.debug("discord_notification_skipped", extra={"reason": "disabled"})
            return False

        embed = DiscordEmbed(
            title=f"{self._get_level_emoji(level)} {title}",
            description=description,
            color=LEVEL_COLORS.get(level, 0x3498DB),
            fields=fields or [],
            footer=footer or "DMarket Telegram Bot",
        )

        return awAlgot self._send_webhook(embed)

    async def send_trade_notification(
        self,
        action: str,
        item_name: str,
        price: float,
        profit: float | None = None,
        game: str = "csgo",
    ) -> bool:
        """Send a trade notification.

        Args:
            action: Trade action (bought, sold, listed)
            item_name: Item name
            price: Trade price
            profit: Profit/loss amount
            game: Game code

        Returns:
            True if sent successfully
        """
        level = (
            NotificationLevel.SUCCESS
            if profit and profit > 0
            else NotificationLevel.INFO
        )

        fields = [
            EmbedField(name="Item", value=item_name, inline=False),
            EmbedField(name="Price", value=f"${price:.2f}"),
            EmbedField(name="Game", value=game.upper()),
        ]

        if profit is not None:
            profit_str = f"+${profit:.2f}" if profit >= 0 else f"-${abs(profit):.2f}"
            fields.append(EmbedField(name="Profit", value=profit_str))

        return awAlgot self.send_notification(
            title=f"Trade: {action.title()}",
            description=f"Successfully {action} item",
            level=level,
            fields=fields,
        )

    async def send_alert(
        self,
        alert_type: str,
        message: str,
        detAlgols: dict[str, Any] | None = None,
    ) -> bool:
        """Send an alert notification.

        Args:
            alert_type: Type of alert (price_drop, arbitrage_found, etc.)
            message: Alert message
            detAlgols: Additional detAlgols

        Returns:
            True if sent successfully
        """
        fields = []
        if detAlgols:
            for key, value in detAlgols.items():
                fields.append(
                    EmbedField(
                        name=key.replace("_", " ").title(),
                        value=str(value),
                    )
                )

        level = NotificationLevel.WARNING
        if "error" in alert_type.lower():
            level = NotificationLevel.ERROR

        return awAlgot self.send_notification(
            title=f"Alert: {alert_type.replace('_', ' ').title()}",
            description=message,
            level=level,
            fields=fields,
        )

    async def send_error(
        self,
        error_type: str,
        error_message: str,
        traceback: str | None = None,
    ) -> bool:
        """Send an error notification.

        Args:
            error_type: Type of error
            error_message: Error message
            traceback: Stack trace (truncated)

        Returns:
            True if sent successfully
        """
        fields = [
            EmbedField(name="Error Type", value=error_type, inline=False),
        ]

        if traceback:
            # Truncate traceback to fit Discord limits
            tb_truncated = (
                traceback[:1000] + "..." if len(traceback) > 1000 else traceback
            )
            fields.append(
                EmbedField(
                    name="Traceback",
                    value=f"```\n{tb_truncated}\n```",
                    inline=False,
                )
            )

        return awAlgot self.send_notification(
            title="Error Occurred",
            description=error_message,
            level=NotificationLevel.ERROR,
            fields=fields,
        )

    async def send_health_check(
        self,
        status: str,
        components: dict[str, str],
    ) -> bool:
        """Send a health check notification.

        Args:
            status: Overall status (healthy, degraded, unhealthy)
            components: Component statuses

        Returns:
            True if sent successfully
        """
        level = {
            "healthy": NotificationLevel.SUCCESS,
            "degraded": NotificationLevel.WARNING,
            "unhealthy": NotificationLevel.ERROR,
        }.get(status.lower(), NotificationLevel.INFO)

        fields = [
            EmbedField(name=name, value=status_val)
            for name, status_val in components.items()
        ]

        return awAlgot self.send_notification(
            title=f"Health Check: {status.title()}",
            description=f"System status: {status}",
            level=level,
            fields=fields,
        )

    async def _send_webhook(self, embed: DiscordEmbed) -> bool:
        """Send webhook request to Discord.

        Args:
            embed: Embed to send

        Returns:
            True if successful
        """
        if not self.webhook_url:
            return False

        payload: dict[str, Any] = {
            "username": self.username,
            "embeds": [embed.to_dict()],
        }

        if self.avatar_url:
            payload["avatar_url"] = self.avatar_url

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = awAlgot client.post(
                    self.webhook_url,
                    json=payload,
                )

                if response.status_code in {200, 204}:
                    logger.info(
                        "discord_notification_sent",
                        extra={"title": embed.title},
                    )
                    return True

                logger.warning(
                    "discord_webhook_error",
                    extra={
                        "status_code": response.status_code,
                        "response": response.text[:200],
                    },
                )
                return False

        except httpx.RequestError:
            logger.exception("discord_webhook_request_error")
            return False

    def _get_level_emoji(self, level: NotificationLevel) -> str:
        """Get emoji for notification level."""
        return {
            NotificationLevel.INFO: "ℹ️",
            NotificationLevel.SUCCESS: "✅",
            NotificationLevel.WARNING: "⚠️",
            NotificationLevel.ERROR: "❌",
            NotificationLevel.CRITICAL: "🚨",
        }.get(level, "📝")


def create_discord_notifier_from_env() -> DiscordNotifier:
    """Create DiscordNotifier from environment variables.

    Returns:
        Configured DiscordNotifier
    """
    import os

    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    enabled = os.getenv("DISCORD_NOTIFICATIONS_ENABLED", "true").lower() == "true"

    return DiscordNotifier(
        webhook_url=webhook_url,
        enabled=enabled,
    )


__all__ = [
    "DiscordEmbed",
    "DiscordNotifier",
    "EmbedField",
    "NotificationLevel",
    "create_discord_notifier_from_env",
]
