"""
Optimal Arbitrage Strategy - Единая оптимальная стратегия для прибыльного арбитража.

Эта стратегия объединяет лучшие практики из индустрии и все улучшения репозитория:
- Multi-platform scanning (DMarket, Waxpeer)
- Float Value Analysis
- Pattern/Phase detection
- Liquidity filtering
- Risk management
- ROI optimization

На основе анализа стратегий 2024-2025:
- Минимальный ROI: 10-15% после комиссий
- Real-time market scanning
- Multi-market trading
- Wear & Float value consideration
- Manual safeguards for captchas/locks
"""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


class RiskLevel(Enum):
    """Уровень риска сделки."""

    VERY_LOW = "very_low"  # ROI > 20%, высокая ликвидность
    LOW = "low"  # ROI 15-20%, хорошая ликвидность
    MEDIUM = "medium"  # ROI 10-15%, средняя ликвидность
    HIGH = "high"  # ROI 5-10%, низкая ликвидность
    VERY_HIGH = "very_high"  # ROI < 5%, очень низкая ликвидность


class TradeLockStrategy(Enum):
    """Стратегия работы с trade lock."""

    INSTANT_ONLY = "instant_only"  # Только предметы без лока
    SHORT_LOCK = "short_lock"  # Лок до 3 дней
    INVESTMENT = "investment"  # Любой лок (7+ дней)


@dataclass
class MarketFees:
    """Комиссии торговых площадок."""

    dmarket: float = 0.05  # 5%
    waxpeer: float = 0.06  # 6%
    steam: float = 0.15  # 15%
    # buff163 исключен по запросу пользователя


@dataclass
class ArbitrageOpportunity:
    """Арбитражная возможность."""

    item_id: str
    item_name: str
    game: str

    # Цены
    buy_price: float
    sell_price: float
    buy_platform: str
    sell_platform: str

    # Расчёты
    gross_profit: float
    net_profit: float
    roi_percent: float
    fees_paid: float

    # Характеристики
    float_value: float | None = None
    pattern_id: int | None = None
    phase: str | None = None
    stickers: list[dict[str, Any]] = field(default_factory=list)

    # Риски и ликвидность
    risk_level: RiskLevel = RiskLevel.MEDIUM
    liquidity_score: float = 0.5  # 0-1
    sales_per_day: float = 0.0
    days_to_sell: float = 7.0

    # Trade lock
    has_trade_lock: bool = False
    lock_days: int = 0

    # Скор
    opportunity_score: float = 0.0

    # Время
    found_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    valid_until: datetime | None = None


@dataclass
class StrategySettings:
    """Настройки оптимальной стратегии."""

    # ROI фильтры
    min_roi_percent: float = 10.0  # Минимальный ROI после комиссий
    target_roi_percent: float = 15.0  # Целевой ROI
    max_roi_percent: float = 50.0  # Макс ROI (защита от скама)

    # Цены
    min_price: float = 1.0  # $1 минимум
    max_price: float = 500.0  # $500 максимум
    max_single_trade: float = 100.0  # Максимум на одну сделку

    # Ликвидность
    min_liquidity_score: float = 0.3  # 0-1
    min_sales_per_day: float = 0.5  # Минимум продаж в день
    max_days_to_sell: float = 14.0  # Максимум дней на продажу

    # Trade Lock
    lock_strategy: TradeLockStrategy = TradeLockStrategy.SHORT_LOCK
    max_lock_days: int = 3

    # Риск менеджмент
    max_risk_level: RiskLevel = RiskLevel.MEDIUM
    max_daily_trades: int = 50
    max_daily_spend: float = 500.0
    diversification_min_items: int = 5  # Минимум разных предметов

    # Площадки
    enabled_platforms: list[str] = field(default_factory=lambda: ["dmarket", "waxpeer"])

    # Игры
    enabled_games: list[str] = field(
        default_factory=lambda: ["csgo", "dota2", "tf2", "rust"]
    )

    # Float Value (только для CS:GO)
    float_premium_enabled: bool = True
    premium_float_threshold: float = 0.07  # FN boundary

    # Pattern/Phase (только для CS:GO)
    doppler_premium_enabled: bool = True
    blue_gem_premium_enabled: bool = True


