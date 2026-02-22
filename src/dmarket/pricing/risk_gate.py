"""
Risk Gate - The 'Brain' of Strategy v2.
Validates opportunities against FeeOracle, Steam Price, and Game Profiles.
"""

import logging
from src.dmarket.pricing.game_profiles import get_profile
from src.dmarket.pricing.fee_oracle import fee_oracle
from src.dmarket.steam_api import SteamMarketAPI
from src.rust_core import calculate_obi

logger = logging.getLogger(__name__)

class RiskGate:
    def __init__(self):
        self.steam_api = SteamMarketAPI()

    async def check_opportunity(
        self,
        game_id: str,
        title: str,
        price_usd: float,
        buy_vol: int,
        sell_vol: int,
        spread_percent: float
    ) -> dict:
        """
        Validates a potential BUY opportunity using Rust OBI.
        """
        profile = get_profile(game_id)
        
        # 1. Rust OBI Calculation
        # Rust function signature: calculate_obi(buy_vol: int, sell_vol: int) -> float
        obi = calculate_obi(buy_vol, sell_vol)
        
        if obi < -0.3:
            return {'decision': False, 'reason': f"OBI {obi:.2f} too negative (sell pressure)"}

        # 3. Fee Oracle
        fee_fraction = await fee_oracle.get_fee_for_item(game_id, title)
        
        # 4. Steam Fair Price Check (The Oracle)
        # Assuming we have a cache or fetch it now.
        # For HFT, this should be pre-cached. We'll fetch if missing.
        steam_data = await self.steam_api.get_item_price(None, title) # app_id handled by wrapper? Need mapping.
        
        steam_price = 0.0
        if steam_data:
            steam_price = float(steam_data.get("price", 0))
        
        if steam_price <= 0:
             # Fallback: If no Steam price, rely purely on DMarket Spread?
             # Risky. Block for now.
             return {'decision': False, 'reason': "No Steam Price"}

        # 5. K_s2c Calculation
        k_s2c = price_usd / steam_price
        
        if k_s2c > profile.k_s2c_max:
             return {'decision': False, 'reason': f"K_s2c {k_s2c:.2f} > Max {profile.k_s2c_max}"}

        # 6. Profit Projection
        # Breakeven = BuyPrice / (1 - Fee)
        breakeven = price_usd / (1 - fee_fraction)
        
        # Target Sell: Undercut Steam or match DMarket top?
        # Strategy v2: Sell at min(Steam * 0.85, BestOffer - 1 cent)
        # But for now, let's use the profile target
        target_sell = steam_price * 0.85 
        
        if target_sell <= breakeven:
             return {'decision': False, 'reason': f"No Profit Room. Break: ${breakeven:.2f}, Target: ${target_sell:.2f}"}

        return {
            'decision': True,
            'reason': "GREEN LIGHT",
            'target_sell': target_sell,
            'fee_used': fee_fraction,
            'k_s2c': k_s2c
        }

risk_gate = RiskGate()
