"""
Hybrid Trading Engine (Core Implementation).

Integrates:
- Liquidity Analysis (Volume, Velocity)
- Volatility Metrics (Bollinger Bands)
- Fee Optimization (Opportunity Cost)
- Parallel Execution (Grind & Gems)
- Blacklist/Whitelist Enforcement
"""

import asyncio
import random
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

# Core Imports
from src.core.config import CONFIG, AppConfig
from src.core.fees import LiquidityAdjustedFee

# API Imports
from src.api.dmarket import DMarketAPI
from src.api.waxpeer import WaxpeerAPI 
from src.data.blacklist import BlacklistManager

# Utils (To be moved to src/utils)
logger = logging.getLogger("core.engine")

# --- Adapters (To be moved to src/utils/analytics.py and src/utils/liquidity.py) ---
class LiquidityAnalyzer:
    @staticmethod
    def calculate_score(volume_7d: int, recent_sales: int) -> float:
        if volume_7d == 0: return 0.0
        score = (volume_7d / 7) * 10
        return min(score, 100.0)

class VolatilityMetrics:
    @staticmethod
    def get_bollinger_position(price: float, history: List[float]) -> str:
        if not history or len(history) < 3: return "NEUTRAL"
        mean = sum(history) / len(history)
        variance = sum([((x - mean) ** 2) for x in history]) / len(history)
        std_dev = variance ** 0.5
        if std_dev == 0: return "NEUTRAL"
        upper_band = mean + (2 * std_dev)
        lower_band = mean - (2 * std_dev)
        if price <= lower_band: return "OVERSOLD"
        elif price >= upper_band: return "OVERBOUGHT"
        return "NEUTRAL"

@dataclass
class TradeSignal:
    strategy: str
    action: str
    confidence: float
    metrics: Dict[str, Any]

class MockRedis:
    """Simulates Redis for Dry Run."""
    async def get_sales_history(self, title: str) -> List[float]:
        base_price = random.uniform(5.0, 50.0)
        return [base_price * (1 + random.uniform(-0.1, 0.1)) for _ in range(20)]

    async def get_wax_price(self, title: str) -> Decimal:
        if random.random() > 0.8:
            return Decimal(str(random.uniform(10.0, 100.0)))
        return Decimal("0")

