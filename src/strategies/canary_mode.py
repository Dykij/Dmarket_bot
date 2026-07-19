"""
canary_mode.py — A/B testing framework for trading strategy variants.

v15.10: Parallel execution of CONTROL (current strategy) and TREATMENT
(experimental filter/parameter) on split capital. After 100+ trades,
statistical test determines if TREATMENT is superior → promote or revert.

This is the trading equivalent of feature flags with gradual rollout.

Usage:
    canary = CanaryTesting(control_capital=50, treatment_capital=50)
    canary.start()
    # In each cycle:
    canary.record_trade(StrategyVariant.CONTROL, item, buy_price, sell_price, fee, status)
    # After enough trades:
    is_better, analysis = canary.is_treatment_superior()
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

logger = logging.getLogger("SnipingBot")


class StrategyVariant(Enum):
    """Trading strategy variant for A/B testing."""
    CONTROL = "control"      # Current proven strategy
    TREATMENT = "treatment"   # Experimental strategy with new filter/parameter


@dataclass
class TradeRecord:
    """Single trade record for statistical analysis."""
    timestamp: datetime
    variant: StrategyVariant
    title: str
    buy_price: float
    sell_price: float | None  # None if still in inventory
    fee_paid: float
    status: str  # 'sold', 'held', 'failed'
    pnl: float = 0.0

    def __post_init__(self) -> None:
        if self.sell_price is not None and self.status == "sold":
            self.pnl = (self.sell_price - self.buy_price) - self.fee_paid


@dataclass
class VariantMetrics:
    """Aggregated metrics for one strategy variant."""
    variant: StrategyVariant
    trades: list[TradeRecord] = field(default_factory=list)

    @property
    def trade_count(self) -> int:
        return len(self.trades)

    @property
    def wins(self) -> int:
        return sum(1 for t in self.trades if t.pnl > 0 and t.status == "sold")

    @property
    def losses(self) -> int:
        return sum(1 for t in self.trades if t.pnl <= 0 and t.status == "sold")

    @property
    def sold_count(self) -> int:
        return sum(1 for t in self.trades if t.status == "sold")

    @property
    def win_rate(self) -> float:
        if self.sold_count == 0:
            return 0.0
        return self.wins / self.sold_count

    @property
    def total_pnl(self) -> float:
        return sum(t.pnl for t in self.trades if t.status == "sold")

    @property
    def avg_pnl(self) -> float:
        if self.sold_count == 0:
            return 0.0
        return self.total_pnl / self.sold_count

    @property
    def profit_factor(self) -> float:
        gross_profit = sum(t.pnl for t in self.trades if t.pnl > 0 and t.status == "sold")
        gross_loss = abs(sum(t.pnl for t in self.trades if t.pnl <= 0 and t.status == "sold"))
        if gross_loss == 0:
            return float("inf") if gross_profit > 0 else 0.0
        return gross_profit / gross_loss

    @property
    def pnl_std(self) -> float:
        """Standard deviation of per-trade PnL."""
        sold_pnls = [t.pnl for t in self.trades if t.status == "sold"]
        if len(sold_pnls) < 2:
            return 0.0
        mean = sum(sold_pnls) / len(sold_pnls)
        variance = sum((p - mean) ** 2 for p in sold_pnls) / (len(sold_pnls) - 1)
        return math.sqrt(variance)

    @property
    def sharpe_ratio(self) -> float:
        """Annualized Sharpe ratio (simplified: mean/std * sqrt(252))."""
        if self.pnl_std == 0 or self.sold_count == 0:
            return 0.0
        return (self.avg_pnl / self.pnl_std) * math.sqrt(252)

    def to_dict(self) -> dict[str, Any]:
        pf = self.profit_factor
        return {
            "variant": self.variant.value,
            "trade_count": self.trade_count,
            "sold_count": self.sold_count,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": round(self.win_rate, 4),
            "total_pnl": round(self.total_pnl, 4),
            "avg_pnl": round(self.avg_pnl, 4),
            "profit_factor": round(pf, 4) if math.isfinite(pf) else None,
            "sharpe_ratio": round(self.sharpe_ratio, 4),
        }


class CanaryTesting:
    """
    A/B testing framework for trading strategies.

    Splits capital between CONTROL and TREATMENT variants,
    records trades, and performs statistical comparison.
    """

    def __init__(
        self,
        control_capital: float = 50.0,
        treatment_capital: float = 50.0,
        min_trades: int = 100,
        significance_level: float = 0.05,
    ):
        self.control_capital = control_capital
        self.treatment_capital = treatment_capital
        self.min_trades = min_trades
        self.significance_level = significance_level

        self._active = False
        self._start_time: datetime | None = None
        self._experiment_name: str = ""

        self.metrics: dict[StrategyVariant, VariantMetrics] = {
            StrategyVariant.CONTROL: VariantMetrics(variant=StrategyVariant.CONTROL),
            StrategyVariant.TREATMENT: VariantMetrics(variant=StrategyVariant.TREATMENT),
        }

        # Filter rejection counters (for analysis)
        self._filter_rejections: dict[StrategyVariant, dict[str, int]] = {
            StrategyVariant.CONTROL: {},
            StrategyVariant.TREATMENT: {},
        }

    @property
    def is_active(self) -> bool:
        return self._active

    @property
    def experiment_name(self) -> str:
        return self._experiment_name

    def start(self, experiment_name: str = "unnamed") -> None:
        """Start a new A/B test. Resets all previous experiment data."""
        # Reset metrics from any previous experiment
        self.metrics = {
            StrategyVariant.CONTROL: VariantMetrics(variant=StrategyVariant.CONTROL),
            StrategyVariant.TREATMENT: VariantMetrics(variant=StrategyVariant.TREATMENT),
        }
        self._filter_rejections = {
            StrategyVariant.CONTROL: {},
            StrategyVariant.TREATMENT: {},
        }
        self._active = True
        self._start_time = datetime.utcnow()
        self._experiment_name = experiment_name
        logger.info(
            f"[CANARY] Started experiment '{experiment_name}': "
            f"CONTROL=${self.control_capital:.0f} vs "
            f"TREATMENT=${self.treatment_capital:.0f}, "
            f"min_trades={self.min_trades}"
        )

    def stop(self) -> None:
        """Stop the current A/B test."""
        self._active = False
        logger.info(f"[CANARY] Stopped experiment '{self._experiment_name}'")

    def get_capital(self, variant: StrategyVariant) -> float:
        """Get allocated capital for a variant."""
        if variant == StrategyVariant.CONTROL:
            return self.control_capital
        return self.treatment_capital

    # ──────────────────────────────────────────────────────────────
    # TRADE RECORDING
    # ──────────────────────────────────────────────────────────────

    def record_trade(
        self,
        variant: StrategyVariant,
        title: str,
        buy_price: float,
        sell_price: float | None,
        fee_paid: float,
        status: str,
    ) -> None:
        """Record a trade for the specified variant."""
        if not self._active:
            return

        record = TradeRecord(
            timestamp=datetime.utcnow(),
            variant=variant,
            title=title,
            buy_price=buy_price,
            sell_price=sell_price,
            fee_paid=fee_paid,
            status=status,
        )
        self.metrics[variant].trades.append(record)

    def record_filter_rejection(
        self,
        variant: StrategyVariant,
        filter_name: str,
    ) -> None:
        """Record that a candidate was rejected by a specific filter."""
        if not self._active:
            return
        counters = self._filter_rejections[variant]
        counters[filter_name] = counters.get(filter_name, 0) + 1

    # ──────────────────────────────────────────────────────────────
    # STATISTICAL COMPARISON
    # ──────────────────────────────────────────────────────────────

    def is_treatment_superior(self) -> tuple[bool, dict[str, Any]]:
        """
        Statistical test: is TREATMENT better than CONTROL?

        Uses:
        1. Two-proportion z-test on win_rate
        2. Profit factor comparison
        3. Effect size (Cohen's h for proportions)

        Returns:
            (is_superior, analysis_dict)
        """
        control = self.metrics[StrategyVariant.CONTROL]
        treatment = self.metrics[StrategyVariant.TREATMENT]

        # Check minimum data
        total_sold = control.sold_count + treatment.sold_count
        if total_sold < self.min_trades:
            return False, {
                "reason": "insufficient_data",
                "sold_trades": total_sold,
                "required": self.min_trades,
            }

        # 1. Two-proportion z-test (win rate)
        p_control = control.win_rate
        p_treatment = treatment.win_rate
        n_control = control.sold_count
        n_treatment = treatment.sold_count

        if n_control < 10 or n_treatment < 10:
            return False, {
                "reason": "insufficient_per_variant",
                "control_sold": n_control,
                "treatment_sold": n_treatment,
            }

        # Pooled proportion
        p_pool = (control.wins + treatment.wins) / (n_control + n_treatment)
        se = math.sqrt(p_pool * (1 - p_pool) * (1 / n_control + 1 / n_treatment))

        z_stat = 0.0
        p_value = 1.0
        if se > 0:
            z_stat = (p_treatment - p_control) / se
            # Approximate p-value using normal CDF (one-tailed: treatment > control)
            p_value = 0.5 * (1 - math.erf(z_stat / math.sqrt(2)))

        # 2. Cohen's h (effect size for proportions)
        cohens_h = 2 * (math.asin(math.sqrt(p_treatment)) - math.asin(math.sqrt(p_control)))

        # 3. Profit factor improvement
        pf_control = control.profit_factor
        pf_treatment = treatment.profit_factor
        if math.isinf(pf_control) and math.isinf(pf_treatment):
            pf_improvement = 1.0  # Both perfect, no differential
        elif math.isinf(pf_control):
            pf_improvement = 0.0  # Control already perfect, treatment can't beat it
        elif pf_control == 0:
            pf_improvement = float("inf") if pf_treatment > 0 else 0.0
        else:
            pf_improvement = pf_treatment / max(pf_control, 0.01)

        # Decision
        is_superior = (
            p_value < self.significance_level
            and pf_improvement > 1.10  # At least 10% better profit factor
            and cohens_h >= 0.2    # Small-medium positive effect size
        )

        analysis = {
            "experiment": self._experiment_name,
            "control": control.to_dict(),
            "treatment": treatment.to_dict(),
            "tests": {
                "z_statistic": round(z_stat, 4),
                "p_value": round(p_value, 6),
                "cohens_h": round(cohens_h, 4),
                "pf_improvement": round(pf_improvement, 4),
            },
            "is_superior": is_superior,
            "recommendation": (
                "PROMOTE" if is_superior
                else "CONTINUE" if total_sold < self.min_trades * 2
                else "REVERT"
            ),
        }

        logger.info(
            f"[CANARY] Analysis: z={z_stat:.3f}, p={p_value:.4f}, "
            f"h={cohens_h:.3f}, PF_impr={pf_improvement:.3f} → "
            f"{'SUPERIOR' if is_superior else 'NOT YET'}"
        )

        return is_superior, analysis

    def get_summary(self) -> dict[str, Any]:
        """Get current experiment summary."""
        return {
            "active": self._active,
            "experiment": self._experiment_name,
            "started": self._start_time.isoformat() if self._start_time else None,
            "control": self.metrics[StrategyVariant.CONTROL].to_dict(),
            "treatment": self.metrics[StrategyVariant.TREATMENT].to_dict(),
            "filter_rejections": {
                variant.value: dict(counts)
                for variant, counts in self._filter_rejections.items()
            },
        }
