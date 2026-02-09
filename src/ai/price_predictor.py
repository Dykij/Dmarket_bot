"""AI Price Predictor Module.

This module implements machine learning-based price prediction for DMarket items.
It uses RandomForest regression with protection against anomalies and "hallucinations".

Key features:
- LabelEncoder for item name encoding
- RandomForest with min_samples_leaf=5 to prevent overfitting on single outliers
- Z-score filtering for anomaly detection during training
- Prediction guard to reject unrealistic AI outputs (max 40% deviation)

Usage:
    ```python
    predictor = PricePredictor()

    # Train model (requires at least 100 data points)
    result = predictor.train_model("data/market_history.csv")

    # Predict fair price with protection
    fair_price = predictor.predict_with_guard(
        item_name="AK-47 | Redline (Field-Tested)", market_price=10.0, current_float=0.25
    )

    if fair_price and fair_price > market_price:
        print(f"Good deal! Fair price: ${fair_price:.2f}")
    ```
"""

import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Default paths for model and encoder
DEFAULT_MODEL_PATH = "data/price_model.pkl"
DEFAULT_ENCODER_PATH = "data/label_encoder.pkl"
DEFAULT_HISTORY_PATH = "data/market_history.csv"

# Protection thresholds
MAX_PROFIT_DEVIATION = 0.40  # Max 40% profit to prevent hallucinations
MAX_ZSCORE = 3.0  # Z-score threshold for outlier detection
MIN_TRAINING_SAMPLES = 100  # Minimum samples required for training


