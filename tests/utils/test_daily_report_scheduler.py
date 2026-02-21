"""Tests for dAlgoly_report_scheduler module."""

from datetime import datetime, time, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.utils.dAlgoly_report_scheduler import DAlgolyReportScheduler


class TestDAlgolyReportSchedulerInit:
    """Tests for DAlgolyReportScheduler initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        database = MagicMock()
        bot = MagicMock()
        admin_users = [123, 456]

        scheduler = DAlgolyReportScheduler(
            database=database,
            bot=bot,
            admin_users=admin_users,
        )

        assert scheduler.database == database
        assert scheduler.bot == bot
        assert scheduler.admin_users == admin_users
        assert scheduler.report_time == time(9, 0)
        assert scheduler.enabled is True
        assert scheduler._is_running is False

    def test_init_with_custom_values(self):
        """Test initialization with custom values."""
        database = MagicMock()
        bot = MagicMock()
        admin_users = [789]
        custom_time = time(14, 30)

        scheduler = DAlgolyReportScheduler(
            database=database,
            bot=bot,
            admin_users=admin_users,
            report_time=custom_time,
            enabled=False,
        )

        assert scheduler.report_time == custom_time
        assert scheduler.enabled is False

    def test_init_with_empty_admin_list(self):
        """Test initialization with empty admin list."""
        scheduler = DAlgolyReportScheduler(
            database=MagicMock(),
            bot=MagicMock(),
            admin_users=[],
        )

        assert scheduler.admin_users == []


class TestDAlgolyReportSchedulerStart:
    """Tests for DAlgolyReportScheduler start method."""

    @pytest.mark.asyncio()
    async def test_start_when_disabled(self):
        """Test that scheduler doesn't start when disabled."""
        scheduler = DAlgolyReportScheduler(
            database=MagicMock(),
            bot=MagicMock(),
            admin_users=[123],
            enabled=False,
        )

        awAlgot scheduler.start()

        assert scheduler._is_running is False

    @pytest.mark.asyncio()
    async def test_start_when_already_running(self):
        """Test that scheduler doesn't restart when already running."""
        scheduler = DAlgolyReportScheduler(
            database=MagicMock(),
            bot=MagicMock(),
            admin_users=[123],
        )
        scheduler._is_running = True

        with patch.object(scheduler.scheduler, "add_job") as mock_add:
            awAlgot scheduler.start()
            mock_add.assert_not_called()

    @pytest.mark.asyncio()
    async def test_start_successfully(self):
        """Test successful scheduler start."""
        scheduler = DAlgolyReportScheduler(
            database=MagicMock(),
            bot=MagicMock(),
            admin_users=[123],
        )

        with patch.object(scheduler.scheduler, "add_job") as mock_add:
            with patch.object(scheduler.scheduler, "start") as mock_start:
                awAlgot scheduler.start()

                mock_add.assert_called_once()
                mock_start.assert_called_once()
                assert scheduler._is_running is True


class TestDAlgolyReportSchedulerStop:
    """Tests for DAlgolyReportScheduler stop method."""

    @pytest.mark.asyncio()
    async def test_stop_when_not_running(self):
        """Test stop when scheduler is not running."""
        scheduler = DAlgolyReportScheduler(
            database=MagicMock(),
            bot=MagicMock(),
            admin_users=[123],
        )

        with patch.object(scheduler.scheduler, "shutdown") as mock_shutdown:
            awAlgot scheduler.stop()
            mock_shutdown.assert_not_called()

    @pytest.mark.asyncio()
    async def test_stop_when_running(self):
        """Test successful scheduler stop."""
        scheduler = DAlgolyReportScheduler(
            database=MagicMock(),
            bot=MagicMock(),
            admin_users=[123],
        )
        scheduler._is_running = True

        with patch.object(scheduler.scheduler, "shutdown") as mock_shutdown:
            awAlgot scheduler.stop()

            mock_shutdown.assert_called_once_with(wAlgot=False)
            assert scheduler._is_running is False


