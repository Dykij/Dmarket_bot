"""
Configuration: src/config.py (v14.9)
Center of Operations. All strategy parameters are strictly defined here.
Game: CS2 Only (a8db).
Risk Management: Max Price $20, Min Spread 7%.
Oracle Integration: MultiSourceOracle (Market.CSGO + Waxpeer + CSFloat + Steam).

v14.9 Improvements (based on PythonHub best practices):
- Pydantic BaseSettings for validation and type safety
- Fail-fast on invalid config at startup
- Environment variable validation with defaults
- Type coercion and constraints (ge, le, etc.)
- Removed paid oracle backward compatibility (replaced by MultiSourceOracle)
"""

from __future__ import annotations

from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    """Trading bot configuration with validation."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # --- Credentials ---
    DMARKET_PUBLIC_KEY: str | None = None
    DMARKET_SECRET_KEY: str | None = None

    # --- Target Game ---
    GAME_ID: str = "a8db"  # Counter-Strike 2

    # --- Trading Parameters ---
    MIN_SPREAD_PCT: float = Field(default=0.1, ge=0.0, le=100.0)
    FEE_RATE: float = Field(default=0.05, ge=0.0, le=1.0)
    TARGET_FEE_RATE: float = Field(default=0.025, ge=0.0, le=1.0)
    WITHDRAWAL_FEE_RATE: float = Field(default=0.005, ge=0.0, le=1.0)

    # --- Intra-Spread Strategy ---
    INTRA_MIN_SPREAD_PCT: float = Field(default=0.1, ge=0.0)
    INTRA_LIST_DISCOUNT: float = Field(default=0.01, ge=0.0)

    # --- Value Detection Scanner ---
    VALUE_SCAN_ENABLED: bool = True
    VALUE_SIGNAL_WEIGHT: float = Field(default=0.5, ge=0.0, le=1.0)
    VALUE_SCAN_MIN_PREMIUM: float = Field(default=1.05, ge=1.0)
    VALUE_SCAN_MIN_PROFIT_PCT: float = Field(default=0.5, ge=0.0)
    VALUE_SCAN_MIN_PROFIT_USD: float = Field(default=0.20, ge=0.0)
    VALUE_SCAN_MAX_ITEMS_PER_CYCLE: int = Field(default=20, ge=1, le=100)

    # --- Liquidity / Wash-Trading Filters ---
    USE_LIQUIDITY_FILTER: bool = False
    WASH_TRADING_DETECTION: bool = True
    TRIMMED_MEAN_BOOST_PCT: float = Field(default=5.0, ge=0.0)
    TRIMMED_MEAN_MAX_OUTLIERS: int = Field(default=2, ge=0)

    # --- Liquidity metrics ---
    MIN_TOTAL_SALES: int = Field(default=3, ge=0)
    MIN_SALES_IN_WINDOW: int = Field(default=2, ge=0)
    MIN_BID_ASK_COUNT: int = Field(default=2, ge=0)
    MAX_FIRST_SALE_AGE_DAYS: int = Field(default=30, ge=1)

    # --- Repricing ---
    REPRICE_AFTER_HOURS: int = Field(default=24, ge=1)

    # --- Risk Management ---
    MIN_PRICE_USD: float = Field(default=0.50, ge=0.0)
    MAX_PRICE_USD: float = Field(default=20.00, ge=0.0)

    # --- Dynamic Balance-Aware Position Sizing ---
    BALANCE_RESERVE_USD: float = Field(default=5.00, ge=0.0)

    # --- Dynamic Max Snipe Price ---
    MAX_SNIPING_PRICE_FLOOR: float = Field(default=5.00, ge=0.0)
    MAX_SNIPING_PRICE_BALANCE_FRACTION: float = Field(default=0.10, ge=0.0, le=1.0)
    MAX_SNIPING_PRICE_USD: float = Field(default=5.00, ge=0.0)

    # --- Fractional Kelly Position Sizing ---
    KELLY_ENABLED: bool = True
    KELLY_FRACTION: float = Field(default=0.50, ge=0.0, le=1.0)
    KELLY_FLOOR_PCT: float = Field(default=3.0, ge=0.0)

    # --- Lock-Aware Inventory Cap ---
    LOCK_AWARE_CAP_ENABLED: bool = True
    LOCK_AWARE_LIQUID_FRACTION: float = Field(default=0.80, ge=0.0, le=1.0)

    # --- Capital Velocity Constraint ---
    CAPITAL_VELOCITY_ENABLED: bool = True
    CAPITAL_VELOCITY_MIN: float = Field(default=0.50, ge=0.0)

    # --- Drawdown-Aware Spending Freeze ---
    DRAWDOWN_FREEZE_ENABLED: bool = True
    DRAWDOWN_FREEZE_THRESHOLD: float = Field(default=0.15, ge=0.0, le=1.0)

    MAX_OPEN_TARGETS: int = Field(default=50, ge=1)

    # --- Inventory & Sale Age ---
    MAX_LAST_SALE_AGE_DAYS: int = Field(default=30, ge=1)
    MAX_OPEN_INVENTORY: int = Field(default=200, ge=1)
    BOT_VERSION: str = "v14.9"

    # --- Performance ---
    SCAN_INTERVAL: int = Field(default=30, ge=1)
    BATCH_SIZE: int = Field(default=100, ge=1)

    # --- Oracle Settings ---
    ORACLE_BATCH_SIZE: int = Field(default=100, ge=1)
    ORACLE_TOP_K_VALIDATE: int = Field(default=50, ge=1)
    ORACLE_SELECTIVE_MODE: bool = True
    ORACLE_CACHE_TTL_SECONDS: int = Field(default=900, ge=0)
    ORACLE_CACHE_REFRESH_TOP_N: int = Field(default=200, ge=1)
    ORACLE_CACHE_REFRESH_ON_START: bool = True
    AGG_SCAN_TOP_N: int = Field(default=100, ge=1)
    LISTINGS_FETCH_LIMIT: int = Field(default=20, ge=1)

    # --- Price-Range Market Scan ---
    PRICE_RANGE_SCAN_ENABLED: bool = True
    PRICE_RANGE_MIN_USD: float = Field(default=0.50, ge=0.0)
    PRICE_RANGE_MAX_USD: float = Field(default=20.00, ge=0.0)
    PRICE_RANGE_MAX_TITLES: int = Field(default=500, ge=1)
    PRICE_RANGE_MAX_PAGES: int = Field(default=20, ge=1)
    PRICE_RANGE_CYCLE_INTERVAL: int = Field(default=1, ge=1)

    # --- Low-Fee Items Scan ---
    LOW_FEE_ITEMS_SCAN_ENABLED: bool = True
    LOW_FEE_ITEMS_SCAN_LIMIT: int = Field(default=100, ge=1)

    # --- Cross-Market Arbitrage ---
    CROSS_MARKET_DESTINATION_FEE: float = Field(default=0.025, ge=0.0)
    CROSS_MARKET_FEE_AWARE: bool = True

    # --- Cross-Market Buy Targets ---
    CROSS_MARKET_TARGET_ENABLED: bool = True
    CROSS_MARKET_TARGET_MARGIN: float = Field(default=0.02, ge=0.0)
    CROSS_MARKET_TARGET_MAX_PER_CYCLE: int = Field(default=20, ge=1)

    # --- DMarket-Internal Underpriced Detection ---
    DMARKET_INTERNAL_UNDERPRICED_ENABLED: bool = True
    DM_UNDERPRICED_SALES_DAYS: int = Field(default=7, ge=1)
    DM_UNDERPRICED_PERCENTILE: float = Field(default=0.25, ge=0.0, le=1.0)
    DM_UNDERPRICED_MIN_MARGIN_PCT: float = Field(default=3.0, ge=0.0)

    # --- Microstructure Filter Toggle ---
    STRICT_MICROSTRUCTURE_FILTERS: bool = False

    # --- API Keys ---
    MARKETCSGO_API_KEY: str = ""
    WAXPEER_API_KEY: str = ""
    CSFLOAT_API_KEY: str = ""
    STEAM_API_KEY: str = ""

    # --- Advanced Attributes ---
    PREFER_LOW_FLOAT: bool = True
    FLOAT_PREMIUM_ENABLED: bool = True
    FLOAT_CODES: dict[str, list[str]] = {
        "FN": ["FN-0", "FN-1"],
        "MW": ["MW-0", "MW-1"],
        "FT": ["FT-0", "FT-1"],
        "WW": ["WW-0"],
        "BS": ["BS-0"],
    }

    # --- Value Detection Layers ---
    PATTERN_PREMIUM_ENABLED: bool = True
    STICKER_COMBO_ENABLED: bool = True
    SEASONAL_TIMING_ENABLED: bool = True
    FILLER_TRACKING_ENABLED: bool = True
    DIRTY_BS_ENABLED: bool = True
    ROUND_FLOAT_ENABLED: bool = True
    FLOAT_DATE_ENABLED: bool = True
    COMMISSION_OPTIMIZER_ENABLED: bool = True

    # --- Operation Mode ---
    DRY_RUN: bool = True
    MARKETPLACE_INSTANT_RESALE: bool = True

    @property
    def IS_DRY_RUN(self) -> bool:
        """Cached DRY_RUN check — avoids repeated os.getenv() calls in hot path."""
        return self.DRY_RUN

    # --- Trade lock ---
    TRADE_LOCK_HOURS: int = Field(default=0, ge=0)

    # --- Multi-Strategy Engine ---
    ACTIVE_STRATEGY: str = "ValueScanner"

    # --- Dynamic Position Sizing ---
    USE_DYNAMIC_SIZING: bool = True
    MAX_POSITION_RISK_PCT: float = Field(default=15.0, ge=0.0, le=100.0)
    MAX_SAME_ITEM_HOLDINGS: int = Field(default=3, ge=1)
    MAX_CONCURRENT_POSITIONS: int = Field(default=50, ge=1)
    MAX_TOTAL_INVENTORY_VALUE: float = Field(default=100.0, ge=0.0)
    MAX_TOTAL_INVENTORY_ITEMS: int = Field(default=30, ge=1)

    # --- Loop Selection ---
    USE_V12_LOOP: bool = True

    # --- Self-Reflection ---
    SELF_REFLECTION_WINDOW: int = Field(default=50, ge=1)
    SELF_REFLECTION_INTERVAL: int = Field(default=100, ge=1)
    PARAMETER_ADJUSTMENT_ENABLED: bool = True
    MIN_TRADES_FOR_ADJUSTMENT: int = Field(default=10, ge=1)

    # --- Turnover Regularization ---
    TURNOVER_PENALTY_ENABLED: bool = True
    MAX_DAILY_TRADES: int = Field(default=200, ge=1)
    TURNOVER_PENALTY_PER_TRADE: float = Field(default=0.002, ge=0.0)

    # --- Cross-Market Strategy ---
    CROSS_MARKET_ENABLED: bool = True
    CROSS_MARKET_MIN_EDGE_PCT: float = Field(default=3.0, ge=0.0)
    CROSS_MARKET_MAX_SPREAD_PCT: float = Field(default=15.0, ge=0.0)

    # --- Enhanced Volatility ---
    VOLATILITY_METHOD: str = "garman_klass"
    VOLATILITY_MAX_ANNUALIZED: float = Field(default=0.60, ge=0.0)
    VOLATILITY_LOOKBACK_SALES: int = Field(default=20, ge=1)

    # --- Order Book Microstructure ---
    OBI_ENABLED: bool = True
    OBI_MIN_RATIO: float = Field(default=0.5, ge=0.0)
    OBI_BOOST_RATIO: float = Field(default=1.3, ge=1.0)

    OFI_ENABLED: bool = False
    OFI_BUY_THRESHOLD: int = Field(default=5, ge=0)
    OFI_SELL_THRESHOLD: int = Field(default=-10, le=0)

    BAIT_DETECTION_ENABLED: bool = True
    BAIT_MAX_PRICE_CHANGES: int = Field(default=3, ge=1)

    MICRO_PRICE_ENABLED: bool = False
    DOM_GAP_ENABLED: bool = False

    FLOAT_PHASE_SCAN_ENABLED: bool = True
    FLOAT_PHASE_MAX_EXTRA_CALLS: int = Field(default=10, ge=0)

    STOIKOV_MICRO_PRICE_ENABLED: bool = False
    STOIKOV_CALIBRATION: float = Field(default=0.35, ge=0.0, le=1.0)

    MULTI_LEVEL_OBI_ENABLED: bool = False
    MULTI_LEVEL_OBI_DEPTH: int = Field(default=5, ge=1)

    QUEUE_IMBALANCE_ENABLED: bool = False
    QI_BUY_THRESHOLD: float = Field(default=1.5, ge=0.0)
    QI_SELL_THRESHOLD: float = Field(default=0.5, ge=0.0)

    AS_ENABLED: bool = False
    AS_RISK_AVERSION: float = Field(default=0.3, ge=0.0, le=1.0)
    AS_TIME_HORIZON_DAYS: float = Field(default=7.0, ge=0.1)

    VWAP_FILTER_ENABLED: bool = True
    VWAP_DISCOUNT_THRESHOLD: float = Field(default=0.90, ge=0.0, le=1.0)
    VWAP_BANDS_ENABLED: bool = False

    SLIPPAGE_GATE_ENABLED: bool = False
    SLIPPAGE_TEMP_IMPACT_BPS: float = Field(default=5.0, ge=0.0)
    SLIPPAGE_PERM_IMPACT_BPS: float = Field(default=2.0, ge=0.0)

    CVD_ENABLED: bool = False
    CVD_WINDOW_ITEMS: int = Field(default=5, ge=1)

    VPIN_ENABLED: bool = False
    VPIN_BUCKETS: int = Field(default=8, ge=2)
    VPIN_THRESHOLD: float = Field(default=0.8, ge=0.0, le=1.0)

    ADVERSER_SELECTION_ENABLED: bool = False
    KYLE_LAMBDA_MAX: float = Field(default=0.05, ge=0.0)
    AMIHUD_ILLIQUIDITY_MAX: float = Field(default=0.10, ge=0.0)

    VOL_REGIME_ENABLED: bool = False
    VOL_REGIME_HIGH_THRESHOLD: float = Field(default=0.50, ge=0.0)

    ROLL_MODEL_ENABLED: bool = False

    VOLUME_PROFILE_ENABLED: bool = False
    VP_NUM_BUCKETS: int = Field(default=10, ge=2)

    # --- v15.7: Event Detection ---
    EVENT_DETECTION_ENABLED: bool = True
    EVENT_VOLUME_SPIKE_THRESHOLD: float = Field(default=3.0, ge=1.0)
    EVENT_IMPACT_WINDOW_HOURS: int = Field(default=24, ge=1)

    # --- v15.7: Supply Tracking ---
    SUPPLY_TRACKING_ENABLED: bool = True
    SUPPLY_THIN_MARKET_THRESHOLD: int = Field(default=5, ge=1)
    SUPPLY_MARGIN_BOOST_ENABLED: bool = True

    # --- v15.7: Volume Profile Refinement ---
    VP_REFINEMENT_ENABLED: bool = True
    VP_POC_WEIGHT: float = Field(default=0.3, ge=0.0, le=1.0)
    VP_VALUE_AREA_PCT: float = Field(default=0.70, ge=0.5, le=0.95)

    SMART_REPRICE_ENABLED: bool = False

    COMPOSITE_SCORE_ENABLED: bool = False

    # --- Stop-Loss / Take-Profit / Time-Stop (v14.5+) ---
    STOP_LOSS_PCT: float = Field(default=10.0, ge=0.0, le=100.0)
    TAKE_PROFIT_PCT: float = Field(default=15.0, ge=0.0, le=1000.0)
    STOP_LOSS_ENABLED: bool = True
    TAKE_PROFIT_ENABLED: bool = True
    STOP_LOSS_MIN_AGE_HOURS: float = Field(default=24.0, ge=0.0)
    TIME_STOP_ENABLED: bool = True
    TIME_STOP_MINUTES: int = Field(default=90, ge=1)

    # --- Time of Day Adjustment ---
    TIME_OF_DAY_ENABLED: bool = True
    TIME_OF_DAY_NIGHT_START_UTC: int = Field(default=4, ge=0, le=23)
    TIME_OF_DAY_NIGHT_END_UTC: int = Field(default=10, ge=0, le=23)
    TIME_OF_DAY_WEEKEND_ENABLED: bool = True
    TIME_OF_DAY_NIGHT_MULTIPLIER: float = Field(default=1.2, ge=0.0)
    TIME_OF_DAY_DAY_MULTIPLIER: float = Field(default=1.0, ge=0.0)

    # --- Sharpe-Optimized Objective ---
    SHARPE_OPTIMIZATION_ENABLED: bool = True
    TARGET_SHARPE_RATIO: float = Field(default=1.5, ge=0.0)
    DRAWDOWN_PENALTY_WEIGHT: float = Field(default=0.5, ge=0.0)
    OBJECTIVE_FUNCTION: str = "sharpe_adjusted"

    # --- Ornstein-Uhlenbeck Mean-Reversion ---
    OU_ENTRY_Z_SCORE: float = Field(default=-1.5, le=0.0)
    OU_STOP_Z_SCORE: float = Field(default=-3.0, le=0.0)
    OU_MIN_R_SQUARED: float = Field(default=0.3, ge=0.0, le=1.0)

    # --- Backward Compatibility Aliases ---
    @property
    def TOD_ENABLED(self) -> bool:
        return self.TIME_OF_DAY_ENABLED

    @property
    def TOD_NIGHT_START_UTC(self) -> int:
        return self.TIME_OF_DAY_NIGHT_START_UTC

    @property
    def TOD_NIGHT_END_UTC(self) -> int:
        return self.TIME_OF_DAY_NIGHT_END_UTC

    @property
    def TOD_WEEKEND_ENABLED(self) -> bool:
        return self.TIME_OF_DAY_WEEKEND_ENABLED

    @property
    def TOD_NIGHT_MULTIPLIER(self) -> float:
        return self.TIME_OF_DAY_NIGHT_MULTIPLIER

    @property
    def TOD_DAY_MULTIPLIER(self) -> float:
        return self.TIME_OF_DAY_DAY_MULTIPLIER

    # Legacy aliases
    @property
    def PUBLIC_KEY(self) -> str | None:
        return self.DMARKET_PUBLIC_KEY

    @property
    def SECRET_KEY(self) -> str | None:
        return self.DMARKET_SECRET_KEY

    @field_validator("MAX_PRICE_USD")
    @classmethod
    def validate_max_price(cls, v: float, info: Any) -> float:
        """Ensure MAX_PRICE_USD > MIN_PRICE_USD."""
        min_price = info.data.get("MIN_PRICE_USD", 0.0)
        if v <= min_price:
            raise ValueError(
                f"MAX_PRICE_USD ({v}) must be greater than MIN_PRICE_USD ({min_price})"
            )
        return v

    @field_validator("TIME_OF_DAY_NIGHT_END_UTC")
    @classmethod
    def validate_night_end(cls, v: int, info: Any) -> int:
        """Ensure night end != night start."""
        night_start = info.data.get("TIME_OF_DAY_NIGHT_START_UTC", 0)
        if v == night_start:
            raise ValueError(
                f"TIME_OF_DAY_NIGHT_END_UTC ({v}) must differ from "
                f"TIME_OF_DAY_NIGHT_START_UTC ({night_start})"
            )
        return v


# Singleton instance
Config = Config()  # type: ignore[misc]


def reset_config() -> None:
    """Re-initialize the global Config singleton from current environment.

    Call this in test fixtures (e.g. conftest.py autouse) to prevent
    state leakage between tests that monkeypatch env vars.
    """
    import src.config as _mod

    _cls = type(_mod.Config)
    _mod.Config = _cls()  # type: ignore[misc]
