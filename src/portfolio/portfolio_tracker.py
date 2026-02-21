"""Portfolio Tracking Module.

Track user inventory, profit/loss, and trading performance across marketplaces.

Features:
- Inventory tracking across DMarket and Waxpeer
- Profit/Loss calculation with commission consideration
- Historical performance analysis
- Portfolio valuation
- Trade journaling

Usage:
    ```python
    from src.portfolio.portfolio_tracker import PortfolioTracker

    tracker = PortfolioTracker(
        dmarket_api=dmarket_api,
        waxpeer_api=waxpeer_api,
    )

    # Get portfolio summary
    summary = await tracker.get_portfolio_summary()
    print(f"Total Value: ${summary.total_value}")
    print(f"Total P/L: ${summary.total_pnl}")
    ```

Created: January 10, 2026
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI
    from src.waxpeer.waxpeer_api import WaxpeerAPI


logger = structlog.get_logger(__name__)


class TradeType(StrEnum):
    """Type of trade."""

    BUY = "buy"
    SELL = "sell"
    TRANSFER = "transfer"


class Marketplace(StrEnum):
    """Supported marketplaces."""

    DMARKET = "dmarket"
    WAXPEER = "waxpeer"
    STEAM = "steam"


@dataclass
class Trade:
    """A single trade record."""

    trade_id: str
    item_name: str
    trade_type: TradeType
    marketplace: Marketplace
    price: Decimal
    commission: Decimal
    net_amount: Decimal  # After commission
    timestamp: datetime
    item_id: str | None = None
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "trade_id": self.trade_id,
            "item_name": self.item_name,
            "type": self.trade_type.value,
            "marketplace": self.marketplace.value,
            "price": str(self.price),
            "commission": str(self.commission),
            "net_amount": str(self.net_amount),
            "timestamp": self.timestamp.isoformat(),
            "notes": self.notes,
        }


@dataclass
class InventoryItem:
    """An item in the portfolio."""

    item_id: str
    item_name: str
    marketplace: Marketplace
    purchase_price: Decimal
    current_price: Decimal
    quantity: int = 1
    acquired_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def unrealized_pnl(self) -> Decimal:
        """Calculate unrealized P/L."""
        return (self.current_price - self.purchase_price) * self.quantity

    @property
    def unrealized_pnl_percent(self) -> Decimal:
        """Calculate unrealized P/L percentage."""
        if self.purchase_price == 0:
            return Decimal(0)
        return (self.unrealized_pnl / (self.purchase_price * self.quantity)) * 100

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_id": self.item_id,
            "item_name": self.item_name,
            "marketplace": self.marketplace.value,
            "purchase_price": str(self.purchase_price),
            "current_price": str(self.current_price),
            "quantity": self.quantity,
            "unrealized_pnl": str(self.unrealized_pnl),
            "unrealized_pnl_percent": str(round(self.unrealized_pnl_percent, 2)),
            "acquired_at": self.acquired_at.isoformat(),
        }


@dataclass
class PortfolioSummary:
    """Portfolio summary."""

    total_value: Decimal
    total_cost: Decimal
    total_pnl: Decimal
    total_pnl_percent: Decimal
    realized_pnl: Decimal
    unrealized_pnl: Decimal
    total_items: int
    total_trades: int
    win_rate: Decimal  # Percentage of profitable trades
    avg_trade_pnl: Decimal
    best_trade: Trade | None
    worst_trade: Trade | None
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "total_value": str(self.total_value),
            "total_cost": str(self.total_cost),
            "total_pnl": str(self.total_pnl),
            "total_pnl_percent": str(round(self.total_pnl_percent, 2)),
            "realized_pnl": str(self.realized_pnl),
            "unrealized_pnl": str(self.unrealized_pnl),
            "total_items": self.total_items,
            "total_trades": self.total_trades,
            "win_rate": str(round(self.win_rate, 2)),
            "avg_trade_pnl": str(self.avg_trade_pnl),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class PerformanceMetrics:
    """Trading performance metrics."""

    period_start: datetime
    period_end: datetime
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_volume: Decimal
    total_pnl: Decimal
    best_day_pnl: Decimal
    worst_day_pnl: Decimal
    avg_hold_time: timedelta
    profit_factor: Decimal  # Gross profit / Gross loss
    sharpe_ratio: Decimal | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "period_start": self.period_start.isoformat(),
            "period_end": self.period_end.isoformat(),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "win_rate": (
                round(self.winning_trades / self.total_trades * 100, 2)
                if self.total_trades > 0
                else 0
            ),
            "total_volume": str(self.total_volume),
            "total_pnl": str(self.total_pnl),
            "best_day_pnl": str(self.best_day_pnl),
            "worst_day_pnl": str(self.worst_day_pnl),
            "avg_hold_time_hours": round(self.avg_hold_time.total_seconds() / 3600, 2),
            "profit_factor": str(round(self.profit_factor, 2)),
        }


class PortfolioTracker:
    """Portfolio tracking and performance analysis."""

    # Commission rates
    COMMISSIONS = {
        Marketplace.DMARKET: Decimal("0.07"),  # 7%
        Marketplace.WAXPEER: Decimal("0.06"),  # 6%
        Marketplace.STEAM: Decimal("0.15"),  # ~15%
    }

    def __init__(
        self,
        dmarket_api: DMarketAPI | None = None,
        waxpeer_api: WaxpeerAPI | None = None,
        user_id: int | None = None,
    ) -> None:
        """Initialize portfolio tracker.

        Args:
            dmarket_api: DMarket API client
            waxpeer_api: Waxpeer API client
            user_id: User ID for multi-user support
        """
        self.dmarket = dmarket_api
        self.waxpeer = waxpeer_api
        self.user_id = user_id

        # In-memory storage (replace with database in production)
        self._inventory: dict[str, InventoryItem] = {}
        self._trades: list[Trade] = []
        self._trade_counter = 0

    async def sync_inventory(self) -> int:
        """Sync inventory from all marketplaces.

        Returns:
            Number of items synced
        """
        synced = 0

        # Sync DMarket
        if self.dmarket:
            try:
                inventory = await self.dmarket.get_user_inventory()
                for item in inventory.get("items", []):
                    item_id = item.get("itemId", "")
                    title = item.get("title", "")
                    price_cents = int(item.get("price", {}).get("USD", "0"))
                    price = Decimal(str(price_cents)) / 100

                    if item_id not in self._inventory:
                        self._inventory[item_id] = InventoryItem(
                            item_id=item_id,
                            item_name=title,
                            marketplace=Marketplace.DMARKET,
                            purchase_price=price,  # Use current as purchase if unknown
                            current_price=price,
                        )
                    else:
                        self._inventory[item_id].current_price = price

                    synced += 1
            except Exception as e:
                logger.exception("portfolio_sync_dmarket_error", error=str(e))

        # Sync Waxpeer
        if self.waxpeer:
            try:
                items = await self.waxpeer.get_my_items()
                for item in items:
                    item_id = item.item_id
                    if item_id not in self._inventory:
                        self._inventory[item_id] = InventoryItem(
                            item_id=item_id,
                            item_name=item.name,
                            marketplace=Marketplace.WAXPEER,
                            purchase_price=item.price,
                            current_price=item.price,
                        )
                    else:
                        self._inventory[item_id].current_price = item.price

                    synced += 1
            except Exception as e:
                logger.exception("portfolio_sync_waxpeer_error", error=str(e))

        logger.info("portfolio_synced", items_count=synced)
        return synced

    def record_trade(
        self,
        item_name: str,
        trade_type: TradeType,
        marketplace: Marketplace,
        price: Decimal,
        item_id: str | None = None,
        notes: str | None = None,
    ) -> Trade:
        """Record a trade.

        Args:
            item_name: Item name
            trade_type: Buy or sell
            marketplace: Marketplace
            price: Trade price
            item_id: Optional item ID
            notes: Optional notes

        Returns:
            Trade record
        """
        self._trade_counter += 1
        trade_id = f"T{self._trade_counter:06d}"

        commission_rate = self.COMMISSIONS.get(marketplace, Decimal(0))

        if trade_type == TradeType.SELL:
            commission = price * commission_rate
            net_amount = price - commission
        else:
            commission = Decimal(0)
            net_amount = price

        trade = Trade(
            trade_id=trade_id,
            item_name=item_name,
            trade_type=trade_type,
            marketplace=marketplace,
            price=price,
            commission=commission,
            net_amount=net_amount,
            timestamp=datetime.now(UTC),
            item_id=item_id,
            notes=notes,
        )

        self._trades.append(trade)

        # Update inventory
        if trade_type == TradeType.BUY and item_id:
            self._inventory[item_id] = InventoryItem(
                item_id=item_id,
                item_name=item_name,
                marketplace=marketplace,
                purchase_price=price,
                current_price=price,
            )
        elif trade_type == TradeType.SELL and item_id and item_id in self._inventory:
            del self._inventory[item_id]

        logger.info(
            "trade_recorded",
            trade_id=trade_id,
            item=item_name,
            type=trade_type.value,
            price=str(price),
        )

        return trade

    def record_buy(
        self,
        item_name: str,
        price: Decimal,
        marketplace: Marketplace = Marketplace.DMARKET,
        item_id: str | None = None,
    ) -> Trade:
        """Record a buy trade.

        Args:
            item_name: Item name
            price: Purchase price
            marketplace: Marketplace
            item_id: Item ID

        Returns:
            Trade record
        """
        return self.record_trade(
            item_name=item_name,
            trade_type=TradeType.BUY,
            marketplace=marketplace,
            price=price,
            item_id=item_id,
        )

    def record_sell(
        self,
        item_name: str,
        price: Decimal,
        marketplace: Marketplace = Marketplace.WAXPEER,
        item_id: str | None = None,
    ) -> Trade:
        """Record a sell trade.

        Args:
            item_name: Item name
            price: Sale price
            marketplace: Marketplace
            item_id: Item ID

        Returns:
            Trade record
        """
        return self.record_trade(
            item_name=item_name,
            trade_type=TradeType.SELL,
            marketplace=marketplace,
            price=price,
            item_id=item_id,
        )

    def get_inventory(self) -> list[InventoryItem]:
        """Get current inventory.

        Returns:
            List of inventory items
        """
        return list(self._inventory.values())

    def get_trades(
        self,
        limit: int = 100,
        trade_type: TradeType | None = None,
        marketplace: Marketplace | None = None,
    ) -> list[Trade]:
        """Get trade history.

        Args:
            limit: Maximum trades to return
            trade_type: Filter by type
            marketplace: Filter by marketplace

        Returns:
            List of trades
        """
        trades = self._trades.copy()

        if trade_type:
            trades = [t for t in trades if t.trade_type == trade_type]

        if marketplace:
            trades = [t for t in trades if t.marketplace == marketplace]

        return sorted(trades, key=lambda t: t.timestamp, reverse=True)[:limit]

    def calculate_realized_pnl(self) -> Decimal:
        """Calculate realized P/L from completed trades.

        Returns:
            Realized P/L
        """
        buys: dict[str, list[Trade]] = {}
        pnl = Decimal(0)

        for trade in sorted(self._trades, key=lambda t: t.timestamp):
            if trade.trade_type == TradeType.BUY:
                if trade.item_name not in buys:
                    buys[trade.item_name] = []
                buys[trade.item_name].append(trade)
            elif trade.trade_type == TradeType.SELL:
                if buys.get(trade.item_name):
                    buy_trade = buys[trade.item_name].pop(0)  # FIFO
                    pnl += trade.net_amount - buy_trade.price

        return pnl

    def calculate_unrealized_pnl(self) -> Decimal:
        """Calculate unrealized P/L from inventory.

        Returns:
            Unrealized P/L
        """
        return sum(item.unrealized_pnl for item in self._inventory.values())

    async def get_portfolio_summary(self) -> PortfolioSummary:
        """Get portfolio summary.

        Returns:
            Portfolio summary
        """
        # Sync inventory first
        await self.sync_inventory()

        total_value = sum(
            item.current_price * item.quantity for item in self._inventory.values()
        )
        total_cost = sum(
            item.purchase_price * item.quantity for item in self._inventory.values()
        )
        realized_pnl = self.calculate_realized_pnl()
        unrealized_pnl = self.calculate_unrealized_pnl()
        total_pnl = realized_pnl + unrealized_pnl

        total_pnl_percent = (
            (total_pnl / total_cost * 100) if total_cost > 0 else Decimal(0)
        )

        # Calculate win rate
        sells = [t for t in self._trades if t.trade_type == TradeType.SELL]
        winning_trades = 0
        total_trade_pnl = Decimal(0)

        for sell in sells:
            # Find corresponding buy
            buys = [
                b
                for b in self._trades
                if b.trade_type == TradeType.BUY
                and b.item_name == sell.item_name
                and b.timestamp < sell.timestamp
            ]
            if buys:
                buy = buys[-1]
                trade_pnl = sell.net_amount - buy.price
                total_trade_pnl += trade_pnl
                if trade_pnl > 0:
                    winning_trades += 1

        win_rate = (
            (Decimal(str(winning_trades)) / Decimal(str(len(sells))) * 100)
            if sells
            else Decimal(0)
        )
        avg_trade_pnl = total_trade_pnl / len(sells) if sells else Decimal(0)

        # Find best/worst trades
        best_trade = None
        worst_trade = None
        if self._trades:
            best_trade = max(self._trades, key=lambda t: t.net_amount)
            worst_trade = min(self._trades, key=lambda t: t.net_amount)

        return PortfolioSummary(
            total_value=total_value,
            total_cost=total_cost,
            total_pnl=total_pnl,
            total_pnl_percent=total_pnl_percent,
            realized_pnl=realized_pnl,
            unrealized_pnl=unrealized_pnl,
            total_items=len(self._inventory),
            total_trades=len(self._trades),
            win_rate=win_rate,
            avg_trade_pnl=avg_trade_pnl,
            best_trade=best_trade,
            worst_trade=worst_trade,
        )

    def get_performance_metrics(
        self,
        days: int = 30,
    ) -> PerformanceMetrics:
        """Get trading performance metrics.

        Args:
            days: Number of days to analyze

        Returns:
            Performance metrics
        """
        period_end = datetime.now(UTC)
        period_start = period_end - timedelta(days=days)

        # Filter trades in period
        period_trades = [
            t for t in self._trades if period_start <= t.timestamp <= period_end
        ]

        if not period_trades:
            return PerformanceMetrics(
                period_start=period_start,
                period_end=period_end,
                total_trades=0,
                winning_trades=0,
                losing_trades=0,
                total_volume=Decimal(0),
                total_pnl=Decimal(0),
                best_day_pnl=Decimal(0),
                worst_day_pnl=Decimal(0),
                avg_hold_time=timedelta(0),
                profit_factor=Decimal(0),
            )

        # Calculate metrics
        total_volume = sum(t.price for t in period_trades)
        gross_profit = Decimal(0)
        gross_loss = Decimal(0)
        winning = 0
        losing = 0

        daily_pnl: dict[str, Decimal] = {}
        hold_times: list[timedelta] = []

        sells = [t for t in period_trades if t.trade_type == TradeType.SELL]
        for sell in sells:
            # Find buy
            buys = [
                b
                for b in self._trades
                if b.trade_type == TradeType.BUY
                and b.item_name == sell.item_name
                and b.timestamp < sell.timestamp
            ]
            if buys:
                buy = buys[-1]
                pnl = sell.net_amount - buy.price
                hold_times.append(sell.timestamp - buy.timestamp)

                date_key = sell.timestamp.date().isoformat()
                daily_pnl[date_key] = daily_pnl.get(date_key, Decimal(0)) + pnl

                if pnl > 0:
                    gross_profit += pnl
                    winning += 1
                else:
                    gross_loss += abs(pnl)
                    losing += 1

        total_pnl = gross_profit - gross_loss
        profit_factor = gross_profit / gross_loss if gross_loss > 0 else gross_profit
        avg_hold_time = (
            sum(hold_times, timedelta()) / len(hold_times)
            if hold_times
            else timedelta(0)
        )

        best_day = max(daily_pnl.values()) if daily_pnl else Decimal(0)
        worst_day = min(daily_pnl.values()) if daily_pnl else Decimal(0)

        return PerformanceMetrics(
            period_start=period_start,
            period_end=period_end,
            total_trades=len(period_trades),
            winning_trades=winning,
            losing_trades=losing,
            total_volume=total_volume,
            total_pnl=total_pnl,
            best_day_pnl=best_day,
            worst_day_pnl=worst_day,
            avg_hold_time=avg_hold_time,
            profit_factor=profit_factor,
        )

    def export_trades(self, output_format: str = "dict") -> list[dict[str, Any]]:
        """Export trade history.

        Args:
            output_format: Export format (dict, csv)

        Returns:
            Trade data
        """
        return [t.to_dict() for t in self._trades]

    def clear_history(self) -> None:
        """Clear trade history (for testing)."""
        self._trades.clear()
        self._inventory.clear()
        self._trade_counter = 0


# Factory function
def create_portfolio_tracker(
    dmarket_api: DMarketAPI | None = None,
    waxpeer_api: WaxpeerAPI | None = None,
) -> PortfolioTracker:
    """Create portfolio tracker.

    Args:
        dmarket_api: DMarket API client
        waxpeer_api: Waxpeer API client

    Returns:
        PortfolioTracker instance
    """
    return PortfolioTracker(
        dmarket_api=dmarket_api,
        waxpeer_api=waxpeer_api,
    )