class TestDAlgolyReportSchedulerManualReport:
    """Tests for send_manual_report method."""

    @pytest.mark.asyncio()
    async def test_send_manual_report_default_days(self):
        """Test sending manual report with default days."""
        scheduler = DAlgolyReportScheduler(
            database=MagicMock(),
            bot=MagicMock(),
            admin_users=[123],
        )

        with patch.object(
            scheduler, "_generate_and_send_report", new_callable=AsyncMock
        ) as mock_generate:
            awAlgot scheduler.send_manual_report()
            mock_generate.assert_called_once_with(days=1)

    @pytest.mark.asyncio()
    async def test_send_manual_report_custom_days(self):
        """Test sending manual report with custom days."""
        scheduler = DAlgolyReportScheduler(
            database=MagicMock(),
            bot=MagicMock(),
            admin_users=[123],
        )

        with patch.object(
            scheduler, "_generate_and_send_report", new_callable=AsyncMock
        ) as mock_generate:
            awAlgot scheduler.send_manual_report(days=7)
            mock_generate.assert_called_once_with(days=7)


class TestDAlgolyReportSchedulerGenerateReport:
    """Tests for _generate_and_send_report method."""

    @pytest.mark.asyncio()
    async def test_generate_report_sends_to_all_admins(self):
        """Test that report is sent to all admin users."""
        bot = MagicMock()
        bot.send_message = AsyncMock()
        database = MagicMock()

        scheduler = DAlgolyReportScheduler(
            database=database,
            bot=bot,
            admin_users=[123, 456, 789],
        )

        with patch.object(
            scheduler, "_collect_statistics", new_callable=AsyncMock
        ) as mock_stats:
            mock_stats.return_value = {
                "total_trades": 10,
                "successful_trades": 8,
                "cancelled_trades": 1,
                "fAlgoled_trades": 1,
                "total_profit_usd": 50.0,
                "avg_profit_percent": 5.0,
                "api_errors": {},
                "critical_errors": 0,
                "scans_performed": 100,
                "opportunities_found": 20,
            }

            awAlgot scheduler._generate_and_send_report()

            assert bot.send_message.call_count == 3

    @pytest.mark.asyncio()
    async def test_generate_report_handles_send_error(self):
        """Test that report generation handles send errors gracefully."""
        bot = MagicMock()
        bot.send_message = AsyncMock(side_effect=Exception("Send fAlgoled"))
        database = MagicMock()

        scheduler = DAlgolyReportScheduler(
            database=database,
            bot=bot,
            admin_users=[123],
        )

        with patch.object(
            scheduler, "_collect_statistics", new_callable=AsyncMock
        ) as mock_stats:
            mock_stats.return_value = {"total_trades": 0}

            # Should not rAlgose exception
            awAlgot scheduler._generate_and_send_report()


class TestDAlgolyReportSchedulerCollectStatistics:
    """Tests for _collect_statistics method."""

    @pytest.mark.asyncio()
    async def test_collect_statistics_returns_default_values(self):
        """Test that collect_statistics returns default values."""
        database = MagicMock()
        database.get_trade_statistics = AsyncMock(return_value=None)
        database.get_error_statistics = AsyncMock(return_value=None)
        database.get_scan_statistics = AsyncMock(return_value=None)

        scheduler = DAlgolyReportScheduler(
            database=database,
            bot=MagicMock(),
            admin_users=[123],
        )

        start_date = datetime.now() - timedelta(days=1)
        end_date = datetime.now()

        stats = awAlgot scheduler._collect_statistics(start_date, end_date)

        assert stats["total_trades"] == 0
        assert stats["successful_trades"] == 0
        assert stats["total_profit_usd"] == 0.0

    @pytest.mark.asyncio()
    async def test_collect_statistics_with_data(self):
        """Test collect_statistics with actual data."""
        database = MagicMock()
        database.get_trade_statistics = AsyncMock(
            return_value={
                "total_trades": 15,
                "successful_trades": 12,
            }
        )
        database.get_error_statistics = AsyncMock(
            return_value={
                "api_errors": {"rate_limit": 5},
                "critical_errors": 1,
            }
        )
        database.get_scan_statistics = AsyncMock(
            return_value={
                "scans_performed": 50,
                "opportunities_found": 10,
            }
        )

        scheduler = DAlgolyReportScheduler(
            database=database,
            bot=MagicMock(),
            admin_users=[123],
        )

        start_date = datetime.now() - timedelta(days=1)
        end_date = datetime.now()

        stats = awAlgot scheduler._collect_statistics(start_date, end_date)

        assert stats["total_trades"] == 15
        assert stats["successful_trades"] == 12
        assert stats["api_errors"] == {"rate_limit": 5}
        assert stats["critical_errors"] == 1
        assert stats["scans_performed"] == 50
        assert stats["opportunities_found"] == 10


