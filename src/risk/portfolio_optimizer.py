"""
portfolio_optimizer.py — Markowitz Portfolio Optimization.

Computes optimal portfolio weights using mean-variance optimization.
Supports efficient frontier calculation and rebalancing triggers.

Usage:
    from src.risk.portfolio_optimizer import PortfolioOptimizer

    optimizer = PortfolioOptimizer()
    weights = optimizer.optimize(returns_matrix, risk_aversion=1.0)
    rebalance = optimizer.should_rebalance(current_weights, target_weights)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("PortfolioOptimizer")


@dataclass
class PortfolioWeights:
    """Optimal portfolio weights."""

    weights: dict[str, float]  # item -> weight
    expected_return: float = 0.0
    expected_volatility: float = 0.0
    sharpe_ratio: float = 0.0


@dataclass
class EfficientFrontier:
    """Efficient frontier points."""

    points: list[PortfolioWeights] = field(default_factory=list)
    min_volatility_point: PortfolioWeights | None = None
    max_sharpe_point: PortfolioWeights | None = None


class PortfolioOptimizer:
    """Markowitz mean-variance portfolio optimization.

    Computes optimal weights to maximize Sharpe ratio or minimize
    volatility for a given target return.
    """

    def __init__(
        self,
        risk_free_rate: float = 0.02,  # 2% annual
        max_weight: float = 0.40,  # Max 40% in single item
        min_weight: float = 0.0,   # No short selling
    ) -> None:
        self.risk_free_rate = risk_free_rate
        self.max_weight = max_weight
        self.min_weight = min_weight

    def optimize(
        self,
        returns_matrix: dict[str, list[float]],
        risk_aversion: float = 1.0,
    ) -> PortfolioWeights:
        """Compute optimal portfolio weights.

        Args:
            returns_matrix: Dict of item_title -> list of daily returns.
            risk_aversion: Higher = more risk-averse (default 1.0).

        Returns:
            PortfolioWeights with optimal allocation.
        """
        items = list(returns_matrix.keys())
        n = len(items)

        if n == 0:
            return PortfolioWeights(weights={})

        if n == 1:
            return PortfolioWeights(
                weights={items[0]: 1.0},
                expected_return=self._mean(returns_matrix[items[0]]),
                expected_volatility=self._std(returns_matrix[items[0]]),
            )

        # Compute statistics
        means = [self._mean(returns_matrix[item]) for item in items]
        cov_matrix = self._compute_covariance(returns_matrix, items)

        # Simple analytical solution for equal-risk-contribution
        # (approximation of Markowitz without scipy)
        weights = self._equal_risk_contribution(cov_matrix, n)

        # Apply risk aversion: shift toward lower volatility
        if risk_aversion > 1.0:
            vol_weights = self._min_variance_weights(cov_matrix, n)
            blend = min(1.0, 1.0 / risk_aversion)
            weights = [
                blend * w + (1 - blend) * vw
                for w, vw in zip(weights, vol_weights)
            ]

        # Normalize and clamp
        weights = self._normalize_weights(weights, n)

        # Compute portfolio statistics
        port_return = sum(w * m for w, m in zip(weights, means))
        port_vol = self._portfolio_volatility(weights, cov_matrix, n)
        sharpe = (
            (port_return - self.risk_free_rate / 365) / port_vol
            if port_vol > 0
            else 0.0
        )

        weight_dict = {items[i]: weights[i] for i in range(n) if weights[i] > 0.001}

        return PortfolioWeights(
            weights=weight_dict,
            expected_return=port_return,
            expected_volatility=port_vol,
            sharpe_ratio=sharpe,
        )

    def efficient_frontier(
        self,
        returns_matrix: dict[str, list[float]],
        n_points: int = 10,
    ) -> EfficientFrontier:
        """Compute efficient frontier.

        Args:
            returns_matrix: Dict of item_title -> list of daily returns.
            n_points: Number of points on the frontier.

        Returns:
            EfficientFrontier with frontier points.
        """
        frontier = EfficientFrontier()

        for i in range(n_points):
            risk_aversion = 0.5 + (i / n_points) * 4.0  # 0.5 to 4.5
            weights = self.optimize(returns_matrix, risk_aversion)
            frontier.points.append(weights)

        # Find min volatility and max Sharpe
        if frontier.points:
            frontier.min_volatility_point = min(
                frontier.points, key=lambda p: p.expected_volatility
            )
            frontier.max_sharpe_point = max(
                frontier.points, key=lambda p: p.sharpe_ratio
            )

        return frontier

    def should_rebalance(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        threshold: float = 0.05,
    ) -> bool:
        """Check if portfolio needs rebalancing.

        Args:
            current_weights: Current portfolio weights.
            target_weights: Target portfolio weights.
            threshold: Rebalance if any weight drifts by more than this.

        Returns:
            True if rebalancing needed.
        """
        all_items = set(current_weights.keys()) | set(target_weights.keys())

        for item in all_items:
            current = current_weights.get(item, 0.0)
            target = target_weights.get(item, 0.0)
            if abs(current - target) > threshold:
                return True

        return False

    def compute_rebalance_trades(
        self,
        current_weights: dict[str, float],
        target_weights: dict[str, float],
        total_value: float,
    ) -> list[dict[str, Any]]:
        """Compute trades needed to rebalance.

        Args:
            current_weights: Current portfolio weights.
            target_weights: Target portfolio weights.
            total_value: Total portfolio value.

        Returns:
            List of trades: {item, action, amount_usd}
        """
        trades = []
        all_items = set(current_weights.keys()) | set(target_weights.keys())

        for item in all_items:
            current_val = current_weights.get(item, 0.0) * total_value
            target_val = target_weights.get(item, 0.0) * total_value
            diff = target_val - current_val

            if abs(diff) < 1.0:  # Skip tiny trades
                continue

            trades.append({
                "item": item,
                "action": "buy" if diff > 0 else "sell",
                "amount_usd": abs(diff),
            })

        return trades

    def _equal_risk_contribution(
        self, cov_matrix: list[list[float]], n: int
    ) -> list[float]:
        """Equal risk contribution weights (simple approximation)."""
        # Start with equal weights
        weights = [1.0 / n] * n

        # Iterate to equalize risk contributions
        for _ in range(50):
            port_vol = self._portfolio_volatility(weights, cov_matrix, n)
            if port_vol < 1e-10:
                break

            # Marginal risk contribution
            marginal = []
            for i in range(n):
                mc = sum(cov_matrix[i][j] * weights[j] for j in range(n))
                marginal.append(mc * weights[i] / port_vol)

            # Adjust weights toward equal contribution
            target = 1.0 / n
            for i in range(n):
                if marginal[i] > 0:
                    weights[i] *= target / marginal[i]

            weights = self._normalize_weights(weights, n)

        return weights

    def _min_variance_weights(
        self, cov_matrix: list[list[float]], n: int
    ) -> list[float]:
        """Minimum variance portfolio weights (approximation)."""
        # Inverse variance weights (simplified)
        inv_vars = []
        for i in range(n):
            var = cov_matrix[i][i]
            inv_vars.append(1.0 / max(var, 1e-10))

        total = sum(inv_vars)
        return [iv / total for iv in inv_vars]

    def _compute_covariance(
        self,
        returns_matrix: dict[str, list[float]],
        items: list[str],
    ) -> list[list[float]]:
        """Compute covariance matrix."""
        n = len(items)
        means = [self._mean(returns_matrix[item]) for item in items]

        cov = [[0.0] * n for _ in range(n)]
        for i in range(n):
            for j in range(n):
                ri = returns_matrix[items[i]]
                rj = returns_matrix[items[j]]
                min_len = min(len(ri), len(rj))
                if min_len < 2:
                    cov[i][j] = 0.0
                    continue

                cov_sum = sum(
                    (ri[t] - means[i]) * (rj[t] - means[j])
                    for t in range(min_len)
                )
                cov[i][j] = cov_sum / (min_len - 1)

        return cov

    def _portfolio_volatility(
        self, weights: list[float], cov_matrix: list[list[float]], n: int
    ) -> float:
        """Compute portfolio volatility."""
        vol_sq = 0.0
        for i in range(n):
            for j in range(n):
                vol_sq += weights[i] * weights[j] * cov_matrix[i][j]
        return math.sqrt(max(0.0, vol_sq))

    def _normalize_weights(self, weights: list[float], n: int) -> list[float]:
        """Normalize weights to sum to 1 and clamp."""
        # Clamp
        weights = [max(self.min_weight, min(self.max_weight, w)) for w in weights]

        # Normalize
        total = sum(weights)
        if total > 0:
            weights = [w / total for w in weights]

        return weights

    @staticmethod
    def _mean(data: list[float]) -> float:
        return sum(data) / len(data) if data else 0.0

    @staticmethod
    def _std(data: list[float]) -> float:
        if len(data) < 2:
            return 0.0
        m = sum(data) / len(data)
        var = sum((x - m) ** 2 for x in data) / (len(data) - 1)
        return math.sqrt(var)
