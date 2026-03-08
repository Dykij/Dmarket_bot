"""
price_validator.py — Strict price sanity checks (V3 hardening).

Blocks Data Poisoning attacks by rejecting prices outside the
sane CS2 market range BEFORE any AI agent sees the data.

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
