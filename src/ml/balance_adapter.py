"""Адаптивная стратегия на основе баланса пользователя.

Этот модуль автоматически адаптирует:
- Размер позиций
- Пороги прибыли
- Уровень риска
- Диверсификацию

К текущему балансу пользователя (маленький/средний/большой).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

logger = logging.getLogger(__name__)


class BalanceCategory(StrEnum):
    """Категория баланса пользователя."""

    MICRO = "micro"  # < $20 - очень маленький баланс
    SMALL = "small"  # $20-100 - маленький баланс
    MEDIUM = "medium"  # $100-500 - средний баланс
    LARGE = "large"  # $500-2000 - большой баланс
    WHALE = "whale"  # > $2000 - очень большой баланс


class StrategyMode(StrEnum):
    """Режим стратегии."""

    GROWTH = "growth"  # Агрессивный рост капитала
    BALANCED = "balanced"  # Сбалансированный подход
    PRESERVATION = "preservation"  # Сохранение капитала


@dataclass
class StrategyRecommendation:
    """Рекомендация по стратегии."""

    # Категория и режим
    balance_category: BalanceCategory
    recommended_mode: StrategyMode

    # Параметры позиций
    max_position_percent: float  # Максимальный % баланса на одну позицию
    min_profit_threshold: float  # Минимальный порог прибыли (%)
    max_risk_tolerance: float  # Максимальный допустимый риск (0-1)

    # Диверсификация
    max_concurrent_positions: int  # Максимум одновременных позиций
    recommended_price_range: tuple[float, float]  # Рекомендуемый диапазон цен

    # Время и частота
    recommended_scan_interval: int  # Интервал сканирования (секунды)
    hold_time_recommendation: str  # Рекомендуемое время удержания

    # Дополнительные рекомендации
    recommendations: list[str]

    # Мета-информация
    timestamp: datetime
    balance_usd: float

    def to_dict(self) -> dict[str, Any]:
        """Преобразовать в словарь."""
        return {
            "balance_category": self.balance_category.value,
            "recommended_mode": self.recommended_mode.value,
            "max_position_percent": self.max_position_percent,
            "min_profit_threshold": self.min_profit_threshold,
            "max_risk_tolerance": self.max_risk_tolerance,
            "max_concurrent_positions": self.max_concurrent_positions,
            "recommended_price_range": self.recommended_price_range,
            "recommended_scan_interval": self.recommended_scan_interval,
            "hold_time_recommendation": self.hold_time_recommendation,
            "recommendations": self.recommendations,
            "balance_usd": self.balance_usd,
        }


class BalanceAdaptiveStrategy:
    """Стратегия, адаптирующаяся к балансу пользователя.

    Автоматически настраивает все параметры торговли
    в зависимости от текущего баланса.
    """

    # Пороги категорий баланса (USD)
    BALANCE_THRESHOLDS = {
        BalanceCategory.MICRO: (0, 20),
        BalanceCategory.SMALL: (20, 100),
        BalanceCategory.MEDIUM: (100, 500),
        BalanceCategory.LARGE: (500, 2000),
        BalanceCategory.WHALE: (2000, float("inf")),
    }

    # Параметры для каждой категории
    CATEGORY_PARAMS = {
        BalanceCategory.MICRO: {
            "max_position_percent": 50.0,  # Можем рискнуть бОльшим %
            "min_profit_threshold": 15.0,  # Высокий порог - только верные сделки
            "max_risk_tolerance": 0.3,  # Низкий риск
            "max_concurrent_positions": 1,  # Только одна позиция
            "scan_interval": 60,  # Редкое сканирование (экономия ресурсов)
            "hold_time": "short",  # Быстрые сделки
            "mode": StrategyMode.GROWTH,  # Фокус на росте
        },
        BalanceCategory.SMALL: {
            "max_position_percent": 30.0,
            "min_profit_threshold": 10.0,
            "max_risk_tolerance": 0.4,
            "max_concurrent_positions": 2,
            "scan_interval": 45,
            "hold_time": "short",
            "mode": StrategyMode.GROWTH,
        },
        BalanceCategory.MEDIUM: {
            "max_position_percent": 20.0,
            "min_profit_threshold": 7.0,
            "max_risk_tolerance": 0.5,
            "max_concurrent_positions": 4,
            "scan_interval": 30,
            "hold_time": "medium",
            "mode": StrategyMode.BALANCED,
        },
        BalanceCategory.LARGE: {
            "max_position_percent": 15.0,
            "min_profit_threshold": 5.0,
            "max_risk_tolerance": 0.6,
            "max_concurrent_positions": 8,
            "scan_interval": 20,
            "hold_time": "medium",
            "mode": StrategyMode.BALANCED,
        },
        BalanceCategory.WHALE: {
            "max_position_percent": 10.0,
            "min_profit_threshold": 3.0,  # Низкий порог - больше сделок
            "max_risk_tolerance": 0.7,  # Можем позволить больше риска
            "max_concurrent_positions": 15,
            "scan_interval": 15,  # Частое сканирование
            "hold_time": "long",  # Можем ждать
            "mode": StrategyMode.PRESERVATION,  # Сохранение капитала
        },
    }

    def __init__(self, user_balance: float = 0.0):
        """Инициализация адаптивной стратегии.

        Args:
            user_balance: Текущий баланс пользователя (USD)
        """
        self.user_balance = user_balance
        self._category = self._categorize_balance(user_balance)
        self._custom_params: dict[str, Any] = {}

    def set_balance(self, balance: float):
        """Установить баланс и обновить категорию.

        Args:
            balance: Новый баланс (USD)
        """
        self.user_balance = max(0.0, balance)
        self._category = self._categorize_balance(self.user_balance)
        logger.info(
            f"Balance updated: ${balance:.2f} -> {self._category.value} category"
        )

    def _categorize_balance(self, balance: float) -> BalanceCategory:
        """Определить категорию баланса."""
        for category, (min_val, max_val) in self.BALANCE_THRESHOLDS.items():
            if min_val <= balance < max_val:
                return category
        return BalanceCategory.WHALE  # Fallback

    @property
    def category(self) -> BalanceCategory:
        """Получить текущую категорию баланса."""
        return self._category

    def get_recommendation(self) -> StrategyRecommendation:
        """Получить рекомендации по стратегии для текущего баланса.

        Returns:
            StrategyRecommendation с параметрами и рекомендациями
        """
        params = self.CATEGORY_PARAMS[self._category]

        # Рассчитываем рекомендуемый диапазон цен
        price_range = self._calculate_price_range()

        # Генерируем текстовые рекомендации
        recommendations = self._generate_recommendations()

        return StrategyRecommendation(
            balance_category=self._category,
            recommended_mode=params["mode"],
            max_position_percent=params["max_position_percent"],
            min_profit_threshold=params["min_profit_threshold"],
            max_risk_tolerance=params["max_risk_tolerance"],
            max_concurrent_positions=params["max_concurrent_positions"],
            recommended_price_range=price_range,
            recommended_scan_interval=params["scan_interval"],
            hold_time_recommendation=params["hold_time"],
            recommendations=recommendations,
            timestamp=datetime.now(UTC),
            balance_usd=self.user_balance,
        )

    def _calculate_price_range(self) -> tuple[float, float]:
        """Рассчитать рекомендуемый диапазон цен для покупки."""
        params = self.CATEGORY_PARAMS[self._category]
        max_position_percent = params["max_position_percent"]

        # Максимальная цена = max_position_percent от баланса
        max_price = self.user_balance * (max_position_percent / 100)

        # Минимальная цена зависит от категории
        if self._category == BalanceCategory.MICRO:
            min_price = 0.10  # Самые дешёвые предметы
        elif self._category == BalanceCategory.SMALL:
            min_price = 0.50
        elif self._category == BalanceCategory.MEDIUM:
            min_price = 1.00
        elif self._category == BalanceCategory.LARGE:
            min_price = 2.00
        else:  # WHALE
            min_price = 5.00

        return (min_price, max(min_price, max_price))

    def _generate_recommendations(self) -> list[str]:
        """Генерировать текстовые рекомендации."""
        recs = []

        if self._category == BalanceCategory.MICRO:
            recs.extend([
                "Focus on cheap items ($0.10-$5) with high profit margin",
                "Wait for 15%+ profit opportunities only",
                "Make one trade at a time",
                "Reinvest all profits to grow balance quickly",
                "Consider depositing more to unlock better opportunities",
            ])
        elif self._category == BalanceCategory.SMALL:
            recs.extend([
                "Target items in $0.50-$30 range",
                "Look for 10%+ profit after commission",
                "Keep 2-3 positions maximum",
                "Focus on high-liquidity items for quick flips",
            ])
        elif self._category == BalanceCategory.MEDIUM:
            recs.extend([
                "Diversify across 3-5 different items",
                "Mix quick flips and medium-term holds",
                "Target 7%+ profit per trade",
                "Use tournament calendar for timing sticker investments",
            ])
        elif self._category == BalanceCategory.LARGE:
            recs.extend([
                "Build a diversified portfolio (5-10 items)",
                "Include some long-term investments",
                "5%+ profit is acceptable at this scale",
                "Consider cross-platform arbitrage (DMarket ↔ Waxpeer)",
                "Use auto-repricing for inventory management",
            ])
        else:  # WHALE
            recs.extend([
                "Maximum diversification recommended (10+ items)",
                "Focus on capital preservation over growth",
                "3%+ profit is sustainable at this volume",
                "Consider market making strategies",
                "Use intelligent hold during market events",
                "Allocate portion to tournament sticker investments",
            ])

        # Общие рекомендации
        recs.extend([
            f"Current balance: ${self.user_balance:.2f}",
            f"Category: {self._category.value}",
        ])

        return recs

    def get_max_position_value(self) -> float:
        """Получить максимальную стоимость одной позиции (USD)."""
        params = self.CATEGORY_PARAMS[self._category]
        return self.user_balance * (params["max_position_percent"] / 100)

    def get_min_profit_threshold(self) -> float:
        """Получить минимальный порог прибыли (%)."""
        return self.CATEGORY_PARAMS[self._category]["min_profit_threshold"]

    def get_max_concurrent_positions(self) -> int:
        """Получить максимальное количество одновременных позиций."""
        return self.CATEGORY_PARAMS[self._category]["max_concurrent_positions"]

    def get_scan_interval(self) -> int:
        """Получить рекомендуемый интервал сканирования (секунды)."""
        return self.CATEGORY_PARAMS[self._category]["scan_interval"]

    def should_buy(
        self,
        item_price: float,
        expected_profit_percent: float,
        risk_score: float,
        current_positions: int = 0,
    ) -> tuple[bool, str]:
        """Проверить, стоит ли покупать предмет.

        Args:
            item_price: Цена предмета
            expected_profit_percent: Ожидаемая прибыль (%)
            risk_score: Оценка риска (0-1)
            current_positions: Текущее количество позиций

        Returns:
            (should_buy, reason)
        """
        params = self.CATEGORY_PARAMS[self._category]

        # Проверка цены
        max_price = self.user_balance * (params["max_position_percent"] / 100)
        if item_price > max_price:
            return False, f"Price ${item_price:.2f} exceeds max position ${max_price:.2f}"

        # Проверка баланса
        if item_price > self.user_balance:
            return False, f"Insufficient balance (${self.user_balance:.2f})"

        # Проверка прибыли
        if expected_profit_percent < params["min_profit_threshold"]:
            return False, f"Profit {expected_profit_percent:.1f}% below threshold {params['min_profit_threshold']}%"

        # Проверка риска
        if risk_score > params["max_risk_tolerance"]:
            return False, f"Risk {risk_score:.2f} exceeds tolerance {params['max_risk_tolerance']}"

        # Проверка количества позиций
        if current_positions >= params["max_concurrent_positions"]:
            return False, f"Max positions ({params['max_concurrent_positions']}) reached"

        return True, "All checks passed"

    def calculate_position_size(
        self,
        item_price: float,
        confidence_score: float,
        risk_score: float,
    ) -> float:
        """Рассчитать оптимальный размер позиции.

        Args:
            item_price: Цена предмета
            confidence_score: Уверенность в прогнозе (0-1)
            risk_score: Оценка риска (0-1)

        Returns:
            Рекомендуемая сумма инвестиции (USD)
        """
        params = self.CATEGORY_PARAMS[self._category]

        # Базовый размер
        max_position = self.user_balance * (params["max_position_percent"] / 100)

        # Корректировка по уверенности
        confidence_factor = 0.5 + confidence_score * 0.5

        # Корректировка по риску
        risk_factor = 1.0 - risk_score * 0.5

        # Итоговый размер
        position_size = max_position * confidence_factor * risk_factor

        # Не больше цены предмета
        position_size = min(position_size, item_price)

        # Не больше баланса
        position_size = min(position_size, self.user_balance)

        return round(position_size, 2)

    def adapt_to_market_conditions(
        self,
        volatility: float,
        is_sale_period: bool = False,
        is_tournament_period: bool = False,
    ) -> dict[str, Any]:
        """Адаптировать параметры к рыночным условиям.

        Args:
            volatility: Текущая волатильность рынка (0-1)
            is_sale_period: Идёт распродажа Steam
            is_tournament_period: Идёт турнир (стикеры растут)

        Returns:
            Скорректированные параметры
        """
        params = dict(self.CATEGORY_PARAMS[self._category])

        # Высокая волатильность - более консервативно
        if volatility > 0.2:
            params["min_profit_threshold"] *= 1.5
            params["max_risk_tolerance"] *= 0.7
            params["max_concurrent_positions"] = max(1, params["max_concurrent_positions"] - 2)

        # Распродажа - ещё консервативнее
        if is_sale_period:
            params["min_profit_threshold"] *= 1.3
            params["max_position_percent"] *= 0.7

        # Турнирный период - можно рисковать больше на стикерах
        if is_tournament_period:
            params["max_risk_tolerance"] *= 1.2
            params["min_profit_threshold"] *= 0.8

        return params


class AdaptivePortfolioAllocator:
    """Распределитель портфеля с адаптацией к балансу."""

    def __init__(self, strategy: BalanceAdaptiveStrategy):
        """Инициализация аллокатора.

        Args:
            strategy: Адаптивная стратегия
        """
        self.strategy = strategy

    def allocate(
        self,
        opportunities: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Распределить капитал между возможностями.

        Args:
            opportunities: Список возможностей с полями:
                - item_name: Название предмета
                - price: Цена
                - expected_profit: Ожидаемая прибыль (%)
                - risk_score: Риск (0-1)
                - confidence: Уверенность (0-1)

        Returns:
            Список возможностей с добавленным полем allocation (USD)
        """
        if not opportunities:
            return []

        recommendation = self.strategy.get_recommendation()
        max_positions = recommendation.max_concurrent_positions
        available_balance = self.strategy.user_balance

        # Сортируем по ожидаемой прибыли / риск (лучшие первые)
        sorted_opps = sorted(
            opportunities,
            key=lambda x: x.get("expected_profit", 0) / max(x.get("risk_score", 0.5), 0.1),
            reverse=True,
        )

        allocations = []
        positions_taken = 0

        for opp in sorted_opps:
            if positions_taken >= max_positions:
                opp["allocation"] = 0.0
                opp["allocation_reason"] = "Max positions reached"
                allocations.append(opp)
                continue

            price = opp.get("price", 0)
            expected_profit = opp.get("expected_profit", 0)
            risk_score = opp.get("risk_score", 0.5)
            confidence = opp.get("confidence", 0.5)

            should_buy, reason = self.strategy.should_buy(
                item_price=price,
                expected_profit_percent=expected_profit,
                risk_score=risk_score,
                current_positions=positions_taken,
            )

            if should_buy and price <= available_balance:
                allocation = self.strategy.calculate_position_size(
                    item_price=price,
                    confidence_score=confidence,
                    risk_score=risk_score,
                )
                allocation = min(allocation, available_balance)

                opp["allocation"] = allocation
                opp["allocation_reason"] = "Allocated"

                available_balance -= allocation
                positions_taken += 1
            else:
                opp["allocation"] = 0.0
                opp["allocation_reason"] = reason

            allocations.append(opp)

        return allocations
