"""
price_validator.py — Strict price sanity checks (V3 hardening).

Blocks Data Poisoning attacks by rejecting prices outside the
sane CS2 market range BEFORE execution.

Handles:
- Scientific notation strings ("1e5")
- Negative prices
- Extreme outliers (< $0.10 or > $50,000)
- Non-numeric / NaN / Inf values
"""

import math
from typing import Union

MIN_PRICE_USD = 0.10
MAX_PRICE_USD = 50_000.00


class PriceValidationError(Exception):
    """Raised when a price fails sanity checks."""
    pass


def validate_price(
    price: Union[float, int, str],
    label: str = "price",
) -> float:
    """
    Validate and coerce a price value to a safe float.

    Parameters
    ----------
    price : float | int | str
        Raw price value from the API. May be float, int, or string
        (including scientific notation like "1e5").
    label : str
        Human-readable label for error messages (e.g., "best_ask").

    Returns
    -------
    float
        The validated price in USD.

    Raises
    ------
    PriceValidationError
        If the price is outside [$0.10, $50,000], NaN, Inf,
        negative, or not parseable as a number.
    """
    # Coerce to float safely
    try:
        value = float(price)
    except (ValueError, TypeError) as e:
        raise PriceValidationError(
            f"[V3] {label}={price!r} is not a valid number: {e}"
        )

    # Reject NaN / Inf
    if math.isnan(value) or math.isinf(value):
        raise PriceValidationError(
            f"[V3] {label}={value} is NaN or Inf — rejected."
        )

    # Reject negative
    if value < 0:
        raise PriceValidationError(
            f"[V3] {label}=${value:.4f} is negative — rejected."
        )

    # Floor / ceiling
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
    penalty_per_day: float = 0.005  # 0.5% per day penalty
) -> float:
    """
    Validation to ensure an intra-exchange arbitrage trade is profitable, 
    accounting for TVM (Time Value of Money) / Trade Hold penalties.
    """
    net_received = expected_sell_price * (1.0 - fee_markup)
    actual_profit = net_received - buy_price
    
    if actual_profit <= 0:
        raise PriceValidationError(
            f"Absolute LOSS Trade Detected: Buy ${buy_price:.2f}, Sell ${expected_sell_price:.2f} "
            f"(Fee: {fee_markup*100:.1f}%). Blocked."
        )
        
    profit_margin_pct = actual_profit / buy_price
    
    # --- TVM Penalty (v7.6) ---
    # Adjust margin by time penalty: Margin_Adj = Margin - (Penalty * Days)
    # This reflects that $100 profit today is better than $100 profit in 7 days.
    tvm_adjusted_margin = profit_margin_pct - (penalty_per_day * lock_days)
    
    if tvm_adjusted_margin < min_profit_margin:
        raise PriceValidationError(
            f"Insufficient TVM-Adjusted Margin: Raw {profit_margin_pct*100:.2f}% -> "
            f"TVM Adj {tvm_adjusted_margin*100:.2f}% is below threshold {min_profit_margin*100:.2f}%. "
            f"Blocked (7-day lock penalty applied)."
        )
        
    return tvm_adjusted_margin

def validate_slippage(target_price: float, current_market_price: float, max_slippage_pct: float = 0.02) -> None:
    """
    Slippage Control (Iteration 31).
    Ensures that the price we are about to execute against hasn't shifted significantly.
    """
    if current_market_price <= 0:
        raise PriceValidationError("Market price is invalid (<=0).")
        
    slippage = abs(current_market_price - target_price) / target_price
    if slippage > max_slippage_pct:
        raise PriceValidationError(
            f"Slippage Exceeded: Market price {current_market_price} drifted from target {target_price} "
            f"by {slippage*100:.2f}% (Max {max_slippage_pct*100:.2f}%). Blocked."
        )

def validate_volatility(recent_prices: list[float], max_std_dev_pct: float = 0.15) -> None:
    """
    Volatility Check (Iteration 29).
    Blocks purchasing assets that are exhibiting extreme price volatility (pump and dumps).
    """
    if not recent_prices or len(recent_prices) < 2:
        return # Not enough data
        
    mean = sum(recent_prices) / len(recent_prices)
    if mean <= 0: return
    
    variance = sum((p - mean) ** 2 for p in recent_prices) / len(recent_prices)
    std_dev = math.sqrt(variance)
    
    std_dev_pct = std_dev / mean
    
    if std_dev_pct > max_std_dev_pct:
        raise PriceValidationError(
            f"High Volatility Detected: StdDev spread is {std_dev_pct*100:.1f}%. "
            f"Asset is unstable. Blocked."
        )
