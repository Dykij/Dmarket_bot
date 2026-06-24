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
    MIN_SPREAD_PCT = float(os.getenv("MIN_SPREAD_PCT", "2.0"))  # profit margin after fees
    FEE_RATE = 0.03           # DMarket Sell fee (3% for liquid items; 2-10% actual range)
    TARGET_FEE_RATE = 0.025   # DMarket Trade/Buy fee when using targets (2.5%)
    WITHDRAWAL_FEE_RATE = float(os.getenv("WITHDRAWAL_FEE_RATE", "0.015"))  # withdrawal fee

    # --- v12.0 Intra-Spread Strategy (Strategy A) ---
    # These knobs were referenced in the v12.0 loop but never declared in
    # Config (pre-existing latent bug — would have crashed on first cycle
    # if v12.0 had been wired in). Defined here with the original intent.
    INTRA_MIN_SPREAD_PCT = 0.3    # early spread filter (%); real gate is fee-aware validator
    INTRA_LIST_DISCOUNT = 0.01    # Undercut vs best_bid when listing (USD)

    # --- v12.2 Liquidity / Wash-Trading Filters ---
    # Used by _FilterMixin._evaluate_candidate. Defaults match v12.2 intent.
    USE_LIQUIDITY_FILTER = True
    WASH_TRADING_DETECTION = True
    TRIMMED_MEAN_BOOST_PCT = 5.0        # % boost over trimmed mean
    TRIMMED_MEAN_MAX_OUTLIERS = 2        # max outliers to trim

    # --- Liquidity metrics (used in price_history/history.py) ---
    MIN_TOTAL_SALES = int(os.getenv("MIN_TOTAL_SALES", "5"))  # min sales for "liquid"
    MIN_SALES_IN_WINDOW = 2              # Min sales in the recent window
    MIN_BID_ASK_COUNT = int(os.getenv("MIN_BID_ASK_COUNT", "5"))  # min bid+ask orders
    MAX_FIRST_SALE_AGE_DAYS = int(os.getenv("MAX_FIRST_SALE_AGE_DAYS", "30"))

    # --- Repricing ---
    REPRICE_AFTER_HOURS = 24     # Hours after which to reprice a stale offer

    # --- Risk Management ---
    MIN_PRICE_USD = 0.50      # Ignore cheap trash (<$0.50)
    MAX_PRICE_USD = float(os.getenv("MAX_PRICE_USD", "20.00"))  # Ignore high-risk items (>$X)

    # --- v14.4 Dynamic Balance-Aware Position Sizing ---
    # RESEARCH BASIS: Half Kelly Criterion, Risk of Ruin (Wikipedia/Investopedia)
    # The bot adapts its maximum item price, inventory cap, and position size
    # dynamically based on actual DMarket balance. This prevents:
    #   - Overspending when balance is low ($43 → items ≤ $5)
    #   - Underspending when balance grows ($500 → items ≤ $50)
    #   - Capital freeze from 7-day trade-lock (lock-aware inventory cap)
    #   - Risk of ruin from over-concentration (Fractional Kelly sizing)

    # --- Reserve Buffer ---
    # Unspendable safety margin. Effective trading balance = max(0, balance - reserve)
    # Protects against: withdrawal requests, fee spikes, pending order holds.
    BALANCE_RESERVE_USD = float(os.getenv("BALANCE_RESERVE_USD", "10.00"))

    # --- Dynamic Max Snipe Price ---
    # Formula: max(floor, balance * fraction)
    # At $43 → $5 floor. At $500 → $50. At $2000 → $200.
    # This is the Half Kelly approach: use a fraction of Kelly (50%) for safety.
    MAX_SNIPING_PRICE_FLOOR = float(os.getenv("MAX_SNIPING_PRICE_FLOOR", "5.00"))
    MAX_SNIPING_PRICE_BALANCE_FRACTION = float(os.getenv("MAX_SNIPING_PRICE_BALANCE_FRACTION", "0.10"))
    MAX_SNIPING_PRICE_USD = float(os.getenv("MAX_SNIPING_PRICE_USD", "5.00"))  # kept as env-overridable ceiling

    # --- Fractional Kelly Position Sizing ---
    # Kelly formula: f* = win_rate - (1 - win_rate) / win_loss_ratio
    # Half Kelly = 0.5 * f* (reduces drawdown by ~50%, growth rate by ~15%)
    KELLY_ENABLED = os.getenv("KELLY_ENABLED", "true").lower() == "true"
    KELLY_FRACTION = float(os.getenv("KELLY_FRACTION", "0.50"))  # 0.50 = Half Kelly
    KELLY_FLOOR_PCT = float(os.getenv("KELLY_FLOOR_PCT", "3.0"))  # minimum position risk % even if Kelly says less

    # --- Lock-Aware Inventory Cap ---
    # Dynamic ceiling: max items = (balance * liquid_fraction) / max_item_price
    # At $43 with $5 items: cap ≈ 6. At $500 with $50 items: cap ≈ 8.
    # Prevents all capital from being frozen in trade-lock simultaneously.
    LOCK_AWARE_CAP_ENABLED = os.getenv("LOCK_AWARE_CAP_ENABLED", "true").lower() == "true"
    LOCK_AWARE_LIQUID_FRACTION = float(os.getenv("LOCK_AWARE_LIQUID_FRACTION", "0.80"))

    # --- Capital Velocity Constraint ---
    # Ensures bot doesn't freeze all capital in trade-lock. Minimum
    # weekly sell-through rate relative to average balance.
    # velocity < 1.0 → bot pauses buying until locked items sell.
    CAPITAL_VELOCITY_ENABLED = os.getenv("CAPITAL_VELOCITY_ENABLED", "true").lower() == "true"
    CAPITAL_VELOCITY_MIN = float(os.getenv("CAPITAL_VELOCITY_MIN", "0.50"))

    # --- Drawdown-Aware Spending Freeze ---
    # If current balance drops below peak * (1 - threshold), stop buying.
    # Only sells allowed until balance recovers above the threshold.
    DRAWDOWN_FREEZE_ENABLED = os.getenv("DRAWDOWN_FREEZE_ENABLED", "true").lower() == "true"
    DRAWDOWN_FREEZE_THRESHOLD = float(os.getenv("DRAWDOWN_FREEZE_THRESHOLD", "0.15"))  # decimal: 0.15 = 15% drawdown freeze

    MAX_OPEN_TARGETS = 50     # Limit active buy orders (Safety cap)

    # --- Inventory & Sale Age (used in price_history/history.py + telegram) ---
    MAX_LAST_SALE_AGE_DAYS = int(os.getenv("MAX_LAST_SALE_AGE_DAYS", "30"))  # Reject items whose last sale is older than N days
    MAX_OPEN_INVENTORY = int(os.getenv("MAX_OPEN_INVENTORY", "200"))  # Telegram cap on open inventory items
    BOT_VERSION = os.getenv("BOT_VERSION", "v14.8.0")  # Reported in /start, /status

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
    AGG_SCAN_TOP_N = int(os.getenv("AGG_SCAN_TOP_N", "50"))  # v12.3: top-N most-traded items from agg-prices scan per cycle (max 100)
    LISTINGS_FETCH_LIMIT = int(os.getenv("LISTINGS_FETCH_LIMIT", "10"))  # v12.3: N listings per title (DMarket doesn't sort by price; higher = more chance of getting the actual cheapest)

    # --- v14.8 Price-Range Market Scan (wide-net pipeline) ---
    # Enables scanning DMarket by price buckets instead of only top-N volume.
    # Uses get_market_items_v2(priceFrom, priceTo) to discover under-the-radar
    # items that never appear in aggregated-prices top-100.
    PRICE_RANGE_SCAN_ENABLED = os.getenv("PRICE_RANGE_SCAN_ENABLED", "false").lower() == "true"
    PRICE_RANGE_MIN_USD = float(os.getenv("PRICE_RANGE_MIN_USD", "0.50"))
    PRICE_RANGE_MAX_USD = float(os.getenv("PRICE_RANGE_MAX_USD", "5.00"))
    PRICE_RANGE_MAX_TITLES = int(os.getenv("PRICE_RANGE_MAX_TITLES", "100"))  # per cycle
    PRICE_RANGE_MAX_PAGES = int(os.getenv("PRICE_RANGE_MAX_PAGES", "5"))      # 5 * 100 listings = 500 listings
    PRICE_RANGE_CYCLE_INTERVAL = int(os.getenv("PRICE_RANGE_CYCLE_INTERVAL", "5"))  # run every N cycles

    # --- v14.8 Cross-Market Arbitrage Calibration ---
    # Fee-aware cross-market gate: require bid on external marketplace to cover
    # DMarket ask + DMarket sell fee + destination marketplace fee + withdrawal.
    CROSS_MARKET_DESTINATION_FEE = float(os.getenv("CROSS_MARKET_DESTINATION_FEE", "0.025"))  # e.g. Buff163 sell fee 2.5%
    CROSS_MARKET_FEE_AWARE = os.getenv("CROSS_MARKET_FEE_AWARE", "true").lower() == "true"

    # --- v14.9 Cross-Market Buy Targets (Limit Orders) ---
    # Post DMarket buy orders priced from CS2Cap reference when DMarket ask is
    # above external markets. Provides liquidity and catches sellers hitting our
    # price without requiring instant underpriced listings.
    CROSS_MARKET_TARGET_ENABLED = os.getenv("CROSS_MARKET_TARGET_ENABLED", "true").lower() == "true"
    CROSS_MARKET_TARGET_MARGIN = float(os.getenv("CROSS_MARKET_TARGET_MARGIN", "0.03"))
    CROSS_MARKET_TARGET_MAX_PER_CYCLE = int(
        os.getenv("CROSS_MARKET_TARGET_MAX_PER_CYCLE", "10")
    )

    # --- v14.8 Microstructure Filter Toggle ---
    # For low-balance / low-frequency CS2 markets, strict HFT-style filters
    # (OBI, OFI, VWAP, VPIN, Roll, Adverse Selection, Vol Regime) often kill
    # all candidates. Set to false to use only spread + fee + liquidity gates.
    STRICT_MICROSTRUCTURE_FILTERS = (
        os.getenv("STRICT_MICROSTRUCTURE_FILTERS", "true").lower() == "true"
    )

    # --- v12.4 In-Memory CS2Cap Cache ---
    # P0-B: Eliminate per-cycle CS2Cap calls. Background task refreshes
    # the top-N most-traded titles every N seconds. In-cycle validation
    # is pure dict lookups (sub-ms latency).
    CS2CAP_CACHE_TTL_SECONDS = int(os.getenv("CS2CAP_CACHE_TTL_SECONDS", "300"))  # 5 min
    CS2CAP_CACHE_REFRESH_TOP_N = int(os.getenv("CS2CAP_CACHE_REFRESH_TOP_N", "200"))  # 200 = O2: 2x coverage, same HTTP cost
    CS2CAP_CACHE_REFRESH_ON_START = True  # prime cache before first cycle
    CS2CAP_CATALOG_WARMUP_ON_START = int(os.getenv("CS2CAP_CATALOG_WARMUP_ON_START", "0"))  # 0 = save quota; set 1 only if get_item_id() needed

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

    # --- v13.0: Trade lock hours (0 = instant resale on DMarket marketplace) ---
    # DMarket allows IMMEDIATE re-listing of marketplace-bought items.
    # Steam Trade Protection blocks withdrawal to Steam only, not re-selling.
    # Set to positive value only if items come from Steam deposits.
    TRADE_LOCK_HOURS = int(os.getenv("TRADE_LOCK_HOURS", "0"))

    # --- Multi-Strategy Engine ---
    ACTIVE_STRATEGY = "MarketMaker"  # Options: MarketMaker, SpreadHunter, CrossMarket

    # --- Dynamic Position Sizing ---
    USE_DYNAMIC_SIZING = True
    MAX_POSITION_RISK_PCT = float(os.getenv("MAX_POSITION_RISK_PCT", "15.0"))  # Max capital risk per single item (Kelly Criterion proxy)
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

    # =================================================================
    # v14.0 Order Book Microstructure Enhancements
    # =================================================================

    # --- OBI (Order Book Imbalance) ---
    # Measures pressure ratio: bid_volume / ask_volume from agg_prices.
    # OBI > 1.0 = buyer pressure, OBI < 1.0 = seller pressure.
    OBI_ENABLED = os.getenv("OBI_ENABLED", "true").lower() == "true"
    OBI_MIN_RATIO = float(os.getenv("OBI_MIN_RATIO", "0.7"))       # skip if below (seller-dominated)
    OBI_BOOST_RATIO = float(os.getenv("OBI_BOOST_RATIO", "1.3"))   # boost priority if above (buyer-dominated)

    # --- OFI (Order Flow Imbalance) ---
    # Tracks delta of bid/ask counts between cycles. Positive = growing demand.
    OFI_ENABLED = os.getenv("OFI_ENABLED", "true").lower() == "true"
    OFI_BUY_THRESHOLD = int(os.getenv("OFI_BUY_THRESHOLD", "5"))       # ofi > N → buy signal
    OFI_SELL_THRESHOLD = int(os.getenv("OFI_SELL_THRESHOLD", "-10"))   # ofi < N → skip

    # --- Bait/Spoof Detection ---
    # Detects listings with rapidly changing prices (bait traps).
    BAIT_DETECTION_ENABLED = os.getenv("BAIT_DETECTION_ENABLED", "true").lower() == "true"
    BAIT_MAX_PRICE_CHANGES = int(os.getenv("BAIT_MAX_PRICE_CHANGES", "3"))  # max price changes in 5 min

    # --- Micro-Price (Volume-Adjusted Fair Price) ---
    # Weighted mid-price for more accurate listing price vs simple cs2cap * 0.97.
    MICRO_PRICE_ENABLED = os.getenv("MICRO_PRICE_ENABLED", "true").lower() == "true"

    # --- DOM Gap Analysis ---
    # Places listings into price gaps in the market depth profile.
    DOM_GAP_ENABLED = os.getenv("DOM_GAP_ENABLED", "true").lower() == "true"

    # --- Float/Phase Scanning ---
    # Secondary scan for low-float and rare-phase items potentially undervalued.
    FLOAT_PHASE_SCAN_ENABLED = os.getenv("FLOAT_PHASE_SCAN_ENABLED", "true").lower() == "true"
    FLOAT_PHASE_MAX_EXTRA_CALLS = int(os.getenv("FLOAT_PHASE_MAX_EXTRA_CALLS", "10"))

    # --- v14.1 Order Book Microstructure (DMarket-native) ---

    # Stoikov Micro-Price (OBI-adjusted fair price — better than simple volume-weighted)
    STOIKOV_MICRO_PRICE_ENABLED = os.getenv("STOIKOV_MICRO_PRICE_ENABLED", "true").lower() == "true"
    STOIKOV_CALIBRATION = float(os.getenv("STOIKOV_CALIBRATION", "0.35"))  # calibration constant for mid adjustment

    # Multi-Level OBI (depth-weighted from listing DOM data)
    MULTI_LEVEL_OBI_ENABLED = os.getenv("MULTI_LEVEL_OBI_ENABLED", "true").lower() == "true"
    MULTI_LEVEL_OBI_DEPTH = int(os.getenv("MULTI_LEVEL_OBI_DEPTH", "5"))  # number of depth levels

    # Queue Imbalance (bid/ask queue ratio for large-tick assets)
    QUEUE_IMBALANCE_ENABLED = os.getenv("QUEUE_IMBALANCE_ENABLED", "true").lower() == "true"
    QI_BUY_THRESHOLD = float(os.getenv("QI_BUY_THRESHOLD", "1.5"))   # qi > N → strong buy signal
    QI_SELL_THRESHOLD = float(os.getenv("QI_SELL_THRESHOLD", "0.5"))  # qi < N → skip

    # A-S (Avellaneda-Stoikov) Market Making — inventory-aware listing price
    AS_ENABLED = os.getenv("AS_ENABLED", "true").lower() == "true"
    AS_RISK_AVERSION = float(os.getenv("AS_RISK_AVERSION", "0.3"))   # gamma — higher = more aggressive inventory management
    AS_TIME_HORIZON_DAYS = float(os.getenv("AS_TIME_HORIZON_DAYS", "7"))  # T — trade lock + settlement horizon

    # VWAP (Volume-Weighted Average Price) buy filter
    VWAP_FILTER_ENABLED = os.getenv("VWAP_FILTER_ENABLED", "true").lower() == "true"
    VWAP_DISCOUNT_THRESHOLD = float(os.getenv("VWAP_DISCOUNT_THRESHOLD", "0.90"))  # buy if best_ask < VWAP * 0.90 (10% undervaluation)
    VWAP_BANDS_ENABLED = os.getenv("VWAP_BANDS_ENABLED", "false").lower() == "true"  # VWAP bands for listing price

    # Slippage gate (Almgren-Chriss simplified)
    SLIPPAGE_GATE_ENABLED = os.getenv("SLIPPAGE_GATE_ENABLED", "true").lower() == "true"
    SLIPPAGE_TEMP_IMPACT_BPS = float(os.getenv("SLIPPAGE_TEMP_IMPACT_BPS", "5.0"))  # bps per 1% participation
    SLIPPAGE_PERM_IMPACT_BPS = float(os.getenv("SLIPPAGE_PERM_IMPACT_BPS", "2.0"))  # bps per 1% of daily volume

    # CVD (Cumulative Volume Delta)
    CVD_ENABLED = os.getenv("CVD_ENABLED", "true").lower() == "true"
    CVD_WINDOW_ITEMS = int(os.getenv("CVD_WINDOW_ITEMS", "5"))  # fetch last-sales for top N items per cycle

    # VPIN-lite (Volume-Synchronized Probability of Informed Trading)
    VPIN_ENABLED = os.getenv("VPIN_ENABLED", "true").lower() == "true"
    VPIN_BUCKETS = int(os.getenv("VPIN_BUCKETS", "8"))          # number of volume buckets
    VPIN_THRESHOLD = float(os.getenv("VPIN_THRESHOLD", "0.8"))  # VPIN > this → toxic flow

    # Adverse Selection (Kyle λ / Amihud illiquidity)
    ADVERSER_SELECTION_ENABLED = os.getenv("ADVERSER_SELECTION_ENABLED", "true").lower() == "true"
    KYLE_LAMBDA_MAX = float(os.getenv("KYLE_LAMBDA_MAX", "0.05"))
    AMIHUD_ILLIQUIDITY_MAX = float(os.getenv("AMIHUD_ILLIQUIDITY_MAX", "0.10"))

    # Realized Volatility Regime (Parkinson + standard deviation from trade_history)
    VOL_REGIME_ENABLED = os.getenv("VOL_REGIME_ENABLED", "true").lower() == "true"
    VOL_REGIME_HIGH_THRESHOLD = float(os.getenv("VOL_REGIME_HIGH_THRESHOLD", "0.50"))  # annualized vol > this → "high"

    # Roll's Model (effective spread from price autocorrelation)
    ROLL_MODEL_ENABLED = os.getenv("ROLL_MODEL_ENABLED", "true").lower() == "true"

    # Volume Profile / POC (Point of Control — price magnet)
    VOLUME_PROFILE_ENABLED = os.getenv("VOLUME_PROFILE_ENABLED", "true").lower() == "true"
    VP_NUM_BUCKETS = int(os.getenv("VP_NUM_BUCKETS", "10"))

    # Smart Cancel/Reprice (order-book-aware listing management)
    SMART_REPRICE_ENABLED = os.getenv("SMART_REPRICE_ENABLED", "true").lower() == "true"

    # Composite Score (weighted signal ranking — replaces simple spread sorting)
    COMPOSITE_SCORE_ENABLED = os.getenv("COMPOSITE_SCORE_ENABLED", "true").lower() == "true"

    # Time-of-day seasonality
    TOD_ENABLED = os.getenv("TOD_ENABLED", "true").lower() == "true"
    TOD_NIGHT_MULTIPLIER = float(os.getenv("TOD_NIGHT_MULTIPLIER", "0.85"))  # lower spread threshold at night (buy more aggressively)
    TOD_DAY_MULTIPLIER = float(os.getenv("TOD_DAY_MULTIPLIER", "1.0"))       # normal during day
    TOD_NIGHT_START_UTC = int(os.getenv("TOD_NIGHT_START_UTC", "4"))         # 04:00 UTC (~00:00 EST)
    TOD_NIGHT_END_UTC = int(os.getenv("TOD_NIGHT_END_UTC", "10"))            # 10:00 UTC (~06:00 EST)
    TOD_WEEKEND_ENABLED = os.getenv("TOD_WEEKEND_ENABLED", "true").lower() == "true"  # day-of-week adjustment

    # --- Sharpe-Optimized Objective ---
    # Instead of flat threshold, use risk-adjusted objective
    SHARPE_OPTIMIZATION_ENABLED = True
    TARGET_SHARPE_RATIO = 1.5           # Target risk-adjusted return
    DRAWDOWN_PENALTY_WEIGHT = 0.5       # Penalty weight for max drawdown
    OBJECTIVE_FUNCTION = "sharpe_adjusted"  # Options: threshold, sharpe_adjusted
