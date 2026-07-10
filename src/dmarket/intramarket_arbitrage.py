"""
intramarket_arbitrage.py — Intra-market anomaly detection.

Detects underpriced/overpriced items, trending prices, and rare trade-ups.
"""

from enum import Enum


class PriceAnomalyType(str, Enum):
    UNDERPRICED = "underpriced"
    OVERPRICED = "overpriced"
    TRENDING_UP = "trending_up"
    TRENDING_DOWN = "trending_down"
    RARE_TRAlgoTS = "rare_trAlgots"


_SKIP_KEYWORDS = {"sticker", "graffiti", "patch"}

_EXTERIORS = {
    "Factory New",
    "Minimal Wear",
    "Field-Tested",
    "Well-Worn",
    "Battle-Scarred",
}


def _should_skip_csgo_item(title: str) -> bool:
    """Returns True for sticker, graffiti, patch items (case-insensitive)."""
    lower = title.lower()
    return any(kw in lower for kw in _SKIP_KEYWORDS)


def _build_item_key(title: str, item: dict, game: str) -> str:
    """Builds a unique key for an item."""
    if game != "csgo":
        return title

    # Preserve StatTrak/Souvenir prefixes
    prefix = ""
    working = title
    for pfx in ("StatTrak™ ", "Souvenir "):
        if working.startswith(pfx):
            prefix = pfx
            working = working[len(pfx):]
            break

    # Extract name + exterior
    for ext in _EXTERIORS:
        if ext in working:
            return f"{prefix}{working}".strip()

    return title


def _extract_item_price(item: dict) -> float | None:
    """Extracts price from DMarket item dict (cents → dollars)."""
    price_obj = item.get("price")
    if not price_obj or not isinstance(price_obj, dict):
        return None
    amount = price_obj.get("amount")
    if amount is None:
        return None
    try:
        return int(amount) / 100.0
    except (ValueError, TypeError):
        return None
