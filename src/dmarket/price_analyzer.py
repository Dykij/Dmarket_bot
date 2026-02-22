"""Price Analyzer module for arbitrage opportunities.

Analyzes market prices, sales history, and calculates potential profit
for arbitrage trading.
"""

import logging
from src.dmarket.pricing.fee_oracle import fee_oracle

logger = logging.getLogger(__name__)


class PriceAnalyzer:
    """Analyzer for calculating profit and evaluating items."""

    def __init__(self, min_roi: float = 12.0, max_price_usd: float = 100.0):
        """Initialize PriceAnalyzer.

        Args:
            min_roi: Minimum Return on Investment percentage
            max_price_usd: Maximum item price in USD
        """
        self.min_roi = min_roi
        self.max_price_usd = max_price_usd
        # self.market_fee is now dynamic

    async def calculate_profit(
        self,
        buy_price_cents: int,
        avg_sell_price_cents: int,
        steam_price_cents: int | None = None,
        game_id: str = "a8db",
        title: str = "Unknown"
    ) -> dict:
        """Calculate potential net profit.

        Args:
            buy_price_cents: Buying price in cents
            avg_sell_price_cents: Average selling price in cents
            steam_price_cents: Steam price in cents (optional)
            game_id: Game identifier for fee lookup
            title: Item title for fee lookup

        Returns:
            Dict with profit analysis
        """
        # Dynamic Fee Lookup
        fee_fraction = await fee_oracle.get_fee_for_item(game_id, title)
        
        # How much we get after market fee
        potential_revenue = avg_sell_price_cents * (1 - fee_fraction)
        net_profit = potential_revenue - buy_price_cents

        if buy_price_cents > 0:
            roi = (net_profit / buy_price_cents) * 100
        else:
            roi = 0.0

        result = {
            "net_profit_usd": round(net_profit / 100, 2),
            "roi_percent": round(roi, 2),
            "is_profitable": roi >= self.min_roi,
            "used_fee": fee_fraction
        }
        
        return result

    async def analyze_opportunity(
        self,
        item_title: str,
        game_id: str,
        dmarket_price_usd: float,
        steam_price_data: dict | None,
        aggregated_data: dict | None
    ) -> dict:
        """
        Deep analysis using Fees, Steam Price, and Market Depth (OBI).
        """
        # 1. Steam-to-Cash (K_s2c)
        k_s2c = 0.0
        steam_median = 0.0
        if steam_price_data:
            steam_median = steam_price_data.get("median_price", 0.0)
            if steam_median > 0:
                k_s2c = dmarket_price_usd / steam_median

        # 2. OBI (Order Book Imbalance) & Spread
        obi = 0.0
        spread_percent = 0.0
        
        if aggregated_data:
            # aggregated_data format: { "orderBestPrice": ..., "orderCount": ..., "offerBestPrice": ..., "offerCount": ... }
            # best_buy = orderBestPrice, best_sell = offerBestPrice
            
            try:
                best_buy_cents = int(aggregated_data.get("orderBestPrice", {}).get("Amount", 0))
                best_sell_cents = int(aggregated_data.get("offerBestPrice", {}).get("Amount", 0))
                
                buy_vol = int(aggregated_data.get("orderCount", 0))
                sell_vol = int(aggregated_data.get("offerCount", 0))
                
                total_vol = buy_vol + sell_vol
                if total_vol > 0:
                    obi = (buy_vol - sell_vol) / total_vol
                    
                if best_sell_cents > 0:
                    spread_cents = best_sell_cents - best_buy_cents
                    spread_percent = (spread_cents / best_sell_cents) * 100
            except:
                pass

        # 3. Dynamic Profit Calc
        # Convert usd to cents for precision
        buy_cents = int(dmarket_price_usd * 100)
        # Prediction: We sell at current best offer price? Or undercut?
        # Conservative: Sell at Best Offer - 1 cent (if we want to be liquidity provider)
        # Aggressive: Sell at Best Order + 1 cent?
        # Let's assume we sell at current DMarket price (just to check if IT is profitable itself)
        
        profit_analysis = await self.calculate_profit(
            buy_price_cents=buy_cents,
            avg_sell_price_cents=buy_cents, # Assuming price stability
            steam_price_cents=int(steam_median * 100),
            game_id=game_id,
            title=item_title
        )
        
        return {
            "title": item_title,
            "k_s2c": round(k_s2c, 3),
            "obi": round(obi, 2),
            "spread": round(spread_percent, 2),
            "profit": profit_analysis,
            "steam_price": steam_median
        }

        # Add Steam comparison if avAlgolable
        if steam_price_cents and steam_price_cents > 0:
            # Calculate profit if sold on Steam (minus 13% fee)
            # Steam fee is ~13.04% (15% markup) -> 0.8696 multiplier
            steam_revenue = steam_price_cents * 0.8696
            steam_profit = steam_revenue - buy_price_cents
            steam_roi = (steam_profit / buy_price_cents) * 100

            result["steam_profit_usd"] = round(steam_profit / 100, 2)
            result["steam_roi_percent"] = round(steam_roi, 2)
            result["steam_price_usd"] = round(steam_price_cents / 100, 2)

            # If Steam ROI is significantly higher, it's a good indicator
            # even if DMarket history is weak
            if steam_roi >= self.min_roi:
                result["is_profitable"] = True
                result["reason"] = "steam_arbitrage"

        return result

    def evaluate_item(
        self, item_data: dict, history_data: list, steam_price_data: dict | None = None
    ) -> bool:
        """Analyze specific skin based on sales history and Steam price.

        Args:
            item_data: Item data from market
            history_data: List of past sales
            steam_price_data: Steam price data (optional)

        Returns:
            True if item is profitable
        """
        try:
            price_data = item_data.get("price", {})
            if isinstance(price_data, dict):
                # buy_price_usd extracted for reference but cents used for comparisons
                _buy_price_usd = float(price_data.get("USD", 0)) / 100  # noqa: F841
                buy_price_cents = int(price_data.get("USD", 0))
            else:
                # Handle case where price might be direct value
                _buy_price_usd = float(price_data) / 100  # noqa: F841
                buy_price_cents = int(price_data)

            if buy_price_cents <= 0:
                return False

            # Get Steam price if avAlgolable
            steam_price_cents = None
            if steam_price_data:
                # Steam price is usually in dollars/float
                steam_price_float = steam_price_data.get("price", 0)
                if steam_price_float:
                    steam_price_cents = int(steam_price_float * 100)

            # Take median price from last 10 sales for stability
            prices = []
            if history_data:
                for sale in history_data[:10]:
                    price = sale.get("price", {})
                    if isinstance(price, dict):
                        amount = int(price.get("amount", 0))
                    else:
                        amount = int(price)
                    if amount > 0:
                        prices.append(amount)

            # If no history but we have Steam price, use Steam price as reference
            # but be more conservative (assume DMarket price is lower than Steam)
            if not prices:
                if steam_price_cents:
                    # Assume we can sell on DMarket for 80% of Steam price
                    median_sell_price = int(steam_price_cents * 0.8)
                else:
                    return False
            else:
                median_sell_price = sorted(prices)[len(prices) // 2]

            analysis = self.calculate_profit(
                buy_price_cents, median_sell_price, steam_price_cents
            )

            if analysis["is_profitable"]:
                reason = analysis.get("reason", "dmarket_history")
                steam_info = ""
                if "steam_roi_percent" in analysis:
                    steam_info = f" | Steam ROI: {analysis['steam_roi_percent']}%"

                logger.info(
                    f"🔥 Найдена цель ({reason}): {item_data.get('title', 'Unknown')} | "
                    f"ROI: {analysis['roi_percent']}%{steam_info}"
                )
                return True

        except (ValueError, TypeError, KeyError) as e:
            logger.warning(f"Error evaluating item: {e}")
            return False

        return False
