"""
CrossMarketStrategy — Multi-marketplace arbitrage via MultiSourceOracle.

Uses multi-source oracle data to find:
  1. Direct arbitrage: Buy cheap on DMarket, sell high on another market
  2. Bid arbitrage: Place buy targets at prices below highest buy orders
  3. Indicator-driven: Use RSI/MACD/Bollinger to time entries

Requires: MultiSourceOracle (not CSFloat fallback).
"""

import logging
import math
from typing import Any

from src.config import Config
from src.strategies.base import BaseStrategy

logger = logging.getLogger("CrossMarket")


class CrossMarketStrategy(BaseStrategy):
    """
    Strategy that leverages MultiSourceOracle cross-market data for arbitrage.
    """

    def __init__(self):
        super().__init__("CrossMarket")

    def evaluate_opportunity(self, market_data: dict[str, Any]) -> dict[str, Any]:
        """Basic evaluation without cross-market data (fallback)."""
        return {"action": "none"}

    def evaluate_opportunity_enhanced(
        self,
        market_data: dict[str, Any],
        cross_market_data: Any | None = None,
        indicators: dict[str, float] | None = None,
        turnover_penalty: float = 1.0,
        reflection_result: Any | None = None,
    ) -> dict[str, Any]:
        """
        Evaluate an item using cross-market data from the oracle.
        """
        item_name = market_data.get("title", "UnknownItem")
        raw_ask = market_data.get("best_ask", 0.0)
        dmarket_price = raw_ask / 100.0 if isinstance(raw_ask, (int, float)) and raw_ask > 100 else float(raw_ask)

        if dmarket_price <= 0 or dmarket_price < Config.MIN_PRICE_USD:
            return {"action": "none"}

        if cross_market_data is None:
            return {"action": "none"}

        # --- 1. Direct Cross-Market Arbitrage ---
        # Can we buy on DMarket and sell on another market for profit?

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

        if gross_margin_pct < Config.MIN_SPREAD_PCT:
            return {"action": "none"}

        # --- 2. Apply Fee/Slippage Model ---
        dest_fee_pct = float(Config.CROSS_MARKET_DESTINATION_FEE)
        net_sell = sell_price * (1 - dest_fee_pct)
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
        # If there's a buy order above our target price after fees, instant sell is possible
        dest_fee_pct = float(Config.CROSS_MARKET_DESTINATION_FEE)
        instant_sell_opportunity = False
        for _provider, bid in cross_market_data.buy_orders.items():
            if bid * (1 - dest_fee_pct) > dmarket_price:
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

        # --- 8. Position Sizing (v12.7: ATR-enhanced P2-5) ---
        volatility_score = max(1.0, cross_market_data.volatility_24h * 10) if cross_market_data.volatility_24h > 0 else 1.0
        sharpe_estimate = max(0.1, net_margin_pct / (volatility_score + 0.01))

        # Use ATR-based sizing if cross-market data has OHLC, else legacy
        if hasattr(cross_market_data, 'atr') and cross_market_data.atr > 0:
            quantity = self.atr_position_size(
                balance=market_data.get("current_balance", 50.0),
                atr=cross_market_data.atr,
                item_price=dmarket_price,
                risk_per_trade_pct=2.0,
            )
        else:
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
            # Place target at best bid accounting for destination fee (guaranteed instant sell)
            best_bid = cross_market_data.global_max_bid
            if best_bid > 0:
                target_price = round(best_bid * (1 - dest_fee_pct), 2)
            else:
                target_price = round(dmarket_price * 0.95, 2)
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
