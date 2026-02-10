"""TF2 Trading Strategy."""

from decimal import Decimal
from typing import Any
import logging

from src.trading.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class TF2Strategy(BaseStrategy):
    """
    Strategy for Team Fortress 2.
    
    Constraints:
    - Keys are liquid currency.
    - Low margins but high volume.
    """

    def __init__(self, min_profit_percent: float = 1.0):
        # TF2 keys can be traded with very low margin
        super().__init__(game_id="tf2", min_profit_percent=min_profit_percent)

    def get_query_filters(self) -> dict[str, str]:
        """
        TF2 Specific Logic:
        Focus on 'Keys' as the main currency.
        """
        return {
            "title": "Mann Co. Supply Crate Key"
        }

    async def should_buy(self, item_data: dict[str, Any]) -> bool:
        try:
            dmarket_price = Decimal(str(item_data.get("dmarket_price", 0)))
            waxpeer_price = Decimal(str(item_data.get("waxpeer_price", 0)))
            
            if dmarket_price <= 0 or waxpeer_price <= 0:
                return False

            target_sell_price = self.calculate_target_sell_price(dmarket_price)
            
            if waxpeer_price < target_sell_price:
                return False

            roi = self.calculate_roi(dmarket_price, waxpeer_price)
            logger.info(
                f"TF2 Opportunity: {item_data.get('title')} | "
                f"Buy: ${dmarket_price} | Sell: ${waxpeer_price} | "
                f"ROI: {roi:.2f}%"
            )
            return True

        except Exception as e:
            logger.error(f"Error evaluating TF2 item: {e}")
            return False
