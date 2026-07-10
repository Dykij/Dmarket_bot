"""
price_validator.py — Strict price sanity checks (V3 hardening).

Blocks Data Poisoning attacks by rejecting prices outside the
sane CS2 market range BEFORE execution.
"""

import math

MIN_PRICE_USD = 0.10
MAX_PRICE_USD = 50000.0


class PriceValidationError(Exception):
    """Raised when a price fails sanity checks."""
    pass


def validate_price(
    price: float | int | str,
    label: str = "price",
) -> float:
    """Validate and coerce a price value to a safe float."""
    try:
        value = float(price)
    except (ValueError, TypeError) as e:
        raise PriceValidationError(
            f"[V3] {label}={price!r} is not a valid number: {e}"
        )

    if math.isnan(value) or math.isinf(value):
        raise PriceValidationError(
            f"[V3] {label}={value} is NaN or Inf — rejected."
        )

    if value < 0:
        raise PriceValidationError(
            f"[V3] {label}=${value:.4f} is negative — rejected."
        )

    if value < MIN_PRICE_USD:
        raise PriceValidationError(
            f"[V3] {label}=${value:.4f} below floor ${MIN_PRICE_USD:.2f}. "
            f"Possible bait listing."
        )

    if value > MAX_PRICE_USD:
        raise PriceValidationError(
            f"[V3] {label}=${value:.2f} above ceiling ${MAX_PRICE_USD:,.0f}. "
            f"Anomalous price rejected."
        )

    return value


def validate_arbitrage_profit(
    buy_price: float,
    expected_sell_price: float,
    fee_markup: float = 0.05,
    min_profit_margin: float = 0.05,
    lock_days: int = 7,
    penalty_per_day: float = 0.005,
) -> float:
    """Validate arbitrage trade is profitable after fees and TVM penalty."""
    if buy_price <= 0:
        raise PriceValidationError(
            f"Buy price must be > 0, got ${buy_price:.2f}"
        )

    net_received = expected_sell_price * (1.0 - fee_markup)
    actual_profit = net_received - buy_price

    if actual_profit <= 0:
        raise PriceValidationError(
            f"Absolute LOSS Trade Detected: Buy ${buy_price:.2f}, Sell ${expected_sell_price:.2f} "
            f"(Fee: {fee_markup*100:.1f}%). Blocked."
        )

    profit_margin_pct = actual_profit / buy_price
    tvm_adjusted_margin = profit_margin_pct - (penalty_per_day * lock_days)

    if tvm_adjusted_margin < min_profit_margin:
        raise PriceValidationError(
            f"Insufficient TVM-Adjusted Margin: Raw {profit_margin_pct*100:.2f}% -> "
            f"TVM Adj {tvm_adjusted_margin*100:.2f}% is below threshold {min_profit_margin*100:.2f}%. "
            f"Blocked (7-day lock penalty applied)."
        )

    return tvm_adjusted_margin


def validate_slippage(
    target_price: float,
    current_market_price: float,
    max_slippage_pct: float = 0.02,
) -> None:
    """Slippage Control — ensures price hasn't shifted significantly."""
    if current_market_price <= 0:
        raise PriceValidationError("Market price is invalid (<=0).")
    if target_price <= 0:
        raise PriceValidationError(
            f"Target price is invalid (<=0): {target_price}"
        )

    slippage = abs(current_market_price - target_price) / target_price
    if slippage > max_slippage_pct:
        raise PriceValidationError(
            f"Slippage Exceeded: Market price {current_market_price} drifted from target {target_price} "
            f"by {slippage*100:.2f}% (Max {max_slippage_pct*100:.2f}%). Blocked."
        )


def validate_volatility(
    recent_prices: list[float],
    max_std_dev_pct: float = 0.15,
) -> None:
    """Volatility Check — blocks extremely volatile assets."""
    if not recent_prices or len(recent_prices) < 3:
        return

    prices = [float(p) for p in recent_prices]

    returns = []
    for i in range(1, len(prices)):
        if prices[i - 1] > 0:
            ret = (prices[i] - prices[i - 1]) / prices[i - 1]
            returns.append(ret)

    if len(returns) < 2:
        return

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_dev = math.sqrt(variance)

    if std_dev > max_std_dev_pct:
        raise PriceValidationError(
            f"High Volatility Detected: Returns StdDev is {std_dev*100:.1f}%. "
            f"Asset is unstable. Blocked."
        )
