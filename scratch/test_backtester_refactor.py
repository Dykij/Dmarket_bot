"""Smoke test for refactored backtester package — runs an actual backtest."""

import sys
import os
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.analytics.backtester import (
    Backtester,
    BacktestResult,
    Position,
    SimpleArbitrageStrategy,
    Trade,
    TradeType,
    TradingStrategy,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
)
from src.analytics.backtester import engine, models, strategies, metrics


# --- Fake PriceHistory for testing ---
class FakePricePoint:
    def __init__(self, price, timestamp):
        self.price = Decimal(str(price))
        self.timestamp = timestamp


class FakePriceHistory:
    """Minimal stand-in for src.analytics.historical_data.PriceHistory."""

    def __init__(self, title, points):
        self.title = title
        self.points = [FakePricePoint(p, t) for p, t in points]
        self.average_price = (
            sum(p.price for p in self.points) / len(self.points) if self.points else Decimal(0)
        )


def test_imports():
    assert Backtester is engine.Backtester
    assert BacktestResult is models.BacktestResult
    assert Position is models.Position
    assert Trade is models.Trade
    assert TradeType is models.TradeType
    assert TradingStrategy is strategies.TradingStrategy
    assert SimpleArbitrageStrategy is strategies.SimpleArbitrageStrategy
    assert calculate_max_drawdown is metrics.calculate_max_drawdown
    assert calculate_sharpe_ratio is metrics.calculate_sharpe_ratio
    print("[OK] all imports work")


def test_models_dataclasses():
    """Trade, Position, BacktestResult properties."""
    # Trade
    t = Trade(
        trade_type=TradeType.BUY,
        item_title="AK-47 | Redline",
        price=Decimal("10.00"),
        quantity=2,
        timestamp=datetime(2026, 6, 1),
        fees=Decimal("0.50"),
    )
    assert t.total_cost == Decimal("20.50")
    assert t.net_amount == Decimal("-20.50")

    s = Trade(
        trade_type=TradeType.SELL,
        item_title="AK-47 | Redline",
        price=Decimal("11.00"),
        quantity=2,
        timestamp=datetime(2026, 6, 1),
        fees=Decimal("0.50"),
    )
    assert s.net_amount == Decimal("21.50")  # 11*2 - 0.50

    # Position
    p = Position(
        item_title="AK-47 | Redline",
        quantity=2,
        average_cost=Decimal("10.00"),
        created_at=datetime(2026, 6, 1),
    )
    assert p.total_value == Decimal("20.00")
    p.update(2, Decimal("12.00"))
    assert p.quantity == 4
    assert p.average_cost == Decimal("11.00")  # (10*2 + 12*2) / 4
    print("[OK] models: Trade + Position + properties")


def test_metrics_drawdown():
    """Max drawdown calculation."""
    # Up only → 0% drawdown
    hist = [Decimal(str(x)) for x in [100, 110, 120, 130]]
    assert calculate_max_drawdown(hist) == Decimal(0)

    # Down after peak
    hist = [Decimal("100"), Decimal("120"), Decimal("90"), Decimal("95")]
    dd = calculate_max_drawdown(hist)
    assert dd > 0
    # Peak = 120, trough = 90 → drawdown = (120-90)/120 * 100 = 25%
    assert abs(dd - Decimal("25")) < Decimal("0.01")

    # Edge cases
    assert calculate_max_drawdown([Decimal("100")]) == Decimal(0)
    assert calculate_max_drawdown([]) == Decimal(0)
    print("[OK] metrics: max_drawdown (up-only, peak→trough, edges)")


def test_metrics_sharpe():
    """Sharpe ratio calculation."""
    hist = [Decimal(str(x)) for x in [100, 101, 102, 101, 100, 102]]
    sharpe = calculate_sharpe_ratio(hist)
    assert isinstance(sharpe, float)
    # Edge case
    assert calculate_sharpe_ratio([Decimal("100")]) == 0.0
    assert calculate_sharpe_ratio([]) == 0.0
    # Constant history → std dev = 0 → sharpe = 0
    assert calculate_sharpe_ratio([Decimal("100")] * 10) == 0.0
    print(f"[OK] metrics: sharpe_ratio (sample={sharpe:.2f})")


