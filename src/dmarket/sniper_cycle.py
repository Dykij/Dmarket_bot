"""Sniper Cycle module for automated arbitrage trading.

Implements the core logic for finding, analyzing, buying, and selling items.
"""

import logging

from src.dmarket.dmarket_api import DMarketAPI
from src.dmarket.price_analyzer import PriceAnalyzer
from src.dmarket.steam_api import get_steam_price, normalize_item_name
from src.telegram_bot.notifier import send_arbitrage_report

logger = logging.getLogger(__name__)


async def sniper_cycle(
    api: DMarketAPI,
    analyzer: PriceAnalyzer,
    bot=None,
    admin_id: int | None = None,
) -> None:
    """Execute a single sniper cycle: Scan -> Analyze -> Buy -> Sell.

    Args:
        api: DMarket API client
        analyzer: Price analyzer instance
        bot: Telegram bot instance for notifications
        admin_id: User ID to send notifications to
    """
    try:  # noqa: PLR1702
        # 1. Get best deals (items with high discount)
        # Using "best_deals" type if supported, or standard market items
        items_response = await api.get_market_items(
            game="csgo",
            limit=50,
            order_by="best_deals",
        )

        items = items_response.get("objects", [])
        if not items:
            logger.debug("No items found in sniper cycle")
            return

        for item in items:
            title = item.get("title")
            if not title:
                continue

            # 2. Get sales history for analysis
            # Using the new aggregator endpoint
            history_response = await api.buy_item(
                "GET",
                f"/trade-aggregator/v1/last-sales?title={title}&gameId=a8db99ca-dc45-4c0e-9989-11ba71ed97a2",
            )
            history = history_response.get("sales", [])

            # 3. Get Steam price for comparison
            steam_price_data = None
            try:
                normalized_name = normalize_item_name(title)
                steam_price_data = await get_steam_price(normalized_name)
            except Exception as e:
                logger.warning(f"Failed to get Steam price for {title}: {e}")

            # 4. Evaluate profitability (using both DMarket history and Steam price)
            if analyzer.evaluate_item(item, history, steam_price_data):
                # Extract price info
                price_data = item.get("price", {})
                if isinstance(price_data, dict):
                    price_cents = int(price_data.get("USD", 0))
                else:
                    price_cents = int(price_data)

                price_usd = price_cents / 100

                # 5. Buy item
                logger.info(f"💰 Attempting to buy {title} for ")

                # Construct offer data for purchase
                offer_id = item.get("extra", {}).get("offerId")
                if not offer_id:
                    logger.warning(f"No offerId for {title}")
                    continue

                buy_res = await api.buy_item(
                    "POST",
                    api.ENDPOINT_PURCHASE,
                    data={
                        "offers": [{"offerId": offer_id, "price": item.get("price")}]
                    },
                )

                if buy_res.get("status") == "success" or (
                    isinstance(buy_res, dict) and buy_res.get("success")
                ):
                    logger.info(f"✅ Successfully bought {title}")

                    # Extract asset ID from response
                    # Response format varies, need to handle different structures
                    items_bought = buy_res.get("items", [])
                    asset_id = None
                    if items_bought:
                        asset_id = items_bought[0].get("assetId")

                    if asset_id:
                        # 6. Auto-sell (Arbitrage)
                        # Calculate sell price based on analyzer logic or fixed margin
                        # Using 15% ROI as requested
                        sell_res = await api.sell_with_arbitrage(
                            asset_id, price_cents, profit_percent=15.0
                        )

                        if sell_res:
                            # Calculate expected profit for report
                            sell_usd = (price_usd * 1.15) / 0.95
                            expected_profit = (sell_usd * 0.95) - price_usd

                            logger.info(f"🚀 Auto-sold {title} for ")

                            # Send notification
                            if bot and admin_id:
                                await send_arbitrage_report(
                                    bot,
                                    admin_id,
                                    item_name=title,
                                    buy_price=price_usd,
                                    sell_price=sell_usd,
                                    profit=expected_profit,
                                    roi=15.0,
                                )
                    else:
                        logger.warning(
                            f"Could not find assetId in buy response for {title}"
                        )
                else:
                    logger.warning(f"Failed to buy {title}: {buy_res}")

    except Exception as e:
        logger.exception(f"Error in sniper cycle: {e}")
