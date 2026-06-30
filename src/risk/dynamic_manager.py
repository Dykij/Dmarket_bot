import logging
import math
from typing import Optional

logger = logging.getLogger("DynamicRiskManager")
logger.setLevel(logging.INFO)

class DynamicRiskManager:
    """
    Intermediary logic between mathematical models and the Execution Gate.
    Implements Adaptive Kelly Sizing (Half Kelly) based on historical
    win-rate and win/loss ratio.
    """

    def __init__(self, base_kelly_fraction: float = 0.10, soft_halt_threshold: float = 0.015):
        self.base_fraction = base_kelly_fraction
        self.soft_halt_threshold = soft_halt_threshold
        self._total_trades: int = 0
        self._win_trades: int = 0
        self._gross_profit: float = 0.0
        self._gross_loss: float = 0.0

    @staticmethod
    def kelly_fraction(win_rate: float, win_loss_ratio: float, half_kelly: bool = True) -> float:
        """Calculate the Kelly criterion fraction.

        f* = win_rate - (1 - win_rate) / win_loss_ratio

        Args:
            win_rate: historical win rate (0.0 to 1.0)
            win_loss_ratio: average_profit / average_loss
            half_kelly: if True, return f*/2 (Half Kelly for reduced drawdown)

        Returns:
            Kelly fraction clipped to [0, 0.25]; returns 0 for negative edge.
        """
        if win_loss_ratio <= 0 or win_rate <= 0:
            return 0.0
        f_star = win_rate - (1.0 - win_rate) / win_loss_ratio
        if f_star <= 0:
            return 0.0  # negative edge — do not bet
        if half_kelly:
            f_star *= 0.5
        return min(f_star, 0.25)

    def record_trade(self, won: bool, profit_usd: float = 0.0, loss_usd: float = 0.0) -> None:
        """Record trade outcome for Kelly statistics."""
        self._total_trades += 1
        if won:
            self._win_trades += 1
            self._gross_profit += abs(profit_usd)
        else:
            self._gross_loss += abs(loss_usd)

    @property
    def win_rate(self) -> float:
        return self._win_trades / max(self._total_trades, 1)

    @property
    def win_loss_ratio(self) -> float:
        avg_profit = self._gross_profit / max(self._win_trades, 1)
        loss_trades = self._total_trades - self._win_trades
        avg_loss = self._gross_loss / max(loss_trades, 1)
        if avg_loss <= 0:
            return 0.0
        return avg_profit / avg_loss
        
    def evaluate_trade_size(self, 
                            direction: str,
                            original_amount: float, 
                            current_regime: int, 
                            hawkes_intensity: float,
                            current_drawdown: float) -> Optional[float]:
        """
        Calculates the risk-adjusted execution amount.
        Returns None if the trade should be dropped/rejected.
        """
        # 1. SOFT HALT LOGIC
        if current_drawdown >= self.soft_halt_threshold:
            if direction == "BUY":
                logger.warning(f"SOFT HALT ACTIVE (Drawdown: {current_drawdown*100:.2f}%). Rejecting BUY order to reduce exposure.")
                return None
            else:
                logger.info("SOFT HALT ACTIVE. Permitting SELL order for risk reduction.")
                
        # 2. ADAPTIVE SIZING
        adjusted_amount = original_amount
        
        # Assume Regime 1 is "High Volatility" or intensity is peaking
        if current_regime == 1 or hawkes_intensity > 2.0:
            adjusted_amount *= 0.5
            logger.info(f"High Risk Regime Detected. Scaling down trade size by 50%: {original_amount} -> {adjusted_amount}")
            
        return adjusted_amount
