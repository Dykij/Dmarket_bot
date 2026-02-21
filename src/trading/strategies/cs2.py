"""CS2 Trading Strategy (7-day trade lock)."""

from decimal import Decimal
from typing import Any
import logging

from src.trading.strategies.base import BaseStrategy

logger = logging.getLogger(__name__)


class CS2Strategy(BaseStrategy):
    """
    Strategy for Counter-Strike 2.

    Constraints:
    - 7-day trade lock after purchase.
    - High volatility.
    - Requires 3% risk premium (handled in FeeCalculator).
    """

    def __init__(self, min_profit_percent: float = 5.0):
        super().__init__(game_id="csgo", min_profit_percent=min_profit_percent)

    def get_query_filters(self) -> dict[str, str]:
        """
        CS2 Specific Logic:
        Only fetch items with liquid exteriors to ensure resale after 7-day lock.
        Avoiding 'Battle-Scarred' or 'Well-Worn' for high-tier arbitrage unless specified.
        """
        return {
            "treeFilters": "exterior[]=factory new,exterior[]=minimal wear,exterior[]=field-tested"
        }

    async def should_buy(self, item_data: dict[str, Any]) -> bool:
        """
        Evaluate buy opportunity for CS2 item.

        Expected item_data format:
        {
            "dmarket_price": float,
            "waxpeer_price": float,
            "steam_price": float, (optional)
            "waxpeer_volume": int, (optional)
            "title": str
        }
        """
        try:
            dmarket_price = Decimal(str(item_data.get("dmarket_price", 0)))
            waxpeer_price = Decimal(str(item_data.get("waxpeer_price", 0)))
            steam_price = Decimal(str(item_data.get("steam_price", 0)))

            if dmarket_price <= 0 or waxpeer_price <= 0:
                return False

            # 1. Break-even & Target Price Check
            # Calculate target sell price (includes 3% risk premium for CS2)
            target_sell_price = self.calculate_target_sell_price(dmarket_price)

            if waxpeer_price < target_sell_price:
                # logger.debug(f"CS2 Skip {item_data.get('title')}: Waxpeer price {waxpeer_price} < Target {target_sell_price}")
                return False

            # 2. Steam Liquidity/Value Check (Reference)
            # If Steam price is available, ensure we aren't buying significantly above Steam
            # (which would imply inflated DMarket price or very rare item)
            if steam_price > 0:
                # Safety: Don't buy if DMarket is > 110% of Steam (unless you trust Waxpeer price heavily)
                if dmarket_price > steam_price * Decimal("1.1"):
                    logger.debug(
                        f"CS2 Skip {item_data.get('title')}: DMarket price > 110% Steam"
                    )
                    return False

            # 3. Volume Check (Basic)
            # We prefer items that actually sell
            wax_volume = item_data.get("waxpeer_volume", 0)
            if wax_volume < 1:
                # Strict mode: skip if 0 volume
                # logger.debug(f"CS2 Skip {item_data.get('title')}: Zero Waxpeer volume")
                return False

            # If we are here, the numbers look good
            roi = self.calculate_roi(dmarket_price, waxpeer_price)
            logger.info(
                f"CS2 Opportunity: {item_data.get('title')} | "
                f"Buy: ${dmarket_price} | Sell: ${waxpeer_price} | "
                f"Target: ${target_sell_price} | ROI: {roi:.2f}%"
            )
            return True

        except Exception as e:
            logger.error(
                f"Error evaluating CS2 item {item_data.get('title', 'unknown')}: {e}"
            )
            return False
