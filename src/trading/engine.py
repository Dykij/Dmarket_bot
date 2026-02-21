"""
Hybrid Trading Engine.

Integrates:
- Liquidity Analysis (Volume, Velocity)
- Volatility Metrics (Bollinger Bands)
- Fee Optimization (Opportunity Cost)
- Parallel Execution (Grind & Gems)
"""

import asyncio
from decimal import Decimal
from typing import Any, Dict, List, Optional
from dataclasses import dataclass

from src.dmarket.dmarket_api import DMarketAPI
from src.waxpeer.waxpeer_api import WaxpeerAPI
from src.trading.fees import LiquidityAdjustedFee, FeeConfig
from src.utils.logger import logger

# --- Simulated Imports (Adapters for found modules) ---
# In a real scenario, these would be direct imports from src.dmarket...
# We use adapters to ensure compatibility if original modules are messy.


class LiquidityAnalyzer:
    """Adapter for src.dmarket.liquidity_analyzer."""

    @staticmethod
    def calculate_score(volume_7d: int, recent_sales: int) -> float:
        """
        0-100 score based on sales frequency.
        > 50 = Liquid (Good for Grind)
        > 20 = Semi-Liquid (Good for Gems)
        """
        if volume_7d == 0:
            return 0.0
        # Simple heuristic: 1 sale/day = 10 points. Cap at 100.
        score = (volume_7d / 7) * 10
        return min(score, 100.0)


class VolatilityMetrics:
    """Adapter for src.analytics.price_analytics (Bollinger Bands)."""

    @staticmethod
    def get_bollinger_position(price: float, history: List[float]) -> str:
        """
        Returns: 'OVERSOLD' (Buy signal), 'OVERBOUGHT' (Sell signal), or 'NEUTRAL'.
        """
        if not history or len(history) < 3:
            return "NEUTRAL"

        mean = sum(history) / len(history)
        variance = sum([((x - mean) ** 2) for x in history]) / len(history)
        std_dev = variance**0.5

        if std_dev == 0:
            return "NEUTRAL"

        upper_band = mean + (2 * std_dev)
        lower_band = mean - (2 * std_dev)

        if price <= lower_band:
            return "OVERSOLD"  # Price is cheap relative to volatility
        elif price >= upper_band:
            return "OVERBOUGHT"  # Price is expensive
        return "NEUTRAL"


@dataclass
class TradeSignal:
    strategy: str  # 'GRIND' or 'GEM'
    action: str  # 'BUY_RELIST' or 'BUY_WITHDRAW'
    confidence: float  # 0.0 - 1.0
    metrics: Dict[str, Any]


