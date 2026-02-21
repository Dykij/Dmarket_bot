import logging

logger = logging.getLogger(__name__)

class Strategy:
    def __init__(self, api):
        self.api = api

    def check_market_conditions(self, item_name, liquidity, min_ask, best_offer):
        """
        Evaluates market conditions for potential target creation.
        """
        try:
            # Calculate spread
            if min_ask <= 0:
                return

            spread = (min_ask - best_offer) / min_ask
            spread_percentage = spread * 100

            # Logic: If liquidity > 100 and spread > 10% -> Create Target
            if liquidity > 100 and spread > 0.10:
                target_price = min_ask * 0.90
                logger.info(f"Opportunity found for {item_name}: Liquidity={liquidity}, Spread={spread_percentage:.2f}%. Creating target at {target_price}")

                # In a real scenario, this calls the API
                # self.api.create_target(item_name, price=target_price)
                return {
                    "action": "create_target",
                    "price": target_price,
                    "reason": f"Liquidity {liquidity} > 100 and Spread {spread_percentage:.1f}% > 10%"
                }
        except Exception as e:
            logger.error(f"Strategy error for {item_name}: {e}")
            return None
