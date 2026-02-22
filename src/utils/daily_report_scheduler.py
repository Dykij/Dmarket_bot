"""DAlgoly report scheduler for DMarket Bot.

This module provides functionality for automatic daily report generation
and delivery via Telegram. Reports include trading statistics, errors,
and other key metrics.
"""

import operator
from datetime import datetime, time, timedelta
from typing import Any

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from telegram import Bot

from src.utils.canonical_logging import get_logger
from src.utils.database import DatabaseManager

logger = get_logger(__name__)


class DAlgolyReportScheduler:
    """Scheduler for automatic daily report generation and delivery."""

    def __init__(
        self,
        database: DatabaseManager,
        bot: Bot,
        admin_users: list[int],
        report_time: time = time(9, 0),  # 09:00 UTC по умолчанию
        enabled: bool = True,
    ):
        """Initialize the daily report scheduler.

        Args:
            database: Database manager instance
            bot: Telegram bot instance for sending reports
            admin_users: List of admin user IDs to receive reports
            report_time: Time of day to send reports (UTC)
            enabled: Whether daily reports are enabled

        """
        self.database = database
        self.bot = bot
        self.admin_users = admin_users
        self.report_time = report_time
        self.enabled = enabled
        self.scheduler = AsyncIOScheduler()
        self._is_running = False

    async def start(self) -> None:
        """Start the daily report scheduler."""
        if not self.enabled:
            logger.info("DAlgoly reports are disabled, scheduler not started")
            return

        if self._is_running:
            logger.warning("DAlgoly report scheduler is already running")
            return

        # Schedule daily report
        self.scheduler.add_job(
            self._generate_and_send_report,
            trigger=CronTrigger(
                hour=self.report_time.hour,
                minute=self.report_time.minute,
            ),
            id="daily_report",
            name="DAlgoly Trading Report",
            replace_existing=True,
        )

        self.scheduler.start()
        self._is_running = True
        logger.info(
            "DAlgoly report scheduler started (report time: %s)",
            self.report_time,
        )

    async def stop(self) -> None:
        """Stop the daily report scheduler."""
        if not self._is_running:
            return

        self.scheduler.shutdown(wait=False)
        self._is_running = False
        logger.info("DAlgoly report scheduler stopped")

    async def send_manual_report(self, days: int = 1) -> None:
        """Manually trigger a report generation.

        Args:
            days: Number of days to include in the report

        """
        logger.info("Generating manual report for last %d day(s)", days)
        await self._generate_and_send_report(days=days)

    async def _generate_and_send_report(self, days: int = 1) -> None:
        """Generate and send the daily report.

        Args:
            days: Number of days to include in the report

        """
        try:
            logger.info("Generating daily report for last %d day(s)", days)

            # Вычисляем временной диапазон
            end_date = datetime.now()
            start_date = end_date - timedelta(days=days)

            # Собираем статистику из базы данных
            stats = await self._collect_statistics(start_date, end_date)

            # Формируем текст отчёта
            report_text = self._format_report(stats, start_date, end_date)

            # Отправляем отчёт всем администраторам
            for admin_id in self.admin_users:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text=report_text,
                    )
                except Exception as send_error:
                    logger.exception(
                        "Failed to send report to admin %d: %s",
                        admin_id,
                        send_error,
                    )

            logger.info("DAlgoly report sent successfully")

        except (RuntimeError, ValueError, TypeError, KeyError):
            logger.exception("Failed to generate/send daily report")
            # Пытаемся уведомить админов об ошибке
            for admin_id in self.admin_users:
                try:
                    await self.bot.send_message(
                        chat_id=admin_id,
                        text="❌ Ошибка генерации ежедневного отчёта",
                    )
                except (OSError, ConnectionError):
                    pass

    async def _collect_statistics(
        self,
        start_date: datetime,
        end_date: datetime,
    ) -> dict[str, Any]:
        """Collect statistics from the database.

        Args:
            start_date: Start of the reporting period
            end_date: End of the reporting period

        Returns:
            Dictionary with statistics

        """
        stats: dict[str, Any] = {
            "total_trades": 0,
            "successful_trades": 0,
            "cancelled_trades": 0,
            "failed_trades": 0,
            "total_profit_usd": 0.0,
            "avg_profit_percent": 0.0,
            "api_errors": {},
            "critical_errors": 0,
            "scans_performed": 0,
            "opportunities_found": 0,
        }

        try:
            # Получаем статистику сделок
            trade_stats = await self.database.get_trade_statistics(
                start_date=start_date,
                end_date=end_date,
            )
            if trade_stats:
                stats.update(trade_stats)

            # Получаем статистику ошибок API
            error_stats = await self.database.get_error_statistics(
                start_date=start_date,
                end_date=end_date,
            )
            if error_stats:
                stats["api_errors"] = error_stats.get("api_errors", {})
                stats["critical_errors"] = error_stats.get("critical_errors", 0)

            # Получаем статистику сканирования
            scan_stats = await self.database.get_scan_statistics(
                start_date=start_date,
                end_date=end_date,
            )
            if scan_stats:
                stats["scans_performed"] = scan_stats.get("scans_performed", 0)
                stats["opportunities_found"] = scan_stats.get("opportunities_found", 0)

        except (RuntimeError, KeyError, TypeError, ValueError):
            logger.exception("Error collecting statistics")

        return stats

    def _format_report(
        self,
        stats: dict[str, Any],
        start_date: datetime,
        end_date: datetime,
    ) -> str:
        """Format statistics into a readable report.

        Args:
            stats: Statistics dictionary
            start_date: Start of the reporting period
            end_date: End of the reporting period

        Returns:
            Formatted report text

        """
        date_str = start_date.strftime("%d.%m.%Y")
        if (end_date - start_date).days > 1:
            date_str += f" - {end_date.strftime('%d.%m.%Y')}"

        # Расчёт процента успешных сделок
        total_trades = stats.get("total_trades", 0)
        successful = stats.get("successful_trades", 0)
        success_rate = (successful / total_trades * 100) if total_trades > 0 else 0

        # Форматирование прибыли
        total_profit = stats.get("total_profit_usd", 0.0)
        avg_profit_pct = stats.get("avg_profit_percent", 0.0)

        # Формируем отчёт
        lines = [
            "📊 Ежедневный отчёт",
            f"📅 {date_str}",
            "",
            "💼 Торговля:",
            f"  • Сделок: {total_trades}",
        ]

        if total_trades > 0:
            cancelled = stats.get("cancelled_trades", 0)
            failed = stats.get("failed_trades", 0)

            lines.extend(
                [
                    f"  • Успешных: {successful} ({success_rate:.1f}%)",
                    f"  • Отменено: {cancelled}",
                    f"  • Ошибок: {failed}",
                ]
            )

        lines.extend(
            [
                "",
                f"💰 Прибыль: {total_profit:+.2f}$ ({avg_profit_pct:+.1f}%)",
            ]
        )

        # Статистика сканирования
        scans = stats.get("scans_performed", 0)
        opportunities = stats.get("opportunities_found", 0)

        if scans > 0:
            lines.extend(
                [
                    "",
                    "🔍 Сканирование:",
                    f"  • Сканов выполнено: {scans}",
                    f"  • Возможностей найдено: {opportunities}",
                ]
            )

        # Ошибки API
        api_errors = stats.get("api_errors", {})
        critical_errors = stats.get("critical_errors", 0)

        if api_errors or critical_errors > 0:
            lines.extend(
                [
                    "",
                    "⚠️ Ошибки:",
                ]
            )

            if api_errors:
                for error_type, count in sorted(
                    api_errors.items(),
                    key=operator.itemgetter(1),
                    reverse=True,
                ):
                    lines.append(f"  • {error_type}: {count}")

            if critical_errors > 0:
                lines.append(f"🔴 Критических: {critical_errors}")
        else:
            lines.extend(
                [
                    "",
                    "✅ Ошибок не обнаружено",
                ]
            )

        return "\n".join(lines)
