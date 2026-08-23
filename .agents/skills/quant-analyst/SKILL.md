---
name: quant-analyst
description: Quantitative analysis patterns for trading strategies. Use when designing, backtesting, or optimizing trading algorithms — Kelly criterion, VaR, Sharpe ratio, trend detection, position sizing, risk metrics.
---

# Quant Analyst — Trading Strategy Patterns

## When to Use
- Designing or modifying trading strategy parameters
- Calculating position sizes (Kelly criterion)
- Evaluating strategy performance (Sharpe, Sortino, max drawdown)
- Implementing trend guards or filters
- Backtesting strategies against historical data

## Core Concepts in This Bot

### Kelly Criterion (Half-Kelly)
```python
def half_kelly_size(win_rate: float, avg_win: float, avg_loss: float) -> float:
    """Position size using Half Kelly (50% Kelly fraction)."""
    kelly = (win_rate * avg_win - (1 - win_rate) * avg_loss) / avg_win
    return max(0, kelly * 0.5)  # Half Kelly for safety
```

### Dynamic Max Price
```python
def dynamic_max_price(effective_balance: float, floor: float = 5.0) -> float:
    """Max item price = max($5 floor, effective_balance × 10%)."""
    return max(floor, effective_balance * 0.10)
```

### Drawdown Freeze
```python
def is_drawdown_frozen(current_balance: float, peak_balance: float, threshold: float = 0.85) -> bool:
    """Freeze buying if balance drops below 85% of peak."""
    return current_balance < peak_balance * threshold
```

### Trend Guard
```python
def detect_downtrend(prices: list[float], window: int = 20) -> bool:
    """Reject items in sustained downtrend."""
    if len(prices) < window:
        return False
    sma = sum(prices[-window:]) / window
    return prices[-1] < sma * 0.95  # 5% below SMA = downtrend
```

## Key Metrics to Track
- **Win Rate**: % of profitable trades (target: >60%)
- **Average Win / Average Loss**: Profit factor (target: >1.5)
- **Sharpe Ratio**: Risk-adjusted return (target: >1.0)
- **Max Drawdown**: Worst peak-to-trough (alert if >15%)
- **Daily P&L**: Track daily profit/loss for trend analysis
- **Trade Frequency**: Trades per hour (avoid overtrading)

## Strategy Validation Checklist
- [ ] Positive expected value (EV > 0)
- [ ] Win rate × avg_win > loss_rate × avg_loss
- [ ] Max position size < 10% effective balance
- [ ] Drawdown threshold configured (85% of peak)
- [ ] Trend guard active (reject downtrend items)
- [ ] Rate limiting respected (API quota)
- [ ] Slippage accounted for (spread < threshold)

## Anti-Patterns
- Overfitting to historical data (curve fitting)
- Ignoring fees in profit calculations
- No position sizing (flat betting)
- Chasing losses (increasing size after drawdown)
- No stop-loss or exit strategy
