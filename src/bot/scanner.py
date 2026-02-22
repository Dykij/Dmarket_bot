"""
Script: src/bot/scanner.py (The Eyes)
Description: Scans the CS2 market for items with a profitable Spread.
Uses the new "Batch API" to scan 200 items in 3 seconds.
"""

import asyncio
import logging
from typing import List, Dict

from src.config import Config
from src.utils.api_client import AsyncDMarketClient

logger = logging.getLogger("Scanner")

class MarketScanner:
    """
    Finds profitable opportunities (Spread > MIN_SPREAD).
    Returns a list of items to place TARGETS on.
    """
    
    def __init__(self, client: AsyncDMarketClient):
        self.client = client
        self.min_spread = Config.MIN_SPREAD_PCT

    async def scan(self, items: List[str]) -> List[Dict]:
        """
        Scans a batch of items and returns actionable opportunities.
        Input: ["AK-47 | Slate", "AWP | Atheris", ...]
        Output: [{"title": "AK-47 | Slate", "price": 1200, "profit": 0.50}, ...]
        """
        try:
            # High-Speed Batch Fetch
            response = await self.client.get_aggregated_prices(names=items, game=Config.GAME_ID)
            
            if "aggregatedPrices" not in response:
                return []

            market_data = response["aggregatedPrices"]
            opportunities = []

            for item in market_data:
                title = item.get("title", "Unknown")
                
                # Parse Prices safely (handle dict or int)
                bid_raw = item.get("orderBestPrice", 0)
                ask_raw = item.get("offerBestPrice", 0)
                
                bid_cents = self._safe_int(bid_raw)
                ask_cents = self._safe_int(ask_raw)

                if bid_cents == 0 or ask_cents == 0:
                    continue

                bid_usd = bid_cents / 100.0
                ask_usd = ask_cents / 100.0

                # Filter by Price Range
                if not (Config.MIN_PRICE_USD <= ask_usd <= Config.MAX_PRICE_USD):
                    continue

                # Calculate Spread
                spread_pct = ((ask_usd - bid_usd) / ask_usd) * 100

                # Decision Logic: Buy at Bid+1, Sell at Ask-1
                if spread_pct >= self.min_spread:
                    target_price = bid_cents + 1
                    sell_price_est = ask_cents - 1
                    
                    revenue = sell_price_est * (1.0 - Config.FEE_RATE)  # Fee from Config
                    profit = revenue - target_price
                    
                    if profit > 0:
                        logger.info(f"💎 FOUND: {title} | Spread: {spread_pct:.1f}% | Profit: ${(profit/100):.2f}")
                        opportunities.append({
                            "title": title,
                            "target_price": target_price,
                            "sell_price": sell_price_est,
                            "spread": spread_pct,
                            "profit": profit
                        })

            return opportunities

        except Exception as e:
            logger.error(f"Scan failed: {e}")
            return []

    def _safe_int(self, value) -> int:
        if isinstance(value, dict):
            return int(value.get("Amount", 0))
        elif isinstance(value, (int, float)):
            return int(value)
        elif isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return 0
        return 0
