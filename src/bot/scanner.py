"""
Script: src/bot/scanner.py (The Eyes)
Description: Scans the CS2 market for items with a profitable Spread.
Uses the "Batch API" to scan 200 items in 3 seconds.
Now with Pydantic validation and granular error handling.
"""

import asyncio
import logging
from typing import List, Dict

import aiohttp
import json
import numpy as np
from sklearn.linear_model import LinearRegression

try:
    # Attempt to load the PyO3 Rust extension module
    import rust_core
    RUST_CORE_AVAILABLE = True
    logging.info("🦀 Rust Core Engine loaded successfully. Polling will be optimized.")
except ImportError:
    RUST_CORE_AVAILABLE = False
    logging.warning("⚠️ Rust Core Engine not found. Falling back to native Python aiohttp.")

from src.config import Config
from src.models import AggregatedPricesResponse
from src.utils.api_client import AsyncDMarketClient

logger = logging.getLogger("Scanner")

# Minimum absolute profit in USD to consider a trade (filter noise)
MIN_PROFIT_USD = 0.03


class MarketScanner:
    """
    Finds profitable opportunities (Spread > MIN_SPREAD).
    Returns a list of items to place TARGETS on.
    Uses Pydantic models for type-safe API response parsing.
    """

    def __init__(self, client: AsyncDMarketClient):
        self.client = client
        self.base_min_spread = Config.MIN_SPREAD_PCT
        
        # Initialize Rust poller if compiled
        self.rust_poller = None
        if RUST_CORE_AVAILABLE:
            api_url = getattr(client, "api_url", "https://api.dmarket.com")
            self.rust_poller = rust_core.RustPoller(api_url)

    def predict_dynamic_spread(self, history_data: List[float]) -> float:
        """ML Price Prediction (Lightweight on CPU)"""
        if len(history_data) < 3:
            return self.base_min_spread
        try:
            X = np.arange(len(history_data)).reshape(-1, 1)
            y = np.array(history_data)
            model = LinearRegression()
            model.fit(X, y)
            progression = model.predict([[len(history_data)]])[0]
            # Dynamic adjustment: if trend goes up, we can demand more spread
            adjustment = min(max(progression - self.base_min_spread, -1.0), 3.0)
            return self.base_min_spread + adjustment
        except Exception as e:
            logger.warning(f"ML Prediction failed: {e}")
            return self.base_min_spread

    async def scan(self, items: List[str], game_id: str = Config.GAME_ID) -> List[Dict]:
        """
        Scans a batch of items and returns actionable opportunities.
        Expects a game_id parameter for multi-game support.
        """
        try:
            if self.rust_poller:
                # 🦀 High-Frequency Rust Poller
                logger.info(f"Rust Core: Fast-polling {len(items)} items...")
                raw_json = self.rust_poller.poll_market_sync(game_id, len(items))
                raw_response = json.loads(raw_json)
            else:
                # 🐍 Native Python aiohttp fallback
                raw_response = await self.client.get_aggregated_prices(
                    names=items, game=game_id
                )

            # Validate response with Pydantic
            response = AggregatedPricesResponse.model_validate(raw_response)

            if not response.aggregatedPrices:
                return []

            opportunities = []

            for item in response.aggregatedPrices:
                title = item.title
                bid_cents = item.orderBestPrice  # Already normalized by Pydantic
                ask_cents = item.offerBestPrice

                if bid_cents == 0 or ask_cents == 0:
                    continue

                bid_usd = bid_cents / 100.0
                ask_usd = ask_cents / 100.0

                # Filter by Price Range
                if not (Config.MIN_PRICE_USD <= ask_usd <= Config.MAX_PRICE_USD):
                    continue

                # Spread = (Ask - Bid) / Bid * 100
                spread_pct = ((ask_usd - bid_usd) / bid_usd) * 100

                # Adaptive Spread (Dynamic)
                # Using a mock history based on bid/ask for ML calculation (since we lack historical API feed for now)
                mock_history = [spread_pct * 0.9, spread_pct * 1.1, spread_pct]
                dynamic_min_spread = self.predict_dynamic_spread(mock_history)

                # Decision Logic: Buy at Bid+1, Sell at Ask-1
                if spread_pct >= dynamic_min_spread:
                    target_price = bid_cents + 1
                    sell_price_est = ask_cents - 1

                    # Net revenue after DMarket fee (from SELL price only)
                    sell_revenue = sell_price_est * (1.0 - Config.FEE_RATE)
                    net_profit = sell_revenue - target_price

                    if net_profit > 0 and (net_profit / 100.0) >= MIN_PROFIT_USD:
                        logger.info(
                            f"💎 FOUND: {title} | Spread: {spread_pct:.1f}% (DynMin: {dynamic_min_spread:.1f}%) | "
                            f"Buy: ${target_price / 100:.2f} | "
                            f"Sell: ${sell_price_est / 100:.2f} | "
                            f"Net Profit: ${net_profit / 100:.2f}"
                        )

                        opportunities.append(
                            {
                                "title": title,
                                "target_price": target_price,
                                "sell_price": sell_price_est,
                                "spread": spread_pct,
                                "profit": net_profit,
                            }
                        )
            return opportunities

        except aiohttp.ClientResponseError as e:
            logger.error(f"Scan API error ({e.status}): {e.message}")
            return []
        except asyncio.TimeoutError:
            logger.error("Scan timeout: DMarket API did not respond in time")
            return []
        except ValueError as e:
            logger.error(f"Scan validation error: {e}")
            return []
        except Exception as e:
            logger.error(f"Scan unexpected error: {type(e).__name__}: {e}")
            return []
