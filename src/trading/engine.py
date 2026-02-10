"""Core Trading Engine."""

import asyncio
import logging
from decimal import Decimal
from typing import Any

from src.dmarket.dmarket_api import DMarketAPI
from src.waxpeer.waxpeer_api import WaxpeerAPI
from src.trading.strategies import StrategyFactory
from src.trading.fees import FeeCalculator
from src.utils.logger import logger

IS_DRY_RUN = True

class TradingEngine:
    """Orchestrator for multi-game trading."""

    def __init__(self, dmarket_api: DMarketAPI, waxpeer_api: WaxpeerAPI):
        self.dmarket = dmarket_api
        self.waxpeer = waxpeer_api
        self.games = ["csgo", "dota2", "rust", "tf2"]

    async def run_iteration(self) -> None:
        """Run one full cycle of analysis for all games."""
        logger.info("Starting trading iteration", dry_run=IS_DRY_RUN)

        for game in self.games:
            try:
                await self._process_game(game)
            except Exception as e:
                logger.error(f"Error processing game {game}", error=str(e))

    async def _process_game(self, game: str) -> None:
        """Process a single game strategy."""
        strategy = StrategyFactory.get_strategy(game)
        logger.info(f"Processing {game}...", strategy=strategy.__class__.__name__)

        # 1. Fetch DMarket Items (Batch)
        # Using exterior filters for CS2 to reduce noise
        filters = {}
        if game == "csgo":
            filters = {"treeFilters": "exterior[]=factory new,exterior[]=minimal wear,exterior[]=field-tested"}
        
        # Limit to 50 items for this iteration to avoid rate limits
        market_items = await self.dmarket.list_market_items(
            game_id=game, 
            limit=50, 
            **filters
        )
        
        items = market_items.get("objects", [])
        if not items:
            logger.info(f"No items found for {game}")
            return

        # 2. Analyze Items
        for item in items:
            title = item.get("title")
            price_dm = item.get("price", {}).get("USD")
            
            if not title or not price_dm:
                continue
                
            try:
                dmarket_price = Decimal(str(int(price_dm))) / 100
                
                # 3. Get Waxpeer Price (Live)
                # Note: Rate limit 10/min for list_items, but we use get_items_list (GET) which is 60/min
                # Still, need to be careful with batching. For now, one by one.
                wax_data = await self.waxpeer.get_items_list([title], game=game)
                wax_items = wax_data.get("items", [])
                
                if not wax_items:
                    continue
                    
                # Get lowest price on Waxpeer
                # Waxpeer returns price in mils (1/1000 USD)
                wax_price_mils = wax_items[0].get("price", 0)
                waxpeer_price = Decimal(str(wax_price_mils)) / 1000
                wax_volume = wax_items[0].get("count", 0)

                # 4. Strategy Check
                item_data = {
                    "title": title,
                    "dmarket_price": float(dmarket_price),
                    "waxpeer_price": float(waxpeer_price),
                    "waxpeer_volume": wax_volume,
                    # Steam price could be fetched here if needed by strategy
                    "steam_price": 0.0 
                }

                if await strategy.should_buy(item_data):
                    await self._execute_opportunity(item, dmarket_price, waxpeer_price, game)

            except Exception as e:
                logger.error("item_analysis_failed", item=title, error=str(e))

    async def _execute_opportunity(self, item: dict[str, Any], buy_price: Decimal, sell_price: Decimal, game: str) -> None:
        """Handle a profitable finding."""
        
        target_price = FeeCalculator.calculate_target_price(buy_price, game)
        profit = FeeCalculator.calculate_profit(buy_price, sell_price)
        roi = (profit / FeeCalculator.calculate_real_cost(buy_price)) * 100

        log_data = {
            "event": "trade_opportunity",
            "game": game,
            "item": item.get("title"),
            "buy_price": float(buy_price),
            "sell_price": float(sell_price),
            "target_break_even": float(FeeCalculator.calculate_break_even(buy_price)),
            "profit_usd": float(profit),
            "roi_percent": float(roi),
            "dry_run": IS_DRY_RUN
        }

        # Log with specific tag for Cloud Logging
        logger.info("PROFITABLE FIND", **log_data)

        if not IS_DRY_RUN:
            # TODO: Implement real buy logic
            pass
