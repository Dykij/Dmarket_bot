"""Custom Alerts Module.

Provides configurable alert system for market events and price changes.

Features:
- Price threshold alerts (above/below)
- Percentage change alerts
- Arbitrage opportunity alerts
- Inventory change alerts
- Custom condition alerts

Usage:
    ```python
    from src.telegram_bot.notifications.custom_alerts import AlertManager

    manager = AlertManager(user_id=123456)

    # Create price alert
    alert = await manager.create_price_alert(
        item_name="AK-47 | Redline",
        target_price=15.0,
        condition="below",
    )

    # Check alerts
    triggered = await manager.check_alerts(current_prices)
    ```

Created: January 10, 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import Any
from uuid import uuid4

import structlog

logger = structlog.get_logger(__name__)


class AlertType(StrEnum):
    """Alert types."""

    PRICE_THRESHOLD = "price_threshold"  # Price above/below target
    PRICE_CHANGE = "price_change"  # % change from reference
    ARBITRAGE = "arbitrage"  # Arbitrage opportunity
    INVENTORY = "inventory"  # Inventory changes
    LIQUIDITY = "liquidity"  # Liquidity changes
    CUSTOM = "custom"  # Custom conditions


class AlertCondition(StrEnum):
    """Alert conditions."""

    ABOVE = "above"
    BELOW = "below"
    EQUALS = "equals"
    CHANGE_PERCENT = "change_percent"
    AVAILABLE = "available"


class AlertPriority(StrEnum):
    """Alert priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertStatus(StrEnum):
    """Alert status."""

    ACTIVE = "active"
    TRIGGERED = "triggered"
    PAUSED = "paused"
    EXPIRED = "expired"
    DELETED = "deleted"


@dataclass
class AlertConfig:
    """Alert configuration."""

    # General
    max_alerts_per_user: int = 50
    default_expiry_days: int = 30

    # Rate limiting
    min_trigger_interval_seconds: int = 60  # Minimum time between same alert triggers
    max_triggers_per_hour: int = 20

    # Notification
    include_price_history: bool = True
    include_market_link: bool = True


