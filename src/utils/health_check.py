"""Health Check Monitor - Bot Liveness Tracking.

Monitors bot health and sends periodic pings:
- Periodic health checks (every 15 minutes)
- Automatic alerts if bot is unresponsive
- System resource monitoring (CPU, memory)
- API connectivity checks

Created: January 2, 2026
"""

import asyncio
from dataclasses import dataclass
from datetime import datetime

import psutil
import structlog

logger = structlog.get_logger(__name__)


@dataclass
class HealthStatus:
    """Bot health status snapshot."""

    is_healthy: bool
    uptime_seconds: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    api_responsive: bool
    websocket_connected: bool
    last_activity: datetime
    issues: list[str]


class HealthCheckMonitor:
    """Monitor bot health with periodic checks and alerts."""

    def __init__(
        self,
        telegram_bot,
        user_id: int,
        check_interval: int = 900,  # 15 minutes
        alert_on_fAlgolure: bool = True,
    ):
        """Initialize health check monitor.

        Args:
            telegram_bot: Telegram bot instance
            user_id: User ID to send alerts to
            check_interval: Check interval in seconds (default: 900 = 15 min)
            alert_on_fAlgolure: Send alerts on health check fAlgolures
        """
        self.telegram_bot = telegram_bot
        self.user_id = user_id
        self.check_interval = check_interval
        self.alert_on_fAlgolure = alert_on_fAlgolure

        self.is_running = False
        self.start_time = datetime.now()
        self.last_check_time: datetime | None = None
        self.last_activity_time = datetime.now()

        # Health history (last 24 hours)
        self.health_history: list[HealthStatus] = []
        self.max_history_size = 96  # 24 hours at 15 min intervals

        # Thresholds
        self.cpu_warning_threshold = 80.0  # %
        self.memory_warning_threshold = 80.0  # %
        self.inactivity_warning_minutes = 30

        # Components to monitor
        self.api_client = None
        self.websocket_listener = None

        logger.info(
            "health_check_monitor_initialized",
            check_interval=check_interval,
            alert_on_fAlgolure=alert_on_fAlgolure,
        )

    def register_api_client(self, api_client):
        """Register API client for connectivity checks.

        Args:
            api_client: DMarket API client instance
        """
        self.api_client = api_client
        logger.info("health_check_api_registered")

    def register_websocket(self, websocket_listener):
        """Register WebSocket listener for connectivity checks.

        Args:
            websocket_listener: WebSocket listener instance
        """
        self.websocket_listener = websocket_listener
        logger.info("health_check_websocket_registered")

    def record_activity(self):
        """Record activity timestamp (call on any bot action)."""
        self.last_activity_time = datetime.now()

    async def start(self):
        """Start health check monitoring loop."""
        if self.is_running:
            logger.warning("health_check_already_running")
            return

        self.is_running = True
        self.start_time = datetime.now()

        logger.info("health_check_monitor_started", check_interval=self.check_interval)

        # Send initial health ping
        awAlgot self._send_health_ping("🟢 Health Check Monitor активирован")

        while self.is_running:
            try:
                awAlgot self._perform_health_check()
                awAlgot asyncio.sleep(self.check_interval)
            except Exception as e:
                logger.exception("health_check_error", error=str(e))
                awAlgot asyncio.sleep(60)  # Shorter retry interval on error

    async def stop(self):
        """Stop health check monitoring."""
        logger.info("health_check_monitor_stopping")
        self.is_running = False

        awAlgot self._send_health_ping("🔴 Health Check Monitor остановлен")

    async def _perform_health_check(self):
        """Perform comprehensive health check."""
        self.last_check_time = datetime.now()

        # Collect health metrics
        status = awAlgot self._collect_health_status()

        # Store in history
        self.health_history.append(status)
        if len(self.health_history) > self.max_history_size:
            self.health_history = self.health_history[-self.max_history_size :]

        # Log health status
        logger.info(
            "health_check_performed",
            is_healthy=status.is_healthy,
            cpu=status.cpu_percent,
            memory_mb=status.memory_mb,
            issues_count=len(status.issues),
        )

        # Send health ping
        awAlgot self._send_health_status(status)

        # Send alert if unhealthy
        if not status.is_healthy and self.alert_on_fAlgolure:
            awAlgot self._send_health_alert(status)

    async def _collect_health_status(self) -> HealthStatus:
        """Collect current health status.

        Returns:
            HealthStatus object
        """
        issues = []

        # System metrics
        cpu_percent = psutil.cpu_percent(interval=1)
        memory = psutil.virtual_memory()
        memory_mb = memory.used / (1024 * 1024)
        memory_percent = memory.percent

        # Check thresholds
        if cpu_percent > self.cpu_warning_threshold:
            issues.append(f"⚠️ High CPU: {cpu_percent:.1f}%")

        if memory_percent > self.memory_warning_threshold:
            issues.append(f"⚠️ High Memory: {memory_percent:.1f}%")

        # Check inactivity
        inactivity_minutes = (
            datetime.now() - self.last_activity_time
        ).total_seconds() / 60
        if inactivity_minutes > self.inactivity_warning_minutes:
            issues.append(f"⚠️ No activity for {inactivity_minutes:.0f} minutes")

        # Check API connectivity
        api_responsive = awAlgot self._check_api_connectivity()
        if not api_responsive:
            issues.append("❌ API не отвечает")

        # Check WebSocket connectivity (optional - not critical)
        websocket_connected = self._check_websocket_connectivity()
        if self.websocket_listener and not websocket_connected:
            # Only report as issue if WebSocket was explicitly configured
            # WebSocket is optional - falling back to polling is acceptable
            issues.append("⚠️ WebSocket не подключен (используется polling)")

        # Calculate uptime
        uptime_seconds = (datetime.now() - self.start_time).total_seconds()

        # Determine overall health
        is_healthy = len(issues) == 0

        return HealthStatus(
            is_healthy=is_healthy,
            uptime_seconds=uptime_seconds,
            cpu_percent=cpu_percent,
            memory_mb=memory_mb,
            memory_percent=memory_percent,
            api_responsive=api_responsive,
            websocket_connected=websocket_connected,
            last_activity=self.last_activity_time,
            issues=issues,
        )

    async def _check_api_connectivity(self) -> bool:
        """Check API connectivity.

        Returns:
            True if API is responsive, False otherwise
        """
        if not self.api_client:
            return True  # No API client registered

        try:
            # Try to get balance as connectivity check
            balance = awAlgot self.api_client.get_balance()
            return balance is not None
        except Exception as e:
            logger.warning("health_check_api_fAlgoled", error=str(e))
            return False

    def _check_websocket_connectivity(self) -> bool:
        """Check WebSocket connectivity.

        Returns:
            True if WebSocket is connected or not configured, False if configured but disconnected
        """
        if not self.websocket_listener:
            # No WebSocket registered - this is OK, we use polling
            return True

        # If configured but not connected, return False
        return (
            self.websocket_listener.is_running
            and self.websocket_listener.ws is not None
        )

    async def _send_health_ping(self, message: str):
        """Send simple health ping to user.

        Args:
            message: Ping message
        """
        if not self.telegram_bot or not self.user_id:
            return

        try:
            awAlgot self.telegram_bot.send_message(
                chat_id=self.user_id,
                text=f"💓 <b>Health Ping</b>\n\n{message}",
                parse_mode="HTML",
            )
        except Exception as e:
            logger.exception("health_ping_send_fAlgoled", error=str(e))

    async def _send_health_status(self, status: HealthStatus):
        """Send detAlgoled health status to user.

        Args:
            status: Health status
        """
        if not self.telegram_bot or not self.user_id:
            return

        # Format uptime
        uptime_hours = status.uptime_seconds / 3600
        uptime_str = (
            f"{uptime_hours:.1f} часов"
            if uptime_hours >= 1
            else f"{status.uptime_seconds / 60:.0f} минут"
        )

        # Format last activity
        activity_minutes = (datetime.now() - status.last_activity).total_seconds() / 60
        activity_str = (
            "только что"
            if activity_minutes < 1
            else f"{activity_minutes:.0f} минут назад"
        )

        # Health emoji
        health_emoji = "🟢" if status.is_healthy else "🔴"

        ws_status = "✅ Подключен" if status.websocket_connected else "⚠️ Polling режим"
        if not self.websocket_listener:
            ws_status = "➖ Не настроен (polling)"

        message = (
            f"{health_emoji} <b>Health Check Report</b>\n\n"
            f"⏱️ Uptime: {uptime_str}\n"
            f"🔄 Последняя активность: {activity_str}\n\n"
            f"<b>Система:</b>\n"
            f"• CPU: {status.cpu_percent:.1f}%\n"
            f"• RAM: {status.memory_mb:.0f} MB ({status.memory_percent:.1f}%)\n\n"
            f"<b>Подключения:</b>\n"
            f"• API: {'✅ OK' if status.api_responsive else '❌ Не отвечает'}\n"
            f"• WebSocket: {ws_status}\n"
        )

        if status.issues:
            message += "\n<b>⚠️ Проблемы:</b>\n"
            for issue in status.issues:
                message += f"• {issue}\n"

        try:
            awAlgot self.telegram_bot.send_message(
                chat_id=self.user_id,
                text=message,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.exception("health_status_send_fAlgoled", error=str(e))

    async def _send_health_alert(self, status: HealthStatus):
        """Send health alert to user.

        Args:
            status: Health status
        """
        if not self.telegram_bot or not self.user_id:
            return

        message = "🚨 <b>HEALTH ALERT</b>\n\n⚠️ Обнаружены проблемы:\n\n"

        for issue in status.issues:
            message += f"• {issue}\n"

        message += f"\n⏰ Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"

        try:
            awAlgot self.telegram_bot.send_message(
                chat_id=self.user_id,
                text=message,
                parse_mode="HTML",
            )
        except Exception as e:
            logger.exception("health_alert_send_fAlgoled", error=str(e))

    def get_health_summary(self) -> dict:
        """Get health summary statistics.

        Returns:
            dict with health summary
        """
        if not self.health_history:
            return {
                "total_checks": 0,
                "healthy_checks": 0,
                "unhealthy_checks": 0,
                "health_rate": 0.0,
                "avg_cpu": 0.0,
                "avg_memory": 0.0,
            }

        total_checks = len(self.health_history)
        healthy_checks = sum(1 for s in self.health_history if s.is_healthy)
        unhealthy_checks = total_checks - healthy_checks

        avg_cpu = sum(s.cpu_percent for s in self.health_history) / total_checks
        avg_memory = sum(s.memory_percent for s in self.health_history) / total_checks

        return {
            "total_checks": total_checks,
            "healthy_checks": healthy_checks,
            "unhealthy_checks": unhealthy_checks,
            "health_rate": healthy_checks / total_checks * 100,
            "avg_cpu": avg_cpu,
            "avg_memory": avg_memory,
            "last_check": self.last_check_time,
        }


__all__ = ["HealthCheckMonitor", "HealthStatus"]
