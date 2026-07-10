"""Float value arbitrage."""
from typing import Any


class FloatValueArbitrage:
    """Detects arbitrage opportunities based on float values."""

    def __init__(self, api_client: Any = None) -> None:
        self.api = api_client

    def calculate_float_premium(self, float_value: float, base_price: float) -> float:
        """Calculate premium based on float value."""
        if float_value < 0.01:
            return 1.25
        if float_value < 0.03:
            return 1.20
        if float_value < 0.07:
            return 1.08
        return 1.0
