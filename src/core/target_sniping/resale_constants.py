"""
resale_constants.py — Shared constants for resale pipeline.

Extracted from resale.py to break the import cycle between
resale.py ↔ resale_prod.py at the architecture level.
"""

import os

from src.config import Config

LIST_BATCH_SIZE = int(os.getenv("SELL_BATCH_SIZE", "10"))
LIST_MIN_MARGIN_PCT = float(os.getenv("SELL_MIN_MARGIN_PCT", "3.0"))
LIST_PRICE_DISCOUNT = float(os.getenv("SELL_LIST_DISCOUNT", "0.01"))
REPRICE_DROP_PCT = float(os.getenv("SELL_REPRICE_DROP_PCT", "5.0"))
SELL_MAX_OPEN_LISTINGS = int(os.getenv("SELL_MAX_OPEN_LISTINGS", "50"))
SELL_FEE_RATE = float(os.getenv("SELL_FEE_RATE", str(Config.FEE_RATE)))
INVENTORY_SYNC_MAX_PAGES = int(os.getenv("INVENTORY_SYNC_MAX_PAGES", "5"))
CLOSED_OFFERS_LOOKBACK_DAYS = int(os.getenv("CLOSED_OFFERS_LOOKBACK_DAYS", "7"))
