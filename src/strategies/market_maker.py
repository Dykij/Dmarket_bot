"""
MarketMaker — Enhanced spread-based market making.

Improvements:
1. Turnover regularization (penalty for overtrading)
2. Sharpe-adjusted objective (risk-aware scoring)
3. Self-reflection parameter adaptation
4. Better volatility estimation (not just spread proxy)
"""

from typing import Any

from src.analytics.self_reflection import self_reflection
from src.config import Config
from src.strategies.base import BaseStrategy


class MarketMaker(BaseStrategy):
    def __init__(self):
        super().__init__("MarketMaker")

    def evaluate_opportunity(self, market_data: dict[str, Any], current_balance: float = 50.0) -> dict[str, Any]:
        """
        Enhanced Market Maker logic with risk-adjusted objectives.
        """
        item_name = market_data.get("title", "UnknownItem")
        best_ask = market_data.get("best_ask", 0.0)
        best_bid = market_data.get("best_bid", 0.0)

        if best_ask <= 0 or best_bid <= 0:
            return {"action": "none"}

        # --- Volatility ---
        spread_pct = self.spread_volatility(best_ask, best_bid)

        # --- Turnover Penalty ---
        turnover_penalty = self.calculate_turnover_penalty()

        # --- Price Target (spread-proportional undercut) ---
        spread = best_ask - best_bid
        if spread <= 0:
            return {"action": "none"}
        undercut = max(0.01, spread * 0.05)  # 5% of spread, min $0.01
        target_price = round(best_ask - undercut, 2)

        # --- Fee Calculation ---
        estimated_fee = target_price * Config.FEE_RATE
        gross_profit = best_ask - target_price
        net_profit = gross_profit - estimated_fee

        if net_profit <= 0:
            return {"action": "none"}

        net_margin_pct = (net_profit / target_price) * 100.0

        # --- Self-Reflection Adjustment ---
        reflection = self_reflection._cached_result
        adjusted_min_spread = self_reflection.get_adjusted_spread(Config.MIN_SPREAD_PCT, reflection)

        if net_margin_pct < adjusted_min_spread:
            return {"action": "none"}

        # --- Sharpe-Adjusted Objective ---
        volatility_score = max(1.0, spread_pct / float(Config.MIN_SPREAD_PCT))
        sharpe_estimate = net_margin_pct / (volatility_score * float(Config.MIN_SPREAD_PCT) + 0.01)

        objective_score = self.calculate_objective_score(
            expected_return_pct=net_margin_pct,
            volatility=volatility_score * Config.MIN_SPREAD_PCT / 100.0,  # vol proxy from spread level
            liquidity_score=0.5,  # Default, no cross-market data
            spread_pct=spread_pct,
            turnover_penalty=turnover_penalty,
        )

        # --- Position Sizing (v12.7: ATR-enhanced P2-5) ---
        # Use reflection-adjusted risk percentage (was silently discarded before v12.7)
        adjusted_risk_pct = self_reflection.get_adjusted_risk_pct(
            Config.MAX_POSITION_RISK_PCT, reflection
        )
        ohlcv = market_data.get("ohlcv")
        if ohlcv and len(ohlcv.get("high", [])) >= 15:
            atr = self.calculate_atr(
                ohlcv["high"], ohlcv["low"], ohlcv["close"], period=14
            )
            quantity = self.atr_position_size(
                balance=current_balance,
                atr=atr,
                item_price=target_price,
                risk_per_trade_pct=adjusted_risk_pct,
            )
        else:
            quantity = self.calculate_position_size(
                current_balance=current_balance,
                item_price=target_price,
                volatility_score=volatility_score,
                sharpe_estimate=sharpe_estimate,
            )

        if quantity <= 0:
            return {"action": "none"}

        self.logger.info(
            f"Targeting {quantity}x {item_name} at ${target_price:.2f} "
            f"(Spread: {spread_pct:.2f}% | Net: {net_margin_pct:.1f}% | "
            f"Turnover: {turnover_penalty:.2f} | Objective: {objective_score:.3f})"
        )

        return {
            "action": "place_target",
            "target_price": target_price,
            "quantity": quantity,
            "objective_score": objective_score,
            "turnover_penalty": turnover_penalty,
            "net_margin_pct": net_margin_pct,
        }
