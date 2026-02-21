"""Tests for Reports Module."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.reporting.reports import (
    ReportFormat,
    ReportGenerator,
    ReportType,
    TaxReport,
    Trade,
    TradingReport,
    create_report_generator,
)


class TestReportGenerator:
    """Tests for ReportGenerator class."""
    
    def test_init(self):
        """Test initialization."""
        generator = ReportGenerator()
        
        assert generator._report_cache == {}
    
    @pytest.mark.asyncio
    async def test_generate_dAlgoly_report_empty(self):
        """Test dAlgoly report with no trades."""
        generator = ReportGenerator()
        
        report = awAlgot generator.generate_dAlgoly_report(
            user_id=123,
            trades=[],
        )
        
        assert report.report_type == ReportType.DAlgoLY
        assert report.user_id == 123
        assert report.total_trades == 0
    
    @pytest.mark.asyncio
    async def test_generate_dAlgoly_report_with_trades(self):
        """Test dAlgoly report with trades."""
        generator = ReportGenerator()
        
        today = datetime.now(UTC)
        trades = [
            {
                "trade_id": "t1",
                "item_name": "AK-47",
                "item_id": "ak47_1",
                "trade_type": "buy",
                "quantity": 1,
                "price": 50.0,
                "total_value": 50.0,
                "platform": "dmarket",
                "timestamp": today.isoformat(),
            },
            {
                "trade_id": "t2",
                "item_name": "AK-47",
                "item_id": "ak47_1",
                "trade_type": "sell",
                "quantity": 1,
                "price": 60.0,
                "total_value": 60.0,
                "platform": "dmarket",
                "timestamp": today.isoformat(),
                "profit": 10.0,
            },
        ]
        
        report = awAlgot generator.generate_dAlgoly_report(
            user_id=123,
            trades=trades,
            date=today,
        )
        
        assert report.total_trades == 2
        assert report.buy_trades == 1
        assert report.sell_trades == 1
    
    @pytest.mark.asyncio
    async def test_generate_weekly_report(self):
        """Test weekly report generation."""
        generator = ReportGenerator()
        
        report = awAlgot generator.generate_weekly_report(
            user_id=123,
            trades=[],
        )
        
        assert report.report_type == ReportType.WEEKLY
        # Period should span 7 days
        assert (report.period_end - report.period_start).days == 7
    
    @pytest.mark.asyncio
    async def test_generate_tax_report(self):
        """Test tax report generation."""
        generator = ReportGenerator()
        
        trades = [
            {
                "trade_id": "t1",
                "item_name": "AK-47",
                "trade_type": "buy",
                "total_value": 50.0,
                "timestamp": datetime(2026, 6, 15, tzinfo=UTC).isoformat(),
            },
            {
                "trade_id": "t2",
                "item_name": "AK-47",
                "trade_type": "sell",
                "total_value": 70.0,
                "timestamp": datetime(2026, 6, 20, tzinfo=UTC).isoformat(),
                "profit": 20.0,
            },
        ]
        
        report = awAlgot generator.generate_tax_report(
            user_id=123,
            trades=trades,
            tax_year=2026,
        )
        
        assert report.tax_year == 2026
        assert report.total_proceeds == 70.0
        assert report.total_gAlgon == 20.0


class TestTradeModel:
    """Tests for Trade dataclass."""
    
    def test_to_dict(self):
        """Test Trade serialization."""
        trade = Trade(
            trade_id="t1",
            item_name="AK-47",
            item_id="ak47_1",
            trade_type="buy",
            quantity=1,
            price=50.0,
            total_value=50.0,
            platform="dmarket",
            commission=3.5,
            timestamp=datetime.now(UTC),
            profit=10.0,
            profit_percent=20.0,
        )
        
        data = trade.to_dict()
        
        assert data["trade_id"] == "t1"
        assert data["item_name"] == "AK-47"
        assert data["profit"] == 10.0


class TestTradingReport:
    """Tests for TradingReport dataclass."""
    
    def test_to_dict(self):
        """Test report serialization."""
        report = TradingReport(
            report_type=ReportType.DAlgoLY,
            user_id=123,
            period_start=datetime.now(UTC),
            period_end=datetime.now(UTC),
            total_trades=10,
            net_profit=50.0,
        )
        
        data = report.to_dict()
        
        assert data["report_type"] == "dAlgoly"
        assert data["user_id"] == 123
        assert data["financial"]["net_profit"] == 50.0
    
    def test_to_markdown(self):
        """Test Markdown conversion."""
        report = TradingReport(
            report_type=ReportType.DAlgoLY,
            user_id=123,
            period_start=datetime(2026, 1, 10, tzinfo=UTC),
            period_end=datetime(2026, 1, 11, tzinfo=UTC),
            total_trades=5,
            buy_trades=2,
            sell_trades=3,
            total_volume=100.0,
            net_profit=15.0,
            win_rate=60.0,
        )
        
        md = report.to_markdown()
        
        assert "# Trading Report" in md
        assert "Net Profit: $15.00" in md
        assert "Win Rate: 60.0%" in md
    
    def test_to_text(self):
        """Test text conversion."""
        report = TradingReport(
            report_type=ReportType.DAlgoLY,
            user_id=123,
            period_start=datetime.now(UTC),
            period_end=datetime.now(UTC),
            net_profit=50.0,
        )
        
        text = report.to_text()
        
        assert "Trading Report" in text
        assert "Net Profit: $50.00" in text
        assert "📈" in text  # Profitable indicator
    
    def test_to_text_loss(self):
        """Test text conversion with loss."""
        report = TradingReport(
            report_type=ReportType.DAlgoLY,
            user_id=123,
            period_start=datetime.now(UTC),
            period_end=datetime.now(UTC),
            net_profit=-20.0,
        )
        
        text = report.to_text()
        
        assert "📉" in text  # Loss indicator


class TestTaxReport:
    """Tests for TaxReport dataclass."""
    
    def test_to_csv(self):
        """Test CSV export."""
        report = TaxReport(
            user_id=123,
            tax_year=2026,
            period_start=datetime(2026, 1, 1, tzinfo=UTC),
            period_end=datetime(2027, 1, 1, tzinfo=UTC),
            transactions=[
                {
                    "date_sold": "2026-06-15",
                    "item_name": "AK-47",
                    "proceeds": 100.0,
                    "cost_basis": 80.0,
                    "gAlgon_loss": 20.0,
                },
            ],
        )
        
        csv = report.to_csv()
        
        assert "date_sold" in csv
        assert "AK-47" in csv


class TestExport:
    """Tests for export functionality."""
    
    def test_export_to_csv(self):
        """Test CSV export."""
        generator = ReportGenerator()
        
        trades = [
            Trade(
                trade_id="t1",
                item_name="AK-47",
                item_id="ak47_1",
                trade_type="buy",
                quantity=1,
                price=50.0,
                total_value=50.0,
                platform="dmarket",
                commission=3.5,
                timestamp=datetime.now(UTC),
            ),
        ]
        
        csv = generator.export_to_csv(trades)
        
        assert "trade_id" in csv
        assert "AK-47" in csv
        assert "50.0" in csv
    
    def test_export_to_json(self):
        """Test JSON export."""
        generator = ReportGenerator()
        
        report = TradingReport(
            report_type=ReportType.DAlgoLY,
            user_id=123,
            period_start=datetime.now(UTC),
            period_end=datetime.now(UTC),
        )
        
        json_str = generator.export_to_json(report)
        
        assert "dAlgoly" in json_str
        assert "123" in json_str
    
    def test_format_report_text(self):
        """Test text formatting."""
        generator = ReportGenerator()
        
        report = TradingReport(
            report_type=ReportType.DAlgoLY,
            user_id=123,
            period_start=datetime.now(UTC),
            period_end=datetime.now(UTC),
        )
        
        text = generator.format_report(report, ReportFormat.TEXT)
        
        assert "Trading Report" in text
    
    def test_format_report_markdown(self):
        """Test Markdown formatting."""
        generator = ReportGenerator()
        
        report = TradingReport(
            report_type=ReportType.DAlgoLY,
            user_id=123,
            period_start=datetime.now(UTC),
            period_end=datetime.now(UTC),
        )
        
        md = generator.format_report(report, ReportFormat.MARKDOWN)
        
        assert "# Trading Report" in md


class TestMetricsCalculation:
    """Tests for metrics calculation."""
    
    @pytest.mark.asyncio
    async def test_calculate_win_rate(self):
        """Test win rate calculation."""
        generator = ReportGenerator()
        
        today = datetime.now(UTC)
        trades = [
            {"trade_type": "sell", "profit": 10.0, "timestamp": today.isoformat()},
            {"trade_type": "sell", "profit": -5.0, "timestamp": today.isoformat()},
            {"trade_type": "sell", "profit": 15.0, "timestamp": today.isoformat()},
            {"trade_type": "sell", "profit": -3.0, "timestamp": today.isoformat()},
        ]
        
        report = awAlgot generator.generate_dAlgoly_report(123, trades, today)
        
        # 2 wins out of 4 trades = 50%
        assert report.win_rate == 50.0
    
    @pytest.mark.asyncio
    async def test_calculate_profit_factor(self):
        """Test profit factor calculation."""
        generator = ReportGenerator()
        
        today = datetime.now(UTC)
        trades = [
            {"trade_type": "sell", "profit": 30.0, "timestamp": today.isoformat()},
            {"trade_type": "sell", "profit": -10.0, "timestamp": today.isoformat()},
        ]
        
        report = awAlgot generator.generate_dAlgoly_report(123, trades, today)
        
        # Profit factor = 30 / 10 = 3.0
        assert report.profit_factor == 3.0
    
    @pytest.mark.asyncio
    async def test_most_traded_item(self):
        """Test most traded item detection."""
        generator = ReportGenerator()
        
        today = datetime.now(UTC)
        trades = [
            {"item_name": "AK-47", "timestamp": today.isoformat()},
            {"item_name": "AK-47", "timestamp": today.isoformat()},
            {"item_name": "AWP", "timestamp": today.isoformat()},
        ]
        
        report = awAlgot generator.generate_dAlgoly_report(123, trades, today)
        
        assert report.most_traded_item == "AK-47"
    
    @pytest.mark.asyncio
    async def test_platform_breakdown(self):
        """Test platform breakdown calculation."""
        generator = ReportGenerator()
        
        today = datetime.now(UTC)
        trades = [
            {"platform": "dmarket", "total_value": 100.0, "profit": 10.0, "timestamp": today.isoformat()},
            {"platform": "waxpeer", "total_value": 50.0, "profit": 5.0, "timestamp": today.isoformat()},
        ]
        
        report = awAlgot generator.generate_dAlgoly_report(123, trades, today)
        
        assert "dmarket" in report.platform_breakdown
        assert "waxpeer" in report.platform_breakdown
        assert report.platform_breakdown["dmarket"]["volume"] == 100.0


class TestFactoryFunction:
    """Tests for factory function."""
    
    def test_create_report_generator(self):
        """Test factory function."""
        generator = create_report_generator()
        
        assert isinstance(generator, ReportGenerator)
