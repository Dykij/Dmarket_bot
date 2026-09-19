"""Pricing calculations for production resale listing (extracted from resale_prod.py)."""
from __future__ import annotations

import math
import logging
from typing import Any

from src.config import Config
from src.db.price_history import price_db
from src.core.target_sniping.resale_constants import LIST_PRICE_DISCOUNT

logger = logging.getLogger("SnipingBot")

async def calculate_list_price(
    title: str,
    buy_price: float,
    cs_price: float,
    target_sell: float,
    dom_cache: dict | None = None,
) -> float:
    """
    Apply sequential price modifiers (Avellaneda-Stoikov reservation price,
    VWAP bands, DOM gap) to the oracle reference price, then compute the
    final list price with discount.
    """
    # v14.1 A-S (Avellaneda-Stoikov) — inventory-aware reservation price
    if Config.AS_ENABLED:
        mid_price = cs_price
        same_item = len([
            x for x in await price_db.run_in_thread(
                price_db.get_virtual_inventory, "idle", False,
            ) if x["hash_name"] == title
        ])
        vol_est = 0.40
        try:
            hist = await price_db.run_in_thread(price_db.get_recent_prices, title, 14)
            if hist and len(hist) >= 3:
                log_returns = []
                for i in range(1, len(hist)):
                    prev_p = hist[i - 1][0]
                    curr_p = hist[i][0]
                    if prev_p > 0:
                        log_returns.append(abs(math.log(curr_p / prev_p)))
                if log_returns:
                    daily_vol = sum(log_returns) / len(log_returns)
                    vol_est = daily_vol * math.sqrt(365)
        except Exception as e:
            logger.warning(f"[Resale] Volume estimation failed for {title}: {e}")
        from src.analysis.microstructure import reservation_price
        reserv = reservation_price(
            mid_price=mid_price,
            inventory_qty=same_item,
            target_qty=0,
            max_qty=max(1, Config.MAX_SAME_ITEM_HOLDINGS),
            volatility=vol_est,
            gamma=Config.AS_RISK_AVERSION,
            T_days=Config.AS_TIME_HORIZON_DAYS,
        )
        cs_price = max(target_sell * 1.01, reserv)

    # v14.3: VWAP Bands
    if Config.VWAP_BANDS_ENABLED:
        from src.analysis.microstructure import vwap_bands
        item_sales_vwap = await price_db.run_in_thread(price_db.get_trade_history, title, 30, 200)
        if item_sales_vwap and len(item_sales_vwap) >= 5:
            _, lower, upper = vwap_bands(item_sales_vwap, num_std=2.0)
            if upper > cs_price and lower < cs_price:
                cs_price = max(cs_price, upper * 0.98)

    list_price = round(min(cs_price * 0.97, cs_price - LIST_PRICE_DISCOUNT), 2)

    if Config.DOM_GAP_ENABLED and dom_cache is not None:
        dom_listings = dom_cache.get(title, [])
        if dom_listings and len(dom_listings) > 1:
            from src.analysis.orderbook import find_gap_price
            gap_price = find_gap_price(dom_listings, target_sell)
            if gap_price > target_sell:
                list_price = gap_price

    return list_price