class HybridEngine:
    """
    The brain of the operation.
    Orchestrates the pipeline: Scan -> Enrich -> Analyze -> Execute.
    """

    def __init__(
        self,
        dmarket_api: DMarketAPI,
        waxpeer_api: WaxpeerAPI,
        fee_config: Optional[FeeConfig] = None,
    ):
        self.dm = dmarket_api
        self.wp = waxpeer_api
        self.fees = LiquidityAdjustedFee(config=fee_config)

        # Strategies Thresholds
        self.MIN_GRIND_ROI = Decimal("0.03")  # 3% pure profit
        self.MIN_GEM_ROI = Decimal("0.12")  # 12% (after 7d hold cost)
        self.MIN_LIQUIDITY_GRIND = 50.0  # High liquidity needed for quick flips
        self.MIN_LIQUIDITY_GEM = 20.0  # Lower liquidity ok for high margin export

    async def scan_market(self, game: str = "csgo") -> None:
        """Main loop: Fetch items -> Process Batch."""
        logger.info(f"Starting hybrid scan for {game}...")

        # 1. Fetch DMarket Items (Batch)
        # In real impl, we'd use filters from StrategyFactory
        try:
            items = await self.dm.list_market_items(
                game_id=game,
                limit=100,
                price_from=100,  # $1.00
                price_to=50000,  # $500.00
            )

            market_objects = items.get("objects", [])
            if not market_objects:
                logger.warning("No items found.")
                return

            await self._process_batch(market_objects, game)

        except Exception as e:
            logger.error(f"Scan failed: {e}")

    async def _process_batch(self, items: List[Dict], game: str):
        """Pipeline execution."""

        tasks = []
        for item in items:
            tasks.append(self._analyze_item(item, game))

        # Execute analysis in parallel
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for res in results:
            if isinstance(res, TradeSignal):
                await self._execute_signal(res)
            elif isinstance(res, Exception):
                logger.error(f"Item analysis error: {res}")

    async def _analyze_item(self, item: Dict, game: str) -> Optional[TradeSignal]:
        """Deep analysis of a single item using Strategy Routing."""
        title = item.get("title")
        price_dm_cents = int(item.get("price", {}).get("USD", 0))
        price_dm = Decimal(price_dm_cents) / 100

        if price_dm <= 0:
            return None

        # --- ENRICHMENT PHASE ---
        # 1. Get History (for Volatility & Liquidity)
        # Mocking history fetch for now (would be Redis/API call)
        # In real code: history = await self.redis.get_sales_history(title)
        history_prices = []  # Placeholder
        volume_7d = 20  # Placeholder mock

        # 2. Get Waxpeer Price (for Gems)
        # Mocking Waxpeer fetch
        # In real code: wax_price = await self.redis.get_wax_price(title)
        wax_price = Decimal("0")  # Placeholder

        # --- ANALYSIS PHASE ---

        # A. Liquidity Check
        liquidity_score = LiquidityAnalyzer.calculate_score(volume_7d, 5)

        # B. Volatility Check
        volatility_signal = VolatilityMetrics.get_bollinger_position(
            float(price_dm), history_prices
        )

        # --- STRATEGY ROUTING ---

        # 1. GRIND STRATEGY (High Velocity, Internal Flip)
        # Rules: High Liquidity + Oversold (Cheap) + Positive ROI
        if liquidity_score >= self.MIN_LIQUIDITY_GRIND:
            # Check suggested price (DMarket's estimate)
            suggested = Decimal(str(item.get("suggestedPrice", {}).get("USD", 0))) / 100

            # Smart Check: If Volatility says "OVERSOLD", we trust it more
            if volatility_signal == "OVERSOLD":
                # If oversold, we expect price to revert to mean
                # Target = Mean Price (approximated by suggested)
                profit_calc = self.fees.calculate_grind_profit(price_dm, suggested)

                if profit_calc["roi_percent"] >= (self.MIN_GRIND_ROI * 100):
                    return TradeSignal(
                        strategy="GRIND",
                        action="BUY_RELIST",
                        confidence=0.9 if volatility_signal == "OVERSOLD" else 0.7,
                        metrics={
                            "item": title,
                            "buy": float(price_dm),
                            "target": float(suggested),
                            "profit": profit_calc,
                        },
                    )

        # 2. GEM STRATEGY (Cross-Market, 7d Hold)
        # Rules: Good Margin + Acceptable Liquidity + Covers Opportunity Cost
        if wax_price > 0 and liquidity_score >= self.MIN_LIQUIDITY_GEM:
            profit_calc = self.fees.calculate_gem_profit(
                price_dm, wax_price, hold_days=self.fees.cfg.STEAM_HOLD_DAYS
            )

            if profit_calc["roi_percent"] >= (self.MIN_GEM_ROI * 100):
                # Gem Found!
                return TradeSignal(
                    strategy="GEM",
                    action="BUY_WITHDRAW",
                    confidence=0.85,
                    metrics={
                        "item": title,
                        "buy": float(price_dm),
                        "wax_target": float(wax_price),
                        "profit": profit_calc,
                        "hold_days": self.fees.cfg.STEAM_HOLD_DAYS,
                    },
                )

        return None

    async def _execute_signal(self, signal: TradeSignal):
        """Execute the trade."""
        m = signal.metrics
        p = m["profit"]

        log_msg = (
            f"🚀 SIGNAL: {signal.strategy} ({signal.confidence*100:.0f}%)\n"
            f"Item: {m['item']}\n"
            f"Buy: ${m['buy']} -> Sell: ${m.get('target') or m.get('wax_target')}\n"
            f"Net Profit: ${p['net_profit']} (ROI {p['roi_percent']}%)"
        )

        if signal.strategy == "GEM":
            log_msg += f"\nWarning: Requires {m['hold_days']}d hold (OppCost: -${p['opportunity_cost']})"

        logger.info(log_msg)
        # Actual API call would go here:
        # await self.dm.buy_item(m['item_id'], m['buy'])
