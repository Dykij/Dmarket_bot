"""
Self-Reflection Module — Adaptive parameter tuning from trade history.

Inspired by arXiv papers:
  - "TradingGroup: Multi-Agent with Self-Reflection"
  - "Directly Learning Stock Trading Strategies Through Profit Guided Loss Functions"

Analyzes recent trades to:
  1. Calculate realized Sharpe/Sortino ratios
  2. Detect which strategy parameters lead to wins/losses
  3. Auto-adjust MIN_SPREAD_PCT, MAX_POSITION_RISK_PCT, VOLATILITY thresholds
  4. Track PnL attribution (what worked, what didn't)
"""

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any

from src.config import Config
from src.db.price_history import price_db

logger = logging.getLogger("SelfReflection")


@dataclass
class TradeRecord:
    """A single completed or virtual trade."""
    hash_name: str
    buy_price: float
    expected_sell_price: float
    actual_sell_price: float = 0.0
    fee_paid: float = 0.0
    profit: float = 0.0
    hold_days: float = 0.0
    timestamp: float = 0.0
    strategy_params: dict[str, Any] = field(default_factory=dict)
    market_conditions: dict[str, Any] = field(default_factory=dict)


@dataclass
class ReflectionResult:
    """Result of self-reflection analysis."""
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    win_rate: float = 0.0
    avg_profit_per_trade: float = 0.0
    avg_hold_days: float = 0.0
    recommended_spread_adjustment: float = 0.0
    recommended_risk_adjustment: float = 0.0
    recommended_volatility_adjustment: float = 0.0
    total_trades_analyzed: int = 0
    profitable_trades: int = 0
    losing_trades: int = 0
    confidence: float = 0.0  # 0-1, how confident we are in the recommendations


