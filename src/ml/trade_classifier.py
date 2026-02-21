"""Классификатор торговых сигналов с адаптацией к риску.

Классифицирует возможности на:
- Сильная покупка / Покупка / Удержание / Продажа / Сильная продажа
- Оценивает уровень риска сделки
- Адаптируется к балансу и профилю риска пользователя

Использует Random Forest из sklearn (бесплатно).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

import numpy as np

from src.ml.feature_extractor import (
    MarketFeatureExtractor,
    PriceFeatures,
    TrendDirection,
)

logger = logging.getLogger(__name__)


class TradeSignal(StrEnum):
    """Торговый сигнал."""

    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"
    SKIP = "skip"  # Не торговать (высокий риск, низкая ликвидность)


class RiskLevel(StrEnum):
    """Уровень риска сделки."""

    VERY_LOW = "very_low"  # <10% вероятность убытка
    LOW = "low"  # 10-25%
    MEDIUM = "medium"  # 25-40%
    HIGH = "high"  # 40-60%
    VERY_HIGH = "very_high"  # >60%


@dataclass
class TradeClassification:
    """Результат классификации торговой возможности."""

    item_name: str
    signal: TradeSignal
    risk_level: RiskLevel

    # Вероятности сигналов
    signal_probabilities: dict[str, float]
    risk_score: float  # 0-1

    # Рекомендуемый размер позиции
    recommended_position_size: float  # % от баланса
    max_loss_percent: float  # Максимальный возможный убыток

    # Мета-информация
    classification_timestamp: datetime
    reasoning: list[str]

    # Связанные метрики
    expected_profit_percent: float
    profit_probability: float  # Вероятность прибыльной сделки

    def is_actionable(self) -> bool:
        """Проверить, стоит ли действовать по сигналу."""
        return self.signal in {
            TradeSignal.STRONG_BUY,
            TradeSignal.BUY,
            TradeSignal.SELL,
            TradeSignal.STRONG_SELL,
        }


class AdaptiveTradeClassifier:
    """Адаптивный классификатор торговых сигналов.

    Классифицирует торговые возможности и оценивает риски.

    Attributes:
        user_balance: Текущий баланс пользователя (USD).
        risk_tolerance: Толерантность к риску (conservative/moderate/aggressive).
        thresholds: Адаптивные пороги для классификации.

    Example:
        >>> classifier = AdaptiveTradeClassifier(user_balance=100.0)
        >>> result = classifier.classify("AK-47 | Redline", 10.0, 12.0)
        >>> print(result.signal)  # TradeSignal.BUY
    """

    # Risk tolerance options
    RISK_TOLERANCES = ("conservative", "moderate", "aggressive")

    def __init__(
        self,
        user_balance: float = 100.0,
        risk_tolerance: str = "moderate",
    ) -> None:
        """Инициализация классификатора.

        Args:
            user_balance: Текущий баланс пользователя (USD)
            risk_tolerance: Толерантность к риску (conservative/moderate/aggressive)
        """
        self.user_balance = user_balance
        self.risk_tolerance = risk_tolerance

        self.feature_extractor = MarketFeatureExtractor()

        # ML модель (ленивая инициализация)
        self._classifier = None
        self._is_trAlgoned = False

        # Пороги для классификации (адаптивные)
        self._update_thresholds()

    def _update_thresholds(self) -> None:
        """Обновить пороги классификации на основе профиля риска."""
        # Базовые пороги для moderate
        base_thresholds = {
            "strong_buy_profit": 10.0,  # % ожидаемой прибыли
            "buy_profit": 5.0,
            "sell_profit": -5.0,
            "strong_sell_profit": -10.0,
            "max_risk_score": 0.6,  # Максимальный допустимый риск
            "min_liquidity": 0.3,  # Минимальная ликвидность
        }

        # Адаптация к профилю риска
        if self.risk_tolerance == "conservative":
            self.thresholds = {
                "strong_buy_profit": base_thresholds["strong_buy_profit"] * 1.5,
                "buy_profit": base_thresholds["buy_profit"] * 1.5,
                "sell_profit": base_thresholds["sell_profit"] * 0.8,
                "strong_sell_profit": base_thresholds["strong_sell_profit"] * 0.8,
                "max_risk_score": 0.4,
                "min_liquidity": 0.5,
            }
        elif self.risk_tolerance == "aggressive":
            self.thresholds = {
                "strong_buy_profit": base_thresholds["strong_buy_profit"] * 0.7,
                "buy_profit": base_thresholds["buy_profit"] * 0.7,
                "sell_profit": base_thresholds["sell_profit"] * 1.2,
                "strong_sell_profit": base_thresholds["strong_sell_profit"] * 1.2,
                "max_risk_score": 0.75,
                "min_liquidity": 0.2,
            }
        else:  # moderate
            self.thresholds = base_thresholds.copy()

        # Адаптация к балансу
        balance_factor = self._get_balance_factor()
        self.thresholds["max_position_percent"] = 30.0 / balance_factor

    def _get_balance_factor(self) -> float:
        """Получить фактор масштабирования по балансу.

        Returns:
            Фактор для адаптации порогов к размеру баланса.
        """
        if self.user_balance < 50:
            return 2.0  # Очень консервативно
        if self.user_balance < 100:
            return 1.5
        if self.user_balance < 300:
            return 1.0
        if self.user_balance < 500:
            return 0.8
        return 0.6

    def set_user_balance(self, balance: float) -> None:
        """Установить баланс пользователя.

        Args:
            balance: Новый баланс (USD)
        """
        self.user_balance = max(0.0, balance)
        self._update_thresholds()

    def set_risk_tolerance(self, tolerance: str) -> None:
        """Установить толерантность к риску.

        Args:
            tolerance: Уровень толерантности (conservative/moderate/aggressive)
        """
        if tolerance in self.RISK_TOLERANCES:
            self.risk_tolerance = tolerance
            self._update_thresholds()

    def classify(
        self,
        item_name: str,
        current_price: float,
        expected_price: float,
        price_history: list[tuple[datetime, float]] | None = None,
        sales_history: list[dict[str, Any]] | None = None,
        market_offers: list[dict[str, Any]] | None = None,
    ) -> TradeClassification:
        """Классифицировать торговую возможность.

        Args:
            item_name: Название предмета
            current_price: Текущая цена
            expected_price: Ожидаемая цена (из прогноза)
            price_history: История цен
            sales_history: История продаж
            market_offers: Текущие предложения

        Returns:
            TradeClassification с сигналом и метриками риска
        """
        # Извлекаем признаки
        features = self.feature_extractor.extract_features(
            item_name=item_name,
            current_price=current_price,
            price_history=price_history,
            sales_history=sales_history,
            market_offers=market_offers,
        )

        # Рассчитываем ожидаемую прибыль
        expected_profit_percent = 0.0
        if current_price > 0:
            expected_profit_percent = (
                (expected_price - current_price) / current_price
            ) * 100

        # Оцениваем риск
        risk_score, risk_factors = self._calculate_risk(
            features, expected_profit_percent
        )
        risk_level = self._score_to_risk_level(risk_score)

        # Оцениваем ликвидность
        liquidity_score = self._calculate_liquidity_score(features)

        # Классифицируем сигнал
        signal, signal_probs = self._classify_signal(
            expected_profit_percent=expected_profit_percent,
            risk_score=risk_score,
            liquidity_score=liquidity_score,
            features=features,
        )

        # Рассчитываем рекомендуемый размер позиции
        position_size = self._calculate_position_size(
            current_price=current_price,
            risk_score=risk_score,
            signal=signal,
        )

        # Рассчитываем максимальный возможный убыток
        max_loss = self._calculate_max_loss(features, current_price)

        # Рассчитываем вероятность прибыли
        profit_probability = self._calculate_profit_probability(
            features=features,
            expected_profit_percent=expected_profit_percent,
        )

        # Генерируем обоснование
        reasoning = self._generate_reasoning(
            signal=signal,
            risk_factors=risk_factors,
            expected_profit_percent=expected_profit_percent,
            liquidity_score=liquidity_score,
        )

        return TradeClassification(
            item_name=item_name,
            signal=signal,
            risk_level=risk_level,
            signal_probabilities=signal_probs,
            risk_score=risk_score,
            recommended_position_size=position_size,
            max_loss_percent=max_loss,
            classification_timestamp=datetime.now(UTC),
            reasoning=reasoning,
            expected_profit_percent=expected_profit_percent,
            profit_probability=profit_probability,
        )

    def _calculate_risk(
        self,
        features: PriceFeatures,
        expected_profit: float,
    ) -> tuple[float, list[str]]:
        """Рассчитать риск-скор и факторы риска."""
        risk_score = 0.0
        risk_factors = []

        # Волатильность (0-0.3)
        volatility_risk = min(features.volatility * 1.5, 0.3)
        risk_score += volatility_risk
        if features.volatility > 0.1:
            risk_factors.append(f"High volatility ({features.volatility:.1%})")

        # Низкая ликвидность (0-0.25)
        if features.sales_count_24h < 3:
            liquidity_risk = 0.25
            risk_factors.append("Very low liquidity")
        elif features.sales_count_24h < 10:
            liquidity_risk = 0.15
            risk_factors.append("Low liquidity")
        else:
            liquidity_risk = 0.0
        risk_score += liquidity_risk

        # Нестабильный тренд (0-0.15)
        if features.trend_direction == TrendDirection.VOLATILE:
            risk_score += 0.15
            risk_factors.append("Volatile market trend")
        elif features.trend_direction == TrendDirection.DOWN and expected_profit > 0:
            risk_score += 0.1
            risk_factors.append("Buying agAlgonst downtrend")

        # RSI экстремальные значения (0-0.1)
        if features.rsi > 80 and expected_profit > 0:
            risk_score += 0.1
            risk_factors.append("Overbought RSI (>80)")
        elif features.rsi < 20 and expected_profit < 0:
            risk_score += 0.1
            risk_factors.append("Oversold RSI (<20)")

        # Низкое качество данных (0-0.15)
        data_risk = (1 - features.data_quality_score) * 0.15
        risk_score += data_risk
        if features.data_quality_score < 0.7:
            risk_factors.append("Insufficient data quality")

        # Размер позиции относительно баланса (0-0.15)
        if features.current_price > self.user_balance * 0.5:
            risk_score += 0.15
            risk_factors.append("Large position relative to balance")
        elif features.current_price > self.user_balance * 0.3:
            risk_score += 0.08
            risk_factors.append("Moderate position size")

        return min(risk_score, 1.0), risk_factors

    def _score_to_risk_level(self, score: float) -> RiskLevel:
        """Преобразовать числовой скор в уровень риска."""
        if score < 0.1:
            return RiskLevel.VERY_LOW
        if score < 0.25:
            return RiskLevel.LOW
        if score < 0.4:
            return RiskLevel.MEDIUM
        if score < 0.6:
            return RiskLevel.HIGH
        return RiskLevel.VERY_HIGH

    def _calculate_liquidity_score(self, features: PriceFeatures) -> float:
        """Рассчитать скор ликвидности (0-1)."""
        # Базовый скор по продажам
        if features.avg_sales_per_day >= 10:
            base_score = 1.0
        elif features.avg_sales_per_day >= 5:
            base_score = 0.8
        elif features.avg_sales_per_day >= 2:
            base_score = 0.6
        elif features.avg_sales_per_day >= 1:
            base_score = 0.4
        else:
            base_score = 0.2

        # Корректировка по глубине рынка
        depth_factor = min(features.market_depth / 50, 1.0)

        return base_score * 0.7 + depth_factor * 0.3

    def _classify_signal(
        self,
        expected_profit_percent: float,
        risk_score: float,
        liquidity_score: float,
        features: PriceFeatures,
    ) -> tuple[TradeSignal, dict[str, float]]:
        """Классифицировать сигнал на основе метрик."""
        # Инициализация вероятностей
        probs = {
            "strong_buy": 0.0,
            "buy": 0.0,
            "hold": 0.3,  # Базовая вероятность
            "sell": 0.0,
            "strong_sell": 0.0,
            "skip": 0.0,
        }

        # Проверка на SKIP (высокий риск или низкая ликвидность)
        if risk_score > self.thresholds["max_risk_score"]:
            probs["skip"] = 0.6 + risk_score * 0.4
            return TradeSignal.SKIP, probs

        if liquidity_score < self.thresholds["min_liquidity"]:
            probs["skip"] = 0.5 + (1 - liquidity_score) * 0.3
            return TradeSignal.SKIP, probs

        # Классификация по ожидаемой прибыли
        if expected_profit_percent >= self.thresholds["strong_buy_profit"]:
            probs["strong_buy"] = min(0.9, 0.5 + expected_profit_percent * 0.02)
            probs["buy"] = 1 - probs["strong_buy"] - probs["hold"]
            signal = TradeSignal.STRONG_BUY

        elif expected_profit_percent >= self.thresholds["buy_profit"]:
            probs["buy"] = min(0.8, 0.4 + expected_profit_percent * 0.04)
            probs["strong_buy"] = max(0, probs["buy"] - 0.3)
            probs["hold"] = 1 - probs["buy"] - probs["strong_buy"]
            signal = TradeSignal.BUY

        elif expected_profit_percent <= self.thresholds["strong_sell_profit"]:
            probs["strong_sell"] = min(0.9, 0.5 + abs(expected_profit_percent) * 0.02)
            probs["sell"] = 1 - probs["strong_sell"] - probs["hold"]
            signal = TradeSignal.STRONG_SELL

        elif expected_profit_percent <= self.thresholds["sell_profit"]:
            probs["sell"] = min(0.8, 0.4 + abs(expected_profit_percent) * 0.04)
            probs["strong_sell"] = max(0, probs["sell"] - 0.3)
            probs["hold"] = 1 - probs["sell"] - probs["strong_sell"]
            signal = TradeSignal.SELL

        else:
            # Нет явного сигнала
            probs["hold"] = 0.7
            signal = TradeSignal.HOLD

        # Корректировка по риску
        if risk_score > 0.3:
            risk_penalty = risk_score * 0.3
            for key in ["strong_buy", "buy", "sell", "strong_sell"]:
                probs[key] *= 1 - risk_penalty
            probs["hold"] += risk_penalty

        # Нормализация
        total = sum(probs.values())
        probs = {k: v / total for k, v in probs.items()}

        return signal, probs

    def _calculate_position_size(
        self,
        current_price: float,
        risk_score: float,
        signal: TradeSignal,
    ) -> float:
        """Рассчитать рекомендуемый размер позиции (% от баланса)."""
        max_position = self.thresholds["max_position_percent"]

        # Базовый размер зависит от сигнала
        if signal == TradeSignal.STRONG_BUY:
            base_size = max_position * 0.8
        elif signal == TradeSignal.BUY:
            base_size = max_position * 0.5
        elif signal in {TradeSignal.HOLD, TradeSignal.SKIP}:
            return 0.0
        else:
            base_size = max_position * 0.3

        # Корректировка по риску
        risk_factor = 1 - risk_score
        position_size = base_size * risk_factor

        # Проверка, что позиция не превышает цену предмета
        if self.user_balance > 0:
            max_affordable = (current_price / self.user_balance) * 100
            position_size = min(position_size, max_affordable)

        return max(0.0, min(position_size, max_position))

    def _calculate_max_loss(
        self,
        features: PriceFeatures,
        current_price: float,
    ) -> float:
        """Рассчитать максимальный возможный убыток (%)."""
        # Базовый риск из волатильности
        base_risk = features.volatility * 3  # 3x волатильности

        # Учёт комиссии DMarket (7%)
        commission_risk = 7.0

        # Учёт тренда
        if features.trend_direction == TrendDirection.DOWN:
            trend_risk = 5.0
        elif features.trend_direction == TrendDirection.VOLATILE:
            trend_risk = 3.0
        else:
            trend_risk = 0.0

        total_risk = base_risk * 100 + commission_risk + trend_risk

        return min(total_risk, 50.0)  # Максимум 50% потерь

    def _calculate_profit_probability(
        self,
        features: PriceFeatures,
        expected_profit_percent: float,
    ) -> float:
        """Рассчитать вероятность прибыльной сделки."""
        # Базовая вероятность 50%
        probability = 0.5

        # Корректировка по ожидаемой прибыли
        if expected_profit_percent > 0:
            probability += min(expected_profit_percent * 0.02, 0.25)
        else:
            probability -= min(abs(expected_profit_percent) * 0.02, 0.25)

        # Корректировка по тренду
        if features.trend_direction == TrendDirection.UP:
            probability += 0.1
        elif features.trend_direction == TrendDirection.DOWN:
            probability -= 0.1

        # Корректировка по RSI
        if 40 <= features.rsi <= 60:
            probability += 0.05  # Нейтральная зона - стабильнее
        elif features.rsi > 70 or features.rsi < 30:
            probability -= 0.05  # Экстремальные значения - рискованнее

        # Корректировка по ликвидности
        if features.sales_count_24h >= 10:
            probability += 0.05
        elif features.sales_count_24h < 3:
            probability -= 0.1

        return float(np.clip(probability, 0.1, 0.9))

    def _generate_reasoning(
        self,
        signal: TradeSignal,
        risk_factors: list[str],
        expected_profit_percent: float,
        liquidity_score: float,
    ) -> list[str]:
        """Генерировать обоснование классификации."""
        reasoning = []

        # Основной сигнал
        if signal == TradeSignal.STRONG_BUY:
            reasoning.append(
                f"Strong buy opportunity: {expected_profit_percent:.1f}% expected profit"
            )
        elif signal == TradeSignal.BUY:
            reasoning.append(
                f"Buy opportunity: {expected_profit_percent:.1f}% expected profit"
            )
        elif signal == TradeSignal.STRONG_SELL:
            reasoning.append(
                f"Strong sell signal: {expected_profit_percent:.1f}% expected change"
            )
        elif signal == TradeSignal.SELL:
            reasoning.append(
                f"Sell signal: {expected_profit_percent:.1f}% expected change"
            )
        elif signal == TradeSignal.SKIP:
            reasoning.append("Skip: high risk or low liquidity")
        else:
            reasoning.append("Hold: no clear signal")

        # Ликвидность
        if liquidity_score < 0.3:
            reasoning.append("Warning: very low liquidity")
        elif liquidity_score > 0.8:
            reasoning.append("Good liquidity")

        # Факторы риска
        reasoning.extend(risk_factors)

        # Профиль риска
        reasoning.append(f"Risk tolerance: {self.risk_tolerance}")

        return reasoning

    def batch_classify(
        self,
        items: list[dict[str, Any]],
        predictions: list[Any] | None = None,
    ) -> list[TradeClassification]:
        """Классифицировать список предметов.

        Args:
            items: Список предметов
            predictions: Список прогнозов (опционально)

        Returns:
            Список TradeClassification
        """
        classifications = []

        for i, item in enumerate(items):
            item_name = item.get("title", item.get("name", "unknown"))
            price = item.get("price", {})

            if isinstance(price, dict):
                current_price = float(price.get("USD", 0)) / 100
            else:
                current_price = float(price) / 100 if price else 0.0

            # Ожидаемая цена из прогноза или текущая
            if predictions and i < len(predictions):
                expected_price = predictions[i].predicted_price_24h
            else:
                expected_price = current_price

            classification = self.classify(
                item_name=item_name,
                current_price=current_price,
                expected_price=expected_price,
                price_history=item.get("price_history"),
                sales_history=item.get("sales_history"),
                market_offers=item.get("offers"),
            )
            classifications.append(classification)

        return classifications
