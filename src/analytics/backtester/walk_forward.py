"""
walk_forward.py — Walk-Forward Optimization Pipeline.

Splits historical data into train/test windows, optimizes parameters
on train set, validates on test set. Repeats with rolling windows.

This prevents overfitting by ensuring parameters work on unseen data.

Usage:
    from src.analytics.backtester.walk_forward import WalkForwardPipeline

    pipeline = WalkForwardPipeline(
        train_days=90,
        test_days=30,
        step_days=30,
    )
    results = await pipeline.run(strategy, price_histories, initial_balance)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

from .engine import Backtester
from .metrics import calculate_max_drawdown, calculate_sharpe_ratio
from .models import BacktestResult
from .strategies import TradingStrategy

logger = logging.getLogger("WalkForward")


@dataclass
class WindowResult:
    """Result for a single train/test window."""

    window_id: int
    train_start: datetime
    train_end: datetime
    test_start: datetime
    test_end: datetime
    train_result: BacktestResult | None = None
    test_result: BacktestResult | None = None
    best_params: dict[str, Any] = field(default_factory=dict)
    optimization_score: float = 0.0


@dataclass
class WalkForwardResult:
    """Aggregate result of walk-forward optimization."""

    total_windows: int = 0
    windows: list[WindowResult] = field(default_factory=list)
    aggregate_sharpe: float = 0.0
    aggregate_drawdown: float = 0.0
    aggregate_win_rate: float = 0.0
    total_profit: Decimal = Decimal(0)
    oos_sharpe: float = 0.0  # Out-of-sample Sharpe
    oos_win_rate: float = 0.0
    is_robust: bool = False  # OOS performance >= 50% of IS performance
    parameter_stability: float = 0.0  # How stable params are across windows


class WalkForwardPipeline:
    """Walk-forward optimization with rolling windows.

    Process:
    1. Split data into overlapping train/test windows
    2. For each window:
       a. Optimize strategy parameters on train set
       b. Validate optimized parameters on test set
    3. Aggregate out-of-sample results
    4. Check robustness (OOS vs IS performance)
    """

    def __init__(
        self,
        train_days: int = 90,
        test_days: int = 30,
        step_days: int = 30,
        min_trades: int = 5,
    ) -> None:
        self.train_days = train_days
        self.test_days = test_days
        self.step_days = step_days
        self.min_trades = min_trades
        self.backtester = Backtester()

    async def run(
        self,
        strategy: TradingStrategy,
        price_histories: dict[str, Any],
        initial_balance: Decimal,
        param_grid: dict[str, list[Any]] | None = None,
    ) -> WalkForwardResult:
        """Run walk-forward optimization.

        Args:
            strategy: Strategy to optimize.
            price_histories: Historical price data.
            initial_balance: Starting balance per window.
            param_grid: Parameter grid for optimization.
                       e.g., {"spread_threshold": [0.05, 0.08, 0.10],
                              "stop_loss": [0.05, 0.10, 0.15]}

        Returns:
            WalkForwardResult with aggregate metrics.
        """
        # Determine date range
        all_dates = self._get_all_dates(price_histories)
        if not all_dates:
            logger.warning("[WalkForward] No price data available")
            return WalkForwardResult()

        min_date = min(all_dates)
        max_date = max(all_dates)

        # Generate windows
        windows = self._generate_windows(min_date, max_date)
        logger.info(
            f"[WalkForward] Generated {len(windows)} windows "
            f"({self.train_days}d train / {self.test_days}d test)"
        )

        result = WalkForwardResult(total_windows=len(windows))

        # Process each window
        for i, (train_start, train_end, test_start, test_end) in enumerate(windows):
            logger.info(
                f"[WalkForward] Window {i+1}/{len(windows)}: "
                f"train={train_start.date()}→{train_end.date()}, "
                f"test={test_start.date()}→{test_end.date()}"
            )

            window_result = WindowResult(
                window_id=i,
                train_start=train_start,
                train_end=train_end,
                test_start=test_start,
                test_end=test_end,
            )

            # Optimize on train set
            if param_grid:
                best_params, best_score = await self._optimize(
                    strategy, price_histories, initial_balance,
                    train_start, train_end, param_grid,
                )
                window_result.best_params = best_params
                window_result.optimization_score = best_score

                # Apply best params to strategy
                self._apply_params(strategy, best_params)

            # Run on train set
            window_result.train_result = await self.backtester.run(
                strategy, price_histories, train_start, train_end, initial_balance,
            )

            # Run on test set (out-of-sample)
            window_result.test_result = await self.backtester.run(
                strategy, price_histories, test_start, test_end, initial_balance,
            )

            result.windows.append(window_result)

        # Aggregate results
        self._aggregate_results(result)

        logger.info(
            f"[WalkForward] Complete: OOS Sharpe={result.oos_sharpe:.2f}, "
            f"OOS Win Rate={result.oos_win_rate:.1f}%, "
            f"Robust={result.is_robust}"
        )

        return result

    async def _optimize(
        self,
        strategy: TradingStrategy,
        price_histories: dict[str, Any],
        initial_balance: Decimal,
        start: datetime,
        end: datetime,
        param_grid: dict[str, list[Any]],
    ) -> tuple[dict[str, Any], float]:
        """Grid search optimization on train set.

        Returns:
            (best_params, best_score) tuple.
        """
        best_params: dict[str, Any] = {}
        best_score = float("-inf")

        # Generate all param combinations
        param_combinations = self._expand_grid(param_grid)

        for params in param_combinations:
            # Apply params
            self._apply_params(strategy, params)

            # Run backtest
            result = await self.backtester.run(
                strategy, price_histories, start, end, initial_balance,
            )

            # Score: Sharpe ratio (risk-adjusted return)
            score = result.sharpe_ratio

            # Penalize if too few trades
            if result.total_trades < self.min_trades:
                score *= 0.5

            if score > best_score:
                best_score = score
                best_params = params.copy()

        return best_params, best_score

    def _expand_grid(
        self, param_grid: dict[str, list[Any]]
    ) -> list[dict[str, Any]]:
        """Expand parameter grid into list of param dicts."""
        keys = list(param_grid.keys())
        values = list(param_grid.values())

        if not keys:
            return [{}]

        combinations: list[dict[str, Any]] = [{}]

        for key, vals in zip(keys, values):
            new_combinations = []
            for combo in combinations:
                for val in vals:
                    new_combo = combo.copy()
                    new_combo[key] = val
                    new_combinations.append(new_combo)
            combinations = new_combinations

        return combinations

    def _apply_params(
        self, strategy: TradingStrategy, params: dict[str, Any]
    ) -> None:
        """Apply parameters to strategy."""
        for key, value in params.items():
            if hasattr(strategy, key):
                setattr(strategy, key, value)

    def _generate_windows(
        self, min_date: datetime, max_date: datetime
    ) -> list[tuple[datetime, datetime, datetime, datetime]]:
        """Generate train/test windows."""
        windows = []
        current = min_date
        window_id = 0

        while True:
            train_start = current
            train_end = train_start + timedelta(days=self.train_days)
            test_start = train_end
            test_end = test_start + timedelta(days=self.test_days)

            if test_end > max_date:
                break

            windows.append((train_start, train_end, test_start, test_end))
            current += timedelta(days=self.step_days)
            window_id += 1

        return windows

    def _get_all_dates(
        self, price_histories: dict[str, Any]
    ) -> list[datetime]:
        """Extract all unique dates from price histories."""
        dates = set()
        for history in price_histories.values():
            if hasattr(history, "points"):
                for point in history.points:
                    dates.add(point.timestamp.replace(
                        hour=0, minute=0, second=0, microsecond=0
                    ))
        return sorted(dates)

    def _aggregate_results(self, result: WalkForwardResult) -> None:
        """Aggregate window results into overall metrics."""
        if not result.windows:
            return

        # Out-of-sample metrics
        oos_sharpes = []
        oos_win_rates = []
        oos_profits = []
        is_sharpes = []

        for window in result.windows:
            if window.test_result:
                oos_sharpes.append(window.test_result.sharpe_ratio)
                oos_win_rates.append(window.test_result.win_rate)
                oos_profits.append(window.test_result.total_profit)

            if window.train_result:
                is_sharpes.append(window.train_result.sharpe_ratio)

        if oos_sharpes:
            result.oos_sharpe = sum(oos_sharpes) / len(oos_sharpes)
            result.oos_win_rate = sum(oos_win_rates) / len(oos_win_rates)
            result.total_profit = sum(oos_profits, Decimal(0))

        if is_sharpes:
            is_avg = sum(is_sharpes) / len(is_sharpes)
            # Robust if OOS >= 50% of IS performance
            result.is_robust = (
                result.oos_sharpe >= is_avg * 0.5
                if is_avg > 0
                else result.oos_sharpe >= 0
            )

        # Parameter stability: how much params vary across windows
        if len(result.windows) > 1:
            param_sets = [w.best_params for w in result.windows if w.best_params]
            if param_sets:
                # Simple stability metric: fraction of windows with same params
                from collections import Counter
                param_strs = [str(sorted(p.items())) for p in param_sets]
                counts = Counter(param_strs)
                most_common_count = counts.most_common(1)[0][1]
                result.parameter_stability = most_common_count / len(param_sets)