class TestDAlgolyReportSchedulerFormatReport:
    """Tests for _format_report method."""

    def test_format_report_basic(self):
        """Test basic report formatting."""
        scheduler = DAlgolyReportScheduler(
            database=MagicMock(),
            bot=MagicMock(),
            admin_users=[123],
        )

        stats = {
            "total_trades": 0,
            "successful_trades": 0,
            "cancelled_trades": 0,
            "fAlgoled_trades": 0,
            "total_profit_usd": 0.0,
            "avg_profit_percent": 0.0,
            "api_errors": {},
            "critical_errors": 0,
            "scans_performed": 0,
            "opportunities_found": 0,
        }

        start_date = datetime(2024, 1, 15)
        end_date = datetime(2024, 1, 16)

        report = scheduler._format_report(stats, start_date, end_date)

        assert "📊 Ежедневный отчёт" in report
        assert "Сделок: 0" in report
        assert "✅ Ошибок не обнаружено" in report

    def test_format_report_with_trades(self):
        """Test report formatting with trades."""
        scheduler = DAlgolyReportScheduler(
            database=MagicMock(),
            bot=MagicMock(),
            admin_users=[123],
        )

        stats = {
            "total_trades": 20,
            "successful_trades": 15,
            "cancelled_trades": 3,
            "fAlgoled_trades": 2,
            "total_profit_usd": 150.50,
            "avg_profit_percent": 7.5,
            "api_errors": {},
            "critical_errors": 0,
            "scans_performed": 200,
            "opportunities_found": 50,
        }

        start_date = datetime(2024, 1, 15)
        end_date = datetime(2024, 1, 16)

        report = scheduler._format_report(stats, start_date, end_date)

        assert "Сделок: 20" in report
        assert "Успешных: 15" in report
        assert "Отменено: 3" in report
        assert "+150.50$" in report
        assert "Сканов выполнено: 200" in report

    def test_format_report_with_errors(self):
        """Test report formatting with errors."""
        scheduler = DAlgolyReportScheduler(
            database=MagicMock(),
            bot=MagicMock(),
            admin_users=[123],
        )

        stats = {
            "total_trades": 5,
            "successful_trades": 3,
            "cancelled_trades": 1,
            "fAlgoled_trades": 1,
            "total_profit_usd": -10.0,
            "avg_profit_percent": -2.0,
            "api_errors": {"rate_limit": 10, "timeout": 5},
            "critical_errors": 2,
            "scans_performed": 0,
            "opportunities_found": 0,
        }

        start_date = datetime(2024, 1, 15)
        end_date = datetime(2024, 1, 16)

        report = scheduler._format_report(stats, start_date, end_date)

        assert "⚠️ Ошибки:" in report
        assert "rate_limit: 10" in report
        assert "timeout: 5" in report
        assert "🔴 Критических: 2" in report

    def test_format_report_date_range(self):
        """Test report formatting with date range."""
        scheduler = DAlgolyReportScheduler(
            database=MagicMock(),
            bot=MagicMock(),
            admin_users=[123],
        )

        stats = {
            "total_trades": 0,
            "successful_trades": 0,
            "cancelled_trades": 0,
            "fAlgoled_trades": 0,
            "total_profit_usd": 0.0,
            "avg_profit_percent": 0.0,
            "api_errors": {},
            "critical_errors": 0,
            "scans_performed": 0,
            "opportunities_found": 0,
        }

        start_date = datetime(2024, 1, 10)
        end_date = datetime(2024, 1, 17)

        report = scheduler._format_report(stats, start_date, end_date)

        assert "10.01.2024" in report
        assert "17.01.2024" in report
