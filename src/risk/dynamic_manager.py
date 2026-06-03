import logging
from typing import Optional

logger = logging.getLogger("DynamicRiskManager")
logger.setLevel(logging.INFO)

class DynamicRiskManager:
    """
    Intermediary logic between mathematical models and the Execution Gate.
    Implements Adaptive Kelly Sizing based on real-time Z_t and lambda(t) metrics.
    """
    def __init__(self, base_kelly_fraction: float = 0.10, soft_halt_threshold: float = 0.015):
        self.base_fraction = base_kelly_fraction
        self.soft_halt_threshold = soft_halt_threshold
        
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
                logger.info(f"SOFT HALT ACTIVE. Permitting SELL order for risk reduction.")
                
        # 2. ADAPTIVE SIZING
        adjusted_amount = original_amount
        
        # Assume Regime 1 is "High Volatility" or intensity is peaking
        if current_regime == 1 or hawkes_intensity > 2.0:
            adjusted_amount *= 0.5
            logger.info(f"High Risk Regime Detected. Scaling down trade size by 50%: {original_amount} -> {adjusted_amount}")
            
        return adjusted_amount