class OptimalArbitrageStrategy:
    """
    Единая оптимальная стратегия для прибыльного арбитража.

    Объединяет все стратегии репозитория в одну оптимизированную систему:
    1. Cross-Platform Arbitrage
    2. Intramarket Arbitrage
    3. Float Value Arbitrage
    4. Pattern/Phase Arbitrage
    5. Smart Market Finder
    6. Enhanced Scanner

    Принципы работы:
    - Минимальный ROI 10-15% после всех комиссий
    - Фокус на ликвидных предметах
    - Risk management с diversification
    - Автоматический выбор лучших возможностей
    """

    def __init__(
        self,
        settings: StrategySettings | None = None,
        fees: MarketFees | None = None,
    ):
        """Initialize optimal strategy."""
        self.settings = settings or StrategySettings()
        self.fees = fees or MarketFees()

        # Статистика
        self.stats = {
            "total_scans": 0,
            "opportunities_found": 0,
            "trades_executed": 0,
            "total_profit": 0.0,
            "average_roi": 0.0,
        }

        # История сделок
        self.trade_history: list[ArbitrageOpportunity] = []

        # Дневные лимиты
        self.daily_trades = 0
        self.daily_spend = 0.0
        self.last_reset = datetime.now(UTC)

        logger.info(
            "optimal_strategy_initialized",
            min_roi=self.settings.min_roi_percent,
            enabled_games=self.settings.enabled_games,
        )

    def calculate_net_profit(
        self,
        buy_price: float,
        sell_price: float,
        buy_platform: str,
        sell_platform: str,
    ) -> tuple[float, float, float]:
        """
        Рассчитать чистую прибыль после комиссий.

        Returns:
            Tuple of (gross_profit, net_profit, fees_paid)
        """
        # Получить комиссии
        _ = getattr(self.fees, buy_platform, 0.05)  # buy_fee for future use
        sell_fee = getattr(self.fees, sell_platform, 0.05)

        # Gross profit
        gross_profit = sell_price - buy_price

        # Fees: комиссия при продаже
        fees_paid = sell_price * sell_fee

        # Net profit
        net_profit = gross_profit - fees_paid

        return gross_profit, net_profit, fees_paid

    def calculate_roi(
        self,
        buy_price: float,
        net_profit: float,
    ) -> float:
        """Рассчитать ROI в процентах."""
        if buy_price <= 0:
            return 0.0
        return (net_profit / buy_price) * 100

    def assess_risk_level(
        self,
        roi_percent: float,
        liquidity_score: float,
        sales_per_day: float,
    ) -> RiskLevel:
        """Оценить уровень риска сделки."""
        # Высокий ROI + высокая ликвидность = низкий риск
        if roi_percent >= 20 and liquidity_score >= 0.7 and sales_per_day >= 2:
            return RiskLevel.VERY_LOW
        if roi_percent >= 15 and liquidity_score >= 0.5 and sales_per_day >= 1:
            return RiskLevel.LOW
        if roi_percent >= 10 and liquidity_score >= 0.3 and sales_per_day >= 0.5:
            return RiskLevel.MEDIUM
        if roi_percent >= 5:
            return RiskLevel.HIGH
        return RiskLevel.VERY_HIGH

    def calculate_opportunity_score(
        self,
        opportunity: ArbitrageOpportunity,
    ) -> float:
        """
        Рассчитать общий скор возможности (0-100).

        Учитывает:
        - ROI (40%)
        - Ликвидность (30%)
        - Риск (20%)
        - Float/Pattern премия (10%)
        """
        score = 0.0

        # ROI компонент (40%)
        roi_score = min(opportunity.roi_percent / 30 * 40, 40)
        score += roi_score

        # Ликвидность (30%)
        liquidity_score = opportunity.liquidity_score * 30
        score += liquidity_score

        # Риск (20%) - чем ниже риск, тем выше скор
        risk_scores = {
            RiskLevel.VERY_LOW: 20,
            RiskLevel.LOW: 16,
            RiskLevel.MEDIUM: 12,
            RiskLevel.HIGH: 6,
            RiskLevel.VERY_HIGH: 0,
        }
        score += risk_scores.get(opportunity.risk_level, 10)

        # Float/Pattern премия (10%)
        if opportunity.float_value and opportunity.float_value < 0.07:
            score += 5  # FN bonus
        if opportunity.phase in {"Ruby", "Sapphire", "Black Pearl"}:
            score += 5  # Rare phase bonus
        if opportunity.pattern_id in {661, 670, 321, 387}:
            score += 5  # Blue gem bonus

        return min(score, 100)

    def filter_opportunity(
        self,
        opportunity: ArbitrageOpportunity,
    ) -> tuple[bool, str]:
        """
        Проверить возможность на соответствие критериям.

        Returns:
            Tuple of (is_valid, rejection_reason)
        """
        s = self.settings

        # ROI фильтры
        if opportunity.roi_percent < s.min_roi_percent:
            return (
                False,
                f"ROI {opportunity.roi_percent:.1f}% < min {s.min_roi_percent}%",
            )

        if opportunity.roi_percent > s.max_roi_percent:
            return (
                False,
                f"ROI {opportunity.roi_percent:.1f}% > max {s.max_roi_percent}% (possible scam)",
            )

        # Цена
        if opportunity.buy_price < s.min_price:
            return False, f"Price ${opportunity.buy_price:.2f} < min ${s.min_price}"

        if opportunity.buy_price > s.max_price:
            return False, f"Price ${opportunity.buy_price:.2f} > max ${s.max_price}"

        if opportunity.buy_price > s.max_single_trade:
            return (
                False,
                f"Price ${opportunity.buy_price:.2f} > max single trade ${s.max_single_trade}",
            )

        # Ликвидность
        if opportunity.liquidity_score < s.min_liquidity_score:
            return (
                False,
                f"Liquidity {opportunity.liquidity_score:.2f} < min {s.min_liquidity_score}",
            )

        if opportunity.sales_per_day < s.min_sales_per_day:
            return (
                False,
                f"Sales/day {opportunity.sales_per_day:.1f} < min {s.min_sales_per_day}",
            )

        if opportunity.days_to_sell > s.max_days_to_sell:
            return (
                False,
                f"Days to sell {opportunity.days_to_sell:.0f} > max {s.max_days_to_sell}",
            )

        # Trade lock
        if (
            s.lock_strategy == TradeLockStrategy.INSTANT_ONLY
            and opportunity.has_trade_lock
        ):
            return False, "Trade lock not allowed"

        if opportunity.lock_days > s.max_lock_days:
            return False, f"Lock {opportunity.lock_days} days > max {s.max_lock_days}"

        # Риск
        risk_order = [
            RiskLevel.VERY_LOW,
            RiskLevel.LOW,
            RiskLevel.MEDIUM,
            RiskLevel.HIGH,
            RiskLevel.VERY_HIGH,
        ]
        if risk_order.index(opportunity.risk_level) > risk_order.index(
            s.max_risk_level
        ):
            return (
                False,
                f"Risk {opportunity.risk_level.value} > max {s.max_risk_level.value}",
            )

        # Дневные лимиты
        if self.daily_trades >= s.max_daily_trades:
            return False, f"Daily trades limit {s.max_daily_trades} reached"

        if self.daily_spend + opportunity.buy_price > s.max_daily_spend:
            return False, f"Daily spend limit ${s.max_daily_spend} would be exceeded"

        return True, ""

    def analyze_item(
        self,
        item: dict[str, Any],
        buy_platform: str,
        sell_platform: str,
        sell_price: float,
    ) -> ArbitrageOpportunity | None:
        """
        Анализировать предмет на арбитражную возможность.

        Args:
            item: Данные предмета с buy platform
            buy_platform: Платформа покупки
            sell_platform: Платформа продажи
            sell_price: Цена продажи на sell platform
        """
        try:
            # Извлечь данные
            buy_price = (
                float(item.get("price", {}).get("USD", 0)) / 100
            )  # Центы в доллары
            if buy_price <= 0 or sell_price <= 0:
                return None

            # Рассчитать прибыль
            gross_profit, net_profit, fees_paid = self.calculate_net_profit(
                buy_price, sell_price, buy_platform, sell_platform
            )

            if net_profit <= 0:
                return None

            # Рассчитать ROI
            roi_percent = self.calculate_roi(buy_price, net_profit)

            # Ликвидность (примерная оценка)
            sales_history = item.get("salesHistory", [])
            if sales_history:
                sales_per_day = len(sales_history) / max(7, 1)  # За неделю
            else:
                sales_per_day = 0.5  # Дефолт

            liquidity_score = min(sales_per_day / 5, 1.0)  # Нормализация

            # Оценить риск
            risk_level = self.assess_risk_level(
                roi_percent, liquidity_score, sales_per_day
            )

            # Создать возможность
            opp = ArbitrageOpportunity(
                item_id=item.get("itemId", item.get("id", "")),
                item_name=item.get("title", "Unknown"),
                game=item.get("gameId", "csgo"),
                buy_price=buy_price,
                sell_price=sell_price,
                buy_platform=buy_platform,
                sell_platform=sell_platform,
                gross_profit=gross_profit,
                net_profit=net_profit,
                roi_percent=roi_percent,
                fees_paid=fees_paid,
                float_value=item.get("floatValue")
                or item.get("extra", {}).get("floatValue"),
                pattern_id=item.get("extra", {}).get("paintSeed"),
                phase=item.get("extra", {}).get("phase"),
                stickers=item.get("extra", {}).get("stickers", []),
                risk_level=risk_level,
                liquidity_score=liquidity_score,
                sales_per_day=sales_per_day,
                days_to_sell=7.0 / max(sales_per_day, 0.1),
                has_trade_lock=item.get("tradeLock", False),
                lock_days=item.get("lockDays", 0),
                valid_until=datetime.now(UTC) + timedelta(minutes=5),
            )

            # Рассчитать скор
            opp.opportunity_score = self.calculate_opportunity_score(opp)

            return opp

        except (ValueError, KeyError, TypeError) as e:
            logger.debug(
                "item_analysis_error", error=str(e), item_id=item.get("itemId")
            )
            return None

    def find_best_opportunities(
        self,
        opportunities: list[ArbitrageOpportunity],
        top_n: int = 20,
    ) -> list[ArbitrageOpportunity]:
        """
        Найти лучшие возможности с учётом diversification.

        Returns:
            Топ-N лучших возможностей, отфильтрованных и отсортированных
        """
        # Фильтрация
        valid_opps = []
        for opp in opportunities:
            is_valid, reason = self.filter_opportunity(opp)
            if is_valid:
                valid_opps.append(opp)
            else:
                logger.debug("opportunity_rejected", item=opp.item_name, reason=reason)

        # Сортировка по скору
        valid_opps.sort(key=lambda x: x.opportunity_score, reverse=True)

        # Diversification: не более 3 одинаковых предметов
        diversified = []
        item_counts: dict[str, int] = {}

        for opp in valid_opps:
            count = item_counts.get(opp.item_name, 0)
            if count < 3:
                diversified.append(opp)
                item_counts[opp.item_name] = count + 1

            if len(diversified) >= top_n:
                break

        self.stats["opportunities_found"] += len(diversified)
        self.stats["total_scans"] += 1

        logger.info(
            "best_opportunities_found",
            total_analyzed=len(opportunities),
            valid=len(valid_opps),
            selected=len(diversified),
        )

        return diversified

    def record_trade(self, opportunity: ArbitrageOpportunity) -> None:
        """Записать выполненную сделку."""
        self.trade_history.append(opportunity)
        self.daily_trades += 1
        self.daily_spend += opportunity.buy_price
        self.stats["trades_executed"] += 1
        self.stats["total_profit"] += opportunity.net_profit

        if self.stats["trades_executed"] > 0:
            self.stats["average_roi"] = (
                self.stats["total_profit"]
                / sum(t.buy_price for t in self.trade_history)
                * 100
            )

    def reset_daily_limits(self) -> None:
        """Сбросить дневные лимиты."""
        self.daily_trades = 0
        self.daily_spend = 0.0
        self.last_reset = datetime.now(UTC)
        logger.info("daily_limits_reset")

    def get_statistics(self) -> dict[str, Any]:
        """Получить статистику работы стратегии."""
        return {
            **self.stats,
            "daily_trades": self.daily_trades,
            "daily_spend": self.daily_spend,
            "trade_history_count": len(self.trade_history),
            "last_reset": self.last_reset.isoformat(),
        }


