"""
Configuration: src/config.py
Center of Operations. All strategy parameters are strictly defined here.
Game: CS2 Only (a8db).
Risk Management: Max Price $20, Min Spread 7%.
CS2Cap Integration: Multi-market oracle for 41 CS2 marketplaces.
"""

import os
from decimal import Decimal
from dotenv import load_dotenv

# Load Environment
load_dotenv()

class Config:
    # --- Credentials ---
    PUBLIC_KEY = os.getenv("DMARKET_PUBLIC_KEY")
    SECRET_KEY = os.getenv("DMARKET_SECRET_KEY")

    # --- Target Game ---
    GAME_ID = "a8db"  # Counter-Strike 2

    # --- Trading Parameters ---
    MIN_SPREAD_PCT = Decimal(os.getenv("MIN_SPREAD_PCT", "0.1"))  # profit margin after fees (reduced for value scanner)
    FEE_RATE = Decimal(os.getenv("FEE_RATE", "0.05"))   # DMarket Sell fee (5% for most CS2 items; 2-10% actual range)
    TARGET_FEE_RATE = Decimal("0.025")   # DMarket Trade/Buy fee when using targets (2.5%)
    WITHDRAWAL_FEE_RATE = Decimal(os.getenv("WITHDRAWAL_FEE_RATE", "0.005"))  # withdrawal fee

    # --- v12.0 Intra-Spread Strategy (Strategy A) ---
    INTRA_MIN_SPREAD_PCT = Decimal("0.1")    # reduced for value scanner; real gate is fee-aware validator
    INTRA_LIST_DISCOUNT = Decimal("0.01")    # Undercut vs best_bid when listing (USD)

    # --- v14.9 Value Detection Scanner (NEW) ---
    # Primary strategy: find undervalued items by rarity (float/pattern/sticker)
    # instead of requiring natural bid/ask spread.
    VALUE_SCAN_ENABLED = os.getenv("VALUE_SCAN_ENABLED", "true").lower() == "true"
    VALUE_SIGNAL_WEIGHT = Decimal(os.getenv("VALUE_SIGNAL_WEIGHT", "0.5"))
    VALUE_SCAN_MIN_PREMIUM = Decimal("1.05")  # Minimum 5% premium from rarity to trigger buy
    VALUE_SCAN_MIN_PROFIT_PCT = Decimal(os.getenv("VALUE_SCAN_MIN_PROFIT_PCT", "0.5"))  # 0.5% min profit
    VALUE_SCAN_MIN_PROFIT_USD = Decimal(os.getenv("VALUE_SCAN_MIN_PROFIT_USD", "0.20"))  # $0.20 min
    VALUE_SCAN_MAX_ITEMS_PER_CYCLE = int(os.getenv("VALUE_SCAN_MAX_ITEMS_PER_CYCLE", "20"))

    # --- v12.2 Liquidity / Wash-Trading Filters ---
    # Relaxed for value scanner: rare items are naturally illiquid.
    USE_LIQUIDITY_FILTER = os.getenv("USE_LIQUIDITY_FILTER", "false").lower() == "true"
    WASH_TRADING_DETECTION = True
    TRIMMED_MEAN_BOOST_PCT = Decimal("5.0")        # % boost over trimmed mean
    TRIMMED_MEAN_MAX_OUTLIERS = 2        # max outliers to trim

    # --- Liquidity metrics (used in price_history/history.py) ---
    MIN_TOTAL_SALES = int(os.getenv("MIN_TOTAL_SALES", "3"))  # min sales for "liquid"
    MIN_SALES_IN_WINDOW = 2              # Min sales in the recent window
    MIN_BID_ASK_COUNT = int(os.getenv("MIN_BID_ASK_COUNT", "2"))  # min bid+ask orders
    MAX_FIRST_SALE_AGE_DAYS = int(os.getenv("MAX_FIRST_SALE_AGE_DAYS", "30"))

    # --- Repricing ---
    REPRICE_AFTER_HOURS = 24     # Hours after which to reprice a stale offer

    # --- Risk Management ---
    MIN_PRICE_USD = Decimal("0.50")      # Ignore cheap trash (<$0.50)
    MAX_PRICE_USD = Decimal(os.getenv("MAX_PRICE_USD", "20.00"))  # Ignore high-risk items (>$X)

    # --- v14.4 Dynamic Balance-Aware Position Sizing ---
    BALANCE_RESERVE_USD = Decimal(os.getenv("BALANCE_RESERVE_USD", "5.00"))  # reduced reserve

    # --- Dynamic Max Snipe Price ---
    # Formula: max(floor, balance * fraction)
    MAX_SNIPING_PRICE_FLOOR = Decimal(os.getenv("MAX_SNIPING_PRICE_FLOOR", "5.00"))
    MAX_SNIPING_PRICE_BALANCE_FRACTION = Decimal(os.getenv("MAX_SNIPING_PRICE_BALANCE_FRACTION", "0.10"))
    MAX_SNIPING_PRICE_USD = Decimal(os.getenv("MAX_SNIPING_PRICE_USD", "5.00"))

    # --- Fractional Kelly Position Sizing ---
    KELLY_ENABLED = os.getenv("KELLY_ENABLED", "true").lower() == "true"
    KELLY_FRACTION = Decimal(os.getenv("KELLY_FRACTION", "0.50"))
    KELLY_FLOOR_PCT = Decimal(os.getenv("KELLY_FLOOR_PCT", "3.0"))

    # --- Lock-Aware Inventory Cap ---
    LOCK_AWARE_CAP_ENABLED = os.getenv("LOCK_AWARE_CAP_ENABLED", "true").lower() == "true"
    LOCK_AWARE_LIQUID_FRACTION = Decimal(os.getenv("LOCK_AWARE_LIQUID_FRACTION", "0.80"))

    # --- Capital Velocity Constraint ---
    CAPITAL_VELOCITY_ENABLED = os.getenv("CAPITAL_VELOCITY_ENABLED", "true").lower() == "true"
    CAPITAL_VELOCITY_MIN = Decimal(os.getenv("CAPITAL_VELOCITY_MIN", "0.50"))

    # --- Drawdown-Aware Spending Freeze ---
    DRAWDOWN_FREEZE_ENABLED = os.getenv("DRAWDOWN_FREEZE_ENABLED", "true").lower() == "true"
    DRAWDOWN_FREEZE_THRESHOLD = Decimal(os.getenv("DRAWDOWN_FREEZE_THRESHOLD", "0.15"))

    MAX_OPEN_TARGETS = 50

    # --- Inventory & Sale Age ---
    MAX_LAST_SALE_AGE_DAYS = int(os.getenv("MAX_LAST_SALE_AGE_DAYS", "30"))
    MAX_OPEN_INVENTORY = int(os.getenv("MAX_OPEN_INVENTORY", "200"))
    BOT_VERSION = os.getenv("BOT_VERSION", "v14.9")

    # --- Performance ---
    SCAN_INTERVAL = 30
    BATCH_SIZE = 100

    # --- CS2Cap Batch Settings ---
    CS2CAP_BATCH_SIZE = 100
    CS2CAP_TOP_K_VALIDATE = int(os.getenv("CS2CAP_TOP_K_VALIDATE", "50"))  # increased for value scanner
    CS2CAP_SELECTIVE_MODE = True
    AGG_SCAN_TOP_N = int(os.getenv("AGG_SCAN_TOP_N", "100"))
    LISTINGS_FETCH_LIMIT = int(os.getenv("LISTINGS_FETCH_LIMIT", "20"))

    # --- v14.8 Price-Range Market Scan (wide-net pipeline) ---
    PRICE_RANGE_SCAN_ENABLED = os.getenv("PRICE_RANGE_SCAN_ENABLED", "true").lower() == "true"
    PRICE_RANGE_MIN_USD = Decimal(os.getenv("PRICE_RANGE_MIN_USD", "0.50"))
    PRICE_RANGE_MAX_USD = Decimal(os.getenv("PRICE_RANGE_MAX_USD", "20.00"))
    PRICE_RANGE_MAX_TITLES = int(os.getenv("PRICE_RANGE_MAX_TITLES", "500"))
    PRICE_RANGE_MAX_PAGES = int(os.getenv("PRICE_RANGE_MAX_PAGES", "20"))
    PRICE_RANGE_CYCLE_INTERVAL = int(os.getenv("PRICE_RANGE_CYCLE_INTERVAL", "1"))  # every cycle

    # --- v14.8.1 Low-Fee Items Scan ---
    LOW_FEE_ITEMS_SCAN_ENABLED = os.getenv("LOW_FEE_ITEMS_SCAN_ENABLED", "true").lower() == "true"
    LOW_FEE_ITEMS_SCAN_LIMIT = int(os.getenv("LOW_FEE_ITEMS_SCAN_LIMIT", "100"))

    # --- v14.8 Cross-Market Arbitrage Calibration ---
    CROSS_MARKET_DESTINATION_FEE = Decimal(os.getenv("CROSS_MARKET_DESTINATION_FEE", "0.025"))
    CROSS_MARKET_FEE_AWARE = os.getenv("CROSS_MARKET_FEE_AWARE", "true").lower() == "true"

    # --- v14.9 Cross-Market Buy Targets (Limit Orders) ---
    CROSS_MARKET_TARGET_ENABLED = os.getenv("CROSS_MARKET_TARGET_ENABLED", "true").lower() == "true"
    CROSS_MARKET_TARGET_MARGIN = Decimal(os.getenv("CROSS_MARKET_TARGET_MARGIN", "0.02"))
    CROSS_MARKET_TARGET_MAX_PER_CYCLE = int(os.getenv("CROSS_MARKET_TARGET_MAX_PER_CYCLE", "20"))

    # --- v14.8.1 DMarket-Internal Underpriced Detection ---
    DMARKET_INTERNAL_UNDERPRICED_ENABLED = (
        os.getenv("DMARKET_INTERNAL_UNDERPRICED_ENABLED", "true").lower() == "true"
    )
    DM_UNDERPRICED_SALES_DAYS = int(os.getenv("DM_UNDERPRICED_SALES_DAYS", "7"))
    DM_UNDERPRICED_PERCENTILE = Decimal(os.getenv("DM_UNDERPRICED_PERCENTILE", "0.25"))
    DM_UNDERPRICED_MIN_MARGIN_PCT = Decimal(os.getenv("DM_UNDERPRICED_MIN_MARGIN_PCT", "3.0"))

    # --- v14.9 Microstructure Filter Toggle ---
    # For value scanner strategy, strict HFT-style filters are disabled by default.
    STRICT_MICROSTRUCTURE_FILTERS = (
        os.getenv("STRICT_MICROSTRUCTURE_FILTERS", "false").lower() == "true"
    )

    # --- v12.4 In-Memory CS2Cap Cache ---
    CS2CAP_CACHE_TTL_SECONDS = int(os.getenv("CS2CAP_CACHE_TTL_SECONDS", "300"))
    CS2CAP_CACHE_REFRESH_TOP_N = int(os.getenv("CS2CAP_CACHE_REFRESH_TOP_N", "200"))
    CS2CAP_CACHE_REFRESH_ON_START = True
    CS2CAP_CATALOG_WARMUP_ON_START = int(os.getenv("CS2CAP_CATALOG_WARMUP_ON_START", "0"))

    # --- Advanced Attributes (Float/Phase) ---
    PREFER_LOW_FLOAT = True
    FLOAT_PREMIUM_ENABLED = os.getenv("FLOAT_PREMIUM_ENABLED", "true").lower() == "true"
    FLOAT_CODES = {
        "FN": ["FN-0", "FN-1"],
        "MW": ["MW-0", "MW-1"],
        "FT": ["FT-0", "FT-1"],
        "WW": ["WW-0"],
        "BS": ["BS-0"]
    }

    # --- v14.6 Value Detection Layers (TA Site Analysis) ---
    PATTERN_PREMIUM_ENABLED = os.getenv("PATTERN_PREMIUM_ENABLED", "true").lower() == "true"
    STICKER_COMBO_ENABLED = os.getenv("STICKER_COMBO_ENABLED", "true").lower() == "true"
    SEASONAL_TIMING_ENABLED = os.getenv("SEASONAL_TIMING_ENABLED", "true").lower() == "true"
    FILLER_TRACKING_ENABLED = os.getenv("FILLER_TRACKING_ENABLED", "true").lower() == "true"
    DIRTY_BS_ENABLED = os.getenv("DIRTY_BS_ENABLED", "true").lower() == "true"
    ROUND_FLOAT_ENABLED = os.getenv("ROUND_FLOAT_ENABLED", "true").lower() == "true"
    FLOAT_DATE_ENABLED = os.getenv("FLOAT_DATE_ENABLED", "true").lower() == "true"
    COMMISSION_OPTIMIZER_ENABLED = os.getenv("COMMISSION_OPTIMIZER_ENABLED", "true").lower() == "true"

    # --- Operation Mode ---
    DRY_RUN = os.getenv("DRY_RUN", "true").lower() == "true"
    MARKETPLACE_INSTANT_RESALE = os.getenv("MARKETPLACE_INSTANT_RESALE", "true").lower() == "true"

    # --- v13.0: Trade lock hours ---
    TRADE_LOCK_HOURS = int(os.getenv("TRADE_LOCK_HOURS", "0"))

    # --- Multi-Strategy Engine ---
    ACTIVE_STRATEGY = "ValueScanner"  # Options: MarketMaker, SpreadHunter, CrossMarket, ValueScanner

    # --- Dynamic Position Sizing ---
    USE_DYNAMIC_SIZING = True
    MAX_POSITION_RISK_PCT = Decimal(os.getenv("MAX_POSITION_RISK_PCT", "15.0"))
    MAX_SAME_ITEM_HOLDINGS = int(os.getenv("MAX_SAME_ITEM_HOLDINGS", "3"))
    MAX_CONCURRENT_POSITIONS = int(os.getenv("MAX_CONCURRENT_POSITIONS", "50"))
    MAX_TOTAL_INVENTORY_VALUE = Decimal(os.getenv("MAX_TOTAL_INVENTORY_VALUE", "100.0"))
    MAX_TOTAL_INVENTORY_ITEMS = int(os.getenv("MAX_TOTAL_INVENTORY_ITEMS", "30"))

    # --- CS2Cap Integration ---
    CS2CAP_API_KEY = os.getenv("CS2CAP_API_KEY", "")
    CS2CAP_ORACLE_PRIMARY = True
    CS2CAP_TIER = os.getenv("CS2CAP_TIER", "starter")

    # --- Loop Selection ---
    USE_V12_LOOP = os.getenv("USE_V12_LOOP", "true").lower() == "true"

    # --- Self-Reflection ---
    SELF_REFLECTION_WINDOW = 50
    SELF_REFLECTION_INTERVAL = 100
    PARAMETER_ADJUSTMENT_ENABLED = True
    MIN_TRADES_FOR_ADJUSTMENT = 10

    # --- Turnover Regularization ---
    TURNOVER_PENALTY_ENABLED = True
    MAX_DAILY_TRADES = 200
    TURNOVER_PENALTY_PER_TRADE = Decimal("0.002")

    # --- Cross-Market Strategy ---
    CROSS_MARKET_ENABLED = True
    CROSS_MARKET_MIN_EDGE_PCT = Decimal("3.0")
    CROSS_MARKET_MAX_SPREAD_PCT = Decimal("15.0")

    # --- Enhanced Volatility ---
    VOLATILITY_METHOD = "garman_klass"
    VOLATILITY_MAX_ANNUALIZED = Decimal("0.60")
    VOLATILITY_LOOKBACK_SALES = 20

    # --- v14.0 Order Book Microstructure (disabled by default for Value Scanner) ---
    OBI_ENABLED = os.getenv("OBI_ENABLED", "false").lower() == "true"
    OBI_MIN_RATIO = Decimal(os.getenv("OBI_MIN_RATIO", "0.5"))
    OBI_BOOST_RATIO = Decimal(os.getenv("OBI_BOOST_RATIO", "1.3"))

    OFI_ENABLED = os.getenv("OFI_ENABLED", "false").lower() == "true"
    OFI_BUY_THRESHOLD = int(os.getenv("OFI_BUY_THRESHOLD", "5"))
    OFI_SELL_THRESHOLD = int(os.getenv("OFI_SELL_THRESHOLD", "-10"))

    BAIT_DETECTION_ENABLED = os.getenv("BAIT_DETECTION_ENABLED", "true").lower() == "true"
    BAIT_MAX_PRICE_CHANGES = int(os.getenv("BAIT_MAX_PRICE_CHANGES", "3"))

    MICRO_PRICE_ENABLED = os.getenv("MICRO_PRICE_ENABLED", "false").lower() == "true"
    DOM_GAP_ENABLED = os.getenv("DOM_GAP_ENABLED", "false").lower() == "true"

    FLOAT_PHASE_SCAN_ENABLED = os.getenv("FLOAT_PHASE_SCAN_ENABLED", "true").lower() == "true"
    FLOAT_PHASE_MAX_EXTRA_CALLS = int(os.getenv("FLOAT_PHASE_MAX_EXTRA_CALLS", "10"))

    STOIKOV_MICRO_PRICE_ENABLED = os.getenv("STOIKOV_MICRO_PRICE_ENABLED", "false").lower() == "true"
    STOIKOV_CALIBRATION = Decimal(os.getenv("STOIKOV_CALIBRATION", "0.35"))

    MULTI_LEVEL_OBI_ENABLED = os.getenv("MULTI_LEVEL_OBI_ENABLED", "false").lower() == "true"
    MULTI_LEVEL_OBI_DEPTH = int(os.getenv("MULTI_LEVEL_OBI_DEPTH", "5"))

    QUEUE_IMBALANCE_ENABLED = os.getenv("QUEUE_IMBALANCE_ENABLED", "false").lower() == "true"
    QI_BUY_THRESHOLD = Decimal(os.getenv("QI_BUY_THRESHOLD", "1.5"))
    QI_SELL_THRESHOLD = Decimal(os.getenv("QI_SELL_THRESHOLD", "0.5"))

    AS_ENABLED = os.getenv("AS_ENABLED", "false").lower() == "true"
    AS_RISK_AVERSION = Decimal(os.getenv("AS_RISK_AVERSION", "0.3"))
    AS_TIME_HORIZON_DAYS = Decimal(os.getenv("AS_TIME_HORIZON_DAYS", "7"))

    VWAP_FILTER_ENABLED = os.getenv("VWAP_FILTER_ENABLED", "false").lower() == "true"
    VWAP_DISCOUNT_THRESHOLD = Decimal(os.getenv("VWAP_DISCOUNT_THRESHOLD", "0.90"))
    VWAP_BANDS_ENABLED = os.getenv("VWAP_BANDS_ENABLED", "false").lower() == "true"

    SLIPPAGE_GATE_ENABLED = os.getenv("SLIPPAGE_GATE_ENABLED", "false").lower() == "true"
    SLIPPAGE_TEMP_IMPACT_BPS = Decimal(os.getenv("SLIPPAGE_TEMP_IMPACT_BPS", "5.0"))
    SLIPPAGE_PERM_IMPACT_BPS = Decimal(os.getenv("SLIPPAGE_PERM_IMPACT_BPS", "2.0"))

    CVD_ENABLED = os.getenv("CVD_ENABLED", "false").lower() == "true"
    CVD_WINDOW_ITEMS = int(os.getenv("CVD_WINDOW_ITEMS", "5"))

    VPIN_ENABLED = os.getenv("VPIN_ENABLED", "false").lower() == "true"
    VPIN_BUCKETS = int(os.getenv("VPIN_BUCKETS", "8"))
    VPIN_THRESHOLD = Decimal(os.getenv("VPIN_THRESHOLD", "0.8"))

    ADVERSER_SELECTION_ENABLED = os.getenv("ADVERSER_SELECTION_ENABLED", "false").lower() == "true"
    KYLE_LAMBDA_MAX = Decimal(os.getenv("KYLE_LAMBDA_MAX", "0.05"))
    AMIHUD_ILLIQUIDITY_MAX = Decimal(os.getenv("AMIHUD_ILLIQUIDITY_MAX", "0.10"))

    VOL_REGIME_ENABLED = os.getenv("VOL_REGIME_ENABLED", "false").lower() == "true"
    VOL_REGIME_HIGH_THRESHOLD = Decimal(os.getenv("VOL_REGIME_HIGH_THRESHOLD", "0.50"))

    ROLL_MODEL_ENABLED = os.getenv("ROLL_MODEL_ENABLED", "false").lower() == "true"

    VOLUME_PROFILE_ENABLED = os.getenv("VOLUME_PROFILE_ENABLED", "false").lower() == "true"
    VP_NUM_BUCKETS = int(os.getenv("VP_NUM_BUCKETS", "10"))

    SMART_REPRICE_ENABLED = os.getenv("SMART_REPRICE_ENABLED", "false").lower() == "true"

    COMPOSITE_SCORE_ENABLED = os.getenv("COMPOSITE_SCORE_ENABLED", "false").lower() == "true"

    # --- Time of Day Adjustment ---
    TIME_OF_DAY_ENABLED = os.getenv("TIME_OF_DAY_ENABLED", "true").lower() == "true"
    TIME_OF_DAY_NIGHT_START_UTC = int(os.getenv("TIME_OF_DAY_NIGHT_START_UTC", "4"))
    TIME_OF_DAY_NIGHT_END_UTC = int(os.getenv("TIME_OF_DAY_NIGHT_END_UTC", "10"))
    TIME_OF_DAY_WEEKEND_ENABLED = os.getenv("TIME_OF_DAY_WEEKEND_ENABLED", "true").lower() == "true"
    TIME_OF_DAY_NIGHT_MULTIPLIER = Decimal(os.getenv("TIME_OF_DAY_NIGHT_MULTIPLIER", "1.2"))
    TIME_OF_DAY_DAY_MULTIPLIER = Decimal(os.getenv("TIME_OF_DAY_DAY_MULTIPLIER", "1.0"))
    # Backward compat aliases
    TOD_ENABLED = TIME_OF_DAY_ENABLED
    TOD_NIGHT_START_UTC = TIME_OF_DAY_NIGHT_START_UTC
    TOD_NIGHT_END_UTC = TIME_OF_DAY_NIGHT_END_UTC
    TOD_WEEKEND_ENABLED = TIME_OF_DAY_WEEKEND_ENABLED
    TOD_NIGHT_MULTIPLIER = TIME_OF_DAY_NIGHT_MULTIPLIER
    TOD_DAY_MULTIPLIER = TIME_OF_DAY_DAY_MULTIPLIER

    # --- Sharpe-Optimized Objective ---
    SHARPE_OPTIMIZATION_ENABLED = True
    TARGET_SHARPE_RATIO = Decimal("1.5")
    DRAWDOWN_PENALTY_WEIGHT = Decimal("0.5")
    OBJECTIVE_FUNCTION = "sharpe_adjusted"