@dataclass
class Alert:
    """Alert definition."""

    alert_id: str
    user_id: int
    alert_type: AlertType
    item_name: str
    condition: AlertCondition
    target_value: Decimal
    priority: AlertPriority = AlertPriority.MEDIUM
    status: AlertStatus = AlertStatus.ACTIVE
    message_template: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    last_triggered: datetime | None = None
    trigger_count: int = 0
    reference_price: Decimal | None = None  # For % change alerts
    marketplace: str | None = None
    game: str = "csgo"
    tags: list[str] = field(default_factory=list)

    def is_expired(self) -> bool:
        """Check if alert has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(UTC) > self.expires_at

    def can_trigger(self, min_interval_seconds: int = 60) -> bool:
        """Check if alert can be triggered."""
        if self.status != AlertStatus.ACTIVE:
            return False
        if self.is_expired():
            return False
        if self.last_triggered:
            elapsed = (datetime.now(UTC) - self.last_triggered).total_seconds()
            if elapsed < min_interval_seconds:
                return False
        return True

    def check_condition(self, current_value: Decimal) -> bool:
        """Check if condition is met.

        Args:
            current_value: Current price/value

        Returns:
            True if condition is met
        """
        if self.condition == AlertCondition.ABOVE:
            return current_value > self.target_value
        if self.condition == AlertCondition.BELOW:
            return current_value < self.target_value
        if self.condition == AlertCondition.EQUALS:
            return abs(current_value - self.target_value) < Decimal("0.01")
        if self.condition == AlertCondition.CHANGE_PERCENT:
            if self.reference_price and self.reference_price > 0:
                change_percent = abs((current_value - self.reference_price) / self.reference_price * 100)
                return change_percent >= self.target_value
        return False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert_id,
            "user_id": self.user_id,
            "type": self.alert_type.value,
            "item_name": self.item_name,
            "condition": self.condition.value,
            "target_value": str(self.target_value),
            "priority": self.priority.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "trigger_count": self.trigger_count,
            "game": self.game,
            "tags": self.tags,
        }


@dataclass
class TriggeredAlert:
    """A triggered alert notification."""

    alert: Alert
    triggered_at: datetime
    current_value: Decimal
    message: str
    marketplace: str | None = None
    item_url: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "alert_id": self.alert.alert_id,
            "item_name": self.alert.item_name,
            "condition": self.alert.condition.value,
            "target_value": str(self.alert.target_value),
            "current_value": str(self.current_value),
            "triggered_at": self.triggered_at.isoformat(),
            "message": self.message,
            "priority": self.alert.priority.value,
        }


class AlertManager:
    """Manages custom alerts for users."""

    def __init__(
        self,
        user_id: int | None = None,
        config: AlertConfig | None = None,
    ) -> None:
        """Initialize alert manager.

        Args:
            user_id: Default user ID
            config: Alert configuration
        """
        self.default_user_id = user_id
        self.config = config or AlertConfig()

        # Storage (replace with database in production)
        self._alerts: dict[str, Alert] = {}
        self._user_alerts: dict[int, set[str]] = {}  # user_id -> alert_ids
        self._triggers_history: list[TriggeredAlert] = []

        # Rate limiting
        self._user_triggers: dict[int, list[datetime]] = {}

    def create_alert(  # noqa: PLR0917
        self,
        item_name: str,
        alert_type: AlertType,
        condition: AlertCondition,
        target_value: float | Decimal,
        user_id: int | None = None,
        priority: AlertPriority = AlertPriority.MEDIUM,
        expires_in_days: int | None = None,
        message_template: str | None = None,
        reference_price: float | Decimal | None = None,
        marketplace: str | None = None,
        game: str = "csgo",
        tags: list[str] | None = None,
    ) -> Alert | None:
        """Create a new alert.

        Args:
            item_name: Item name
            alert_type: Alert type
            condition: Alert condition
            target_value: Target value (price or percentage)
            user_id: User ID
            priority: Alert priority
            expires_in_days: Days until expiry
            message_template: Custom message template
            reference_price: Reference price for % change
            marketplace: Target marketplace
            game: Game
            tags: Optional tags

        Returns:
            Created alert or None if limit reached
        """
        user_id = user_id or self.default_user_id
        if user_id is None:
            logger.error("alert_create_no_user_id")
            return None

        # Check limit
        user_alert_ids = self._user_alerts.get(user_id, set())
        if len(user_alert_ids) >= self.config.max_alerts_per_user:
            logger.warning("alert_limit_reached", user_id=user_id)
            return None

        # Create alert
        alert_id = f"alert_{uuid4().hex[:12]}"
        expires_in = expires_in_days or self.config.default_expiry_days
        expires_at = datetime.now(UTC) + timedelta(days=expires_in)

        alert = Alert(
            alert_id=alert_id,
            user_id=user_id,
            alert_type=alert_type,
            item_name=item_name,
            condition=condition,
            target_value=Decimal(str(target_value)),
            priority=priority,
            expires_at=expires_at,
            message_template=message_template,
            reference_price=Decimal(str(reference_price)) if reference_price else None,
            marketplace=marketplace,
            game=game,
            tags=tags or [],
        )

        # Store
        self._alerts[alert_id] = alert
        if user_id not in self._user_alerts:
            self._user_alerts[user_id] = set()
        self._user_alerts[user_id].add(alert_id)

        logger.info(
            "alert_created",
            alert_id=alert_id,
            user_id=user_id,
            item=item_name,
            condition=condition.value,
        )

        return alert

    def create_price_alert(
        self,
        item_name: str,
        target_price: float | Decimal,
        condition: str = "below",
        user_id: int | None = None,
        **kwargs: Any,
    ) -> Alert | None:
        """Create a price threshold alert.

        Args:
            item_name: Item name
            target_price: Target price
            condition: "above" or "below"
            user_id: User ID
            **kwargs: Additional alert parameters

        Returns:
            Created alert
        """
        cond = AlertCondition.ABOVE if condition == "above" else AlertCondition.BELOW

        return self.create_alert(
            item_name=item_name,
            alert_type=AlertType.PRICE_THRESHOLD,
            condition=cond,
            target_value=target_price,
            user_id=user_id,
            **kwargs,
        )

    def create_change_alert(
        self,
        item_name: str,
        change_percent: float,
        reference_price: float | Decimal,
        user_id: int | None = None,
        **kwargs: Any,
    ) -> Alert | None:
        """Create a percentage change alert.

        Args:
            item_name: Item name
            change_percent: % change to trigger
            reference_price: Reference price
            user_id: User ID
            **kwargs: Additional alert parameters

        Returns:
            Created alert
        """
        return self.create_alert(
            item_name=item_name,
            alert_type=AlertType.PRICE_CHANGE,
            condition=AlertCondition.CHANGE_PERCENT,
            target_value=change_percent,
            reference_price=reference_price,
            user_id=user_id,
            **kwargs,
        )

    def create_arbitrage_alert(
        self,
        item_name: str,
        min_profit_percent: float = 5.0,
        user_id: int | None = None,
        **kwargs: Any,
    ) -> Alert | None:
        """Create an arbitrage opportunity alert.

        Args:
            item_name: Item name
            min_profit_percent: Minimum profit %
            user_id: User ID
            **kwargs: Additional alert parameters

        Returns:
            Created alert
        """
        return self.create_alert(
            item_name=item_name,
            alert_type=AlertType.ARBITRAGE,
            condition=AlertCondition.ABOVE,
            target_value=min_profit_percent,
            user_id=user_id,
            priority=AlertPriority.HIGH,
            **kwargs,
        )

    def get_alert(self, alert_id: str) -> Alert | None:
        """Get alert by ID.

        Args:
            alert_id: Alert ID

        Returns:
            Alert or None
        """
        return self._alerts.get(alert_id)

    def get_user_alerts(
        self,
        user_id: int | None = None,
        status: AlertStatus | None = None,
        alert_type: AlertType | None = None,
    ) -> list[Alert]:
        """Get alerts for a user.

        Args:
            user_id: User ID
            status: Filter by status
            alert_type: Filter by type

        Returns:
            List of alerts
        """
        user_id = user_id or self.default_user_id
        if user_id is None:
            return []

        alert_ids = self._user_alerts.get(user_id, set())
        alerts = [self._alerts[aid] for aid in alert_ids if aid in self._alerts]

        if status:
            alerts = [a for a in alerts if a.status == status]

        if alert_type:
            alerts = [a for a in alerts if a.alert_type == alert_type]

        return sorted(alerts, key=lambda a: a.created_at, reverse=True)

    def update_alert(
        self,
        alert_id: str,
        target_value: float | Decimal | None = None,
        priority: AlertPriority | None = None,
        status: AlertStatus | None = None,
    ) -> bool:
        """Update an alert.

        Args:
            alert_id: Alert ID
            target_value: New target value
            priority: New priority
            status: New status

        Returns:
            Success status
        """
        alert = self._alerts.get(alert_id)
        if not alert:
            return False

        if target_value is not None:
            alert.target_value = Decimal(str(target_value))

        if priority is not None:
            alert.priority = priority

        if status is not None:
            alert.status = status

        logger.info("alert_updated", alert_id=alert_id)
        return True

    def delete_alert(self, alert_id: str) -> bool:
        """Delete an alert.

        Args:
            alert_id: Alert ID

        Returns:
            Success status
        """
        alert = self._alerts.get(alert_id)
        if not alert:
            return False

        alert.status = AlertStatus.DELETED

        # Remove from user's alerts
        if alert.user_id in self._user_alerts:
            self._user_alerts[alert.user_id].discard(alert_id)

        del self._alerts[alert_id]

        logger.info("alert_deleted", alert_id=alert_id)
        return True

    def pause_alert(self, alert_id: str) -> bool:
        """Pause an alert.

        Args:
            alert_id: Alert ID

        Returns:
            Success status
        """
        return self.update_alert(alert_id, status=AlertStatus.PAUSED)

    def resume_alert(self, alert_id: str) -> bool:
        """Resume a paused alert.

        Args:
            alert_id: Alert ID

        Returns:
            Success status
        """
        return self.update_alert(alert_id, status=AlertStatus.ACTIVE)

    async def check_alerts(
        self,
        prices: dict[str, Decimal],
        user_id: int | None = None,
    ) -> list[TriggeredAlert]:
        """Check alerts against current prices.

        Args:
            prices: Dict of item_name -> current_price
            user_id: Optional user ID filter

        Returns:
            List of triggered alerts
        """
        triggered = []

        # Get alerts to check
        if user_id:
            alerts = self.get_user_alerts(user_id, status=AlertStatus.ACTIVE)
        else:
            alerts = [a for a in self._alerts.values() if a.status == AlertStatus.ACTIVE]

        for alert in alerts:
            # Skip if expired
            if alert.is_expired():
                alert.status = AlertStatus.EXPIRED
                continue

            # Skip if can't trigger
            if not alert.can_trigger(self.config.min_trigger_interval_seconds):
                continue

            # Check rate limit for user
            if not self._check_user_rate_limit(alert.user_id):
                continue

            # Get current price
            current_price = prices.get(alert.item_name)
            if current_price is None:
                continue

            # Check condition
            if alert.check_condition(current_price):
                triggered_alert = self._trigger_alert(alert, current_price)
                triggered.append(triggered_alert)

        return triggered

    def _check_user_rate_limit(self, user_id: int) -> bool:
        """Check if user is within rate limit.

        Args:
            user_id: User ID

        Returns:
            True if within limit
        """
        now = datetime.now(UTC)
        hour_ago = now - timedelta(hours=1)

        if user_id not in self._user_triggers:
            self._user_triggers[user_id] = []

        # Clean old triggers
        self._user_triggers[user_id] = [
            t for t in self._user_triggers[user_id]
            if t > hour_ago
        ]

        return len(self._user_triggers[user_id]) < self.config.max_triggers_per_hour

    def _trigger_alert(self, alert: Alert, current_value: Decimal) -> TriggeredAlert:
        """Trigger an alert.

        Args:
            alert: Alert to trigger
            current_value: Current value that triggered

        Returns:
            Triggered alert
        """
        now = datetime.now(UTC)

        # Update alert
        alert.last_triggered = now
        alert.trigger_count += 1

        # Record for rate limiting
        if alert.user_id not in self._user_triggers:
            self._user_triggers[alert.user_id] = []
        self._user_triggers[alert.user_id].append(now)

        # Generate message
        message = self._generate_message(alert, current_value)

        triggered = TriggeredAlert(
            alert=alert,
            triggered_at=now,
            current_value=current_value,
            message=message,
            marketplace=alert.marketplace,
        )

        self._triggers_history.append(triggered)

        logger.info(
            "alert_triggered",
            alert_id=alert.alert_id,
            item=alert.item_name,
            current_value=str(current_value),
        )

        return triggered

    def _generate_message(self, alert: Alert, current_value: Decimal) -> str:
        """Generate notification message.

        Args:
            alert: Alert
            current_value: Current value

        Returns:
            Message string
        """
        if alert.message_template:
            return alert.message_template.format(
                item_name=alert.item_name,
                target=alert.target_value,
                current=current_value,
            )

        priority_emoji = {
            AlertPriority.LOW: "ℹ️",
            AlertPriority.MEDIUM: "⚠️",
            AlertPriority.HIGH: "🔔",
            AlertPriority.CRITICAL: "🚨",
        }

        emoji = priority_emoji.get(alert.priority, "📢")

        if alert.condition == AlertCondition.BELOW:
            return f"{emoji} {alert.item_name}: Цена упала до ${current_value} (цель: ${alert.target_value})"
        if alert.condition == AlertCondition.ABOVE:
            return f"{emoji} {alert.item_name}: Цена выросла до ${current_value} (цель: ${alert.target_value})"
        if alert.condition == AlertCondition.CHANGE_PERCENT:
            return f"{emoji} {alert.item_name}: Изменение цены {alert.target_value}% - сейчас ${current_value}"
        return f"{emoji} Алерт: {alert.item_name} - ${current_value}"

    def get_trigger_history(
        self,
        user_id: int | None = None,
        limit: int = 100,
    ) -> list[TriggeredAlert]:
        """Get trigger history.

        Args:
            user_id: Filter by user
            limit: Max results

        Returns:
            List of triggered alerts
        """
        history = self._triggers_history

        if user_id:
            history = [t for t in history if t.alert.user_id == user_id]

        return sorted(history, key=lambda t: t.triggered_at, reverse=True)[:limit]

    def get_stats(self, user_id: int | None = None) -> dict[str, Any]:
        """Get alert statistics.

        Args:
            user_id: Filter by user

        Returns:
            Statistics dict
        """
        if user_id:
            alerts = self.get_user_alerts(user_id)
        else:
            alerts = list(self._alerts.values())

        active = sum(1 for a in alerts if a.status == AlertStatus.ACTIVE)
        triggered = sum(a.trigger_count for a in alerts)

        return {
            "total_alerts": len(alerts),
            "active_alerts": active,
            "total_triggers": triggered,
            "by_type": {
                t.value: sum(1 for a in alerts if a.alert_type == t)
                for t in AlertType
            },
            "by_priority": {
                p.value: sum(1 for a in alerts if a.priority == p)
                for p in AlertPriority
            },
        }


# Singleton instance
_alert_manager: AlertManager | None = None


def get_alert_manager(user_id: int | None = None) -> AlertManager:
    """Get alert manager instance.

    Args:
        user_id: Default user ID

    Returns:
        AlertManager instance
    """
    global _alert_manager
    if _alert_manager is None:
        _alert_manager = AlertManager(user_id=user_id)
    return _alert_manager


def init_alert_manager(user_id: int | None = None) -> AlertManager:
    """Initialize alert manager.

    Args:
        user_id: Default user ID

    Returns:
        AlertManager instance
    """
    global _alert_manager
    _alert_manager = AlertManager(user_id=user_id)
    return _alert_manager
