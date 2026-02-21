"""Адаптивный прогнозатор цен на основе ML.

Использует ансамбль моделей для прогнозирования цен:
- Gradient Boosting (sklearn) - основная модель
- Ridge Regression - для быстрых прогнозов
- Экспоненциальное сглаживание - для краткосрочных прогнозов

Модели адаптируются к:
- Балансу пользователя (большой/маленький)
- Волатильности рынка
- Типу предмета (дешёвый/дорогой)

Все библиотеки бесплатные (scikit-learn, numpy).
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import Any

import joblib
import numpy as np

from src.ml.feature_extractor import MarketFeatureExtractor, PriceFeatures

logger = logging.getLogger(__name__)

# Constants for model configuration
MIN_TRAINING_SAMPLES = 10
CACHE_TTL_MINUTES = 5
RETRAIN_THRESHOLD_SAMPLES = 100


class PredictionConfidence(StrEnum):
    """Уровень уверенности в прогнозе."""

    VERY_HIGH = "very_high"  # >85% уверенность
    HIGH = "high"  # 70-85%
    MEDIUM = "medium"  # 50-70%
    LOW = "low"  # 30-50%
    VERY_LOW = "very_low"  # <30%


@dataclass
class PricePrediction:
    """Результат прогнозирования цены."""

    item_name: str
    current_price: float
    predicted_price_1h: float
    predicted_price_24h: float
    predicted_price_7d: float

    # Уверенность
    confidence: PredictionConfidence
    confidence_score: float  # 0-1

    # Диапазоны (для учёта неопределённости)
    price_range_1h: tuple[float, float]
    price_range_24h: tuple[float, float]
    price_range_7d: tuple[float, float]

    # Мета-информация
    prediction_timestamp: datetime
    model_version: str

    # Рекомендации
    buy_recommendation: str  # "strong_buy", "buy", "hold", "sell", "strong_sell"
    reasoning: str

    def expected_profit_percent(self, horizon: str = "24h") -> float:
        """Рассчитать ожидаемый профит в процентах."""
        if horizon == "1h":
            predicted = self.predicted_price_1h
        elif horizon == "24h":
            predicted = self.predicted_price_24h
        elif horizon == "7d":
            predicted = self.predicted_price_7d
        else:
            predicted = self.predicted_price_24h

        if self.current_price <= 0:
            return 0.0

        return ((predicted - self.current_price) / self.current_price) * 100


class AdaptivePricePredictor:
    """Адаптивный прогнозатор цен с ансамблем моделей.

    Особенности:
    - Использует только бесплатные библиотеки (sklearn, numpy)
    - Адаптируется к балансу пользователя
    - Обучается на исторических данных
    - Автоматически переобучается при накоплении новых данных
    """

    MODEL_VERSION = "1.1.0"  # Updated for joblib serialization

    def __init__(
        self,
        model_path: str | Path | None = None,
        user_balance: float = 100.0,
    ):
        """Инициализация прогнозатора.

        Args:
            model_path: Путь для сохранения/загрузки модели
            user_balance: Текущий баланс пользователя (USD)
        """
        self.model_path = Path(model_path) if model_path else None
        self.user_balance = user_balance

        # Экстрактор признаков
        self.feature_extractor = MarketFeatureExtractor()

        # Модели (ленивая инициализация)
        self._gradient_boost = None
        self._ridge = None

        # Данные для обучения
        self._training_data_X: list[np.ndarray] = []
        self._training_data_y: list[float] = []
        self._new_samples_count = 0

        # Кэш прогнозов
        self._prediction_cache: dict[str, tuple[datetime, PricePrediction]] = {}
        self._cache_ttl = timedelta(minutes=CACHE_TTL_MINUTES)

        # Загрузка модели, если есть
        if self.model_path and self.model_path.exists():
            self._load_model()

    def _init_models(self):
        """Инициализация ML моделей (ленивая загрузка sklearn)."""
        if self._gradient_boost is not None:
            return

        try:
            from sklearn.ensemble import GradientBoostingRegressor
            from sklearn.linear_model import Ridge

            # Gradient Boosting - основная модель
            self._gradient_boost = GradientBoostingRegressor(
                n_estimators=50,
                max_depth=3,
                learning_rate=0.1,
                min_samples_split=5,
                min_samples_leaf=2,
                random_state=42,
            )

            # Ridge Regression - быстрая модель для fallback
            self._ridge = Ridge(alpha=1.0)

            logger.info("ML models initialized successfully")

        except ImportError as e:
            logger.warning(f"sklearn not available, using fallback: {e}")
            self._gradient_boost = None
            self._ridge = None

    def set_user_balance(self, balance: float):
        """Установить баланс пользователя для адаптации стратегии.

        Args:
            balance: Текущий баланс (USD)
        """
        self.user_balance = max(0.0, balance)
        logger.info(f"User balance updated to ${balance:.2f}")

    def predict(
        self,
        item_name: str,
        current_price: float,
        price_history: list[tuple[datetime, float]] | None = None,
        sales_history: list[dict[str, Any]] | None = None,
        market_offers: list[dict[str, Any]] | None = None,
        use_cache: bool = True,
    ) -> PricePrediction:
        """Прогнозировать будущую цену предмета.

        Args:
            item_name: Название предмета
            current_price: Текущая цена
            price_history: История цен
            sales_history: История продаж
            market_offers: Текущие предложения
            use_cache: Использовать кэш

        Returns:
            PricePrediction с прогнозами и рекомендациями
        """
        # Проверяем кэш
        cache_key = f"{item_name}:{current_price:.2f}"
        if use_cache and cache_key in self._prediction_cache:
            cached_time, cached_pred = self._prediction_cache[cache_key]
            if datetime.now(UTC) - cached_time < self._cache_ttl:
                return cached_pred

        # Извлекаем признаки
        features = self.feature_extractor.extract_features(
            item_name=item_name,
            current_price=current_price,
            price_history=price_history,
            sales_history=sales_history,
            market_offers=market_offers,
        )

        # Прогнозирование
        prediction = self._make_prediction(item_name, features)

        # Кэшируем результат
        self._prediction_cache[cache_key] = (datetime.now(UTC), prediction)

        return prediction

    def _make_prediction(
        self,
        item_name: str,
        features: PriceFeatures,
    ) -> PricePrediction:
        """Выполнить прогнозирование на основе признаков."""
        current_price = features.current_price

        # Пробуем использовать ML модели
        if self._has_trained_models():
            predicted_1h, std_1h = self._ml_predict(features, horizon_hours=1)
            predicted_24h, std_24h = self._ml_predict(features, horizon_hours=24)
            predicted_7d, std_7d = self._ml_predict(features, horizon_hours=168)
        else:
            # Fallback: статистические методы
            predicted_1h, std_1h = self._statistical_predict(features, horizon_hours=1)
            predicted_24h, std_24h = self._statistical_predict(
                features, horizon_hours=24
            )
            predicted_7d, std_7d = self._statistical_predict(
                features, horizon_hours=168
            )

        # Рассчитываем уверенность
        confidence_score = self._calculate_confidence(
            features, std_24h / current_price if current_price > 0 else 1.0
        )
        confidence = self._score_to_confidence(confidence_score)

        # Рассчитываем диапазоны (±1 std)
        price_range_1h = (max(0, predicted_1h - std_1h), predicted_1h + std_1h)
        price_range_24h = (max(0, predicted_24h - std_24h), predicted_24h + std_24h)
        price_range_7d = (max(0, predicted_7d - std_7d), predicted_7d + std_7d)

        # Генерируем рекомендацию с учётом баланса
        buy_recommendation, reasoning = self._generate_recommendation(
            current_price=current_price,
            predicted_24h=predicted_24h,
            confidence_score=confidence_score,
            features=features,
        )

        return PricePrediction(
            item_name=item_name,
            current_price=current_price,
            predicted_price_1h=predicted_1h,
            predicted_price_24h=predicted_24h,
            predicted_price_7d=predicted_7d,
            confidence=confidence,
            confidence_score=confidence_score,
            price_range_1h=price_range_1h,
            price_range_24h=price_range_24h,
            price_range_7d=price_range_7d,
            prediction_timestamp=datetime.now(UTC),
            model_version=self.MODEL_VERSION,
            buy_recommendation=buy_recommendation,
            reasoning=reasoning,
        )

    def _has_trained_models(self) -> bool:
        """Проверить, есть ли обученные модели."""
        if self._gradient_boost is None:
            return False
        try:
            # Проверяем, что модель обучена
            return hasattr(self._gradient_boost, "n_estimators_")
        except (AttributeError, TypeError):
            return False

    def _ml_predict(
        self,
        features: PriceFeatures,
        horizon_hours: int,
    ) -> tuple[float, float]:
        """Прогноз с использованием ML моделей."""
        X = features.to_array().reshape(1, -1)

        # Gradient Boosting prediction
        try:
            gb_pred = self._gradient_boost.predict(X)[0]
        except Exception:
            gb_pred = features.current_price

        # Ridge prediction
        try:
            ridge_pred = self._ridge.predict(X)[0]
        except Exception:
            ridge_pred = features.current_price

        # Ансамбль: взвешенное среднее
        prediction = 0.7 * gb_pred + 0.3 * ridge_pred

        # Масштабирование по горизонту
        if horizon_hours in {1, 24}:
            scale = 1.0
        else:  # 7 days
            scale = 1.2  # Больше неопределённости

        # Стандартное отклонение (оценка)
        std = abs(gb_pred - ridge_pred) * scale

        return float(prediction), float(std)

    def _statistical_predict(
        self,
        features: PriceFeatures,
        horizon_hours: int,
    ) -> tuple[float, float]:
        """Статистический прогноз без ML (fallback)."""
        current_price = features.current_price

        # Экспоненциальное сглаживание на основе трендов
        # Учитываем: изменение за 24h, momentum, RSI

        # Базовый прогноз: продолжение текущего тренда
        hourly_change = features.price_change_24h / 24  # % в час
        trend_factor = 1 + (hourly_change * horizon_hours / 100)

        # Коррекция по RSI (mean reversion)
        if features.rsi > 70:
            # Перекуплен - ожидаем падение
            rsi_factor = 0.98
        elif features.rsi < 30:
            # Перепродан - ожидаем рост
            rsi_factor = 1.02
        else:
            rsi_factor = 1.0

        # Коррекция по momentum
        momentum_factor = 1 + (features.momentum * 0.001)

        # Итоговый прогноз
        prediction = current_price * trend_factor * rsi_factor * momentum_factor

        # Стандартное отклонение на основе волатильности
        base_std = current_price * max(features.volatility, 0.02)
        horizon_multiplier = 1 + (horizon_hours / 24) * 0.5
        std = base_std * horizon_multiplier

        return float(prediction), float(std)

    def _calculate_confidence(
        self,
        features: PriceFeatures,
        relative_std: float,
    ) -> float:
        """Рассчитать уверенность в прогнозе (0-1)."""
        confidence = 1.0

        # Снижаем уверенность при высокой волатильности
        if features.volatility > 0.2:
            confidence *= 0.6
        elif features.volatility > 0.1:
            confidence *= 0.8

        # Снижаем при низком качестве данных
        confidence *= features.data_quality_score

        # Снижаем при большом std относительно цены
        if relative_std > 0.2:
            confidence *= 0.5
        elif relative_std > 0.1:
            confidence *= 0.7

        # Повышаем при хорошей ликвидности
        if features.sales_count_24h > 10:
            confidence *= 1.1
        elif features.sales_count_24h < 2:
            confidence *= 0.8

        return float(np.clip(confidence, 0.0, 1.0))

    def _score_to_confidence(self, score: float) -> PredictionConfidence:
        """Преобразовать числовую уверенность в категорию."""
        if score >= 0.85:
            return PredictionConfidence.VERY_HIGH
        if score >= 0.70:
            return PredictionConfidence.HIGH
        if score >= 0.50:
            return PredictionConfidence.MEDIUM
        if score >= 0.30:
            return PredictionConfidence.LOW
        return PredictionConfidence.VERY_LOW

    def _generate_recommendation(
        self,
        current_price: float,
        predicted_24h: float,
        confidence_score: float,
        features: PriceFeatures,
    ) -> tuple[str, str]:
        """Генерировать рекомендацию с учётом баланса пользователя."""
        if current_price <= 0:
            return "hold", "Invalid price data"

        # Ожидаемое изменение
        expected_change = ((predicted_24h - current_price) / current_price) * 100

        # Адаптация к балансу: при маленьком балансе - консервативнее
        balance_factor = self._get_balance_factor()

        # Пороги для рекомендаций (адаптивные)
        strong_buy_threshold = 8.0 * balance_factor  # %
        buy_threshold = 5.0 * balance_factor
        sell_threshold = -5.0 * balance_factor
        strong_sell_threshold = -8.0 * balance_factor

        # Проверяем, можем ли позволить покупку
        can_afford = current_price <= self.user_balance * 0.3  # Не более 30% баланса

        reasoning_parts = []

        if expected_change >= strong_buy_threshold and confidence_score >= 0.6:
            if can_afford:
                recommendation = "strong_buy"
                reasoning_parts.extend(
                    (
                        f"Expected growth: {expected_change:.1f}%",
                        f"Confidence: {confidence_score:.0%}",
                    )
                )
            else:
                recommendation = "buy"
                reasoning_parts.append("Strong signal but exceeds position size limit")
        elif expected_change >= buy_threshold and confidence_score >= 0.5:
            if can_afford:
                recommendation = "buy"
                reasoning_parts.append(f"Expected growth: {expected_change:.1f}%")
            else:
                recommendation = "hold"
                reasoning_parts.append("Good signal but exceeds budget")
        elif expected_change <= strong_sell_threshold and confidence_score >= 0.6:
            recommendation = "strong_sell"
            reasoning_parts.append(f"Expected drop: {expected_change:.1f}%")
        elif expected_change <= sell_threshold and confidence_score >= 0.5:
            recommendation = "sell"
            reasoning_parts.append(f"Expected decline: {expected_change:.1f}%")
        else:
            recommendation = "hold"
            reasoning_parts.append("No clear signal")

        # Добавляем контекст по балансу
        if self.user_balance < 50:
            reasoning_parts.append("Low balance: conservative mode")
        elif self.user_balance > 500:
            reasoning_parts.append("High balance: diversification recommended")

        # Добавляем рыночный контекст
        if features.is_weekend:
            reasoning_parts.append("Weekend: lower liquidity expected")
        if not features.is_peak_hours:
            reasoning_parts.append("Off-peak hours")

        return recommendation, "; ".join(reasoning_parts)

    def _get_balance_factor(self) -> float:
        """Получить фактор адаптации к балансу.

        Маленький баланс → более консервативные пороги (factor > 1)
        Большой баланс → более агрессивные пороги (factor < 1)
        """
        if self.user_balance < 50:
            return 1.5  # Очень консервативно
        if self.user_balance < 100:
            return 1.3
        if self.user_balance < 300:
            return 1.0  # Стандартно
        if self.user_balance < 500:
            return 0.9
        return 0.8  # Более агрессивно

    def add_training_example(
        self,
        features: PriceFeatures,
        actual_future_price: float,
    ) -> None:
        """Добавить пример для обучения модели.

        Args:
            features: Признаки на момент прогноза
            actual_future_price: Реальная цена после horizon
        """
        X = features.to_array()
        y = actual_future_price

        self._training_data_X.append(X)
        self._training_data_y.append(y)
        self._new_samples_count += 1

        # Автоматическое переобучение
        if self._new_samples_count >= RETRAIN_THRESHOLD_SAMPLES:
            self.train()

    def train(self, force: bool = False) -> None:
        """Обучить модели на накопленных данных.

        Args:
            force: Принудительное обучение даже при малом количестве данных
        """
        if len(self._training_data_X) < MIN_TRAINING_SAMPLES and not force:
            logger.warning(
                f"Not enough training data (minimum {MIN_TRAINING_SAMPLES} samples)"
            )
            return

        self._init_models()

        if self._gradient_boost is None:
            logger.warning("ML models not available")
            return

        X = np.array(self._training_data_X)
        y = np.array(self._training_data_y)

        try:
            # Обучаем модели
            self._gradient_boost.fit(X, y)
            self._ridge.fit(X, y)

            self._new_samples_count = 0
            logger.info(f"Models trained on {len(X)} samples")

            # Сохраняем модель
            if self.model_path:
                self._save_model()

        except Exception as e:
            logger.exception(f"Training failed: {e}")

    def _save_model(self) -> None:
        """Сохранить модели на диск.

        Uses joblib for safer and more efficient ML model serialization.
        """
        if not self.model_path:
            return

        try:
            self.model_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "gradient_boost": self._gradient_boost,
                "ridge": self._ridge,
                "training_data_X": self._training_data_X,
                "training_data_y": self._training_data_y,
                "version": self.MODEL_VERSION,
            }
            joblib.dump(data, self.model_path)
            logger.info(f"Model saved to {self.model_path}")
        except Exception as e:
            logger.exception(f"Failed to save model: {e}")

    def _load_model(self) -> None:
        """Загрузить модели с диска.

        Uses joblib for safer ML model deserialization.
        """
        if not self.model_path or not self.model_path.exists():
            return

        try:
            data = joblib.load(self.model_path)

            self._gradient_boost = data.get("gradient_boost")
            self._ridge = data.get("ridge")
            self._training_data_X = data.get("training_data_X", [])
            self._training_data_y = data.get("training_data_y", [])

            logger.info(f"Model loaded from {self.model_path}")
        except Exception as e:
            logger.exception(f"Failed to load model: {e}")

    def batch_predict(
        self,
        items: list[dict[str, Any]],
    ) -> list[PricePrediction]:
        """Прогнозировать для списка предметов.

        Args:
            items: Список предметов с данными

        Returns:
            Список PricePrediction
        """
        predictions = []

        for item in items:
            item_name = item.get("title", item.get("name", "unknown"))
            price = item.get("price", {})

            if isinstance(price, dict):
                current_price = float(price.get("USD", 0)) / 100
            else:
                current_price = float(price) / 100 if price else 0.0

            prediction = self.predict(
                item_name=item_name,
                current_price=current_price,
                price_history=item.get("price_history"),
                sales_history=item.get("sales_history"),
                market_offers=item.get("offers"),
            )
            predictions.append(prediction)

        return predictions