class SelfReflectionEngine:
    """
    Analyzes trade history and recommends parameter adjustments.
    Runs periodically during scan cycles.
    """

    def __init__(self):
        self._last_reflection_cycle = 0
        self._cached_result: ReflectionResult | None = None
        self._reflection_count = 0

    async def maybe_run_reflection(self, cycle_count: int) -> ReflectionResult | None:
        """
        Run reflection if enough cycles have passed.
        Called from the main sniping loop.
        """
        if not Config.PARAMETER_ADJUSTMENT_ENABLED:
            return None

        interval = Config.SELF_REFLECTION_INTERVAL
        if cycle_count - self._last_reflection_cycle < interval:
            return self._cached_result

        result = await self.analyze_recent_trades()
        self._cached_result = result
        self._last_reflection_cycle = cycle_count
        self._reflection_count += 1

        if result and result.confidence > 0.3:
            logger.info(
                f"🔍 [REFLECTION #{self._reflection_count}] "
                f"Sharpe={result.sharpe_ratio:.2f} Sortino={result.sortino_ratio:.2f} "
                f"WinRate={result.win_rate:.1%} Trades={result.total_trades_analyzed} "
                f"Confidence={result.confidence:.1%}"
            )
            logger.info(
                f"  → Spread adj: {result.recommended_spread_adjustment:+.2f}% "
                f"Risk adj: {result.recommended_risk_adjustment:+.2f}% "
                f"Vol adj: {result.recommended_volatility_adjustment:+.2f}%"
            )

        return result

    async def analyze_recent_trades(self) -> ReflectionResult | None:
        """
        Analyze recent trades from the virtual inventory and calculate
        performance metrics + parameter recommendations.
        """
        # Get virtual inventory with PnL
        try:
            cursor = await price_db.run_in_thread(
                price_db.state_conn.execute,
                """SELECT hash_name, buy_price, sell_price, fee_paid, profit,
                          status, acquired_at, sold_at
                   FROM virtual_inventory
                   WHERE status IN ('sold', 'idle', 'selling')
                   ORDER BY acquired_at DESC
                   LIMIT ?""",
                (Config.SELF_REFLECTION_WINDOW,),
            )
            rows = await price_db.run_in_thread(cursor.fetchall)
        except Exception as e:
            logger.debug(f"Self-reflection query failed: {e}")
            return None

        if len(rows) < Config.MIN_TRADES_FOR_ADJUSTMENT:
            return ReflectionResult(total_trades_analyzed=len(rows), confidence=0.0)

        trades = []
        for row in rows:
            buy = row["buy_price"]
            sell = row["sell_price"] or 0.0
            fee = row["fee_paid"] or 0.0
            status = row["status"]
            acquired = row["acquired_at"]
            sold_at = row["sold_at"]

            if status == "sold" and sell > 0:
                profit = sell - buy - fee
                hold = (sold_at - acquired) / 86400 if sold_at and acquired else 0.0
            else:
                continue  # skip idle/selling — not yet realized

            trades.append(TradeRecord(
                hash_name=row["hash_name"],
                buy_price=buy,
                expected_sell_price=sell if sell > 0 else buy * 1.05,
                actual_sell_price=sell,
                fee_paid=fee,
                profit=profit,
                hold_days=hold,
                timestamp=acquired,
            ))

        if not trades:
            return ReflectionResult(confidence=0.0)

        return self._calculate_metrics(trades)

    def _calculate_metrics(self, trades: list[TradeRecord]) -> ReflectionResult:
        """Calculate Sharpe, Sortino, drawdown, and parameter recommendations."""
        result = ReflectionResult()
        result.total_trades_analyzed = len(trades)

        # --- Basic Stats ---
        profits = [t.profit for t in trades]
        result.profitable_trades = sum(1 for p in profits if p > 0)
        result.losing_trades = sum(1 for p in profits if p < 0)
        result.avg_profit_per_trade = sum(profits) / len(profits) if profits else 0.0
        result.win_rate = result.profitable_trades / len(trades) if trades else 0.0
        result.avg_hold_days = sum(t.hold_days for t in trades) / len(trades) if trades else 0.0

        # --- Returns Series (percentage) ---
        returns = []
        for t in trades:
            if t.buy_price > 0:
                ret = t.profit / t.buy_price
                returns.append(ret)

        if len(returns) < 2:
            result.confidence = len(trades) / Config.MIN_TRADES_FOR_ADJUSTMENT
            return result

        # --- Sharpe Ratio ---
        mean_ret = sum(returns) / len(returns)
        variance = sum((r - mean_ret) ** 2 for r in returns) / (len(returns) - 1)
        std_dev = math.sqrt(variance) if variance > 0 else 1e-10

        # Annualize (assume ~1 trade/day for conservative estimate)
        result.sharpe_ratio = (mean_ret / std_dev) * math.sqrt(252) if std_dev > 0 else 0.0

        # --- Sortino Ratio (only downside deviation) ---
        downside_returns = [r for r in returns if r < 0]
        if downside_returns:
            downside_var = sum(r ** 2 for r in downside_returns) / len(downside_returns)
            downside_std = math.sqrt(downside_var)
            result.sortino_ratio = (mean_ret / downside_std) * math.sqrt(252) if downside_std > 0 else 0.0
        else:
            result.sortino_ratio = float('inf') if mean_ret > 0 else 0.0

        # --- Max Drawdown ---
        cumulative = 0.0
        peak = 0.0
        max_dd = 0.0
        for r in returns:
            cumulative += r
            if cumulative > peak:
                peak = cumulative
            dd = peak - cumulative
            if dd > max_dd:
                max_dd = dd
        result.max_drawdown = max_dd

        # --- Parameter Recommendations ---
        # Based on arXiv: Profit-Guided Loss Functions
        # We adjust parameters toward better risk-adjusted returns

        target_sharpe = Config.TARGET_SHARPE_RATIO

        # If Sharpe is below target, tighten spread requirement
        if result.sharpe_ratio < target_sharpe:
            # Need higher margins per trade
            deficit = target_sharpe - result.sharpe_ratio
            result.recommended_spread_adjustment = min(2.0, deficit * 0.5)
        else:
            # Can afford to be slightly more aggressive
            surplus = result.sharpe_ratio - target_sharpe
            result.recommended_spread_adjustment = max(-1.0, -surplus * 0.3)

        # If win rate is low, reduce position size per item
        if result.win_rate < 0.4:
            result.recommended_risk_adjustment = -1.0  # Reduce risk
        elif result.win_rate > 0.7 and result.sharpe_ratio > 1.5:
            result.recommended_risk_adjustment = 0.5  # Slightly increase risk

        # If Sortino is much lower than Sharpe, volatility is a problem
        if result.sortino_ratio < result.sharpe_ratio * 0.5 and result.sortino_ratio < 1.0:
            result.recommended_volatility_adjustment = -0.05  # Tighten vol filter

        # --- Confidence Score ---
        # Higher with more trades and lower drawdown
        trade_confidence = min(1.0, len(trades) / Config.SELF_REFLECTION_WINDOW)
        dd_confidence = max(0.0, 1.0 - result.max_drawdown * 5)
        result.confidence = (trade_confidence + dd_confidence) / 2.0

        return result

    def get_adjusted_spread(self, base_spread: float, reflection: ReflectionResult | None = None) -> float:
        """Apply self-reflection adjustment to MIN_SPREAD_PCT."""
        if reflection is None:
            reflection = self._cached_result
        if reflection is None or reflection.confidence < 0.3:
            return base_spread
        return base_spread + reflection.recommended_spread_adjustment

    def get_adjusted_risk_pct(self, base_risk: float, reflection: ReflectionResult | None = None) -> float:
        """Apply self-reflection adjustment to MAX_POSITION_RISK_PCT."""
        if reflection is None:
            reflection = self._cached_result
        if reflection is None or reflection.confidence < 0.3:
            return base_risk
        adjusted = base_risk + reflection.recommended_risk_adjustment
        return max(1.0, min(10.0, adjusted))  # Clamp to 1-10%

    def get_adjusted_volatility_max(self, base_max: float, reflection: ReflectionResult | None = None) -> float:
        """Apply self-reflection adjustment to volatility threshold."""
        if reflection is None:
            reflection = self._cached_result
        if reflection is None or reflection.confidence < 0.3:
            return base_max
        adjusted = base_max + reflection.recommended_volatility_adjustment
        return max(0.1, min(1.0, adjusted))  # Clamp to 10-100%

    async def get_volatility_regime_adjustment(self) -> float:
        """
        v12.7: Dynamic spread adjustment based on market volatility regime.

        Classifies recent market conditions and adjusts MIN_SPREAD_PCT:
        - HIGH volatility (>2% avg daily moves): +1.5% spread (be selective)
        - MEDIUM volatility (0.5-2%): no adjustment
        - LOW volatility (<0.5%): -0.5% spread (capture more opportunities)

        Returns: adjustment to add to MIN_SPREAD_PCT (can be negative).
        """
        try:
            # Sample recent price volatility from DB
            cursor = await price_db.run_in_thread(
                price_db.history_conn.execute,
                """SELECT hash_name, price, recorded_at
                   FROM price_history
                   WHERE recorded_at > ? AND price > 0
                   ORDER BY recorded_at DESC
                   LIMIT 500""",
                (time.time() - 86400,),
            )
            rows = await price_db.run_in_thread(cursor.fetchall)

            if len(rows) < 50:
                return 0.0  # Not enough data

            # Group by item and calculate per-item volatility
            from collections import defaultdict
            item_prices: dict[str, list[float]] = defaultdict(list)
            for row in rows:
                item_prices[row["hash_name"]].append(row["price"])

            volatilities = []
            for prices in item_prices.values():
                if len(prices) < 3:
                    continue
                # Calculate average absolute return
                returns = []
                for i in range(1, len(prices)):
                    if prices[i-1] > 0:
                        returns.append(abs(prices[i] / prices[i-1] - 1))
                if returns:
                    volatilities.append(sum(returns) / len(returns))

            if not volatilities:
                return 0.0

            avg_vol = sum(volatilities) / len(volatilities)

            # Classify regime and return adjustment
            if avg_vol > 0.02:  # >2% avg daily move
                logger.info(f"[VOL-REGIME] HIGH volatility ({avg_vol:.2%}), tightening spread +1.5%")
                return 1.5
            elif avg_vol < 0.005:  # <0.5% avg daily move
                logger.info(f"[VOL-REGIME] LOW volatility ({avg_vol:.2%}), loosening spread -0.5%")
                return -0.5
            else:
                return 0.0

        except Exception as e:
            logger.debug(f"Volatility regime detection failed: {e}")
            return 0.0


# Singleton
self_reflection = SelfReflectionEngine()
