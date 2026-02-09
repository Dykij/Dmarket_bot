"""High-Frequency Trading (HFT) mode for DMarket.

This module provides aggressive automated trading with:
- Configurable scan intervals (default: every 10 minutes)
- Automatic buy execution when arbitrage opportunity exceeds threshold
- Balance-stop mechanism to prevent overdrafts
- Circuit breaker for error protection
- Trade statistics tracking

Example:
    from src.dmarket.hft_mode import HighFrequencyTrader

    trader = HighFrequencyTrader(api_client, config)
    await trader.start()
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any

from src.dmarket.scanner.engine import ArbitrageScanner

logger = logging.getLogger(__name__)


class HFTStatus(StrEnum):
    """HFT trader status."""

    STOPPED = "stopped"
    RUNNING = "running"
    PAUSED = "paused"
    BALANCE_STOP = "balance_stop"
    ERROR_STOP = "error_stop"
    RATE_LIMITED = "rate_limited"


@dataclass
class HFTConfig:
    """High-Frequency Trading configuration.

    Attributes:
        enabled: Whether HFT mode is enabled
        scan_interval_minutes: Time between scans (default: 10 min)
        auto_buy_threshold_percent: Minimum profit % for auto-buy
        max_concurrent_orders: Maximum simultaneous orders
        orders_base: Budget per cycle in USD
        stop_orders_balance: Stop trading if balance below this (USD)
        max_consecutive_errors: Circuit breaker threshold
        rate_limit_pause_seconds: Pause on rate limit
        dry_run: Simulate trades without real execution
    """

    enabled: bool = False
    scan_interval_minutes: int = 10
    auto_buy_threshold_percent: float = 15.0
    max_concurrent_orders: int = 5
    orders_base: float = 20.0
    stop_orders_balance: float = 10.0
    max_consecutive_errors: int = 5
    rate_limit_pause_seconds: int = 60
    dry_run: bool = True
    games: list[str] = field(default_factory=lambda: ["csgo", "dota2"])
    arbitrage_level: str = "standard"


@dataclass
class TradeRecord:
    """Record of a single trade."""

    timestamp: datetime
    item_id: str
    item_name: str
    game: str
    buy_price: float
    expected_sell_price: float
    expected_profit: float
    profit_percent: float
    status: str  # "pending", "completed", "failed"
    dry_run: bool = False


@dataclass
class HFTStatistics:
    """HFT trading statistics."""

    total_trades: int = 0
    successful_trades: int = 0
    failed_trades: int = 0
    total_profit: float = 0.0
    total_spent: float = 0.0
    start_balance: float = 0.0
    current_balance: float = 0.0
    start_time: datetime | None = None
    last_scan_time: datetime | None = None
    trades: list[TradeRecord] = field(default_factory=list)

    @property
    def win_rate(self) -> float:
        """Calculate win rate percentage."""
        if self.total_trades == 0:
            return 0.0
        return (self.successful_trades / self.total_trades) * 100

    @property
    def average_profit(self) -> float:
        """Calculate average profit per trade."""
        if self.successful_trades == 0:
            return 0.0
        return self.total_profit / self.successful_trades

    @property
    def balance_change(self) -> float:
        """Calculate balance change since start."""
        return self.current_balance - self.start_balance

    @property
    def runtime_hours(self) -> float:
        """Calculate runtime in hours."""
        if not self.start_time:
            return 0.0
        delta = datetime.now() - self.start_time
        return delta.total_seconds() / 3600

    def get_trades_in_period(self, hours: int) -> list[TradeRecord]:
        """Get trades within specified period."""
        cutoff = datetime.now() - timedelta(hours=hours)
        return [t for t in self.trades if t.timestamp > cutoff]

    def get_stats_for_period(self, hours: int) -> dict[str, Any]:
        """Get statistics for specified period."""
        trades = self.get_trades_in_period(hours)
        successful = [t for t in trades if t.status == "completed"]
        failed = [t for t in trades if t.status == "failed"]

        return {
            "period_hours": hours,
            "total_trades": len(trades),
            "successful_trades": len(successful),
            "failed_trades": len(failed),
            "win_rate": (len(successful) / len(trades) * 100) if trades else 0,
            "total_profit": sum(t.expected_profit for t in successful),
            "total_spent": sum(t.buy_price for t in trades),
            "average_profit": (
                sum(t.expected_profit for t in successful) / len(successful) if successful else 0
            ),
        }


class HighFrequencyTrader:
    """High-Frequency Trading manager.

    Provides automated trading with configurable intervals and safety mechanisms.
    """

    def __init__(
        self,
        api_client: Any,
        config: HFTConfig | None = None,
        notifier: Any | None = None,
    ) -> None:
        """Initialize HFT trader.

        Args:
            api_client: DMarket API client
            config: HFT configuration
            notifier: Telegram notifier for alerts
        """
        self.api = api_client
        self.config = config or HFTConfig()
        self.notifier = notifier

        self.scanner = ArbitrageScanner(api_client)

        self.status = HFTStatus.STOPPED
        self.stats = HFTStatistics()
        self.consecutive_errors = 0
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

        logger.info(
            f"HFT Trader initialized: enabled={self.config.enabled}, "
            f"interval={self.config.scan_interval_minutes}min, "
            f"threshold={self.config.auto_buy_threshold_percent}%, "
            f"dry_run={self.config.dry_run}"
        )

    async def start(self) -> bool:
        """Start HFT trading loop.

        Returns:
            True if started successfully
        """
        if not self.config.enabled:
            logger.warning("HFT mode is disabled in config")
            return False

        if self.status == HFTStatus.RUNNING:
            logger.warning("HFT is already running")
            return False

        # Get initial balance
        balance_result = await self.api.get_balance()
        if isinstance(balance_result, dict) and balance_result.get("error"):
            logger.error(f"Failed to get initial balance: {balance_result}")
            return False

        # DMarket API returns "usd" key in lowercase, value in cents (as string or int)
        if isinstance(balance_result, dict):
            usd_cents = balance_result.get("usd", balance_result.get("USD", 0))
            # Handle string or int
            usd_cents = int(usd_cents) if usd_cents else 0
        else:
            usd_cents = 0
        self.stats.start_balance = usd_cents / 100.0
        self.stats.current_balance = self.stats.start_balance
        self.stats.start_time = datetime.now()

        # Check if balance is above stop threshold
        if not await self._check_balance():
            logger.error("Initial balance below stop threshold, cannot start HFT")
            return False

        self._stop_event.clear()
        self.status = HFTStatus.RUNNING
        self.consecutive_errors = 0

        self._task = asyncio.create_task(self._trading_loop())

        logger.info(
            f"🚀 HFT Started: balance=${self.stats.start_balance:.2f}, "
            f"threshold={self.config.auto_buy_threshold_percent}%"
        )

        if self.notifier:
            await self._send_notification(
                f"🚀 HFT режим запущен\n"
                f"💰 Баланс: ${self.stats.start_balance:.2f}\n"
                f"⏱️ Интервал: {self.config.scan_interval_minutes} мин\n"
                f"🎯 Порог: {self.config.auto_buy_threshold_percent}%"
            )

        return True

    async def stop(self) -> None:
        """Stop HFT trading loop."""
        if self.status == HFTStatus.STOPPED:
            return

        self._stop_event.set()

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None

        self.status = HFTStatus.STOPPED

        logger.info(
            f"🛑 HFT Stopped: trades={self.stats.total_trades}, "
            f"profit=${self.stats.total_profit:.2f}, "
            f"win_rate={self.stats.win_rate:.1f}%"
        )

        if self.notifier:
            await self._send_notification(
                f"🛑 HFT режим остановлен\n"
                f"📊 Сделок: {self.stats.total_trades}\n"
                f"💰 Прибыль: ${self.stats.total_profit:.2f}\n"
                f"📈 Win rate: {self.stats.win_rate:.1f}%"
            )

    async def pause(self) -> None:
        """Pause HFT trading."""
        if self.status == HFTStatus.RUNNING:
            self.status = HFTStatus.PAUSED
            logger.info("HFT Paused")

    async def resume(self) -> None:
        """Resume HFT trading."""
        if self.status == HFTStatus.PAUSED:
            self.status = HFTStatus.RUNNING
            logger.info("HFT Resumed")

    async def _trading_loop(self) -> None:
        """Main trading loop."""
        scan_interval = self.config.scan_interval_minutes * 60

        while not self._stop_event.is_set():
            try:
                if self.status != HFTStatus.RUNNING:
                    await asyncio.sleep(5)
                    continue

                # Check balance
                if not await self._check_balance():
                    self.status = HFTStatus.BALANCE_STOP
                    logger.warning("⚠️ Balance below threshold, HFT stopped")
                    if self.notifier:
                        await self._send_notification(
                            f"⚠️ HFT остановлен: баланс ниже порога\n"
                            f"💰 Текущий: ${self.stats.current_balance:.2f}\n"
                            f"📉 Порог: ${self.config.stop_orders_balance:.2f}"
                        )
                    break

                # Scan for opportunities
                await self._scan_and_trade()

                # Reset error counter on successful scan
                self.consecutive_errors = 0

                # Update last scan time
                self.stats.last_scan_time = datetime.now()

                # Wait for next scan
                await asyncio.sleep(scan_interval)

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.consecutive_errors += 1
                logger.exception(
                    f"HFT error ({self.consecutive_errors}/{self.config.max_consecutive_errors}): {e}"
                )

                # Circuit breaker
                if self.consecutive_errors >= self.config.max_consecutive_errors:
                    self.status = HFTStatus.ERROR_STOP
                    logger.exception("🔴 HFT Circuit breaker triggered!")
                    if self.notifier:
                        await self._send_notification(
                            f"🔴 HFT Circuit breaker!\n"
                            f"❌ {self.consecutive_errors} ошибок подряд\n"
                            f"Остановлено автоматически"
                        )
                    break

                # Check if rate limited
                if "429" in str(e) or "rate" in str(e).lower():
                    self.status = HFTStatus.RATE_LIMITED
                    logger.warning(
                        f"Rate limited, pausing for {self.config.rate_limit_pause_seconds}s"
                    )
                    await asyncio.sleep(self.config.rate_limit_pause_seconds)
                    self.status = HFTStatus.RUNNING
                else:
                    # Brief pause before retry
                    await asyncio.sleep(30)

    async def _check_balance(self) -> bool:
        """Check if balance is above stop threshold.

        Returns:
            True if balance is sufficient
        """
        try:
            balance_result = await self.api.get_balance()
            if isinstance(balance_result, dict) and balance_result.get("error"):
                logger.warning(f"Balance check failed: {balance_result}")
                return True  # Don't stop on balance check errors

            # DMarket API returns "usd" key in lowercase, value in cents
            if isinstance(balance_result, dict):
                usd_cents = balance_result.get(
                    "usd", balance_result.get("USD", balance_result.get("balance", 0))
                )
                usd_cents = int(usd_cents) if usd_cents else 0
            else:
                usd_cents = 0
            self.stats.current_balance = usd_cents / 100.0

            return self.stats.current_balance >= self.config.stop_orders_balance

        except Exception as e:
            logger.exception(f"Error checking balance: {e}")
            return True  # Don't stop on errors

    async def _scan_and_trade(self) -> None:
        """Scan for arbitrage and execute trades."""
        logger.info(f"🔍 HFT Scan: games={self.config.games}, level={self.config.arbitrage_level}")

        opportunities: list[dict[str, Any]] = []

        # Scan each game
        for game in self.config.games:
            try:
                results = await self.scanner.scan(
                    game=game,
                    level=self.config.arbitrage_level,
                )

                # Filter by profit threshold
                filtered = [
                    item
                    for item in results
                    if item.get("profit_percent", 0) >= self.config.auto_buy_threshold_percent
                ]

                opportunities.extend(filtered)

            except Exception as e:
                logger.warning(f"Scan error for {game}: {e}")

        if not opportunities:
            logger.info("No opportunities found above threshold")
            return

        # Sort by profit percent (highest first)
        opportunities.sort(key=lambda x: x.get("profit_percent", 0), reverse=True)

        # Limit to max concurrent orders
        to_buy = opportunities[: self.config.max_concurrent_orders]

        # Filter by budget
        budget = self.config.orders_base
        final_orders: list[dict[str, Any]] = []

        for item in to_buy:
            price = item.get("buy_price", 0)
            if price <= budget:
                final_orders.append(item)
                budget -= price

        logger.info(f"Found {len(opportunities)} opportunities, executing {len(final_orders)}")

        # Execute trades
        for item in final_orders:
            await self._execute_trade(item)

    async def _execute_trade(self, item: dict[str, Any]) -> bool:
        """Execute a single trade.

        Args:
            item: Arbitrage opportunity details

        Returns:
            True if trade was successful
        """
        item_id = item.get("item_id", "")
        item_name = item.get("title", "Unknown")
        game = item.get("game", "csgo")
        buy_price = item.get("buy_price", 0)
        sell_price = item.get("sell_price", 0)
        profit = item.get("profit", 0)
        profit_percent = item.get("profit_percent", 0)

        trade_record = TradeRecord(
            timestamp=datetime.now(),
            item_id=item_id,
            item_name=item_name,
            game=game,
            buy_price=buy_price,
            expected_sell_price=sell_price,
            expected_profit=profit,
            profit_percent=profit_percent,
            status="pending",
            dry_run=self.config.dry_run,
        )

        try:
            mode = "[DRY-RUN]" if self.config.dry_run else "[LIVE]"
            logger.info(
                f"{mode} 🛒 HFT Buy: {item_name} @ ${buy_price:.2f} "
                f"(profit: ${profit:.2f}, {profit_percent:.1f}%)"
            )

            # Execute buy
            result = await self.api.buy_item(
                item_id=item_id,
                price=buy_price,
                game=game,
                item_name=item_name,
                sell_price=sell_price,
                profit=profit,
                source="hft_mode",
            )

            if result.get("success") or result.get("dry_run"):
                trade_record.status = "completed"
                self.stats.successful_trades += 1
                self.stats.total_profit += profit
                logger.info(f"✅ HFT Buy successful: {item_name}")
            else:
                trade_record.status = "failed"
                self.stats.failed_trades += 1
                logger.warning(f"❌ HFT Buy failed: {item_name} - {result}")

        except Exception as e:
            trade_record.status = "failed"
            self.stats.failed_trades += 1
            logger.exception(f"❌ HFT Buy error: {item_name} - {e}")

        self.stats.total_trades += 1
        self.stats.total_spent += buy_price
        self.stats.trades.append(trade_record)

        return trade_record.status == "completed"

    async def _send_notification(self, message: str) -> None:
        """Send notification via Telegram.

        Args:
            message: Notification text
        """
        if self.notifier:
            try:
                # Assuming notifier has send_message method
                if hasattr(self.notifier, "send_message"):
                    await self.notifier.send_message(message)
                elif hasattr(self.notifier, "notify"):
                    await self.notifier.notify(message)
            except Exception as e:
                logger.warning(f"Failed to send HFT notification: {e}")

    def get_status(self) -> dict[str, Any]:
        """Get current HFT status.

        Returns:
            Status dictionary
        """
        return {
            "status": self.status.value,
            "enabled": self.config.enabled,
            "dry_run": self.config.dry_run,
            "scan_interval_minutes": self.config.scan_interval_minutes,
            "auto_buy_threshold": self.config.auto_buy_threshold_percent,
            "stop_balance": self.config.stop_orders_balance,
            "current_balance": self.stats.current_balance,
            "start_balance": self.stats.start_balance,
            "balance_change": self.stats.balance_change,
            "total_trades": self.stats.total_trades,
            "successful_trades": self.stats.successful_trades,
            "failed_trades": self.stats.failed_trades,
            "win_rate": self.stats.win_rate,
            "total_profit": self.stats.total_profit,
            "total_spent": self.stats.total_spent,
            "average_profit": self.stats.average_profit,
            "runtime_hours": self.stats.runtime_hours,
            "last_scan": (
                self.stats.last_scan_time.isoformat() if self.stats.last_scan_time else None
            ),
            "consecutive_errors": self.consecutive_errors,
        }

    def get_statistics(self, period_hours: int | None = None) -> dict[str, Any]:
        """Get trading statistics.

        Args:
            period_hours: Optional period filter (24, 168 for 7d, 720 for 30d)

        Returns:
            Statistics dictionary
        """
        if period_hours:
            return self.stats.get_stats_for_period(period_hours)

        return {
            "total_trades": self.stats.total_trades,
            "successful_trades": self.stats.successful_trades,
            "failed_trades": self.stats.failed_trades,
            "win_rate": self.stats.win_rate,
            "total_profit": self.stats.total_profit,
            "total_spent": self.stats.total_spent,
            "average_profit": self.stats.average_profit,
            "start_balance": self.stats.start_balance,
            "current_balance": self.stats.current_balance,
            "balance_change": self.stats.balance_change,
            "runtime_hours": self.stats.runtime_hours,
            "trades_24h": self.stats.get_stats_for_period(24),
            "trades_7d": self.stats.get_stats_for_period(168),
            "trades_30d": self.stats.get_stats_for_period(720),
        }


def load_hft_config_from_dict(config_dict: dict[str, Any]) -> HFTConfig:
    """Load HFT config from dictionary.

    Args:
        config_dict: Configuration dictionary

    Returns:
        HFTConfig instance
    """
    hft_section = config_dict.get("hft_mode", {})

    return HFTConfig(
        enabled=hft_section.get("enabled", False),
        scan_interval_minutes=hft_section.get("scan_interval_minutes", 10),
        auto_buy_threshold_percent=hft_section.get("auto_buy_threshold_percent", 15.0),
        max_concurrent_orders=hft_section.get("max_concurrent_orders", 5),
        orders_base=hft_section.get("orders_base", 20.0),
        stop_orders_balance=hft_section.get("stop_orders_balance", 10.0),
        max_consecutive_errors=hft_section.get("max_consecutive_errors", 5),
        rate_limit_pause_seconds=hft_section.get("rate_limit_pause_seconds", 60),
        dry_run=hft_section.get("dry_run", True),
        games=hft_section.get("games", ["csgo", "dota2"]),
        arbitrage_level=hft_section.get("arbitrage_level", "standard"),
    )
