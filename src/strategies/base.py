"""
BaseStrategy — Enhanced with arXiv-inspired improvements.

Improvements over original:
1. Garman-Klass volatility estimation (not just spread proxy)
2. Turnover regularization (penalty for excessive trading)
3. Sharpe-adjusted objective (risk-aware opportunity scoring)
4. Self-reflection integration (adaptive parameters)
"""

import logging
import math
import time
from abc import ABC, abstractmethod
from typing import Any

from src.config import Config

logger = logging.getLogger("Strategy")


class BaseStrategy(ABC):
    def __init__(self, name: str):
        self.name = name
        self.logger = logging.getLogger(f"Strategy.{name}")
        self._daily_trade_count = 0
        self._daily_trades_reset_ts = 0.0

    # ----------------------------------------------------------------
    # 1. ENHANCED POSITION SIZING (Pseudo-Kelly + Volatility)
    # ----------------------------------------------------------------
    def calculate_position_size(
        self,
        current_balance: float,
        item_price: float,
        volatility_score: float = 1.0,
        sharpe_estimate: float = 1.0,
    ) -> int:
        """Dynamic Position Sizing (Pseudo-Kelly Criterion, v2)."""
        if not Config.USE_DYNAMIC_SIZING or current_balance <= 0:
            return 1

        max_risk_amount = current_balance * (Config.MAX_POSITION_RISK_PCT / 100.0)
        adjusted_risk = max_risk_amount / max(volatility_score, 1.0)

        if sharpe_estimate < 1.0:
            adjusted_risk *= max(0.3, sharpe_estimate)
        elif sharpe_estimate > 2.0:
            adjusted_risk *= min(1.5, sharpe_estimate / 1.5)

        if item_price > adjusted_risk:
            self.logger.warning(
                f"Item ${item_price:.2f} exceeds risk tolerance ${adjusted_risk:.2f} "
                f"(vol={volatility_score:.2f}, sharpe={sharpe_estimate:.2f})"
            )
            return 0

        quantity = int(adjusted_risk // item_price)
        return max(1, quantity)

    # ----------------------------------------------------------------
    # 2. VOLATILITY ESTIMATORS
    # ----------------------------------------------------------------
    @staticmethod
    def spread_volatility(best_ask: float, best_bid: float) -> float:
        """Legacy volatility proxy from spread percentage."""
        if best_bid <= 0:
            return 100.0
        return ((best_ask - best_bid) / best_bid) * 100.0

    @staticmethod
    def garman_klass_volatility(
        open_prices: list[float],
        high: list[float],
        low: list[float],
        close: list[float],
    ) -> float:
        """
        Garman-Klass volatility estimator.
        More efficient than close-to-close: uses OHLC data.
        Formula: σ² = 0.5*ln(H/L)² - (2ln2-1)*ln(C/O)²
        Returns annualized volatility.
        """
        if not all(len(x) >= 2 for x in [open_prices, high, low, close]):
            return 0.0

        n = min(len(open_prices), len(high), len(low), len(close))
        if n < 2:
            return 0.0

        sum_sq = 0.0
        count = 0
        for i in range(n):
            if high[i] <= 0 or low[i] <= 0 or open_prices[i] <= 0 or close[i] <= 0:
                continue
            hl = math.log(high[i] / low[i])
            co = math.log(close[i] / open_prices[i])
            sum_sq += 0.5 * hl * hl - (2 * math.log(2) - 1) * co * co
            count += 1

        if count < 2 or sum_sq <= 0:
            return 0.0

        return math.sqrt(sum_sq / count) * math.sqrt(252)

    @staticmethod
    def realized_volatility(prices: list[float]) -> float:
        """Realized volatility from close-to-close log returns."""
        if len(prices) < 2:
            return 0.0

        log_returns = []
        for i in range(1, len(prices)):
            if prices[i - 1] > 0 and prices[i] > 0:
                log_returns.append(math.log(prices[i] / prices[i - 1]))

        if len(log_returns) < 2:
            return 0.0

        mean_ret = sum(log_returns) / len(log_returns)
        variance = sum((r - mean_ret) ** 2 for r in log_returns) / (len(log_returns) - 1)
        return math.sqrt(variance) * math.sqrt(252)

    def get_volatility(
        self,
        hash_name: str = "",
        best_ask: float = 0.0,
        best_bid: float = 0.0,
        ohlcv_data: dict[str, list[float]] | None = None,
        recent_prices: list[float] | None = None,
    ) -> float:
        """
        Get the best available volatility estimate.
        Tries Garman-Klass first, then realized, then spread.
        """
        method = Config.VOLATILITY_METHOD

        if method == "garman_klass" and ohlcv_data:
            vol = self.garman_klass_volatility(
                ohlcv_data.get("open", []),
                ohlcv_data.get("high", []),
                ohlcv_data.get("low", []),
                ohlcv_data.get("close", []),
            )
            if vol > 0:
                return vol

        if method in ("garman_klass", "realized") and recent_prices:
            vol = self.realized_volatility(recent_prices)
            if vol > 0:
                return vol

        # Fallback to spread-based proxy
        return self.spread_volatility(best_ask, best_bid)

    # ----------------------------------------------------------------
    # 2b. ATR (Average True Range) ESTIMATOR
    # ----------------------------------------------------------------
    @staticmethod
    def calculate_atr(
        high: list[float],
        low: list[float],
        close: list[float],
        period: int = 14,
    ) -> float:
        """
        v12.7: Average True Range (ATR) volatility estimator.

        ATR measures market volatility by decomposing the entire range
        of price movement for each period. More responsive to sudden
        price moves than standard deviation.

        True Range = max(H-L, |H-Cp|, |L-Cp|)
        where Cp = previous close.

        Returns: ATR value (absolute, not percentage).
        """
        if len(high) < 2 or len(low) < 2 or len(close) < 2:
            return 0.0

        n = min(len(high), len(low), len(close))
        true_ranges = []

        for i in range(1, n):
            hl = high[i] - low[i]
            hc = abs(high[i] - close[i - 1])
            lc = abs(low[i] - close[i - 1])
            tr = max(hl, hc, lc)
            true_ranges.append(tr)

        if not true_ranges:
            return 0.0

        # Use exponential moving average for ATR (standard approach)
        if len(true_ranges) <= period:
            return sum(true_ranges) / len(true_ranges)

        # Initial ATR = simple average of first 'period' true ranges
        atr = sum(true_ranges[:period]) / period
        # Smooth with EMA
        for i in range(period, len(true_ranges)):
            atr = (atr * (period - 1) + true_ranges[i]) / period

        return atr

    @staticmethod
    def atr_position_size(
        balance: float,
        atr: float,
        item_price: float,
        risk_per_trade_pct: float = 2.0,
    ) -> int:
        """
        v12.7: ATR-based position sizing (P2-5).

        Uses ATR to determine stop-loss distance and position size.
        Position size = (Balance * Risk%) / (ATR * multiplier)

        The ATR multiplier (1.5-2.0x) gives the stop-loss distance.
        This ensures each trade risks a fixed percentage of capital,
        with position size inversely proportional to volatility.

        Returns: number of units to buy (0 if risk too high).
        """
        if atr <= 0 or item_price <= 0 or balance <= 0:
            return 1  # Default to 1 unit if ATR unavailable

        # Stop-loss distance = 2x ATR (standard for volatile markets)
        stop_distance = atr * 2.0
        risk_amount = balance * (risk_per_trade_pct / 100.0)

        # Position size in units
        qty = int(risk_amount / stop_distance) if stop_distance > 0 else 1

        # Cap at what we can afford
        max_affordable = int(balance / item_price) if item_price > 0 else 0
        qty = min(qty, max_affordable)

        if qty <= 0 or max_affordable <= 0:
            return 0

        return max(1, qty)

    # ----------------------------------------------------------------
    # 3. TURNOVER REGULARIZATION
    # ----------------------------------------------------------------
    def _reset_daily_counter(self):
        """Reset trade counter at start of new day."""
        now = time.time()
        day_start = now - (now % 86400)
        if day_start > self._daily_trades_reset_ts:
            self._daily_trade_count = 0
            self._daily_trades_reset_ts = day_start

    # NOTE: This counter is SEPARATE from RiskManager._daily_trade_count.
    # They serve different purposes:
    #   - Strategy counter → turnover_penalty (frequency-based sizing)
    #   - RiskManager counter → daily_loss_limit, trade_count_limit (hard caps)
    # Both reset on UTC day boundary. They may drift if one is mutated
    # without the other, but this is acceptable: the strategy counter is
    # advisory (penalizes sizing), while the risk counter is authoritative
    # (blocks trades). If a unified counter is needed in the future, inject
    # a shared DailyCounter helper via __init__.
    #
    # v15.7: Added sync_risk_manager() to periodically sync the strategy
    # counter with RiskManager to prevent drift over long runs.
    _risk_manager: Any | None = None

    def set_risk_manager(self, risk_manager: Any) -> None:
        """Inject RiskManager reference for counter synchronization."""
        self._risk_manager = risk_manager

    def sync_risk_manager(self) -> None:
        """Sync strategy counter with RiskManager to prevent drift."""
        if self._risk_manager is not None:
            rm_count = getattr(self._risk_manager, '_daily_trade_count', 0)
            if rm_count > self._daily_trade_count:
                self._daily_trade_count = rm_count

    def calculate_turnover_penalty(self) -> float:
        """
        Calculate penalty for excessive trading frequency.
        Returns a multiplier in [0, 1] where 1 = no penalty, <1 = reduced sizing.
        """
        if not Config.TURNOVER_PENALTY_ENABLED:
            return 1.0

        self._reset_daily_counter()

        if self._daily_trade_count <= Config.MAX_DAILY_TRADES:
            return 1.0

        excess = self._daily_trade_count - Config.MAX_DAILY_TRADES
        penalty = excess * Config.TURNOVER_PENALTY_PER_TRADE
        return max(0.1, 1.0 - penalty)

    def record_trade(self):
        """Call after each trade execution."""
        self._reset_daily_counter()
        self._daily_trade_count += 1

    def get_daily_trade_count(self) -> int:
        self._reset_daily_counter()
        return self._daily_trade_count

    # ----------------------------------------------------------------
    # 4. SHARPE-ADJUSTED OBJECTIVE
    # ----------------------------------------------------------------
    def calculate_objective_score(
        self,
        expected_return_pct: float,
        volatility: float,
        liquidity_score: float = 0.5,
        sales_count: int = 0,
        spread_pct: float = 0.0,
        turnover_penalty: float = 1.0,
    ) -> float:
        """
        Calculate risk-adjusted objective score for an opportunity.
        Higher = better opportunity.

        Objective = (α × Return - β × Volatility + γ × Liquidity) × TurnoverPenalty
        """
        if not Config.SHARPE_OPTIMIZATION_ENABLED:
            # Legacy: just return spread if not using Sharpe optimization
            return spread_pct * turnover_penalty

        # Normalize return to daily (assume ~7 day hold)
        daily_return = expected_return_pct / 7.0

        # Risk-adjusted return (Sharpe-like)
        risk_free_rate = 0.0  # Simplified
        if volatility > 0:
            sharpe_proxy = (daily_return - risk_free_rate) / (volatility / math.sqrt(252))
        else:
            sharpe_proxy = daily_return * 10  # No vol = high confidence

        # Liquidity premium (illiquid items should have higher return requirement)
        liquidity_premium = 1.0 - (liquidity_score * 0.3)  # Up to 30% bonus for illiquid

        # Volume bonus (more sales = more reliable pricing)
        volume_bonus = min(1.0, sales_count / 10.0) * 0.1

        # Compose objective
        objective = (
            sharpe_proxy * 0.6
            + (spread_pct / max(float(Config.MIN_SPREAD_PCT), 0.01)) * 0.3
            + volume_bonus * 0.1
        ) * liquidity_premium * turnover_penalty

        return objective

    # ----------------------------------------------------------------
    # 5. ENHANCED OPPORTUNITY EVALUATION (abstract)
    # ----------------------------------------------------------------
    @abstractmethod
    def evaluate_opportunity(self, market_data: dict[str, Any]) -> dict[str, Any]:
        """
        Strategy core logic to analyze market data and return an action plan.
        Should return a dictionary containing:
          'action': 'place_target' | 'instant_buy' | 'none'
          'target_price': float
          'quantity': int
          'objective_score': float (optional, for ranking)
          'turnover_penalty': float (optional, for logging)
        """
        pass

    def evaluate_opportunity_enhanced(
        self,
        market_data: dict[str, Any],
        cross_market_data: Any | None = None,
        indicators: dict[str, float] | None = None,
        turnover_penalty: float = 1.0,
        reflection_result: Any | None = None,
    ) -> dict[str, Any]:
        """
        Enhanced evaluation that uses oracle cross-market data + indicators.
        Override in subclasses for strategy-specific logic.
        Default: delegate to evaluate_opportunity.
        """
        return self.evaluate_opportunity(market_data)