def test_simple_arbitrage_strategy():
    """SimpleArbitrageStrategy decision logic."""
    strat = SimpleArbitrageStrategy(
        buy_threshold=0.10,  # Buy when 10% below average
        sell_margin=0.05,
        max_position_pct=0.5,
    )

    # History with average = 10
    hist = FakePriceHistory("Test", [
        (10, datetime(2026, 1, 1)),
        (10, datetime(2026, 1, 2)),
        (10, datetime(2026, 1, 3)),
    ])

    # Price = 8 → 20% below avg → should buy
    should_buy, price, qty = strat.should_buy(hist, Decimal("8"), Decimal("100"), {})
    assert should_buy
    assert price == Decimal("8")
    assert qty > 0

    # Price = 9.5 → 5% below avg (less than 10% threshold) → should NOT buy
    should_buy, _, _ = strat.should_buy(hist, Decimal("9.5"), Decimal("100"), {})
    assert not should_buy

    # Position: average_cost = 8, sell_margin = 5%, fee = 7%
    # target = 8 * 1.12 = 8.96
    pos = Position("Test", 1, Decimal("8"), datetime(2026, 1, 1))
    should_sell, _, _ = strat.should_sell(hist, Decimal("9.0"), pos)
    assert should_sell

    # Stop-loss at -10% from 8 = 7.20
    should_sell, _, _ = strat.should_sell(hist, Decimal("7.0"), pos)
    assert should_sell

    # No signal at 8.5 (between 7.20 and 8.96)
    should_sell, _, _ = strat.should_sell(hist, Decimal("8.5"), pos)
    assert not should_sell

    print("[OK] strategies: SimpleArbitrage buy/sell/stop-loss")


def test_backtester_runs():
    """Run a real backtest end-to-end."""
    start = datetime(2026, 1, 1)
    end = datetime(2026, 1, 30)

    # Create a price history that swings: down, up, down, up
    points = []
    base = 10.0
    for i in range(30):
        # Day 0-9: down, Day 10-19: up, Day 20-29: down
        if i < 10:
            price = base - i * 0.3  # Going down
        elif i < 20:
            price = base - 2.7 + (i - 10) * 0.3  # Going up
        else:
            price = base + 0.3 - (i - 20) * 0.3  # Going down
        ts = start + timedelta(days=i)
        points.append((price, ts))

    history = FakePriceHistory("TestItem", points)
    price_histories = {"TestItem": history}

    strategy = SimpleArbitrageStrategy(
        buy_threshold=0.05, sell_margin=0.05, max_position_pct=0.5
    )
    backtester = Backtester(fee_rate=0.07)

    async def run():
        return await backtester.run(
            strategy=strategy,
            price_histories=price_histories,
            start_date=start,
            end_date=end,
            initial_balance=Decimal("1000"),
        )

    result = asyncio.run(run())

    assert isinstance(result, BacktestResult)
    assert result.strategy_name == "SimpleArbitrage"
    assert result.initial_balance == Decimal("1000")
    assert result.sharpe_ratio >= 0  # Always non-negative
    assert result.max_drawdown >= 0
    assert 0 <= result.win_rate <= 100
    assert result.to_dict()["strategy_name"] == "SimpleArbitrage"

    print(
        f"[OK] backtester.run: trades={result.total_trades}, "
        f"profit={result.total_profit}, win_rate={result.win_rate:.1f}%, "
        f"max_dd={result.max_drawdown:.2f}%, sharpe={result.sharpe_ratio:.2f}"
    )


def test_abstract_strategy():
    """TradingStrategy cannot be instantiated directly."""
    try:
        TradingStrategy()
        assert False, "Should have raised TypeError"
    except TypeError:
        pass

    # Subclass without implementing abstract methods also fails
    class IncompleteStrategy(TradingStrategy):
        pass

    try:
        IncompleteStrategy()
        assert False, "Should have raised TypeError"
    except TypeError:
        pass

    print("[OK] strategies: TradingStrategy is properly abstract")


if __name__ == "__main__":
    test_imports()
    test_models_dataclasses()
    test_metrics_drawdown()
    test_metrics_sharpe()
    test_simple_arbitrage_strategy()
    test_backtester_runs()
    test_abstract_strategy()
    print("\n[ALL PASS] backtester refactor: 7/7 smoke tests passed")