class PricePredictor:
    """AI-based price predictor with hallucination protection.

    This class implements a RandomForest-based price prediction model
    that learns from historical market data and provides fair price
    estimates for CS:GO/CS2 items.

    The model includes multiple safety mechanisms:
    1. Z-score filtering during training to remove anomalies
    2. min_samples_leaf=5 to prevent overfitting on outliers
    3. Prediction guard limiting profit deviation to 40%
    4. Market price sanity check (AI price must exceed market price for profit)

    Attributes:
        model_path: Path to save/load the trained model
        encoder_path: Path to save/load the label encoder
        model: RandomForestRegressor model (None if not loaded)
        encoder: LabelEncoder for item names (None if not loaded)
        is_trained: Whether the model is trained and ready
    """

    def __init__(
        self,
        model_path: str = DEFAULT_MODEL_PATH,
        encoder_path: str = DEFAULT_ENCODER_PATH,
    ) -> None:
        """Initialize the price predictor.

        Args:
            model_path: Path to save/load the trained model (.pkl)
            encoder_path: Path to save/load the label encoder (.pkl)
        """
        self.model_path = model_path
        self.encoder_path = encoder_path
        self.model: Any = None
        self.encoder: Any = None
        self.is_trained = False

        # Try to load existing model
        self._try_load_model()

    def _try_load_model(self) -> None:
        """Attempt to load existing model and encoder from disk."""
        try:
            import joblib

            if os.path.exists(self.model_path) and os.path.exists(self.encoder_path):
                self.model = joblib.load(self.model_path)
                self.encoder = joblib.load(self.encoder_path)
                self.is_trained = True
                logger.info(
                    "price_predictor_loaded: model_path=%s",
                    self.model_path,
                )
        except ImportError:
            logger.warning(
                "joblib not installed, cannot load model. Install with: pip install joblib"
            )
        except Exception as e:
            logger.warning(
                "price_predictor_load_failed: error=%s",
                e,
            )

    def train_model(
        self,
        history_path: str = DEFAULT_HISTORY_PATH,
        force_retrain: bool = False,
    ) -> str:
        """Train the price prediction model on historical data.

        This method:
        1. Loads historical market data from CSV
        2. Removes anomalies using Z-score filtering
        3. Encodes item names with LabelEncoder
        4. Trains RandomForest with overfitting protection
        5. Saves model and encoder to disk

        Args:
            history_path: Path to market history CSV file
            force_retrain: Force retraining even if model exists

        Returns:
            Status message describing the result

        CSV Format:
            item_name,price,float_value,is_stat_trak
            "AK-47 | Redline (Field-Tested)",12.50,0.25,0
        """
        try:
            import joblib
            import numpy as np
            import pandas as pd
            from scipy import stats
            from sklearn.ensemble import RandomForestRegressor
            from sklearn.preprocessing import LabelEncoder
        except ImportError as e:
            error_msg = (
                f"❌ Missing dependencies: {e}. "
                "Install with: pip install pandas numpy scikit-learn scipy joblib"
            )
            logger.exception(error_msg)
            return error_msg

        # Check if history file exists
        if not os.path.exists(history_path):
            error_msg = f"❌ Нет данных для обучения. Файл не найден: {history_path}"
            logger.error("training_data_not_found: path=%s", history_path)
            return error_msg

        try:
            # Load historical data
            df = pd.read_csv(history_path)

            # Validate minimum samples
            if len(df) < MIN_TRAINING_SAMPLES:
                return (
                    f"⚠️ Недостаточно данных для обучения: {len(df)}/{MIN_TRAINING_SAMPLES} строк. "
                    f"Бот должен накопить данные минимум 48 часов."
                )

            logger.info(
                "training_started: samples_before_cleaning=%d",
                len(df),
            )

            # Validate required columns
            required_columns = {"item_name", "price"}
            if not required_columns.issubset(df.columns):
                missing = required_columns - set(df.columns)
                return f"❌ Отсутствуют обязательные колонки: {missing}"

            # Clean data: remove anomalies using Z-score
            # Only items with price deviation < 3 standard deviations are kept
            original_len = len(df)
            z_scores = np.abs(stats.zscore(df["price"]))
            df = df[z_scores < MAX_ZSCORE]

            removed_count = original_len - len(df)
            if removed_count > 0:
                logger.info(
                    "outliers_removed: removed=%d, remaining=%d",
                    removed_count,
                    len(df),
                )

            # Ensure we still have enough data after cleaning
            if len(df) < MIN_TRAINING_SAMPLES // 2:
                return (
                    f"⚠️ Слишком много выбросов. После очистки осталось {len(df)} строк. "
                    "Попробуйте собрать более качественные данные."
                )

            # Encode item names to numeric IDs
            self.encoder = LabelEncoder()
            df["item_id"] = self.encoder.fit_transform(df["item_name"])

            # Handle optional columns with defaults
            if "float_value" not in df.columns:
                df["float_value"] = 0.5  # Default float

            if "is_stat_trak" not in df.columns:
                df["is_stat_trak"] = 0  # Default: not StatTrak
            else:
                # Convert boolean strings to int (True -> 1, False -> 0)
                df["is_stat_trak"] = df["is_stat_trak"].apply(
                    lambda x: 1 if str(x).lower() in {"true", "1", "yes"} else 0
                )

            # Prepare features and target
            feature_columns = ["item_id", "float_value", "is_stat_trak"]
            X = df[feature_columns].astype(float)
            y = df["price"].astype(float)

            # Train RandomForest with overfitting protection
            # min_samples_leaf=5 prevents the model from memorizing single outliers
            self.model = RandomForestRegressor(
                n_estimators=100,
                min_samples_leaf=5,
                random_state=42,
                n_jobs=-1,  # Use all CPU cores
            )
            self.model.fit(X, y)

            # Create directory if needed
            os.makedirs(os.path.dirname(self.model_path) or ".", exist_ok=True)

            # Save model and encoder
            joblib.dump(self.model, self.model_path)
            joblib.dump(self.encoder, self.encoder_path)

            self.is_trained = True

            unique_items = len(self.encoder.classes_)
            result_msg = (
                f"✅ Модель обучена успешно!\n"
                f"📊 Использовано: {len(df)} строк\n"
                f"📦 Уникальных предметов: {unique_items}\n"
                f"🧹 Удалено выбросов: {removed_count}"
            )

            logger.info(
                "training_completed: samples=%d, unique_items=%d, outliers_removed=%d",
                len(df),
                unique_items,
                removed_count,
            )

            return result_msg

        except Exception as e:
            error_msg = f"❌ Ошибка обучения модели: {e}"
            logger.exception("training_failed: error=%s", e)
            return error_msg

    def predict_with_guard(
        self,
        item_name: str,
        market_price: float,
        current_float: float | None = None,
        is_stat_trak: bool = False,
    ) -> float | None:
        """Predict fair price with hallucination protection.

        This method provides safe price predictions by:
        1. Checking if item is known to the model
        2. Making prediction with RandomForest
        3. Applying sanity checks (max 40% profit deviation)
        4. Returning None for suspicious predictions

        Args:
            item_name: Full item name (e.g., "AK-47 | Redline (Field-Tested)")
            market_price: Current market price in USD
            current_float: Item float value (0.0-1.0), optional
            is_stat_trak: Whether item is StatTrak

        Returns:
            Predicted fair price in USD, or None if:
            - Model not trained
            - Item unknown to model
            - Prediction is suspicious (hallucination detected)
            - Prediction shows no profit opportunity

        Example:
            >>> predictor = PricePredictor()
            >>> fair_price = predictor.predict_with_guard("AK-47 | Redline (FT)", 10.0, 0.25)
            >>> if fair_price:
            ...     profit = fair_price - 10.0
            ...     print(f"Expected profit: ${profit:.2f}")
        """
        try:
            # Check if model is loaded
            if not self.is_trained or self.model is None or self.encoder is None:
                logger.debug("model_not_loaded")
                return None

            # Check if item is known to the model
            if item_name not in self.encoder.classes_:
                logger.debug(
                    "unknown_item: item_name=%s",
                    item_name,
                )
                return None

            # Encode item name
            item_id = self.encoder.transform([item_name])[0]

            # Prepare input features
            import pandas as pd

            float_value = current_float if current_float is not None else 0.5
            stat_trak = 1 if is_stat_trak else 0

            input_df = pd.DataFrame(
                [[item_id, float_value, stat_trak]],
                columns=["item_id", "float_value", "is_stat_trak"],
            )

            # Make prediction
            ai_price = float(self.model.predict(input_df)[0])

            # SAFETY GUARD 1: No profit = no recommendation
            if ai_price <= market_price:
                logger.debug(
                    "no_profit_opportunity: item=%s, market=%.2f, ai=%.2f",
                    item_name,
                    market_price,
                    ai_price,
                )
                return None

            # SAFETY GUARD 2: Hallucination detection
            # If AI predicts > 40% profit, it's likely wrong
            profit_percent = (ai_price - market_price) / market_price
            if profit_percent > MAX_PROFIT_DEVIATION:
                logger.warning(
                    "hallucination_detected: item=%s, market=%.2f, ai=%.2f, profit=%.1f%%",
                    item_name,
                    market_price,
                    ai_price,
                    profit_percent * 100,
                )
                return None

            logger.debug(
                "price_predicted: item=%s, market=%.2f, ai=%.2f, profit=%.1f%%",
                item_name,
                market_price,
                ai_price,
                profit_percent * 100,
            )

            return ai_price

        except Exception as e:
            logger.exception(
                "prediction_failed: item=%s, error=%s",
                item_name,
                e,
            )
            return None

    def get_raw_prediction(
        self,
        item_name: str,
        current_float: float | None = None,
        is_stat_trak: bool = False,
    ) -> float | None:
        """Get raw price prediction without safety guards.

        Use this method only for analysis/debugging.
        For trading decisions, always use predict_with_guard().

        Args:
            item_name: Full item name
            current_float: Item float value
            is_stat_trak: Whether item is StatTrak

        Returns:
            Raw predicted price or None if prediction fails
        """
        try:
            if not self.is_trained or self.model is None or self.encoder is None:
                return None

            if item_name not in self.encoder.classes_:
                return None

            import pandas as pd

            item_id = self.encoder.transform([item_name])[0]
            float_value = current_float if current_float is not None else 0.5
            stat_trak = 1 if is_stat_trak else 0

            input_df = pd.DataFrame(
                [[item_id, float_value, stat_trak]],
                columns=["item_id", "float_value", "is_stat_trak"],
            )

            return float(self.model.predict(input_df)[0])

        except Exception:
            return None

    def get_model_info(self) -> dict[str, Any]:
        """Get information about the current model state.

        Returns:
            Dictionary with model status and statistics
        """
        info: dict[str, Any] = {
            "is_trained": self.is_trained,
            "model_path": self.model_path,
            "encoder_path": self.encoder_path,
            "model_exists": os.path.exists(self.model_path),
            "encoder_exists": os.path.exists(self.encoder_path),
        }

        if self.is_trained and self.encoder is not None:
            info["known_items_count"] = len(self.encoder.classes_)

        if self.is_trained and self.model is not None:
            info["n_estimators"] = self.model.n_estimators
            info["min_samples_leaf"] = self.model.min_samples_leaf

        return info
