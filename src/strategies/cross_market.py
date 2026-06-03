"""
CrossMarketStrategy — Multi-marketplace arbitrage via CS2Cap.

Uses CS2Cap's 41-market data to find:
  1. Direct arbitrage: Buy cheap on DMarket, sell high on another market
  2. Bid arbitrage: Place buy targets at prices below highest buy orders
  3. Indicator-driven: Use RSI/MACD/Bollinger to time entries

Requires: CS2CapOracle (not CSFloat fallback).
"""

import logging
import math
from typing import Any, Dict, Optional

from src.config import Config
from src.strategies.base import BaseStrategy

logger = logging.getLogger("CrossMarket")


class CrossMarketStrategy(BaseStrategy):
    """
    Strategy that leverages CS2Cap cross-market data for 41-market arbitrage.
    """

    def __init__(self):
        super().__init__("CrossMarket")

    def evaluate_opportunity(self, market_data: Dict[str, Any]) -> Dict[str, Any]:
        """Basic evaluation without cross-market data (fallback)."""
        return {"action": "none"}

    def evaluate_opportunity_enhanced(
        self,
        market_data: Dict[str, Any],
        cross_market_data: Optional[Any] = None,
        indicators: Optional[Dict[str, float]] = None,
        turnover_penalty: float = 1.0,
        reflection_result: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Evaluate an item using cross-market data from CS2Cap.
        """
        item_name = market_data.get("title", "UnknownItem")
        dmarket_price = market_data.get("best_ask", 0.0) / 100.0 if market_data.get("best_ask", 0) > 100 else market_data.get("best_ask", 0.0)

        if dmarket_price <= 0 or dmarket_price < Config.MIN_PRICE_USD:
            return {"action": "none"}

        if cross_market_data is None:
            return {"action": "none"}

        # --- 1. Direct Cross-Market Arbitrage ---
        # Can we buy on DMarket and sell on another market for profit?
        best_sell_price = cross_market_data.global_min_ask  # We'd sell here

        # Find all sell prices above our buy price (potential sell venues)
        profitable_sells = [
            (provider, price)
            for provider, price in cross_market_data.provider_prices.items()
            if price > dmarket_price * 1.05  # At least 5% above buy price
        ]

        # Also check buy orders (we could sell to someone who wants to buy)
        for provider, bid in cross_market_data.buy_orders.items():
            if bid > dmarket_price * 1.05:
                profitable_sells.append((f"{provider}_bid", bid))

        if not profitable_sells:
            return {"action": "none"}

        # Best sell venue
        sell_provider, sell_price = max(profitable_sells, key=lambda x: x[1])
        gross_margin_pct = ((sell_price - dmarket_price) / dmarket_price) * 100.0

        # --- 2. Apply Fee/Slippage Model ---
        # DMarket fee (5%) + potential sell-side fee on destination
        net_sell = sell_price * 0.95  # Assume ~5% fee on sell side
        net_margin_pct = ((net_sell - dmarket_price) / dmarket_price) * 100.0

        # Adjusted spread for self-reflection
        if reflection_result:
            adjusted_min_spread = Config.MIN_SPREAD_PCT + reflection_result.recommended_spread_adjustment
        else:
            adjusted_min_spread = Config.MIN_SPREAD_PCT

        if net_margin_pct < adjusted_min_spread:
            return {"action": "none"}

        # --- 3. Cross-Market Spread Filter ---
        # If there's too much price discrepancy across markets, skip
        all_prices = list(cross_market_data.provider_prices.values())
        if len(all_prices) >= 2:
            price_std = math.sqrt(
                sum((p - sum(all_prices)/len(all_prices))**2 for p in all_prices)
                / len(all_prices)
            )
            price_mean = sum(all_prices) / len(all_prices)
            internal_spread_pct = (price_std / price_mean) * 100.0 if price_mean > 0 else 0

            if internal_spread_pct > Config.CROSS_MARKET_MAX_SPREAD_PCT:
                logger.debug(
                    f"Skipping {item_name}: internal spread {internal_spread_pct:.1f}% "
                    f"exceeds {Config.CROSS_MARKET_MAX_SPREAD_PCT}%"
                )
                return {"action": "none"}

        # --- 4. Indicator-Enhanced Entry Timing ---
        signal_quality = 1.0
        if indicators:
            rsi = indicators.get("rsi", 50.0)
            bb_pos = indicators.get("bb_position", 0.5)

            # Prefer buying when RSI < 30 (oversold) or BB position < 0.2 (near lower band)
            if rsi < 30:
                signal_quality *= 1.3
            elif rsi > 70:
                signal_quality *= 0.7  # Overbought, less attractive

            if bb_pos < 0.2:
                signal_quality *= 1.2  # Near lower Bollinger band
            elif bb_pos > 0.8:
                signal_quality *= 0.8

        # --- 5. Liquidity Check ---
        if cross_market_data.liquidity_score < 0.1:
            logger.debug(f"Skipping {item_name}: too illiquid (score={cross_market_data.liquidity_score:.2f})")
            return {"action": "none"}

        # --- 6. Bid-Arbitrage Check ---
        # If there's a buy order above our target price, instant sell is possible
        instant_sell_opportunity = False
        for provider, bid in cross_market_data.buy_orders.items():
            if bid > dmarket_price * 1.03:  # At least 3% above buy price
                instant_sell_opportunity = True
                break

        # --- 7. Compose Final Score ---
        objective_score = self.calculate_objective_score(
            expected_return_pct=net_margin_pct,
            volatility=cross_market_data.volatility_24h,
            liquidity_score=cross_market_data.liquidity_score,
            sales_count=cross_market_data.sales_count,
            spread_pct=net_margin_pct,
            turnover_penalty=turnover_penalty,
        ) * signal_quality

        # --- 8. Position Sizing ---
        volatility_score = max(1.0, cross_market_data.volatility_24h * 10) if cross_market_data.volatility_24h > 0 else 1.0
        sharpe_estimate = max(0.1, net_margin_pct / (volatility_score + 0.01))

        quantity = self.calculate_position_size(
            current_balance=market_data.get("current_balance", 50.0),
            item_price=dmarket_price,
            volatility_score=volatility_score,
            sharpe_estimate=sharpe_estimate,
        )

        if quantity <= 0:
            return {"action": "none"}

        # --- 9. Determine Target Price ---
        # Target slightly below best buy order, or undercut current ask
        if instant_sell_opportunity:
            # Place target slightly below best bid (guaranteed instant sell)
            best_bid = cross_market_data.global_max_bid
            target_price = round(best_bid * 0.98, 2) if best_bid > 0 else round(dmarket_price * 0.95, 2)
        else:
            # Target below DMarket ask
            target_price = round(dmarket_price * 0.95, 2)

        logger.info(
            f"🎯 {item_name}: DMarket=${dmarket_price:.2f} → "
            f"Sell@{sell_provider}=${sell_price:.2f} | "
            f"Net Margin: {net_margin_pct:.1f}% | Objective: {objective_score:.3f} | "
            f"Qty: {quantity}"
        )

        return {
            "action": "place_target",
            "target_price": target_price,
            "quantity": quantity,
            "objective_score": objective_score,
            "turnover_penalty": turnover_penalty,
            "sell_venue": sell_provider,
            "net_margin_pct": net_margin_pct,
        }
