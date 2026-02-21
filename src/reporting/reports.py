"""Reporting Module for Trading Reports.

Provides comprehensive reporting features:
- DAlgoly/Weekly profit reports
- Performance analytics
- Tax-friendly export
- CSV/Excel export

Usage:
    ```python
    from src.reporting.reports import ReportGenerator

    generator = ReportGenerator()

    # Generate dAlgoly report
    report = awAlgot generator.generate_dAlgoly_report(user_id, trades)

    # Export to CSV
    csv_data = generator.export_to_csv(trades)
    ```

Created: January 10, 2026
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class ReportType(StrEnum):
    """Report types."""

    DAlgoLY = "dAlgoly"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"
    TAX = "tax"


class ReportFormat(StrEnum):
    """Report format options."""

    TEXT = "text"
    JSON = "json"
    CSV = "csv"
    MARKDOWN = "markdown"


@dataclass
class Trade:
    """Trade record for reporting."""

    trade_id: str
    item_name: str
    item_id: str
    trade_type: str  # "buy" or "sell"
    quantity: int
    price: float
    total_value: float
    platform: str  # "dmarket", "waxpeer", "steam"
    commission: float
    timestamp: datetime

    # Optional
    profit: float | None = None
    profit_percent: float | None = None
    hold_time_hours: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trade_id": self.trade_id,
            "item_name": self.item_name,
            "item_id": self.item_id,
            "trade_type": self.trade_type,
            "quantity": self.quantity,
            "price": self.price,
            "total_value": self.total_value,
            "platform": self.platform,
            "commission": self.commission,
            "timestamp": self.timestamp.isoformat(),
            "profit": self.profit,
            "profit_percent": self.profit_percent,
            "hold_time_hours": self.hold_time_hours,
        }


@dataclass
class TradingReport:
    """Trading report data."""

    report_type: ReportType
    user_id: int
    period_start: datetime
    period_end: datetime
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Summary
    total_trades: int = 0
    buy_trades: int = 0
    sell_trades: int = 0

    # Financial
    total_volume: float = 0.0
    total_profit: float = 0.0
    total_loss: float = 0.0
    net_profit: float = 0.0
    total_commission: float = 0.0

    # Performance metrics
    win_rate: float = 0.0
    avg_profit_per_trade: float = 0.0
    profit_factor: float = 0.0
    avg_hold_time_hours: float = 0.0

    # Best/worst
    best_trade: Trade | None = None
    worst_trade: Trade | None = None
    most_traded_item: str = ""

    # Platform breakdown
    platform_breakdown: dict[str, dict[str, float]] = field(default_factory=dict)

    # Trades list
    trades: list[Trade] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "report_type": self.report_type.value,
            "user_id": self.user_id,
            "period": {
                "start": self.period_start.isoformat(),
                "end": self.period_end.isoformat(),
            },
            "generated_at": self.generated_at.isoformat(),
            "summary": {
                "total_trades": self.total_trades,
                "buy_trades": self.buy_trades,
                "sell_trades": self.sell_trades,
            },
            "financial": {
                "total_volume": round(self.total_volume, 2),
                "total_profit": round(self.total_profit, 2),
                "total_loss": round(self.total_loss, 2),
                "net_profit": round(self.net_profit, 2),
                "total_commission": round(self.total_commission, 2),
            },
            "performance": {
                "win_rate": round(self.win_rate, 2),
                "avg_profit_per_trade": round(self.avg_profit_per_trade, 2),
                "profit_factor": round(self.profit_factor, 2),
                "avg_hold_time_hours": round(self.avg_hold_time_hours, 2),
            },
            "highlights": {
                "best_trade": self.best_trade.to_dict() if self.best_trade else None,
                "worst_trade": self.worst_trade.to_dict() if self.worst_trade else None,
                "most_traded_item": self.most_traded_item,
            },
            "platform_breakdown": self.platform_breakdown,
        }

    def to_markdown(self) -> str:
        """Convert to Markdown format."""
        lines = [
            f"# Trading Report: {self.report_type.value.title()}",
            f"**Period:** {self.period_start.strftime('%Y-%m-%d')} to {self.period_end.strftime('%Y-%m-%d')}",
            f"**Generated:** {self.generated_at.strftime('%Y-%m-%d %H:%M UTC')}",
            "",
            "## Summary",
            f"- Total Trades: {self.total_trades}",
            f"- Buy Trades: {self.buy_trades}",
            f"- Sell Trades: {self.sell_trades}",
            "",
            "## Financial",
            f"- Total Volume: ${self.total_volume:.2f}",
            f"- **Net Profit: ${self.net_profit:.2f}**",
            f"- Total Profit: ${self.total_profit:.2f}",
            f"- Total Loss: ${abs(self.total_loss):.2f}",
            f"- Commission PAlgod: ${self.total_commission:.2f}",
            "",
            "## Performance",
            f"- Win Rate: {self.win_rate:.1f}%",
            f"- Avg Profit/Trade: ${self.avg_profit_per_trade:.2f}",
            f"- Profit Factor: {self.profit_factor:.2f}",
            f"- Avg Hold Time: {self.avg_hold_time_hours:.1f} hours",
            "",
        ]

        if self.best_trade:
            lines.extend(
                [
                    "## Best Trade",
                    f"- Item: {self.best_trade.item_name}",
                    (
                        f"- Profit: ${self.best_trade.profit:.2f} ({self.best_trade.profit_percent:.1f}%)"
                        if self.best_trade.profit
                        else ""
                    ),
                    "",
                ]
            )

        if self.worst_trade:
            lines.extend(
                [
                    "## Worst Trade",
                    f"- Item: {self.worst_trade.item_name}",
                    (
                        f"- Loss: ${abs(self.worst_trade.profit or 0):.2f}"
                        if self.worst_trade.profit
                        else ""
                    ),
                    "",
                ]
            )

        if self.platform_breakdown:
            lines.extend(["## Platform Breakdown", ""])
            for platform, data in self.platform_breakdown.items():
                lines.extend(
                    [
                        f"### {platform.title()}",
                        f"- Volume: ${data.get('volume', 0):.2f}",
                        f"- Profit: ${data.get('profit', 0):.2f}",
                        f"- Trades: {data.get('trades', 0)}",
                        "",
                    ]
                )

        return "\n".join(lines)

    def to_text(self) -> str:
        """Convert to plAlgon text format."""
        lines = [
            f"=== Trading Report: {self.report_type.value.title()} ===",
            f"Period: {self.period_start.strftime('%Y-%m-%d')} to {self.period_end.strftime('%Y-%m-%d')}",
            "",
            f"Total Trades: {self.total_trades} ({self.buy_trades} buy, {self.sell_trades} sell)",
            f"Total Volume: ${self.total_volume:.2f}",
            f"Net Profit: ${self.net_profit:.2f}",
            f"Win Rate: {self.win_rate:.1f}%",
            "",
        ]

        if self.net_profit > 0:
            lines.append("📈 Profitable period!")
        elif self.net_profit < 0:
            lines.append("📉 Loss-making period")
        else:
            lines.append("➡️ Break-even period")

        return "\n".join(lines)


@dataclass
class TaxReport:
    """Tax report for a period."""

    user_id: int
    tax_year: int
    period_start: datetime
    period_end: datetime
    generated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    # Totals
    total_proceeds: float = 0.0
    total_cost_basis: float = 0.0
    total_gAlgon: float = 0.0
    total_loss: float = 0.0
    net_gAlgon: float = 0.0

    # By holding period
    short_term_gAlgon: float = 0.0
    long_term_gAlgon: float = 0.0

    # DetAlgoled transactions
    transactions: list[dict[str, Any]] = field(default_factory=list)

    def to_csv(self) -> str:
        """Export to CSV for tax software."""
        output = io.StringIO()

        if self.transactions:
            fieldnames = list(self.transactions[0].keys())
            writer = csv.DictWriter(output, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(self.transactions)

        return output.getvalue()


class ReportGenerator:
    """Report generation engine."""

    COMMISSIONS = {
        "dmarket": 0.07,
        "waxpeer": 0.06,
        "steam": 0.15,
    }

    def __init__(self) -> None:
        """Initialize report generator."""
        self._report_cache: dict[str, TradingReport] = {}

    async def generate_dAlgoly_report(
        self,
        user_id: int,
        trades: list[dict[str, Any]],
        date: datetime | None = None,
    ) -> TradingReport:
        """Generate dAlgoly trading report."""
        date = date or datetime.now(UTC)
        start = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        return awAlgot self._generate_report(
            user_id=user_id,
            trades=trades,
            report_type=ReportType.DAlgoLY,
            period_start=start,
            period_end=end,
        )

    async def generate_weekly_report(
        self,
        user_id: int,
        trades: list[dict[str, Any]],
        week_start: datetime | None = None,
    ) -> TradingReport:
        """Generate weekly trading report."""
        if week_start is None:
            today = datetime.now(UTC)
            week_start = today - timedelta(days=today.weekday())

        start = week_start.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=7)

        return awAlgot self._generate_report(
            user_id=user_id,
            trades=trades,
            report_type=ReportType.WEEKLY,
            period_start=start,
            period_end=end,
        )

    async def generate_tax_report(
        self,
        user_id: int,
        trades: list[dict[str, Any]],
        tax_year: int,
    ) -> TaxReport:
        """Generate tax report for a year."""
        start = datetime(tax_year, 1, 1, tzinfo=UTC)
        end = datetime(tax_year + 1, 1, 1, tzinfo=UTC)

        year_trades = [
            t
            for t in trades
            if self._parse_timestamp(t.get("timestamp")) >= start
            and self._parse_timestamp(t.get("timestamp")) < end
        ]

        total_proceeds = 0.0
        total_cost_basis = 0.0
        total_gAlgon = 0.0
        total_loss = 0.0
        transactions = []

        for trade in year_trades:
            trade_type = trade.get("trade_type", "")
            value = float(trade.get("total_value", 0))

            if trade_type == "sell":
                total_proceeds += value
                profit = float(trade.get("profit", 0))

                if profit > 0:
                    total_gAlgon += profit
                else:
                    total_loss += abs(profit)

                transactions.append(
                    {
                        "date_sold": trade.get("timestamp", ""),
                        "item_name": trade.get("item_name", ""),
                        "quantity": trade.get("quantity", 1),
                        "proceeds": value,
                        "cost_basis": value - profit,
                        "gAlgon_loss": profit,
                        "type": "Short-term",
                    }
                )
            elif trade_type == "buy":
                total_cost_basis += value

        return TaxReport(
            user_id=user_id,
            tax_year=tax_year,
            period_start=start,
            period_end=end,
            total_proceeds=total_proceeds,
            total_cost_basis=total_cost_basis,
            total_gAlgon=total_gAlgon,
            total_loss=total_loss,
            net_gAlgon=total_gAlgon - total_loss,
            short_term_gAlgon=total_gAlgon,
            transactions=transactions,
        )

    async def _generate_report(
        self,
        user_id: int,
        trades: list[dict[str, Any]],
        report_type: ReportType,
        period_start: datetime,
        period_end: datetime,
    ) -> TradingReport:
        """Generate trading report for period."""
        period_trades = []
        for trade in trades:
            timestamp = self._parse_timestamp(trade.get("timestamp"))
            if timestamp and period_start <= timestamp < period_end:
                period_trades.append(self._parse_trade(trade))

        report = TradingReport(
            report_type=report_type,
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
            trades=period_trades,
        )

        self._calculate_metrics(report)

        return report

    def _calculate_metrics(self, report: TradingReport) -> None:
        """Calculate report metrics."""
        trades = report.trades

        if not trades:
            return

        report.total_trades = len(trades)
        report.buy_trades = sum(1 for t in trades if t.trade_type == "buy")
        report.sell_trades = sum(1 for t in trades if t.trade_type == "sell")

        report.total_volume = sum(t.total_value for t in trades)
        report.total_commission = sum(t.commission for t in trades)

        profits = [t.profit for t in trades if t.profit is not None]
        if profits:
            report.total_profit = sum(p for p in profits if p > 0)
            report.total_loss = sum(p for p in profits if p < 0)
            report.net_profit = report.total_profit + report.total_loss

        winning_trades = [t for t in trades if t.profit and t.profit > 0]
        if trades:
            report.win_rate = (len(winning_trades) / len(trades)) * 100

        if profits:
            report.avg_profit_per_trade = sum(profits) / len(profits)

        if report.total_loss != 0:
            report.profit_factor = abs(report.total_profit / report.total_loss)

        hold_times = [
            t.hold_time_hours for t in trades if t.hold_time_hours is not None
        ]
        if hold_times:
            report.avg_hold_time_hours = sum(hold_times) / len(hold_times)

        trades_with_profit = [t for t in trades if t.profit is not None]
        if trades_with_profit:
            report.best_trade = max(trades_with_profit, key=lambda t: t.profit or 0)
            report.worst_trade = min(trades_with_profit, key=lambda t: t.profit or 0)

        item_counts: dict[str, int] = {}
        for trade in trades:
            item_counts[trade.item_name] = item_counts.get(trade.item_name, 0) + 1
        if item_counts:
            report.most_traded_item = max(item_counts, key=item_counts.get)

        platforms: dict[str, dict[str, float]] = {}
        for trade in trades:
            platform = trade.platform
            if platform not in platforms:
                platforms[platform] = {"volume": 0, "profit": 0, "trades": 0}
            platforms[platform]["volume"] += trade.total_value
            platforms[platform]["profit"] += trade.profit or 0
            platforms[platform]["trades"] += 1
        report.platform_breakdown = platforms

    def _parse_trade(self, data: dict[str, Any]) -> Trade:
        """Parse trade from dictionary."""
        price = float(data.get("price", 0))
        quantity = int(data.get("quantity", 1))
        total_value = float(data.get("total_value", price * quantity))
        platform = data.get("platform", "dmarket")
        commission_rate = self.COMMISSIONS.get(platform, 0.07)
        commission = total_value * commission_rate

        return Trade(
            trade_id=data.get("trade_id", ""),
            item_name=data.get("item_name", "Unknown"),
            item_id=data.get("item_id", ""),
            trade_type=data.get("trade_type", "buy"),
            quantity=quantity,
            price=price,
            total_value=total_value,
            platform=platform,
            commission=float(data.get("commission", commission)),
            timestamp=self._parse_timestamp(data.get("timestamp")) or datetime.now(UTC),
            profit=float(data["profit"]) if "profit" in data else None,
            profit_percent=(
                float(data["profit_percent"]) if "profit_percent" in data else None
            ),
            hold_time_hours=(
                float(data["hold_time_hours"]) if "hold_time_hours" in data else None
            ),
        )

    def _parse_timestamp(self, value: Any) -> datetime | None:
        """Parse timestamp from various formats."""
        if value is None:
            return None

        if isinstance(value, datetime):
            return value

        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                try:
                    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(
                        tzinfo=UTC
                    )
                except ValueError:
                    return None

        return None

    def export_to_csv(self, trades: list[Trade] | list[dict[str, Any]]) -> str:
        """Export trades to CSV."""
        output = io.StringIO()

        fieldnames = [
            "trade_id",
            "timestamp",
            "item_name",
            "trade_type",
            "quantity",
            "price",
            "total_value",
            "platform",
            "commission",
            "profit",
            "profit_percent",
        ]

        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()

        for trade in trades:
            if isinstance(trade, Trade):
                row = {
                    "trade_id": trade.trade_id,
                    "timestamp": trade.timestamp.isoformat(),
                    "item_name": trade.item_name,
                    "trade_type": trade.trade_type,
                    "quantity": trade.quantity,
                    "price": trade.price,
                    "total_value": trade.total_value,
                    "platform": trade.platform,
                    "commission": trade.commission,
                    "profit": trade.profit,
                    "profit_percent": trade.profit_percent,
                }
            else:
                row = {k: trade.get(k, "") for k in fieldnames}

            writer.writerow(row)

        return output.getvalue()

    def export_to_json(self, report: TradingReport, pretty: bool = True) -> str:
        """Export report to JSON."""
        data = report.to_dict()
        data["trades"] = [t.to_dict() for t in report.trades]

        if pretty:
            return json.dumps(data, indent=2)
        return json.dumps(data)

    def format_report(
        self,
        report: TradingReport,
        format_type: ReportFormat = ReportFormat.TEXT,
    ) -> str:
        """Format report for output."""
        if format_type == ReportFormat.TEXT:
            return report.to_text()
        if format_type == ReportFormat.MARKDOWN:
            return report.to_markdown()
        if format_type == ReportFormat.JSON:
            return self.export_to_json(report)
        if format_type == ReportFormat.CSV:
            return self.export_to_csv(report.trades)
        return report.to_text()


def create_report_generator() -> ReportGenerator:
    """Create report generator instance."""
    return ReportGenerator()
