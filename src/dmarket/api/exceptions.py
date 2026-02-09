"""Custom exceptions for DMarket API."""

class DMarketError(Exception):
    """Base exception for DMarket API errors."""
    pass

class InsufficientFundsError(DMarketError):
    """Raised when account balance is too low for operation."""
    def __init__(self, required: float, available: float):
        self.required = required
        self.available = available
        super().__init__(f"Insufficient funds: required ${required:.2f}, available ${available:.2f}")

class CircuitBreakerError(DMarketError):
    """Raised when trading is suspended by Circuit Breaker."""
    pass

class RateLimitError(DMarketError):
    """Raised when API rate limit is exceeded."""
    pass
