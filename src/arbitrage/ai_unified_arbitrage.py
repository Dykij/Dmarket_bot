"""AI Unified Arbitrage System.

Автоматический арбитраж с использованием AI:
- DMarket внутренний арбитраж (покупка дешево -> продажа дорого)
- DMarket <-> Waxpeer кросс-платформенный арбитраж
- Проверка цен на Steam для лучших решений

Features:
- AI-оценка каждой возможности
- Автоматическое выполнение сделок (опционально)
- Rate limiting и защита от блокировок
- Real-time мониторинг и уведомления

Created: January 2026
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from telegram import Bot

    from src.dmarket.dmarket_api import DMarketAPI
    from src.ml.ai_coordinator import AICoordinator
    from src.waxpeer.waxpeer_api import WaxpeerAPI


logger = structlog.get_logger(__name__)


class ArbitrageType(StrEnum):
    """Type of arbitrage opportunity."""

    DMARKET_INTERNAL = "dmarket_internal"  # Buy low, sell high on DMarket
    DMARKET_TO_WAXPEER = "dmarket_to_waxpeer"  # Buy DMarket, sell Waxpeer
    WAXPEER_TO_DMARKET = "waxpeer_to_dmarket"  # Buy Waxpeer, sell DMarket
    STEAM_UNDERPRICED = "steam_underpriced"  # Steam price significantly higher


class Platform(StrEnum):
    """Trading platforms."""

    DMARKET = "dmarket"
    WAXPEER = "waxpeer"
    STEAM = "steam"


@dataclass
class PlatformPrice:
    """Price on a specific platform."""

    platform: Platform
    price_usd: Decimal
    commission_percent: Decimal = Decimal(0)
    available: bool = True
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def net_price(self) -> Decimal:
        """Price after platform commission."""
        return self.price_usd * (1 - self.commission_percent / 100)


@dataclass
class ArbitrageOpportunity:
    """An arbitrage opportunity."""

    item_name: str
    item_id: str
    game: str
    arb_type: ArbitrageType

    # Prices
    buy_platform: Platform
    buy_price: Decimal
    sell_platform: Platform
    sell_price: Decimal

    # Profit calculation
    gross_profit: Decimal
    net_profit: Decimal  # After fees
    roi_percent: float

    # AI evaluation
    ai_confidence: float = 0.0
    ai_recommendation: str = "hold"
    risk_score: float = 0.5

    # Metadata
    steam_price: Decimal | None = None
    liquidity_score: float = 0.5
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    executed: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_name": self.item_name,
            "item_id": self.item_id,
            "game": self.game,
            "arb_type": self.arb_type.value,
            "buy_platform": self.buy_platform.value,
            "buy_price": float(self.buy_price),
            "sell_platform": self.sell_platform.value,
            "sell_price": float(self.sell_price),
            "gross_profit": float(self.gross_profit),
            "net_profit": float(self.net_profit),
            "roi_percent": round(self.roi_percent, 2),
            "ai_confidence": round(self.ai_confidence, 3),
            "ai_recommendation": self.ai_recommendation,
            "risk_score": round(self.risk_score, 2),
            "steam_price": float(self.steam_price) if self.steam_price else None,
            "liquidity_score": round(self.liquidity_score, 2),
        }


@dataclass
class ArbitrageConfig:
    """Configuration for arbitrage system."""

    # Minimum thresholds
    min_roi_percent: float = 5.0
    min_profit_usd: float = 0.50
    min_ai_confidence: float = 0.70

    # Price limits
    max_buy_price_usd: float = 100.0
    min_buy_price_usd: float = 0.50

    # Risk management
    max_risk_score: float = 0.70
    min_liquidity_score: float = 0.30

    # Platform fees
    dmarket_buy_fee: Decimal = Decimal(0)  # No buy fee
    dmarket_sell_fee: Decimal = Decimal(7)  # 7% sell fee
    waxpeer_sell_fee: Decimal = Decimal(6)  # 6% sell fee

    # Rate limiting
    scan_interval_seconds: int = 60
    max_items_per_scan: int = 100

    # Execution
    auto_execute: bool = False  # Must be explicitly enabled
    dry_run: bool = True  # Safety default

    # Games to scan
    games: list[str] = field(default_factory=lambda: ["csgo", "dota2", "rust", "tf2"])


class AIUnifiedArbitrage:
    """AI-powered unified arbitrage system.

    Coordinates arbitrage across DMarket, Waxpeer, and Steam.
    Uses AI to evaluate opportunities and make trading decisions.

    Example:
        >>> arbitrage = AIUnifiedArbitrage(dmarket_api, waxpeer_api)
        >>> opportunities = await arbitrage.scan_all()
        >>> for opp in opportunities:
        ...     print(f"{opp.item_name}: {opp.roi_percent}% ROI")
    """

    def __init__(
        self,
        dmarket_api: DMarketAPI | None = None,
        waxpeer_api: WaxpeerAPI | None = None,
        ai_coordinator: AICoordinator | None = None,
        config: ArbitrageConfig | None = None,
    ) -> None:
        """Initialize arbitrage system.

        Args:
            dmarket_api: DMarket API client
            waxpeer_api: Waxpeer API client
            ai_coordinator: AI coordinator for decision making
            config: Arbitrage configuration
        """
        self.dmarket = dmarket_api
        self.waxpeer = waxpeer_api
        self.ai = ai_coordinator
        self.config = config or ArbitrageConfig()

        # State
        self._running = False
        self._task: asyncio.Task | None = None
        self._opportunities: list[ArbitrageOpportunity] = []

        # Statistics
        self._stats = {
            "scans_completed": 0,
            "opportunities_found": 0,
            "opportunities_executed": 0,
            "total_profit_usd": Decimal(0),
            "start_time": None,
        }

        # Telegram notifications
        self._telegram_bot: Bot | None = None
        self._notify_chat_id: int | None = None

        # Steam price cache
        self._steam_cache: dict[str, tuple[Decimal, datetime]] = {}
        self._steam_cache_ttl = 300  # 5 minutes

        logger.info(
            "ai_unified_arbitrage_initialized",
            dmarket=bool(dmarket_api),
            waxpeer=bool(waxpeer_api),
            ai=bool(ai_coordinator),
            auto_execute=self.config.auto_execute,
            dry_run=self.config.dry_run,
        )

    def set_telegram(self, bot: Bot, chat_id: int) -> None:
        """Set Telegram bot for notifications."""
        self._telegram_bot = bot
        self._notify_chat_id = chat_id

    async def _notify(self, message: str) -> None:
        """Send notification via Telegram."""
        if self._telegram_bot and self._notify_chat_id:
            try:
                await self._telegram_bot.send_message(
                    chat_id=self._notify_chat_id,
                    text=message,
                    parse_mode="HTML",
                )
            except Exception as e:
                logger.warning("telegram_notify_failed", error=str(e))

    async def scan_dmarket_internal(self, game: str = "csgo") -> list[ArbitrageOpportunity]:
        """Scan DMarket for internal arbitrage opportunities.

        Finds items that can be bought and resold on DMarket with profit.
        """
        opportunities: list[ArbitrageOpportunity] = []

        if not self.dmarket:
            logger.warning("dmarket_api_not_configured")
            return opportunities

        try:
            # Get market items
            items = await self.dmarket.get_market_items(
                game=game,
                limit=self.config.max_items_per_scan,
                order_by="price",
                order_dir="asc",
            )

            for item in items.get("objects", []):
                opp = await self._evaluate_dmarket_internal(item)
                if opp and self._meets_criteria(opp):
                    opportunities.append(opp)

        except Exception as e:
            logger.error("dmarket_internal_scan_error", error=str(e))

        return opportunities

    async def _evaluate_dmarket_internal(self, item: dict[str, Any]) -> ArbitrageOpportunity | None:
        """Evaluate a DMarket item for internal arbitrage."""
        try:
            item_name = item.get("title", "")
            item_id = item.get("itemId", "")
            game = item.get("gameId", "csgo")

            # Extract prices
            price_data = item.get("price", {})
            if isinstance(price_data, dict):
                buy_price = Decimal(str(price_data.get("USD", 0))) / 100
            else:
                buy_price = Decimal(str(price_data)) / 100

            suggested = item.get("suggestedPrice", {})
            if isinstance(suggested, dict):
                suggested_price = Decimal(str(suggested.get("USD", 0))) / 100
            else:
                suggested_price = Decimal(str(suggested)) / 100 if suggested else buy_price

            if buy_price <= 0 or suggested_price <= 0:
                return None

            # Calculate profit
            sell_price = suggested_price
            sell_after_fee = sell_price * (1 - self.config.dmarket_sell_fee / 100)
            gross_profit = suggested_price - buy_price
            net_profit = sell_after_fee - buy_price

            if net_profit <= 0:
                return None

            roi = float((net_profit / buy_price) * 100) if buy_price > 0 else 0

            # AI evaluation
            ai_confidence = 0.5
            ai_recommendation = "hold"
            risk_score = 0.5

            if self.ai:
                try:
                    analysis = await self.ai.analyze_item(item)
                    ai_confidence = analysis.price_confidence
                    ai_recommendation = analysis.recommendation.value
                    risk_score = 0.3 if analysis.risk_level.value == "low" else 0.7
                except Exception as e:
                    logger.error(f"Error during AI analysis for {item_name}: {e}")

            return ArbitrageOpportunity(
                item_name=item_name,
                item_id=item_id,
                game=game,
                arb_type=ArbitrageType.DMARKET_INTERNAL,
                buy_platform=Platform.DMARKET,
                buy_price=buy_price,
                sell_platform=Platform.DMARKET,
                sell_price=sell_price,
                gross_profit=gross_profit,
                net_profit=net_profit,
                roi_percent=roi,
                ai_confidence=ai_confidence,
                ai_recommendation=ai_recommendation,
                risk_score=risk_score,
            )
        except Exception as e:
            logger.debug("evaluate_dmarket_internal_error", error=str(e))
            return None

    async def scan_cross_platform(self, game: str = "csgo") -> list[ArbitrageOpportunity]:
        """Scan for cross-platform arbitrage (DMarket <-> Waxpeer)."""
        opportunities: list[ArbitrageOpportunity] = []

        if not self.dmarket or not self.waxpeer:
            logger.warning("cross_platform_apis_not_configured")
            return opportunities

        try:
            # Get DMarket items
            dm_items = await self.dmarket.get_market_items(
                game=game,
                limit=self.config.max_items_per_scan,
                order_by="price",
                order_dir="asc",
            )

            # Get item names for Waxpeer lookup
            item_names = [item.get("title", "") for item in dm_items.get("objects", [])]

            if not item_names:
                return opportunities

            # Get Waxpeer prices for these items
            try:
                wp_prices = await self.waxpeer.get_items_list(item_names[:50])
                wp_price_map = {p.name: p.price for p in wp_prices if hasattr(p, "name")}
            except Exception as e:
                logger.warning("waxpeer_prices_error", error=str(e))
                wp_price_map = {}

            # Evaluate cross-platform opportunities
            for item in dm_items.get("objects", []):
                item_name = item.get("title", "")

                if item_name in wp_price_map:
                    opp = await self._evaluate_cross_platform(item, wp_price_map[item_name])
                    if opp and self._meets_criteria(opp):
                        opportunities.append(opp)

        except Exception as e:
            logger.error("cross_platform_scan_error", error=str(e))

        return opportunities

    async def _evaluate_cross_platform(
        self, dm_item: dict[str, Any], wp_price: Decimal
    ) -> ArbitrageOpportunity | None:
        """Evaluate cross-platform arbitrage opportunity."""
        try:
            item_name = dm_item.get("title", "")
            item_id = dm_item.get("itemId", "")
            game = dm_item.get("gameId", "csgo")

            # DMarket price
            price_data = dm_item.get("price", {})
            if isinstance(price_data, dict):
                dm_price = Decimal(str(price_data.get("USD", 0))) / 100
            else:
                dm_price = Decimal(str(price_data)) / 100

            if dm_price <= 0 or wp_price <= 0:
                return None

            # Determine direction - calculate prices after fees
            wp_after_fee = wp_price * (1 - self.config.waxpeer_sell_fee / 100)

            # DMarket -> Waxpeer
            profit_dm_to_wp = wp_after_fee - dm_price

            # Waxpeer -> DMarket
            wp_buy = wp_price  # Waxpeer buy price
            dm_sell_after_fee = dm_price * (1 - self.config.dmarket_sell_fee / 100)
            profit_wp_to_dm = dm_sell_after_fee - wp_buy

            # Choose better direction
            if profit_dm_to_wp > profit_wp_to_dm and profit_dm_to_wp > 0:
                arb_type = ArbitrageType.DMARKET_TO_WAXPEER
                buy_platform = Platform.DMARKET
                buy_price = dm_price
                sell_platform = Platform.WAXPEER
                sell_price = wp_price
                net_profit = profit_dm_to_wp
            elif profit_wp_to_dm > 0:
                arb_type = ArbitrageType.WAXPEER_TO_DMARKET
                buy_platform = Platform.WAXPEER
                buy_price = wp_price
                sell_platform = Platform.DMARKET
                sell_price = dm_price
                net_profit = profit_wp_to_dm
            else:
                return None

            gross_profit = sell_price - buy_price
            roi = float((net_profit / buy_price) * 100) if buy_price > 0 else 0

            # AI evaluation
            ai_confidence = 0.5
            if self.ai:
                try:
                    analysis = await self.ai.analyze_item(dm_item)
                    ai_confidence = analysis.price_confidence
                except Exception as e:
                    logger.error(f"Error during AI analysis for {item_name}: {e}")

            return ArbitrageOpportunity(
                item_name=item_name,
                item_id=item_id,
                game=game,
                arb_type=arb_type,
                buy_platform=buy_platform,
                buy_price=buy_price,
                sell_platform=sell_platform,
                sell_price=sell_price,
                gross_profit=gross_profit,
                net_profit=net_profit,
                roi_percent=roi,
                ai_confidence=ai_confidence,
            )
        except Exception as e:
            logger.debug("evaluate_cross_platform_error", error=str(e))
            return None

    async def get_steam_price(self, item_name: str) -> Decimal | None:
        """Get Steam market price for comparison.

        Uses caching to avoid rate limits.
        """
        # Check cache
        if item_name in self._steam_cache:
            price, cached_at = self._steam_cache[item_name]
            age = (datetime.now(UTC) - cached_at).total_seconds()
            if age < self._steam_cache_ttl:
                return price

        try:
            # Try to get Steam price via DMarket enhancer
            if self.dmarket:
                from src.dmarket.steam_arbitrage_enhancer import SteamArbitrageEnhancer

                enhancer = SteamArbitrageEnhancer()
                steam_data = await enhancer.get_steam_price(item_name)
                if steam_data and steam_data.get("price"):
                    price = Decimal(str(steam_data["price"]))
                    self._steam_cache[item_name] = (price, datetime.now(UTC))
                    return price
        except Exception as e:
            logger.debug("steam_price_error", item=item_name, error=str(e))

        return None

    async def scan_with_steam_comparison(self, game: str = "csgo") -> list[ArbitrageOpportunity]:
        """Scan opportunities and compare with Steam prices."""
        opportunities: list[ArbitrageOpportunity] = []

        if not self.dmarket:
            return opportunities

        try:
            # Get internal opportunities first
            internal_opps = await self.scan_dmarket_internal(game)

            # Enhance with Steam prices
            for opp in internal_opps:
                steam_price = await self.get_steam_price(opp.item_name)
                if steam_price:
                    opp.steam_price = steam_price

                    # Boost confidence if Steam price confirms value
                    if steam_price > opp.sell_price * Decimal("1.1"):
                        opp.ai_confidence = min(1.0, opp.ai_confidence + 0.15)
                        opp.arb_type = ArbitrageType.STEAM_UNDERPRICED

                opportunities.append(opp)

            # Add cross-platform opportunities
            cross_opps = await self.scan_cross_platform(game)
            for opp in cross_opps:
                steam_price = await self.get_steam_price(opp.item_name)
                if steam_price:
                    opp.steam_price = steam_price
                opportunities.append(opp)

        except Exception as e:
            logger.error("scan_with_steam_error", error=str(e))

        return opportunities

    def _meets_criteria(self, opp: ArbitrageOpportunity) -> bool:
        """Check if opportunity meets configured criteria."""
        if opp.roi_percent < self.config.min_roi_percent:
            return False
        if float(opp.net_profit) < self.config.min_profit_usd:
            return False
        if float(opp.buy_price) > self.config.max_buy_price_usd:
            return False
        if float(opp.buy_price) < self.config.min_buy_price_usd:
            return False
        if opp.ai_confidence < self.config.min_ai_confidence:
            return False
        if opp.risk_score > self.config.max_risk_score:
            return False
        return True

    async def scan_all(self, games: list[str] | None = None) -> list[ArbitrageOpportunity]:
        """Scan all configured games for opportunities."""
        games = games or self.config.games
        all_opportunities: list[ArbitrageOpportunity] = []

        for game in games:
            try:
                opps = await self.scan_with_steam_comparison(game)
                all_opportunities.extend(opps)
                await asyncio.sleep(1)  # Rate limiting between games
            except Exception as e:
                logger.error("scan_game_error", game=game, error=str(e))

        # Sort by ROI
        all_opportunities.sort(key=lambda x: x.roi_percent, reverse=True)

        self._opportunities = all_opportunities
        self._stats["scans_completed"] += 1
        self._stats["opportunities_found"] += len(all_opportunities)

        logger.info(
            "scan_completed",
            games=len(games),
            opportunities=len(all_opportunities),
        )

        return all_opportunities

    async def execute_opportunity(self, opp: ArbitrageOpportunity) -> dict[str, Any]:
        """Execute an arbitrage opportunity.

        Args:
            opp: The opportunity to execute

        Returns:
            Execution result
        """
        result = {
            "success": False,
            "opportunity": opp.to_dict(),
            "reason": "",
            "executed_at": datetime.now(UTC).isoformat(),
        }

        if self.config.dry_run:
            result["success"] = True
            result["reason"] = "DRY_RUN - would execute"
            logger.info("dry_run_execute", item=opp.item_name, roi=opp.roi_percent)
            return result

        if not self.config.auto_execute:
            result["reason"] = "auto_execute_disabled"
            return result

        try:
            # Execute buy
            if opp.buy_platform == Platform.DMARKET and self.dmarket:
                buy_result = await self.dmarket.quick_buy(opp.item_id)
                result["buy_result"] = buy_result
                result["success"] = buy_result.get("success", False)

                if result["success"]:
                    opp.executed = True
                    self._stats["opportunities_executed"] += 1
                    self._stats["total_profit_usd"] += opp.net_profit

                    # Notify
                    await self._notify(
                        f"🎯 <b>Арбитраж выполнен!</b>\n\n"
                        f"📦 {opp.item_name}\n"
                        f"💰 Покупка: ${opp.buy_price:.2f}\n"
                        f"📈 ROI: {opp.roi_percent:.1f}%\n"
                        f"✅ Прибыль: ${opp.net_profit:.2f}"
                    )

        except Exception as e:
            result["reason"] = str(e)
            logger.error("execute_opportunity_error", error=str(e))

        return result

    async def start_auto_scan(self) -> None:
        """Start automatic scanning loop."""
        if self._running:
            logger.warning("auto_scan_already_running")
            return

        self._running = True
        self._stats["start_time"] = datetime.now(UTC)

        await self._notify(
            "🤖 <b>AI Арбитраж запущен!</b>\n\n"
            f"📊 Игры: {', '.join(self.config.games)}\n"
            f"💰 Мин. ROI: {self.config.min_roi_percent}%\n"
            f"🔄 Интервал: {self.config.scan_interval_seconds}с\n"
            f"⚡ Авто-покупка: {'Да' if self.config.auto_execute else 'Нет'}"
        )

        logger.info("auto_scan_started", config=self.config.__dict__)

        self._task = asyncio.create_task(self._scan_loop())

    async def _scan_loop(self) -> None:
        """Main scanning loop."""
        while self._running:
            try:
                opportunities = await self.scan_all()

                # Report top opportunities
                if opportunities:
                    top_opps = opportunities[:5]
                    msg = f"🔍 <b>Найдено возможностей:</b> {len(opportunities)}\n\n"
                    for i, opp in enumerate(top_opps, 1):
                        msg += (
                            f"{i}. {opp.item_name[:30]}...\n"
                            f"   💰 {opp.roi_percent:.1f}% ROI | "
                            f"${opp.net_profit:.2f}\n"
                        )

                    if self._telegram_bot:
                        await self._notify(msg)

                    # Auto-execute if enabled
                    if self.config.auto_execute and not self.config.dry_run:
                        for opp in opportunities[:3]:  # Top 3 only
                            if opp.ai_confidence >= self.config.min_ai_confidence:
                                await self.execute_opportunity(opp)
                                await asyncio.sleep(2)  # Delay between trades

            except Exception as e:
                logger.error("scan_loop_error", error=str(e))

            await asyncio.sleep(self.config.scan_interval_seconds)

    async def stop_auto_scan(self) -> None:
        """Stop automatic scanning."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        await self._notify(
            "⏹ <b>AI Арбитраж остановлен</b>\n\n"
            f"📊 Сканов: {self._stats['scans_completed']}\n"
            f"🔍 Найдено: {self._stats['opportunities_found']}\n"
            f"✅ Выполнено: {self._stats['opportunities_executed']}\n"
            f"💰 Прибыль: ${float(self._stats['total_profit_usd']):.2f}"
        )

        logger.info("auto_scan_stopped", stats=self._stats)

    def get_stats(self) -> dict[str, Any]:
        """Get current statistics."""
        uptime = 0
        if self._stats["start_time"]:
            uptime = int((datetime.now(UTC) - self._stats["start_time"]).total_seconds() / 60)

        return {
            **self._stats,
            "uptime_minutes": uptime,
            "is_running": self._running,
            "pending_opportunities": len(self._opportunities),
            "total_profit_usd": float(self._stats["total_profit_usd"]),
        }

    def get_opportunities(self) -> list[ArbitrageOpportunity]:
        """Get current opportunities list."""
        return self._opportunities.copy()


async def create_arbitrage_system(
    dmarket_api: DMarketAPI | None = None,
    waxpeer_api: WaxpeerAPI | None = None,
    config: ArbitrageConfig | None = None,
) -> AIUnifiedArbitrage:
    """Factory function to create arbitrage system with AI.

    Args:
        dmarket_api: DMarket API client
        waxpeer_api: Waxpeer API client
        config: Arbitrage configuration

    Returns:
        Configured AIUnifiedArbitrage instance
    """
    # Try to get AI coordinator
    ai_coordinator = None
    try:
        from src.ml.ai_coordinator import get_ai_coordinator

        ai_coordinator = get_ai_coordinator()
    except ImportError:
        logger.warning("ai_coordinator_not_available")

    return AIUnifiedArbitrage(
        dmarket_api=dmarket_api,
        waxpeer_api=waxpeer_api,
        ai_coordinator=ai_coordinator,
        config=config,
    )
