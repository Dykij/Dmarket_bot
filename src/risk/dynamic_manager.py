import logging
import math

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
        
    @staticmethod
    def volatility_regime_factor(recent_prices: list[float]) -> float:
        """v15.5: Compute volatility regime factor from recent prices.

        Source: arXiv:2508.16598 — "Hybrid Kelly+VIX sizing outperforms pure Kelly"
        Returns 0.0 (calm) to 1.0 (extreme volatility).
        Used to scale down position size in volatile markets.
        """
        if not recent_prices or len(recent_prices) < 3:
            return 0.0
        returns = []
        for i in range(1, len(recent_prices)):
            if recent_prices[i - 1] > 0:
                returns.append((recent_prices[i] - recent_prices[i - 1]) / recent_prices[i - 1])
        if len(returns) < 2:
            return 0.0
        mean_r = sum(returns) / len(returns)
        variance = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance) if variance > 0 else 0.0
        # Map std_dev to 0-1 factor: 5% daily vol = calm (0.0), 25%+ = extreme (1.0)
        return min(1.0, max(0.0, (std_dev - 0.05) / 0.20))

    def evaluate_trade_size(self,
                            direction: str,
                            original_amount: float,
                            current_regime: int,
                            hawkes_intensity: float,
                            current_drawdown: float,
                            recent_prices: list[float] | None = None) -> float | None:
        """
        v15.5: Calculates risk-adjusted execution amount using Hybrid Kelly+Volatility sizing.

        Source: arXiv:2508.16598 — Hybrid Kelly+VIX outperforms pure Kelly.
        Formula: position_size = kelly_fraction × (1 - vol_regime_factor)
        """
        # 1. SOFT HALT LOGIC
        if current_drawdown >= self.soft_halt_threshold:
            if direction == "BUY":
                logger.warning(f"SOFT HALT ACTIVE (Drawdown: {current_drawdown*100:.2f}%). Rejecting BUY order.")
                return None
            else:
                logger.info("SOFT HALT ACTIVE. Permitting SELL order for risk reduction.")

        # 2. KELLY-BASED SIZING (Half Kelly)
        kelly_frac = self.kelly_fraction(
            win_rate=self.win_rate,
            win_loss_ratio=self.win_loss_ratio,
            half_kelly=True,
        )
        if kelly_frac > 0:
            adjusted_amount = original_amount * min(kelly_frac, 0.5)
            logger.info(
                f"Kelly sizing: win_rate={self.win_rate:.2f}, "
                f"wl_ratio={self.win_loss_ratio:.2f}, frac={kelly_frac:.3f} "
                f"→ ${original_amount:.2f} -> ${adjusted_amount:.2f}"
            )
        else:
            adjusted_amount = original_amount

        # 3. VOLATILITY REGIME SCALING (arXiv:2508.16598)
        vol_factor = self.volatility_regime_factor(recent_prices or [])
        if vol_factor > 0.3:
            vol_reduction = 1.0 - (vol_factor * 0.5)  # max 50% reduction at extreme vol
            adjusted_amount *= vol_reduction
            logger.info(
                f"Vol regime: factor={vol_factor:.2f}, "
                f"reduction={vol_reduction:.2f} → ${adjusted_amount:.2f}"
            )

        # 4. REGIME-BASED SCALING (applied on top)
        if current_regime == 1 or hawkes_intensity > 2.0:
            adjusted_amount *= 0.5
            logger.info(f"High Risk Regime. Additional 50% reduction: -> ${adjusted_amount:.2f}")

        return adjusted_amount