# Preset конфигурации для разных стилей торговли
STRATEGY_PRESETS = {
    "conservative": StrategySettings(
        min_roi_percent=15.0,
        target_roi_percent=20.0,
        max_price=100.0,
        min_liquidity_score=0.5,
        max_risk_level=RiskLevel.LOW,
        max_daily_trades=30,
        lock_strategy=TradeLockStrategy.INSTANT_ONLY,
    ),
    "balanced": StrategySettings(
        min_roi_percent=10.0,
        target_roi_percent=15.0,
        max_price=300.0,
        min_liquidity_score=0.3,
        max_risk_level=RiskLevel.MEDIUM,
        max_daily_trades=50,
        lock_strategy=TradeLockStrategy.SHORT_LOCK,
    ),
    "aggressive": StrategySettings(
        min_roi_percent=7.0,
        target_roi_percent=12.0,
        max_price=500.0,
        min_liquidity_score=0.2,
        max_risk_level=RiskLevel.HIGH,
        max_daily_trades=100,
        lock_strategy=TradeLockStrategy.INVESTMENT,
        max_lock_days=7,
    ),
    "high_value": StrategySettings(
        min_roi_percent=12.0,
        target_roi_percent=18.0,
        min_price=50.0,
        max_price=1000.0,
        min_liquidity_score=0.4,
        max_risk_level=RiskLevel.MEDIUM,
        max_daily_trades=20,
        max_single_trade=500.0,
        float_premium_enabled=True,
        doppler_premium_enabled=True,
        blue_gem_premium_enabled=True,
    ),
    "scalper": StrategySettings(
        min_roi_percent=5.0,
        target_roi_percent=8.0,
        min_price=0.5,
        max_price=20.0,
        min_liquidity_score=0.6,
        max_risk_level=RiskLevel.LOW,
        max_daily_trades=200,
        max_daily_spend=1000.0,
        lock_strategy=TradeLockStrategy.INSTANT_ONLY,
    ),
}


def create_strategy(preset: str = "balanced") -> OptimalArbitrageStrategy:
    """
    Создать стратегию с preset настройками.

    Available presets:
    - conservative: Низкий риск, высокий ROI, только instant
    - balanced: Средний риск, хороший ROI (рекомендуется)
    - aggressive: Высокий риск, больше возможностей
    - high_value: Дорогие предметы с премиум характеристиками
    - scalper: Быстрые сделки с низким ROI, высокий объём
    """
    settings = STRATEGY_PRESETS.get(preset, STRATEGY_PRESETS["balanced"])
    return OptimalArbitrageStrategy(settings=settings)
