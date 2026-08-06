"""
fee_utils.py — Single source of truth for DMarket sell fee rate.

All P&L calculations MUST use get_sell_fee_rate() instead of Config.FEE_RATE
directly. This ensures fee consistency across the codebase and prevents
the Config.FEE_RATE / .env desync bug (2.5% vs real 5%).

Usage:
    from src.utils.fee_utils import get_sell_fee_rate

    # With API data (preferred):
    fee = get_sell_fee_rate(item_id, bulk_fees)

    # Without API data (fallback):
    fee = get_sell_fee_rate()
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger("FeeUtils")

# Verified DMarket CS2 sell fee — confirmed via:
# 1. fees.py:75 (_DMARKET_CS2_FEE_RATE = 0.05)
# 2. market.py:179 (API response parsing)
# 3. /exchange/v1/customized-fees API endpoint
VERIFIED_DMARKET_FEE_RATE = 0.05


def get_sell_fee_rate(
    item_id: str = "",
    bulk_fees: dict[str, float] | None = None,
) -> float:
    """Get the sell fee rate for an item.

    Priority:
    1. bulk_fees[item_id] — real-time fee from DMarket API
    2. Config.FEE_RATE — configured fallback (must be kept in sync)
    3. VERIFIED_DMARKET_FEE_RATE — hardcoded verified value

    Args:
        item_id: DMarket item ID for bulk_fees lookup.
        bulk_fees: Dict of {item_id: fee_rate} from DMarket API.

    Returns:
        Sell fee rate as decimal (e.g., 0.05 for 5%).
    """
    # Priority 1: API bulk_fees
    if bulk_fees and item_id and item_id in bulk_fees:
        api_fee = bulk_fees[item_id]
        if 0 < api_fee < 1:
            return api_fee

    # Priority 2: Config.FEE_RATE (with validation)
    try:
        from src.config import Config
        config_fee = Config.FEE_RATE
        if 0 < config_fee < 1:
            if abs(config_fee - VERIFIED_DMARKET_FEE_RATE) > 0.01:
                logger.warning(
                    f"[FeeUtils] Config.FEE_RATE={config_fee:.3f} differs from "
                    f"verified DMarket fee={VERIFIED_DMARKET_FEE_RATE:.3f}. "
                    f"Using Config value. Check .env FEE_RATE setting."
                )
            return config_fee
    except Exception:
        pass

    # Priority 3: Hardcoded verified value
    logger.warning(
        f"[FeeUtils] Using hardcoded verified fee rate: {VERIFIED_DMARKET_FEE_RATE:.3f}"
    )
    return VERIFIED_DMARKET_FEE_RATE


def get_total_fee_rate(
    item_id: str = "",
    bulk_fees: dict[str, float] | None = None,
) -> float:
    """Get total fee rate (sell + withdrawal) for P&L calculations."""
    sell_fee = get_sell_fee_rate(item_id, bulk_fees)
    try:
        from src.config import Config
        withdrawal_fee = Config.WITHDRAWAL_FEE_RATE
    except Exception:
        withdrawal_fee = 0.005  # Default 0.5%
    return sell_fee + withdrawal_fee
