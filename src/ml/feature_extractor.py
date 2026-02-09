"""Извлечение признаков из рыночных данных для ML моделей.

Этот модуль извлекает числовые признаки из данных рынка DMarket
для использования в ML моделях прогнозирования.
"""

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class TrendDirection(StrEnum):
    """Направление тренда цены."""

    UP = "up"
    DOWN = "down"
    STABLE = "stable"
    VOLATILE = "volatile"


@dataclass
class PriceFeatures:
    """Извлечённые признаки для ML модели."""

    # Ценовые признаки
    current_price: float
    price_mean_7d: float = 0.0
    price_std_7d: float = 0.0
    price_min_7d: float = 0.0
    price_max_7d: float = 0.0

    # Признаки изменения цены
    price_change_1h: float = 0.0
    price_change_24h: float = 0.0
    price_change_7d: float = 0.0

    # Технические индикаторы
    rsi: float = 50.0  # Relative Strength Index (0-100)
    volatility: float = 0.0  # Стандартное отклонение / среднее
    momentum: float = 0.0  # Скорость изменения

    # Ликвидность
    sales_count_24h: int = 0
    sales_count_7d: int = 0
    avg_sales_per_day: float = 0.0

    # Сезонность
    hour_of_day: int = 0  # 0-23
    day_of_week: int = 0  # 0-6 (Monday-Sunday)
    is_weekend: bool = False
    is_peak_hours: bool = False  # 14:00-21:00 UTC

    # Рыночные условия
    trend_direction: TrendDirection = TrendDirection.STABLE
    market_depth: float = 0.0  # Количество предложений
    competition_level: float = 0.0  # Насколько много конкурентов

    # Мета-признаки
    data_quality_score: float = 1.0  # 0-1, насколько полные данные
    feature_timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_array(self) -> np.ndarray:
        """Преобразовать признаки в numpy массив для ML модели."""
        return np.array([
            self.current_price,
            self.price_mean_7d,
            self.price_std_7d,
            self.price_change_1h,
            self.price_change_24h,
            self.price_change_7d,
            self.rsi,
            self.volatility,
            self.momentum,
            self.sales_count_24h,
            self.avg_sales_per_day,
            self.hour_of_day,
            self.day_of_week,
            1.0 if self.is_weekend else 0.0,
            1.0 if self.is_peak_hours else 0.0,
            self._trend_to_numeric(),
            self.market_depth,
            self.competition_level,
        ], dtype=np.float64)

    def _trend_to_numeric(self) -> float:
        """Преобразовать тренд в число."""
        trend_map = {
            TrendDirection.UP: 1.0,
            TrendDirection.DOWN: -1.0,
            TrendDirection.STABLE: 0.0,
            TrendDirection.VOLATILE: 0.5,
        }
        return trend_map.get(self.trend_direction, 0.0)

    @classmethod
    def feature_names(cls) -> list[str]:
        """Получить список названий признаков."""
        return [
            "current_price",
            "price_mean_7d",
            "price_std_7d",
            "price_change_1h",
            "price_change_24h",
            "price_change_7d",
            "rsi",
            "volatility",
            "momentum",
            "sales_count_24h",
            "avg_sales_per_day",
            "hour_of_day",
            "day_of_week",
            "is_weekend",
            "is_peak_hours",
            "trend_direction",
            "market_depth",
            "competition_level",
        ]


