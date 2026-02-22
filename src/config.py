"""
Configuration: src/config.py
Center of Operations. All strategy parameters are strictly defined here.
Game: CS2 Only (a8db).
Risk Management: Max Price $20, Min Spread 7%.
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
    GAME_ID = "a8db" # Counter-Strike 2

    # --- Trading Parameters ---
    MIN_SPREAD_PCT = 7.0     # Minimum 7% profit margin (Ask - Bid)
    FEE_RATE = 0.07          # DMarket Fee (7% standard, 5% with subscription)
    
    # --- Risk Management ---
    MIN_PRICE_USD = 0.50     # Ignore cheap trash (<$0.50)
    MAX_PRICE_USD = 20.00    # Ignore high-risk items (>$20.00)
    
    MAX_OPEN_TARGETS = 50    # Limit active buy orders (Safety cap)
    
    # --- Performance ---
    SCAN_INTERVAL = 2        # Seconds between scan cycles
    BATCH_SIZE = 20          # Items per API call

    # --- Smart Strategy ---
    WALL_BREAKER_PCT = 2.0   # If gap between 1st and 2nd listing > 2%, target 2nd price
    INVENTORY_DECAY_HOURS = 24 # Start lowering price after 24 hours
    DECAY_RATE_PCT = 1.0     # Lower price by 1% per decay cycle

    # --- Operation Mode ---
    DRY_RUN = True           # True = Simulation (Paper Trading), False = Real Money!
