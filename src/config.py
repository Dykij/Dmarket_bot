"""
Configuration: src/config.py (v12.0)
Center of Operations. All strategy parameters are strictly defined here.
Game: CS2 Only (a8db).
Strategy: Intra-DMarket Spread (A) with CS2Cap oracle.
"""

import os
from dotenv import load_dotenv

# Load Environment
load_dotenv()


class Config:
    # --- Credentials ---
    PUBLIC_KEY = os.getenv("DMARKET_PUBLIC_KEY")
    SECRET_KEY = os.getenv("DMARKET_SECRET_KEY")

    # --- CS2Cap Oracle ---
    CS2C_API_KEY = os.getenv("CS2C_API_KEY", "")
    CS2C_TIER = os.getenv("CS2C_TIER", "free")  # free | starter | pro
    CS2C_RPS_LIMIT = 1.0  # Conservative for free tier

    # --- Target Game ---
    GAME_ID = "a8db"  # Counter-Strike 2

    # --- Trading Parameters ---
    MIN_SPREAD_PCT = 5.0     # Minimum 5% profit margin (Ask - Bid)
    FEE_RATE = 0.05          # DMarket Fee (5% standard)
    LOW_FEE_THRESHOLD = 0.03  # Items with <= 3% fee are "low-fee"

    # --- Risk Management ---
    MIN_PRICE_USD = 0.50     # Ignore cheap trash (<$0.50)
    MAX_PRICE_USD = 50.00    # Ignore high-risk items (>$50.00)

    MAX_OPEN_TARGETS = 50    # Limit active buy orders (Safety cap)
    MAX_OPEN_INVENTORY = 30  # Max items held (avoid trade lock overflow)

    # --- Performance ---
    SCAN_INTERVAL = 1        # Seconds between scan cycles (faster for A)
    BATCH_SIZE = 50          # Items per API call

    # --- Dynamic Position Sizing ---
    USE_DYNAMIC_SIZING = True
    MAX_POSITION_RISK_PCT = 30.0  # Max 30% of balance per single item

    # --- Advanced Attributes (Float/Phase) ---
    # Prefer Low Float when placing targets?
    PREFER_LOW_FLOAT = True

    # DMarket Codes for Float Ranges
    FLOAT_CODES = {
        "FN": ["FN-0", "FN-1"],  # Top tier Factory New
        "MW": ["MW-0", "MW-1"],  # Top tier Minimal Wear
        "FT": ["FT-0", "FT-1"],  # Top tier Field-Tested (0.15-0.21)
        "WW": ["WW-0"],          # Top tier Well-Worn
        "BS": ["BS-0"],          # Top tier Battle-Scarred
    }

    # --- Operation Mode ---
    DRY_RUN = True  # True = Simulation (Paper Trading), False = Real Money!

    # --- Multi-Strategy Engine (v12.0) ---
    ACTIVE_STRATEGY = "IntraSpread"  # Options: IntraSpread (A), LastSales (B), LowFee (C), Float (E), Sticker (D)

    # --- Strategy A: Intra-Spread Tuning ---
    INTRA_MIN_SPREAD_PCT = 5.0    # 5%+ spread between ask and bid
    INTRA_LIST_DISCOUNT = 0.01   # List at best_bid - $0.01 (competitive)

    # --- Strategy B: Last Sales Tuning ---
    LAST_SALES_DISCOUNT_PCT = 10.0  # Buy at >=10% below avg last sale
    LAST_SALES_DAYS = 30
    LAST_SALES_MIN_VOLUME = 3

    # --- Repricing (v12.0) ---
    REPRICE_INTERVAL_HOURS = 6
    REPRICE_AFTER_HOURS = 24
    REPRICE_DISCOUNT_PCT = 2.0

    # --- v12.2: Wash Trading Detection (Phase 2.3) ---
    WASH_TRADING_DETECTION = True
    TRIMMED_MEAN_BOOST_PCT = 24.0   # ±24% from mean = outlier
    TRIMMED_MEAN_MAX_OUTLIERS = 3   # max points to remove
    WASH_TRADING_DIVERGENCE_PCT = 50.0  # raw>trimmed*1.5 = flagged

    # --- v12.2: Multi-level Liquidity Filter (Phase 2.4) ---
    USE_LIQUIDITY_FILTER = True
    MIN_TOTAL_SALES = 80            # ALL_SALES — total historical observations
    LIQUIDITY_DAYS = 23             # DAYS_COUNT — lookback window
    MIN_SALES_IN_WINDOW = 11        # SALE_COUNT — sales in window
    MAX_FIRST_SALE_AGE_DAYS = 20    # FIRST_SALE — oldest sale in window
    MAX_LAST_SALE_AGE_DAYS = 3      # LAST_SALE — most recent sale age

    # --- v12.2: Dynamic Fee Bulk (Phase 2.2) ---
    FEE_BATCH_SIZE = 50             # items per fee request
    FEE_CACHE_TTL = 43200           # 12 hours

    # --- Bot Metadata ---
    BOT_VERSION = "12.2"
    BOT_NAME = "DMarket Intra-Spread Engine"