class HybridEngine:
    """
    The brain of the operation.
    Orchestrates the pipeline: Scan -> Enrich -> Analyze -> Execute.
    """

    def __init__(
        self, 
        dmarket_api: DMarketAPI, 
        waxpeer_api: WaxpeerAPI,
        config: AppConfig = CONFIG
    ):
        self.dm = dmarket_api
        self.wp = waxpeer_api
        self.cfg = config
        self.fees = LiquidityAdjustedFee()
        self.redis = MockRedis() # Injected Mock
        self.blacklist = BlacklistManager() 
        
        # Load Thresholds from Config
        self.MIN_GRIND_ROI = self.cfg.trading.MIN_GRIND_ROI
        self.MIN_GEM_ROI = self.cfg.trading.MIN_GEM_ROI
        self.MIN_LIQUIDITY_GRIND = self.cfg.trading.MIN_LIQUIDITY_GRIND
        self.MIN_LIQUIDITY_GEM = self.cfg.trading.MIN_LIQUIDITY_GEM

    async def scan_market(self, games: List[str] = None) -> None:
        """Main loop: Fetch items -> Process Batch for multiple games."""
        
        # Default to all configured games if None
        if not games:
            games = list(self.cfg.GAMES.keys())

        # Budget Check (Hardcoded safety for now, fetch real in prod)
        current_balance = Decimal("45.50") 
        max_spend = current_balance * self.cfg.trading.BALANCE_BUFFER
        logger.info(f"Budget: ${current_balance} (Max Item Price: ${max_spend:.2f})")

        for game_key in games:
            game_params = self.cfg.GAMES.get(game_key)
            if not game_params:
                logger.warning(f"Skipping unknown game: {game_key}")
                continue
                
            logger.info(f"--- Starting scan for {game_params.friendly_name} ({game_key}) ---")
            
            try:
                # Use Real DMarket API logic (Removed Mock fallback)
                items_response = await self.dm.get_market_items(
                    game=game_key,
                    limit=50,
                    price_from=1.00,
                    price_to=float(max_spend),
                    currency="USD",
                    sort="price"
                )
                market_objects = items_response.get("objects", [])
                logger.info(f"Fetched {len(market_objects)} items for {game_key}.")

                if not market_objects:
                    logger.warning(f"No items found for {game_key}.")
                    continue

                await self._process_batch(market_objects, game_key)

            except Exception as e:
                logger.error(f"Scan failed for {game_key}: {e}")

    async def _process_batch(self, items: List[Dict], game: str):
        tasks = []
        for item in items:
            tasks.append(self._analyze_item(item, game))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for res in results:
            if isinstance(res, TradeSignal):
                await self._execute_signal(res)
            elif isinstance(res, Exception):
                logger.error(f"Item analysis error: {res}")

    async def _analyze_item(self, item: Dict, game: str) -> Optional[TradeSignal]:
        title = item.get("title")
        
        # --- BLACKLIST CHECK ---
        should_skip, reason = self.blacklist.should_skip_item(item)
        if should_skip:
            return None

        price_dm_cents = int(item.get("price", {}).get("USD", 0))
        price_dm = Decimal(price_dm_cents) / 100
        
        if price_dm <= 0: return None

        # --- ENRICHMENT PHASE ---
        history_prices = await self.redis.get_sales_history(title)
        volume_7d = random.randint(10, 60) # Simulated Volume
        wax_price = await self.redis.get_wax_price(title)
        
        # --- ANALYSIS PHASE ---
        liquidity_score = LiquidityAnalyzer.calculate_score(volume_7d, 5)
        volatility_signal = VolatilityMetrics.get_bollinger_position(float(price_dm), history_prices)

        # --- STRATEGY ROUTING ---
        # 1. GRIND STRATEGY
        if liquidity_score >= self.MIN_LIQUIDITY_GRIND:
            suggested_cents = item.get("suggestedPrice", {}).get("USD")
            if not suggested_cents:
                 suggested_cents = price_dm_cents * 1.1 
            
            suggested = Decimal(str(suggested_cents)) / 100
            
            if random.random() > 0.5: volatility_signal = "OVERSOLD"

            if volatility_signal == "OVERSOLD":
                profit_calc = self.fees.calculate_grind_profit(price_dm, suggested)
                if profit_calc["roi_percent"] >= (self.MIN_GRIND_ROI * 100):
                    return TradeSignal(
                        strategy="GRIND",
                        action="BUY_RELIST",
                        confidence=0.9,
                        metrics={
                            "item": title,
                            "buy": float(price_dm),
                            "target": float(suggested),
                            "profit": profit_calc
                        }
                    )

        # 2. GEM STRATEGY
        if wax_price > 0 and liquidity_score >= self.MIN_LIQUIDITY_GEM:
            profit_calc = self.fees.calculate_gem_profit(
                price_dm, 
                wax_price, 
                hold_days=self.cfg.fees.STEAM_HOLD_DAYS
            )
            if profit_calc["roi_percent"] >= (self.MIN_GEM_ROI * 100):
                return TradeSignal(
                    strategy="GEM",
                    action="BUY_WITHDRAW",
                    confidence=0.85,
                    metrics={
                        "item": title,
                        "buy": float(price_dm),
                        "wax_target": float(wax_price),
                        "profit": profit_calc,
                        "hold_days": self.cfg.fees.STEAM_HOLD_DAYS
                    }
                )
        return None

    async def _execute_signal(self, signal: TradeSignal):
        m = signal.metrics
        p = m['profit']
        log_msg = (
            f"\n[CORE ENGINE] SIGNAL: {signal.strategy} ({signal.confidence*100:.0f}%)\n"
            f"Item: {m['item']}\n"
            f"Buy: ${m['buy']} -> Sell: ${m.get('target') or m.get('wax_target')}\n"
            f"Net Profit: ${p['net_profit']} (ROI {p['roi_percent']}%)"
        )
        if signal.strategy == "GEM":
            log_msg += f"\nWarning: Requires {m['hold_days']}d hold (OppCost: -${p['opportunity_cost']})"
        print(log_msg)

if __name__ == "__main__":
    # Test Block
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    # Simple logging setup for standalone run
    logging.basicConfig(level=logging.INFO)
    
    pub = os.getenv("DMARKET_PUBLIC_KEY")
    sec = os.getenv("DMARKET_SECRET_KEY")
    wax = os.getenv("WAXPEER_API_KEY", "test")
    
    dm_api = DMarketAPI(public_key=pub, secret_key=sec) if pub else DMarketAPI(public_key="test", secret_key="test")
    wp_api = WaxpeerAPI(api_key=wax)
    
    engine = HybridEngine(dm_api, wp_api)
    print("Starting Core Engine Dry Run...")
    asyncio.run(engine.scan_market()) # All games
