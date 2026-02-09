"""Circuit Breaker Pattern for Trading Safety.

This module implements a circuit breaker to stop trading activities when
critical risk thresholds are exceeded. It monitors:
1. Consecutive losses
2. Daily loss limit
3. Balance drops
4. API error rates

Usage:
    breaker = TradeCircuitBreaker()
    
    if not breaker.can_trade():
        raise TradingSuspendedError(breaker.get_status())
        
    try:
        # execute trade
        breaker.record_success()
    except Exception:
        breaker.record_failure()
"""

import time
from dataclasses import dataclass
from datetime import datetime, timedelta

from src.utils.canonical_logging import get_logger

logger = get_logger(__name__)

@dataclass
class CircuitBreakerConfig:
    """Configuration for TradeCircuitBreaker."""
    max_consecutive_losses: int = 5
    max_daily_loss_usd: float = 50.0
    min_balance_threshold: float = 10.0
    max_api_errors_per_hour: int = 20
    cooldown_minutes: int = 60
    enable_emergency_stop: bool = True

class TradeCircuitBreaker:
    """Safeguard against runaway losses or errors."""
    
    def __init__(self, config: CircuitBreakerConfig | None = None):
        self.config = config or CircuitBreakerConfig()
        
        # State
        self.is_open: bool = False  # False = Normal, True = Broken (Stop Trading)
        self.triggered_at: datetime | None = None
        self.trigger_reason: str = ""
        
        # Counters
        self.consecutive_losses: int = 0
        self.daily_loss_usd: float = 0.0
        self.api_errors_last_hour: int = 0
        self._last_error_reset: float = time.time()
        
        # Daily reset tracking
        self._last_daily_reset: float = time.time()

    def can_trade(self, current_balance: float | None = None) -> bool:
        """Check if trading is allowed."""
        # 1. Check if already tripped
        if self.is_open:
            if self._check_cooldown():
                self.reset()
                return True
            return False
            
        # 2. Daily reset check
        if time.time() - self._last_daily_reset > 86400:
            self._reset_daily_stats()

        # 3. Check Balance Threshold
        if current_balance is not None and current_balance < self.config.min_balance_threshold:
            self.trip(f"CRITICAL: Balance ${current_balance:.2f} below threshold ${self.config.min_balance_threshold}")
            return False

        return True

    def record_success(self, profit_usd: float = 0.0):
        """Record a successful trade."""
        self.consecutive_losses = 0
        if profit_usd < 0:
            self.record_loss(abs(profit_usd))

    def record_loss(self, loss_usd: float):
        """Record a losing trade."""
        self.consecutive_losses += 1
        self.daily_loss_usd += loss_usd
        
        logger.warning(
            f"Loss recorded: -${loss_usd:.2f} "
            f"(Seq: {self.consecutive_losses}, Daily: -${self.daily_loss_usd:.2f})"
        )

        # Check Limits
        if self.consecutive_losses >= self.config.max_consecutive_losses:
            self.trip(f"Max consecutive losses reached ({self.consecutive_losses})")
            
        if self.daily_loss_usd >= self.config.max_daily_loss_usd:
            self.trip(f"Daily loss limit reached (-${self.daily_loss_usd:.2f})")

    def record_api_error(self):
        """Record an API error."""
        # Reset hourly counter if needed
        if time.time() - self._last_error_reset > 3600:
            self.api_errors_last_hour = 0
            self._last_error_reset = time.time()
            
        self.api_errors_last_hour += 1
        
        if self.api_errors_last_hour >= self.config.max_api_errors_per_hour:
            self.trip(f"Too many API errors ({self.api_errors_last_hour}/hr)")

    def trip(self, reason: str):
        """Trip the circuit breaker (Stop Trading)."""
        self.is_open = True
        self.triggered_at = datetime.now()
        self.trigger_reason = reason
        logger.critical(f"🔌 CIRCUIT BREAKER TRIPPED: {reason}")
        # Here we could also send a high-priority notification

    def reset(self):
        """Reset the circuit breaker manually or automatically."""
        self.is_open = False
        self.triggered_at = None
        self.trigger_reason = ""
        self.consecutive_losses = 0
        # We generally don't reset daily loss on auto-reset, only manually or next day
        logger.info("🔌 Circuit breaker reset. Trading resumed.")

    def _check_cooldown(self) -> bool:
        """Check if cooldown period has passed."""
        if not self.triggered_at:
            return True
            
        elapsed = datetime.now() - self.triggered_at
        return elapsed > timedelta(minutes=self.config.cooldown_minutes)

    def _reset_daily_stats(self):
        """Reset daily counters."""
        self.daily_loss_usd = 0.0
        self._last_daily_reset = time.time()
        logger.info("Daily trading stats reset.")

# Global instance
circuit_breaker = TradeCircuitBreaker()
