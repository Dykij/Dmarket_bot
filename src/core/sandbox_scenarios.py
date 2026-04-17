"""
Sandbox Scenarios v10.0: Market Weather & Stress Injection.
Models extreme events: Black Swans (crashes) and Tournament spikes.
"""

import random
import logging
import time

logger = logging.getLogger("SandboxScenarios")

class MarketScenarioEngine:
    def __init__(self):
        self.current_event = "normal"
        self.modifier = 1.0
        self.volatility = 1.0
        self.last_update = time.time()

    def get_price_modifier(self) -> float:
        """Returns the current price crash/spike multiplier."""
        # v10.0: Logic for event decay - events shouldn't last forever
        if time.time() - self.last_update > 3600: # Autoreset after 1h
            self.current_event = "normal"
            self.modifier = 1.0
            
        return self.modifier

    def trigger_black_swan(self):
        """Valve Ban / Market Panic Simulation (-20% to -40% drop)."""
        self.current_event = "black_swan"
        self.modifier = random.uniform(0.6, 0.8)
        self.volatility = 4.0
        self.last_update = time.time()
        logger.warning(f"🚨 [SCENARIO] BLACK SWAN TRIGGERED! Market crashing: {self.modifier:.2f}x")

    def trigger_tournament(self):
        """Major Tournament / Hype Spike (+10% to +20% spike)."""
        self.current_event = "tournament"
        self.modifier = random.uniform(1.1, 1.25)
        self.volatility = 2.0
        self.last_update = time.time()
        logger.info(f"🏆 [SCENARIO] TOURNAMENT HYPE! Prices surging: {self.modifier:.2f}x")

    def reset(self):
        self.current_event = "normal"
        self.modifier = 1.0
        self.volatility = 1.0
        logger.info("🌤️ [SCENARIO] Market conditions returned to normal.")

scenario_engine = MarketScenarioEngine()
