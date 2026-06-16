"""
Configuration: src/config.py
Center of Operations. All strategy parameters are strictly defined here.
Game: CS2 Only (a8db).
Risk Management: Max Price $20, Min Spread 7%.
CS2Cap Integration: Multi-market oracle for 41 CS2 marketplaces.
"""

import os
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
    MIN_SPREAD_PCT = 5.0      # Minimum 5% profit margin (Ask - Bid)
    FEE_RATE = 0.05           # DMarket Sell fee (5% standard, 2-10% actual range)
    TARGET_FEE_RATE = 0.025   # DMarket Trade/Buy fee when using targets (2.5%)
    WITHDRAWAL_FEE_RATE = 0.02  # Estimated withdrawal fee (1-3%, for net PnL)

    # --- v12.0 Intra-Spread Strategy (Strategy A) ---
    # These knobs were referenced in the v12.0 loop but never declared in
    # Config (pre-existing latent bug — would have crashed on first cycle
    # if v12.0 had been wired in). Defined here with the original intent.
    INTRA_MIN_SPREAD_PCT = 2.5    # Min spread (intra-DMarket OR cross-market) to consider (%)
    INTRA_LIST_DISCOUNT = 0.01    # Undercut vs best_bid when listing (USD)

    # --- v12.2 Liquidity / Wash-Trading Filters ---
    # Used by _FilterMixin._evaluate_candidate. Defaults match v12.2 intent.
    USE_LIQUIDITY_FILTER = True
    WASH_TRADING_DETECTION = True
    TRIMMED_MEAN_BOOST_PCT = 5.0        # % boost over trimmed mean
    TRIMMED_MEAN_MAX_OUTLIERS = 2        # max outliers to trim

    # --- Liquidity metrics (used in price_history/history.py) ---
    MIN_TOTAL_SALES = 5                  # Min historical sales to consider "liquid"
    MIN_SALES_IN_WINDOW = 2              # Min sales in the recent window
    MAX_FIRST_SALE_AGE_DAYS = int(os.getenv("MAX_FIRST_SALE_AGE_DAYS", "30"))  # Reject items whose first recorded sale is older than N days (stale / pre-restart artifacts)

    # --- Repricing ---
    REPRICE_AFTER_HOURS = 24     # Hours after which to reprice a stale offer

    # --- Risk Management ---
    MIN_PRICE_USD = 0.50      # Ignore cheap trash (<$0.50)
    MAX_PRICE_USD = float(os.getenv("MAX_PRICE_USD", "20.00"))  # Ignore high-risk items (>$X)

    # --- v12.4 Balance Protection (Hard Cap) ---
    # Instant-buy path is restricted to items < $5 to protect against
    # 7-day trade-lock freeze. With balance $43, 3-4 concurrent holds
    # ($15-20) would freeze 35-50% of the bank. Cap at $5 keeps at least
    # $30 liquid for continued turnover.
    MAX_SNIPING_PRICE_USD = float(os.getenv("MAX_SNIPING_PRICE_USD", "5.00"))

    MAX_OPEN_TARGETS = 50     # Limit active buy orders (Safety cap)

    # --- Inventory & Sale Age (used in price_history/history.py + telegram) ---
    MAX_LAST_SALE_AGE_DAYS = int(os.getenv("MAX_LAST_SALE_AGE_DAYS", "30"))  # Reject items whose last sale is older than N days
    MAX_OPEN_INVENTORY = int(os.getenv("MAX_OPEN_INVENTORY", "200"))  # Telegram cap on open inventory items
    BOT_VERSION = os.getenv("BOT_VERSION", "v12.4.1")  # Reported in /start, /status

    # --- Performance ---
    # SCAN_INTERVAL=30s aligns with the CS2Cap Starter tier budget
    # (50K requests/month ≈ 2 calls/cycle × 43,200 cycles/month = 86,400 calls).
    # Combined with BATCH_SIZE=100 and top-K CS2Cap validation, we stay
    # well under the 50K/month quota at 24/7.
    SCAN_INTERVAL = 30        # Seconds between scan cycles
    BATCH_SIZE = 100          # Items per DMarket page (max supported)

    # --- CS2Cap Batch Settings (Phase 3) ---
    CS2CAP_BATCH_SIZE = 100            # Max items per /prices/batch call
    CS2CAP_TOP_K_VALIDATE = 5          # Validate only top-K items via CS2Cap per cycle
    CS2CAP_SELECTIVE_MODE = True       # True = top-K only; False = all (uses more quota)
    AGG_SCAN_TOP_N = 20                # v12.3: top-N most-traded items from agg-prices scan per cycle
    LISTINGS_FETCH_LIMIT = 30          # v12.3: N listings per title (DMarket doesn't sort by price; higher = more chance of getting the actual cheapest)

    # --- v12.4 In-Memory CS2Cap Cache ---
    # P0-B: Eliminate per-cycle CS2Cap calls. Background task refreshes
    # the top-N most-traded titles every N seconds. In-cycle validation
    # is pure dict lookups (sub-ms latency).
    CS2CAP_CACHE_TTL_SECONDS = int(os.getenv("CS2CAP_CACHE_TTL_SECONDS", "300"))  # 5 min
    CS2CAP_CACHE_REFRESH_TOP_N = int(os.getenv("CS2CAP_CACHE_REFRESH_TOP_N", "200"))  # 200 = O2: 2x coverage, same HTTP cost
    CS2CAP_CACHE_REFRESH_ON_START = True  # prime cache before first cycle
    CS2CAP_CATALOG_WARMUP_ON_START = int(os.getenv("CS2CAP_CATALOG_WARMUP_ON_START", "1"))  # 1 = O4: warm catalog on boot

    # --- Advanced Attributes (Float/Phase) ---
    PREFER_LOW_FLOAT = True
    FLOAT_PREMIUM_ENABLED = os.getenv("FLOAT_PREMIUM_ENABLED", "false").lower() == "true"
    FLOAT_CODES = {
        "FN": ["FN-0", "FN-1"],
        "MW": ["MW-0", "MW-1"],
        "FT": ["FT-0", "FT-1"],
        "WW": ["WW-0"],
        "BS": ["BS-0"]
    }

    # --- Operation Mode ---
    DRY_RUN = True
    MARKETPLACE_INSTANT_RESALE = os.getenv("MARKETPLACE_INSTANT_RESALE", "true").lower() == "true"

    # --- v13.0: Trade lock hours (0 = instant resale on DMarket marketplace) ---
    # DMarket allows IMMEDIATE re-listing of marketplace-bought items.
    # Steam Trade Protection blocks withdrawal to Steam only, not re-selling.
    # Set to positive value only if items come from Steam deposits.
    TRADE_LOCK_HOURS = int(os.getenv("TRADE_LOCK_HOURS", "0"))

    # --- Multi-Strategy Engine ---
    ACTIVE_STRATEGY = "MarketMaker"  # Options: MarketMaker, SpreadHunter, CrossMarket

    # --- Dynamic Position Sizing ---
    USE_DYNAMIC_SIZING = True
    MAX_POSITION_RISK_PCT = float(os.getenv("MAX_POSITION_RISK_PCT", "5.0"))  # Max capital risk per single item (Kelly Criterion proxy)
    MAX_SAME_ITEM_HOLDINGS = int(os.getenv("MAX_SAME_ITEM_HOLDINGS", "3"))  # v12.7: max units of same item (saturation filter + execution guard)
    MAX_CONCURRENT_POSITIONS = int(os.getenv("MAX_CONCURRENT_POSITIONS", "50"))  # v12.8: total concurrent holdings cap
    MAX_TOTAL_INVENTORY_VALUE = float(os.getenv("MAX_TOTAL_INVENTORY_VALUE", "100.0"))  # Max total $ value of held inventory
    MAX_TOTAL_INVENTORY_ITEMS = int(os.getenv("MAX_TOTAL_INVENTORY_ITEMS", "30"))  # Max total count of held items

    # =================================================================
    # CS2Cap Integration (arXiv-inspired improvements)
    # =================================================================

    # --- CS2Cap API ---
    CS2CAP_API_KEY = os.getenv("CS2CAP_API_KEY", "")
    CS2CAP_ORACLE_PRIMARY = True  # Use CS2Cap as primary oracle for CS2
    CS2CAP_TIER = os.getenv("CS2CAP_TIER", "starter")  # free | starter | pro | quant

    # --- Loop Selection (Phase 1) ---
    # True  = v12.0 SnipingLoop (uses aggregated_prices + fee_bulk + selective CS2Cap)
    # False = legacy v10.0 loop (per-item CS2Cap calls, 3×N per cycle)
    USE_V12_LOOP = os.getenv("USE_V12_LOOP", "true").lower() == "true"

    # --- Self-Reflection ---
    # Analyze last N trades to adjust strategy parameters
    SELF_REFLECTION_WINDOW = 50       # Number of recent trades to analyze
    SELF_REFLECTION_INTERVAL = 100    # Run reflection every N scan cycles
    PARAMETER_ADJUSTMENT_ENABLED = True
    MIN_TRADES_FOR_ADJUSTMENT = 10    # Minimum trades before adjusting params

    # --- Turnover Regularization ---
    # Penalty for excessive trading frequency (from arXiv: TradingAgents)
    TURNOVER_PENALTY_ENABLED = True
    MAX_DAILY_TRADES = 200            # Cap on trades per day
    TURNOVER_PENALTY_PER_TRADE = 0.002  # 0.2% penalty per trade above limit

    # --- Cross-Market Strategy ---
    CROSS_MARKET_ENABLED = True       # Enable cross-market arbitrage via CS2Cap
    CROSS_MARKET_MIN_EDGE_PCT = 3.0   # Minimum 3% edge across markets
    CROSS_MARKET_MAX_SPREAD_PCT = 15.0  # Reject items with >15% internal spread

    # --- Enhanced Volatility ---
    VOLATILITY_METHOD = "garman_klass"  # Options: garman_klass, realized, spread_proxy
    VOLATILITY_MAX_ANNUALIZED = 0.60    # Max 60% annualized vol
    VOLATILITY_LOOKBACK_SALES = 20      # Number of recent sales for vol calc

    # --- Sharpe-Optimized Objective ---
    # Instead of flat threshold, use risk-adjusted objective
    SHARPE_OPTIMIZATION_ENABLED = True
    TARGET_SHARPE_RATIO = 1.5           # Target risk-adjusted return
    DRAWDOWN_PENALTY_WEIGHT = 0.5       # Penalty weight for max drawdown
    OBJECTIVE_FUNCTION = "sharpe_adjusted"  # Options: threshold, sharpe_adjusted
