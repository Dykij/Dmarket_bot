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
    FEE_RATE = 0.05           # DMarket Fee (7% standard, 5% with subscription)

    # --- Risk Management ---
    MIN_PRICE_USD = 0.50      # Ignore cheap trash (<$0.50)
    MAX_PRICE_USD = 20.00     # Ignore high-risk items (>$20.00)

    MAX_OPEN_TARGETS = 50     # Limit active buy orders (Safety cap)

    # --- Performance ---
    SCAN_INTERVAL = 2         # Seconds between scan cycles
    BATCH_SIZE = 20           # Items per API call

    # --- Advanced Attributes (Float/Phase) ---
    PREFER_LOW_FLOAT = True
    FLOAT_CODES = {
        "FN": ["FN-0", "FN-1"],
        "MW": ["MW-0", "MW-1"],
        "FT": ["FT-0", "FT-1"],
        "WW": ["WW-0"],
        "BS": ["BS-0"]
    }

    # --- Operation Mode ---
    DRY_RUN = True

    # --- Multi-Strategy Engine ---
    ACTIVE_STRATEGY = "MarketMaker"  # Options: MarketMaker, SpreadHunter, CrossMarket

    # --- Dynamic Position Sizing ---
    USE_DYNAMIC_SIZING = True
    MAX_POSITION_RISK_PCT = 5.0  # Max capital risk per single item (Kelly Criterion proxy)

    # =================================================================
    # CS2Cap Integration (arXiv-inspired improvements)
    # =================================================================

    # --- CS2Cap API ---
    CS2CAP_API_KEY = os.getenv("CS2CAP_API_KEY", "")
    CS2CAP_ORACLE_PRIMARY = True  # Use CS2Cap as primary oracle for CS2

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
