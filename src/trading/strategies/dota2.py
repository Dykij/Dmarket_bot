"""Dota 2 Trading Strategy."""

from decimal import Decimal
from typing import Any
import logging

from src.trading.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class Dota2Strategy(BaseStrategy):
    """
    Strategy for Dota 2.

    ConstrAlgonts:
    - Generally lower trade locks (often 0 days for P2P if not market restricted).
    - Lower risk premium needed compared to CS2.
    """

    def __init__(self, min_profit_percent: float = 3.0):
        # Dota items turn faster, so we might accept slightly lower margin per trade
        super().__init__(game_id="dota2", min_profit_percent=min_profit_percent)

    def get_query_filters(self) -> dict[str, str]:
        """
        Dota 2 Specific Logic:
        Focus on high-liquidity rarities: Immortal, Arcana, Legendary.
        This filters out thousands of common 3-cent items.
        """
        # DMarket filters for rarity often use 'rarity[]' or specific IDs.
        # Using generic text params for now, can be refined with exact DMarket rarity IDs.
        return {"treeFilters": "rarity[]=immortal,rarity[]=arcana,rarity[]=legendary"}

    async def should_buy(self, item_data: dict[str, Any]) -> bool:
        try:
            dmarket_price = Decimal(str(item_data.get("dmarket_price", 0)))
            waxpeer_price = Decimal(str(item_data.get("waxpeer_price", 0)))

            if dmarket_price <= 0 or waxpeer_price <= 0:
                return False

            # Calculate target sell price (Risk premium is 0 for Dota2 in Fees)
            target_sell_price = self.calculate_target_sell_price(dmarket_price)

            if waxpeer_price < target_sell_price:
                return False

            # Dota specific: Arcana/High-tier check could go here
            # For now, rely on pure arbitrage math

            roi = self.calculate_roi(dmarket_price, waxpeer_price)
            logger.info(
                f"Dota2 Opportunity: {item_data.get('title')} | "
                f"Buy: ${dmarket_price} | Sell: ${waxpeer_price} | "
                f"ROI: {roi:.2f}%"
            )
            return True

        except Exception as e:
            logger.error(f"Error evaluating Dota2 item: {e}")
            return False