class MarketFeatureExtractor:
    """Извлекает признаки из рыночных данных для ML моделей.

    Attributes:
        PEAK_HOURS_START: Начало пиковых часов торговли (UTC).
        PEAK_HOURS_END: Конец пиковых часов торговли (UTC).
        RSI_PERIOD: Период для расчета RSI индикатора.
    """

    # Пиковые часы торговли (UTC)
    PEAK_HOURS_START = 14
    PEAK_HOURS_END = 21

    # RSI параметры
    RSI_PERIOD = 14

    def __init__(self) -> None:
        """Инициализация экстрактора признаков."""
        self._price_cache: dict[str, list[tuple[datetime, float]]] = {}
        self._sales_cache: dict[str, list[dict[str, Any]]] = {}

    def extract_features(
        self,
        item_name: str,
        current_price: float,
        price_history: list[tuple[datetime, float]] | None = None,
        sales_history: list[dict[str, Any]] | None = None,
        market_offers: list[dict[str, Any]] | None = None,
    ) -> PriceFeatures:
        """Извлечь признаки для предмета.

        Args:
            item_name: Название предмета
            current_price: Текущая цена
            price_history: История цен [(timestamp, price), ...]
            sales_history: История продаж
            market_offers: Текущие предложения на рынке

        Returns:
            PriceFeatures с извлечёнными признаками
        """
        features = PriceFeatures(current_price=current_price)

        # Временные признаки
        now = datetime.now(UTC)
        features.hour_of_day = now.hour
        features.day_of_week = now.weekday()
        features.is_weekend = features.day_of_week >= 5
        features.is_peak_hours = (
            self.PEAK_HOURS_START <= features.hour_of_day < self.PEAK_HOURS_END
        )

        # Обработка истории цен
        if price_history and len(price_history) > 0:
            features = self._extract_price_features(features, price_history, now)
        else:
            features.data_quality_score *= 0.5

        # Обработка истории продаж
        if sales_history and len(sales_history) > 0:
            features = self._extract_sales_features(features, sales_history, now)
        else:
            features.data_quality_score *= 0.7

        # Обработка предложений рынка
        if market_offers and len(market_offers) > 0:
            features = self._extract_market_features(features, market_offers)
        else:
            features.data_quality_score *= 0.8

        return features

    def _extract_price_features(
        self,
        features: PriceFeatures,
        price_history: list[tuple[datetime, float]],
        now: datetime,
    ) -> PriceFeatures:
        """Извлечь ценовые признаки из истории."""
        # Фильтруем данные за последние 7 дней
        cutoff_7d = now - timedelta(days=7)
        cutoff_24h = now - timedelta(hours=24)
        cutoff_1h = now - timedelta(hours=1)

        prices_7d = [p for ts, p in price_history if ts >= cutoff_7d]
        prices_24h = [p for ts, p in price_history if ts >= cutoff_24h]
        prices_1h = [p for ts, p in price_history if ts >= cutoff_1h]

        if prices_7d:
            features.price_mean_7d = np.mean(prices_7d)
            features.price_std_7d = np.std(prices_7d) if len(prices_7d) > 1 else 0.0
            features.price_min_7d = min(prices_7d)
            features.price_max_7d = max(prices_7d)

            # Волатильность
            if features.price_mean_7d > 0:
                features.volatility = features.price_std_7d / features.price_mean_7d

        # Изменение цены
        if prices_7d and len(prices_7d) >= 2:
            first_price = prices_7d[0]
            if first_price > 0:
                features.price_change_7d = (
                    (features.current_price - first_price) / first_price
                ) * 100

        if prices_24h and len(prices_24h) >= 2:
            first_price = prices_24h[0]
            if first_price > 0:
                features.price_change_24h = (
                    (features.current_price - first_price) / first_price
                ) * 100

        if prices_1h and len(prices_1h) >= 2:
            first_price = prices_1h[0]
            if first_price > 0:
                features.price_change_1h = (
                    (features.current_price - first_price) / first_price
                ) * 100

        # RSI
        if len(prices_7d) >= self.RSI_PERIOD:
            features.rsi = self._calculate_rsi(prices_7d)

        # Momentum
        if len(prices_24h) >= 2:
            features.momentum = self._calculate_momentum(prices_24h)

        # Определение тренда
        features.trend_direction = self._determine_trend(
            features.price_change_7d,
            features.volatility,
        )

        return features

    def _extract_sales_features(
        self,
        features: PriceFeatures,
        sales_history: list[dict[str, Any]],
        now: datetime,
    ) -> PriceFeatures:
        """Извлечь признаки из истории продаж."""
        cutoff_24h = now - timedelta(hours=24)
        cutoff_7d = now - timedelta(days=7)

        # Парсинг дат продаж
        sales_24h = 0
        sales_7d = 0

        for sale in sales_history:
            sale_time = sale.get("timestamp") or sale.get("date")
            if isinstance(sale_time, str):
                try:
                    sale_time = datetime.fromisoformat(sale_time)
                except (ValueError, TypeError):
                    continue
            elif isinstance(sale_time, (int, float)):
                sale_time = datetime.fromtimestamp(sale_time, tz=UTC)

            if sale_time and sale_time >= cutoff_7d:
                sales_7d += 1
                if sale_time >= cutoff_24h:
                    sales_24h += 1

        features.sales_count_24h = sales_24h
        features.sales_count_7d = sales_7d
        features.avg_sales_per_day = sales_7d / 7.0 if sales_7d > 0 else 0.0

        return features

    def _extract_market_features(
        self,
        features: PriceFeatures,
        market_offers: list[dict[str, Any]],
    ) -> PriceFeatures:
        """Извлечь признаки из текущих предложений."""
        features.market_depth = float(len(market_offers))

        # Конкуренция - сколько предложений близко к текущей цене (±5%)
        price_range_low = features.current_price * 0.95
        price_range_high = features.current_price * 1.05

        competitive_offers = 0
        for offer in market_offers:
            offer_price = offer.get("price", {})
            if isinstance(offer_price, dict):
                price = float(offer_price.get("USD", 0)) / 100  # Центы в доллары
            else:
                price = float(offer_price) / 100 if offer_price else 0

            if price_range_low <= price <= price_range_high:
                competitive_offers += 1

        if len(market_offers) > 0:
            features.competition_level = competitive_offers / len(market_offers)

        return features

    def _calculate_rsi(self, prices: list[float]) -> float:
        """Рассчитать RSI (Relative Strength Index)."""
        if len(prices) < 2:
            return 50.0

        # Вычисляем изменения цен
        changes = np.diff(prices)

        # Разделяем на gains и losses
        gains = np.maximum(changes, 0)
        losses = np.abs(np.minimum(changes, 0))

        # Среднее значение за период
        period = min(self.RSI_PERIOD, len(changes))
        avg_gain = np.mean(gains[-period:]) if len(gains) >= period else np.mean(gains)
        avg_loss = np.mean(losses[-period:]) if len(losses) >= period else np.mean(losses)

        if avg_loss == 0:
            return 100.0 if avg_gain > 0 else 50.0

        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))

        return float(np.clip(rsi, 0, 100))

    def _calculate_momentum(self, prices: list[float]) -> float:
        """Рассчитать momentum (скорость изменения цены)."""
        if len(prices) < 2:
            return 0.0

        # Momentum = (текущая цена - цена N периодов назад) / цена N периодов назад
        period = min(10, len(prices) - 1)
        old_price = prices[-(period + 1)]
        current_price = prices[-1]

        if old_price == 0:
            return 0.0

        return ((current_price - old_price) / old_price) * 100

    def _determine_trend(
        self,
        price_change_7d: float,
        volatility: float,
    ) -> TrendDirection:
        """Определить направление тренда."""
        # Высокая волатильность
        if volatility > 0.15:
            return TrendDirection.VOLATILE

        # Определяем по изменению цены за 7 дней
        if price_change_7d > 5:
            return TrendDirection.UP
        if price_change_7d < -5:
            return TrendDirection.DOWN
        return TrendDirection.STABLE

    def batch_extract(
        self,
        items: list[dict[str, Any]],
    ) -> list[PriceFeatures]:
        """Извлечь признаки для списка предметов.

        Args:
            items: Список предметов с данными

        Returns:
            Список PriceFeatures
        """
        features_list = []

        for item in items:
            item_name = item.get("title", item.get("name", "unknown"))
            price = item.get("price", {})

            if isinstance(price, dict):
                current_price = float(price.get("USD", 0)) / 100
            else:
                current_price = float(price) / 100 if price else 0.0

            features = self.extract_features(
                item_name=item_name,
                current_price=current_price,
                price_history=item.get("price_history"),
                sales_history=item.get("sales_history"),
                market_offers=item.get("offers"),
            )
            features_list.append(features)

        return features_list
