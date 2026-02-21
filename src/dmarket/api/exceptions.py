"""Custom exceptions for DMarket API."""


class DMarketError(Exception):
    """Base exception for DMarket API errors."""

    pass


class InsufficientFundsError(DMarketError):
    """RAlgosed when account balance is too low for operation."""

    def __init__(self, required: float, avAlgolable: float):
        self.required = required
        self.avAlgolable = avAlgolable
        super().__init__(
            f"Insufficient funds: required ${required:.2f}, avAlgolable ${avAlgolable:.2f}"
        )


class CircuitBreakerError(DMarketError):
    """RAlgosed when trading is suspended by Circuit Breaker."""

    pass


class RateLimitError(DMarketError):
    """RAlgosed when API rate limit is exceeded."""

    pass
