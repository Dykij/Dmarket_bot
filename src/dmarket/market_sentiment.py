"""
Market Sentiment Analyzer Module.

Analyzes overall market health and detects:
- Market crashes (panic sell protection)
- Volume anomalies (X5 hunt opportunities)
- Price velocity (speed of price changes)
- Steam sale periods (dip buying opportunities)

This module helps the bot adapt to market conditions automatically.
"""

import asyncio
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class MarketState(Enum):
    """Current market state."""

    STABLE = "stable"
    VOLATILE = "volatile"
    CRASH = "crash"
    RECOVERY = "recovery"
    BULL_RUN = "bull_run"
    SALE_PERIOD = "sale_period"


@dataclass
class PriceSnapshot:
    """Price snapshot for an indicator item."""

    item_name: str
    price: float
    volume: int
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class MarketHealth:
    """Overall market health metrics."""

    state: MarketState
    price_velocity: float  # % change per hour
    volume_change: float  # Volume vs average
    confidence: float  # 0-100 confidence score
    indicators_checked: int
    last_updated: datetime = field(default_factory=datetime.now)

    @property
    def is_safe_to_buy(self) -> bool:
        """Check if market is safe for normal buying."""
        return self.state in {
            MarketState.STABLE,
            MarketState.RECOVERY,
            MarketState.BULL_RUN,
        }

    @property
    def is_crash(self) -> bool:
        """Check if market is in crash state."""
        return self.state == MarketState.CRASH

    @property
    def is_opportunity(self) -> bool:
        """Check if there's a buying opportunity (dip or recovery)."""
        return self.state in {MarketState.SALE_PERIOD, MarketState.RECOVERY}


@dataclass
class X5Opportunity:
    """Potential high-growth item opportunity."""

    item_name: str
    game: str
    current_price: float
    avg_price_7d: float
    volume_spike: float  # Multiplier vs normal volume
    price_drop_percent: float
    confidence_score: float  # 0-100
    reason: str
    discovered_at: datetime = field(default_factory=datetime.now)


