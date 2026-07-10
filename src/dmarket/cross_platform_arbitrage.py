"""
cross_platform_arbitrage.py — Cross-market arbitrage detection (DMarket ↔ Waxpeer).

Constants, enums, and category filters for cross-platform trading.
"""

from decimal import Decimal
from enum import Enum


class ItemCategory(str, Enum):
    CASE = "Case"
    KEY = "Key"
    WEAPON = "Weapon"
    KNIFE = "Knife"
    GLOVES = "Gloves"
    GRAFFITI = "Graffiti"
    SOUVENIR = "Souvenir Package"
    STICKER = "Sticker"
    AGENT = "Agent"


class ArbitrageDecision(str, Enum):
    BUY_INSTANT = "buy_instant"
    BUY_AND_HOLD = "buy_and_hold"
    SKIP = "skip"
    INSUFFICIENT_LIQUIDITY = "insufficient_liquidity"


# Commission rates
WAXPEER_COMMISSION = Decimal("0.06")
WAXPEER_MULTIPLIER = Decimal("0.94")
DMARKET_COMMISSION = Decimal("0.05")
DMARKET_MULTIPLIER = Decimal("0.95")

CS2_GAME_ID = "a8db-0000-0000-0000-000000000000"

# Profit thresholds
DEFAULT_MIN_PROFIT_USD = Decimal("0.30")
DEFAULT_MIN_ROI_PERCENT = Decimal("5.0")
DEFAULT_LOCK_ROI_PERCENT = Decimal("15.0")
DEFAULT_MAX_LOCK_DAYS = 8
DEFAULT_MIN_LIQUIDITY = 5

# Category filters
ALLOWED_CATEGORIES: set[ItemCategory] = {
    ItemCategory.CASE,
    ItemCategory.KEY,
    ItemCategory.WEAPON,
    ItemCategory.KNIFE,
    ItemCategory.GLOVES,
    ItemCategory.STICKER,
    ItemCategory.SOUVENIR,
    ItemCategory.AGENT,
}

BLACKLISTED_CATEGORIES: set[ItemCategory] = {
    ItemCategory.GRAFFITI,
    ItemCategory.SOUVENIR,
}

BLACKLISTED_KEYWORDS: frozenset[str] = frozenset({
    "graffiti",
    "souvenir",
    "sealed graffiti",
    "patch",
})
