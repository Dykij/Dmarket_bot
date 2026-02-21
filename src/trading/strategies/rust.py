"""Rust Trading Strategy."""

from decimal import Decimal
from typing import Any
import logging

from src.trading.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class RustStrategy(BaseStrategy):
    """
    Strategy for Rust.

    ConstrAlgonts:
    - 7 day trade lock usually applies.
    - High volatility on new skins.
    """

    def __init__(self, min_profit_percent: float = 5.0):
        super().__init__(game_id="rust", min_profit_percent=min_profit_percent)

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
                f"Rust Opportunity: {item_data.get('title')} | "
                f"Buy: ${dmarket_price} | Sell: ${waxpeer_price} | "
                f"ROI: {roi:.2f}%"
            )
            return True

        except Exception as e:
            logger.error(f"Error evaluating Rust item: {e}")
            return False
