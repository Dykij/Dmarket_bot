"""
Game Profiles for DMarket HFT Strategy v2.
Defines K_s2c (Steam-to-Cash) coefficients and Beta (markdown speed) for each game.
"""

from dataclasses import dataclass

@dataclass
class GameProfile:
    game_id: str
    k_s2c_target: float  # Target ratio (e.g. 0.7 means we buy at 70% of Steam)
    k_s2c_max: float     # Maximum allowed ratio (risk threshold)
    beta_markdown: float # Speed of price reduction (0.01 = 1% per tick)
    min_spread: float    # Minimum bid-ask spread to enter
    sell_margin: float   # Target profit margin (0.06 = 6%)
    description: str

PROFILES = {
    # CS2: High liquidity, tight spreads. We need aggressive K.
    "a8db": GameProfile(
        game_id="a8db",
        k_s2c_target=0.68, 
        k_s2c_max=0.72,
        beta_markdown=0.005, # Slow decay
        min_spread=2.5,
        sell_margin=0.07, # 7%
        description="Counter-Strike 2"
    ),
    # Dota 2: Medium liquidity, higher volatility.
    "9a92": GameProfile(
        game_id="9a92",
        k_s2c_target=0.60,
        k_s2c_max=0.65,
        beta_markdown=0.01,
        min_spread=3.0,
        sell_margin=0.10, # 10%
        description="Dota 2"
    ),
    # TF2: Stable currency (Keys), junk items are risky.
    "tf2": GameProfile(
        game_id="tf2",
        k_s2c_target=0.55, # Conservative for items, special logic for Keys needed
        k_s2c_max=0.85,    # Allow higher for Keys (Mann Co)
        beta_markdown=0.002,
        min_spread=1.5,
        sell_margin=0.06, # 6% for Keys
        description="Team Fortress 2"
    ),
    # Rust: High volatility, low volume.
    "rust": GameProfile(
        game_id="rust",
        k_s2c_target=0.50,
        k_s2c_max=0.60,
        beta_markdown=0.02, # Fast decay
        min_spread=5.0,
        sell_margin=0.12, # 12%
        description="Rust"
    )
}

def get_profile(game_id: str) -> GameProfile:
    return PROFILES.get(game_id, PROFILES["a8db"]) # Default to CS2