class MarketSentimentAnalyzer:
    """
    Analyzes market sentiment and provides trading signals.

    Features:
    - Tracks indicator items (cases, keys) to gauge market health
    - Detects panic sells and market crashes
    - Finds X5 opportunities (volume spikes, price anomalies)
    - Adapts trading strategy based on market conditions
    """

    # Default market indicators (most liquid items)
    # Updated 2026: Added new CS2 cases and high-volume items
    DEFAULT_INDICATORS = [
        # CS2 Cases (high liquidity)
        "Fracture Case",
        "Recoil Case",
        "Dreams & Nightmares Case",
        "Revolution Case",
        "Kilowatt Case",
        "Gallery Case",  # New 2025
        "Prisma 2 Case",
        # Keys (stable price reference)
        "Mann Co. Supply Crate Key",
        # High-value reference items
        "Operation Bravo Case",
        "Chroma Case",
    ]

    # CS2 Major sticker indicators (for tournament periods)
    STICKER_INDICATORS = [
        "Sticker Capsule",
        "Legends (Holo/Foil)",
        "Challengers (Holo/Foil)",
        "Contenders (Holo/Foil)",
    ]

    # Steam sale periods (approximate dates, UTC)
    STEAM_SALE_PERIODS = [
        # Summer Sale: Late June
        (6, 20, 7, 10),  # (start_month, start_day, end_month, end_day)
        # Winter Sale: Late December
        (12, 20, 1, 5),
        # Autumn Sale: Late November
        (11, 20, 11, 30),
        # Spring Sale: March
        (3, 15, 3, 25),
        # Lunar New Year Sale: February
        (2, 8, 2, 15),
        # Halloween Sale: Late October
        (10, 26, 11, 1),
    ]

    # Volatility thresholds for market state detection
    VOLATILITY_THRESHOLDS = {
        "stable": 0.02,  # < 2% change = stable
        "volatile": 0.05,  # 2-5% change = volatile
        "crash": -0.10,  # > -10% = crash
        "bull_run": 0.10,  # > +10% = bull run
        "recovery": 0.03,  # +3% after crash = recovery
    }

    def __init__(
        self,
        api_client: Any,
        config: dict | None = None,
        indicators: list[str] | None = None,
    ):
        """
        Initialize Market Sentiment Analyzer.

        Args:
            api_client: DMarket API client for fetching prices
            config: Configuration dictionary
            indicators: List of indicator item names to track
        """
        self.api_client = api_client
        self.config = config or {}
        self.indicators = indicators or self.DEFAULT_INDICATORS

        # Price history for each indicator (last 24 hours)
        self.price_history: dict[str, deque[PriceSnapshot]] = {
            item: deque(maxlen=96)  # 15-min intervals for 24h
            for item in self.indicators
        }

        # Current market state
        self.current_health: MarketHealth | None = None
        self.x5_opportunities: list[X5Opportunity] = []

        # Configuration
        self.panic_threshold = self.config.get("panic_sell_threshold", -0.07)  # -7%
        self.high_risk_hunt = self.config.get("high_risk_hunt", True)
        self.speculative_budget_pct = self.config.get("speculative_budget_pct", 0.15)
        self.check_interval = self.config.get("check_interval_minutes", 15)

        # State tracking
        self._running = False
        self._last_check: datetime | None = None

        logger.info(
            "market_sentiment_initialized",
            indicators=len(self.indicators),
            panic_threshold=self.panic_threshold,
            high_risk_hunt=self.high_risk_hunt,
        )

    async def start(self) -> None:
        """Start background market monitoring."""
        self._running = True
        logger.info("market_sentiment_monitoring_started")

        while self._running:
            try:
                await self.update_market_health()
                if self.high_risk_hunt:
                    await self.scan_for_x5_opportunities()
            except Exception as e:
                logger.exception("market_sentiment_update_error", error=str(e))

            await asyncio.sleep(self.check_interval * 60)

    async def stop(self) -> None:
        """Stop market monitoring."""
        self._running = False
        logger.info("market_sentiment_monitoring_stopped")

    async def update_market_health(self) -> MarketHealth:
        """
        Update market health by checking indicator prices.

        Returns:
            MarketHealth object with current market state
        """
        price_changes = []
        volume_changes = []
        indicators_checked = 0

        for item_name in self.indicators:
            try:
                # Fetch current price
                current_data = await self._fetch_item_price(item_name)
                if not current_data:
                    continue

                # Record snapshot
                snapshot = PriceSnapshot(
                    item_name=item_name,
                    price=current_data["price"],
                    volume=current_data.get("volume", 0),
                )
                self.price_history[item_name].append(snapshot)
                indicators_checked += 1

                # Calculate change vs 1 hour ago
                hour_ago = datetime.now() - timedelta(hours=1)
                old_snapshots = [
                    s for s in self.price_history[item_name] if s.timestamp <= hour_ago
                ]

                if old_snapshots:
                    old_price = old_snapshots[-1].price
                    if old_price > 0:
                        change = (snapshot.price - old_price) / old_price
                        price_changes.append(change)

                    old_volume = old_snapshots[-1].volume
                    if old_volume > 0:
                        vol_change = snapshot.volume / old_volume
                        volume_changes.append(vol_change)

            except Exception as e:
                logger.warning("indicator_fetch_error", item=item_name, error=str(e))

        # Calculate aggregate metrics
        avg_price_change = (
            sum(price_changes) / len(price_changes) if price_changes else 0
        )
        avg_volume_change = (
            sum(volume_changes) / len(volume_changes) if volume_changes else 1.0
        )

        # Determine market state
        state = self._determine_market_state(avg_price_change, avg_volume_change)

        # Calculate confidence (based on how many indicators we checked)
        confidence = (
            (indicators_checked / len(self.indicators)) * 100 if self.indicators else 0
        )

        self.current_health = MarketHealth(
            state=state,
            price_velocity=avg_price_change * 100,  # Convert to percentage
            volume_change=avg_volume_change,
            confidence=confidence,
            indicators_checked=indicators_checked,
        )

        self._last_check = datetime.now()

        logger.info(
            "market_health_updated",
            state=state.value,
            price_velocity=f"{self.current_health.price_velocity:.2f}%",
            volume_change=f"{avg_volume_change:.2f}x",
            confidence=f"{confidence:.0f}%",
        )

        return self.current_health

    def _determine_market_state(
        self, price_change: float, volume_change: float
    ) -> MarketState:
        """
        Determine market state based on price and volume changes.

        Args:
            price_change: Price change ratio (-0.1 = -10%)
            volume_change: Volume multiplier (2.0 = 2x normal)

        Returns:
            MarketState enum value
        """
        # Check if we're in a Steam sale period
        if self._is_steam_sale_period():
            return MarketState.SALE_PERIOD

        # Crash: Price drops significantly with high volume (panic selling)
        if price_change <= self.panic_threshold:
            return MarketState.CRASH

        # Bull run: Price increases with volume
        if price_change >= 0.05 and volume_change >= 1.5:
            return MarketState.BULL_RUN

        # Recovery: Price increases after being low
        if 0.02 <= price_change < 0.05:
            return MarketState.RECOVERY

        # Volatile: High volume but price unstable
        if volume_change >= 2.0 and abs(price_change) < 0.03:
            return MarketState.VOLATILE

        # Default: Stable
        return MarketState.STABLE

    def _is_steam_sale_period(self) -> bool:
        """Check if current date is within a Steam sale period."""
        now = datetime.now()

        for start_month, start_day, end_month, end_day in self.STEAM_SALE_PERIODS:
            # Handle year wrap (Winter sale: Dec 20 - Jan 5)
            if start_month > end_month:
                # Check if we're in December portion
                if now.month == start_month and now.day >= start_day:
                    return True
                # Check if we're in January portion
                if now.month == end_month and now.day <= end_day:
                    return True
            else:
                # Normal date range within same year
                start_date = datetime(now.year, start_month, start_day, tzinfo=UTC)
                end_date = datetime(now.year, end_month, end_day, tzinfo=UTC)
                if start_date <= now <= end_date:
                    return True

        return False

    async def scan_for_x5_opportunities(self) -> list[X5Opportunity]:
        """
        Scan market for potential X5 growth opportunities.

        Looks for:
        - Volume spikes (10x+ normal volume)
        - Price dips on high-liquidity items
        - Limited collection items

        Returns:
            List of X5Opportunity objects
        """
        opportunities = []

        # Get extended list of items to scan
        scan_items = await self._get_x5_scan_list()

        for item_info in scan_items:
            try:
                opportunity = await self._analyze_x5_potential(item_info)
                if opportunity and opportunity.confidence_score >= 60:
                    opportunities.append(opportunity)
                    logger.info(
                        "x5_opportunity_found",
                        item=opportunity.item_name,
                        volume_spike=f"{opportunity.volume_spike:.1f}x",
                        confidence=f"{opportunity.confidence_score:.0f}%",
                        reason=opportunity.reason,
                    )
            except Exception as e:
                logger.debug(
                    "x5_analysis_error", item=item_info.get("name"), error=str(e)
                )

        # Sort by confidence and keep top 10
        opportunities.sort(key=lambda x: x.confidence_score, reverse=True)
        self.x5_opportunities = opportunities[:10]

        return self.x5_opportunities

    async def _get_x5_scan_list(self) -> list[dict]:
        """Get list of items to scan for X5 opportunities."""
        # This would typically fetch from trending items or specific categories
        # For now, return indicator items as a base
        return [{"name": item, "game": "csgo"} for item in self.indicators]

    async def _analyze_x5_potential(self, item_info: dict) -> X5Opportunity | None:
        """Analyze an item for X5 growth potential."""
        item_name = item_info.get("name", "")
        game = item_info.get("game", "csgo")

        # Fetch current and historical data
        current_data = await self._fetch_item_price(item_name)
        if not current_data:
            return None

        current_price = current_data.get("price", 0)
        current_volume = current_data.get("volume", 0)
        avg_price_7d = current_data.get("avg_price_7d", current_price)
        avg_volume = current_data.get("avg_volume", current_volume)

        if current_price <= 0 or avg_volume <= 0:
            return None

        # Calculate metrics
        volume_spike = current_volume / avg_volume if avg_volume > 0 else 1.0
        price_drop = (
            ((avg_price_7d - current_price) / avg_price_7d) * 100
            if avg_price_7d > 0
            else 0
        )

        # Score the opportunity
        confidence = 0
        reasons = []

        # Volume spike (big players accumulating)
        if volume_spike >= 10:
            confidence += 40
            reasons.append(f"Volume spike {volume_spike:.0f}x")
        elif volume_spike >= 5:
            confidence += 25
            reasons.append(f"Volume spike {volume_spike:.0f}x")
        elif volume_spike >= 2:
            confidence += 10

        # Price dip (potential recovery)
        if price_drop >= 30:
            confidence += 30
            reasons.append(f"Price dip -{price_drop:.0f}%")
        elif price_drop >= 20:
            confidence += 20
            reasons.append(f"Price dip -{price_drop:.0f}%")
        elif price_drop >= 10:
            confidence += 10

        # Limited collection bonus
        if self._is_limited_collection(item_name):
            confidence += 20
            reasons.append("Limited collection")

        if confidence < 30:
            return None

        return X5Opportunity(
            item_name=item_name,
            game=game,
            current_price=current_price,
            avg_price_7d=avg_price_7d,
            volume_spike=volume_spike,
            price_drop_percent=price_drop,
            confidence_score=min(confidence, 100),
            reason=", ".join(reasons) if reasons else "Market analysis",
        )

    def _is_limited_collection(self, item_name: str) -> bool:
        """Check if item is from a limited/discontinued collection."""
        limited_keywords = [
            "Operation",
            "Souvenir Package",
            "Cologne",
            "Katowice",
            "Major",
            "2014",
            "2015",
            "2016",
            "2017",
            "2018",
        ]
        return any(kw.lower() in item_name.lower() for kw in limited_keywords)

    async def _fetch_item_price(self, item_name: str) -> dict | None:
        """
        Fetch current price and volume for an item.

        Returns dict with: price, volume, avg_price_7d, avg_volume
        """
        try:
            # Use API client to fetch market data
            if hasattr(self.api_client, "get_market_items"):
                result = await self.api_client.get_market_items(
                    game="csgo",
                    title=item_name,
                    limit=1,
                )

                if result and "objects" in result and result["objects"]:
                    item = result["objects"][0]
                    price_str = item.get("price", {}).get("USD", "0")
                    # DMarket returns prices in cents
                    price = (
                        float(price_str) / 100
                        if isinstance(price_str, str)
                        else price_str / 100
                    )

                    return {
                        "price": price,
                        "volume": item.get("salesCount", 0),
                        "avg_price_7d": price,  # Would need sales history for accurate 7d avg
                        "avg_volume": item.get("salesCount", 0) // 7,
                    }
        except Exception as e:
            logger.debug("price_fetch_error", item=item_name, error=str(e))

        return None

    def get_adjusted_limits(self, base_limits: dict, balance: float) -> dict:
        """
        Adjust trading limits based on current market state.

        Args:
            base_limits: Base trading limits from money manager
            balance: Current account balance

        Returns:
            Adjusted limits dict
        """
        if not self.current_health:
            return base_limits

        adjusted = base_limits.copy()

        # Crash mode: Very conservative, only extreme deals
        if self.current_health.is_crash:
            adjusted["target_roi"] = max(base_limits.get("target_roi", 15), 40)
            adjusted["max_price"] = base_limits.get("max_price", 10) * 0.5
            adjusted["pause_normal_buying"] = True
            logger.warning("crash_mode_limits_applied", new_roi=adjusted["target_roi"])

        # Sale period: More aggressive buying (dip buying)
        elif self.current_health.state == MarketState.SALE_PERIOD:
            adjusted["target_roi"] = max(base_limits.get("target_roi", 15) - 5, 8)
            adjusted["max_price"] = base_limits.get("max_price", 10) * 1.3
            adjusted["dip_buying_active"] = True
            logger.info("sale_period_limits_applied", new_roi=adjusted["target_roi"])

        # Bull run: Tighter margins (prices rising)
        elif self.current_health.state == MarketState.BULL_RUN:
            adjusted["target_roi"] = base_limits.get("target_roi", 15) + 3
            adjusted["max_price"] = base_limits.get("max_price", 10) * 0.8

        # Allocate speculative budget for X5 hunting
        if self.high_risk_hunt and self.current_health.is_safe_to_buy:
            adjusted["speculative_budget"] = balance * self.speculative_budget_pct
        else:
            adjusted["speculative_budget"] = 0

        return adjusted

    def get_status_message(self) -> str:
        """Get human-readable market status for Telegram."""
        if not self.current_health:
            return "📊 Рынок: Данные загружаются..."

        state_emoji = {
            MarketState.STABLE: "✅",
            MarketState.VOLATILE: "⚡",
            MarketState.CRASH: "🔴",
            MarketState.RECOVERY: "📈",
            MarketState.BULL_RUN: "🚀",
            MarketState.SALE_PERIOD: "🎉",
        }

        state_text = {
            MarketState.STABLE: "Стабилен",
            MarketState.VOLATILE: "Волатилен",
            MarketState.CRASH: "ПАНИКА - Защита ВКЛ",
            MarketState.RECOVERY: "Восстановление",
            MarketState.BULL_RUN: "Рост",
            MarketState.SALE_PERIOD: "Распродажа Steam!",
        }

        emoji = state_emoji.get(self.current_health.state, "❓")
        text = state_text.get(self.current_health.state, "Неизвестно")

        msg = f"{emoji} Рынок: {text}\n"
        msg += f"   Скорость: {self.current_health.price_velocity:+.1f}%/час\n"
        msg += f"   Объемы: {self.current_health.volume_change:.1f}x\n"

        if self.x5_opportunities:
            msg += f"   🔥 X5 возможностей: {len(self.x5_opportunities)}"

        return msg

    def get_x5_opportunities_message(self) -> str:
        """Get formatted X5 opportunities for Telegram."""
        if not self.x5_opportunities:
            return "🔍 X5 возможностей пока не найдено.\nБот сканирует рынок каждые 15 минут."

        msg = "🔥 *Потенциальные X5 возможности:*\n\n"

        for i, opp in enumerate(self.x5_opportunities[:5], 1):
            msg += f"{i}. *{opp.item_name}*\n"
            msg += f"   💰 ${opp.current_price:.2f} (было ${opp.avg_price_7d:.2f})\n"
            msg += f"   📊 Объем: {opp.volume_spike:.0f}x\n"
            msg += f"   🎯 Уверенность: {opp.confidence_score:.0f}%\n"
            msg += f"   📝 {opp.reason}\n\n"

        return msg
