"""
Centralized Configuration for DMarket Trading Bot.
Acts as the Single Source of Truth for Fees, Game IDs, and Trading Limits.
"""

import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Dict, Optional


@dataclass(frozen=True)
class GameParams:
    """Standardized parameters for supported games."""

    app_id: int
    context_id: int
    dmarket_id: str
    friendly_name: str


@dataclass(frozen=True)
class FeeConfig:
    """Platform Fees and Economic Constants."""

    # Waxpeer
    WAX_SELLING_FEE: Decimal = Decimal("0.06")  # 6%
    WAX_CASHOUT_FEE: Decimal = Decimal("0.02")  # 2%

    # DMarket
    DM_FEE_F2F: Decimal = Decimal("0.03")  # 3%
    DM_FEE_BOT: Decimal = Decimal("0.07")  # 7% (Default pessimistic)

    # Capital Efficiency
    STEAM_HOLD_DAYS: int = 7
    DAlgoLY_OPPORTUNITY_COST: Decimal = Decimal("0.01")  # 1% daily target


@dataclass(frozen=True)
class TradingConfig:
    """Trading Logic Thresholds."""

    MIN_GRIND_ROI: Decimal = Decimal("0.03")  # 3%
    MIN_GEM_ROI: Decimal = Decimal("0.12")  # 12%

    # Liquidity Scores (0-100)
    MIN_LIQUIDITY_GRIND: float = 50.0
    MIN_LIQUIDITY_GEM: float = 20.0

    # Budget Safety
    BALANCE_BUFFER: Decimal = Decimal("0.9")  # Use only 90% of balance


@dataclass
class AppConfig:
    """Global Application Config."""

    fees: FeeConfig = field(default_factory=FeeConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)

    # Game Definitions
    GAMES: Dict[str, GameParams] = field(
        default_factory=lambda: {
            "csgo": GameParams(730, 2, "a8db", "Counter-Strike 2"),
            "dota2": GameParams(570, 2, "9a92", "Dota 2"),
            "rust": GameParams(252490, 2, "rust", "Rust"),
            "tf2": GameParams(440, 2, "tf2", "Team Fortress 2"),
        }
    )

    # Infrastructure
    REDIS_URL: Optional[str] = os.getenv("REDIS_URL")
    USE_REDIS: bool = str(os.getenv("USE_REDIS", "false")).lower() == "true"


# Singleton Instance
CONFIG = AppConfig()
