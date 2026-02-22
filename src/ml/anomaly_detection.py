"""Anomaly Detection Module for Market Data.

Provides automatic detection of:
- Suspicious transactions (price manipulation, errors)
- API errors and unusual responses
- Market anomalies (sudden price spikes, volume changes)
- User behavior anomalies

Uses statistical methods and isolation forests for detection.

Usage:
    ```python
    from src.ml.anomaly_detection import AnomalyDetector

    detector = AnomalyDetector()

    # Check transaction
    is_anomaly, score, reason = detector.check_transaction(
        item_price=100.0,
        market_avg=95.0,
        historical_prices=[90, 92, 94, 95, 96]
    )

    # Detect price manipulation
    result = detector.detect_price_manipulation(prices, volumes)
    ```

Created: January 10, 2026
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import numpy as np

logger = logging.getLogger(__name__)


class AnomalyType(StrEnum):
    """Types of anomalies."""

    PRICE_SPIKE = "price_spike"
    PRICE_DROP = "price_drop"
    VOLUME_ANOMALY = "volume_anomaly"
    SUSPICIOUS_TRANSACTION = "suspicious_transaction"
    API_ERROR = "api_error"
    MANIPULATION_SUSPECTED = "manipulation_suspected"
    UNUSUAL_PATTERN = "unusual_pattern"
    DATA_QUALITY_ISSUE = "data_quality_issue"


class AnomalySeverity(StrEnum):
    """Anomaly severity levels."""

    CRITICAL = "critical"  # Requires immediate action
    HIGH = "high"  # Should be investigated
    MEDIUM = "medium"  # Worth noting
    LOW = "low"  # Informational
    INFO = "info"  # For logging purposes


@dataclass
class AnomalyResult:
    """Result of anomaly detection."""

    is_anomaly: bool
    anomaly_type: AnomalyType | None = None
    severity: AnomalySeverity = AnomalySeverity.INFO
    score: float = 0.0  # 0-1, higher = more anomalous
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    detected_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "is_anomaly": self.is_anomaly,
            "type": self.anomaly_type.value if self.anomaly_type else None,
            "severity": self.severity.value,
            "score": round(self.score, 4),
            "reason": self.reason,
            "details": self.details,
            "detected_at": self.detected_at.isoformat(),
        }


@dataclass
class PriceAnomaly:
    """Price-specific anomaly details."""

    item_name: str
    current_price: float
    expected_price: float
    deviation_percent: float
    z_score: float
    anomaly_result: AnomalyResult


@dataclass
class TransactionAnomaly:
    """Transaction anomaly details."""

    transaction_id: str | None
    price: float
    quantity: int
    total_value: float
    anomaly_result: AnomalyResult
    recommendations: list[str] = field(default_factory=list)


class AnomalyDetector:
    """Anomaly detection engine for market data.

    Uses multiple detection methods:
    - Statistical methods (z-score, IQR)
    - Isolation Forest (if sklearn avAlgolable)
    - Rule-based detection
    - Pattern matching

    Attributes:
        z_score_threshold: Z-score threshold for anomaly detection.
        iqr_multiplier: IQR multiplier for outlier detection.
        price_change_threshold: Max allowed price change (fraction).
        min_history_length: Minimum history length for analysis.
    """

    # Default thresholds
    DEFAULT_Z_SCORE_THRESHOLD = 3.0
    DEFAULT_IQR_MULTIPLIER = 1.5
    DEFAULT_PRICE_CHANGE_THRESHOLD = 0.3  # 30%
    DEFAULT_MIN_HISTORY_LENGTH = 10
    MAX_ANOMALY_HISTORY = 1000

    # Data drift detection constants
    DRIFT_MIN_SAMPLES = 20  # Minimum samples for drift detection
    DRIFT_WEIGHT_MEAN_SHIFT = 0.4  # Weight for mean shift in drift score
    DRIFT_WEIGHT_VARIANCE = 0.3  # Weight for variance change in drift score
    DRIFT_WEIGHT_QUANTILE = 0.3  # Weight for quantile shift in drift score
    DRIFT_MEAN_SHIFT_SCALE = 2.0  # Scaling factor for normalized mean shift
    DRIFT_QUANTILE_SCALE = 5.0  # Scaling factor for quantile difference

    def __init__(
        self,
        z_score_threshold: float = DEFAULT_Z_SCORE_THRESHOLD,
        iqr_multiplier: float = DEFAULT_IQR_MULTIPLIER,
        price_change_threshold: float = DEFAULT_PRICE_CHANGE_THRESHOLD,
        min_history_length: int = DEFAULT_MIN_HISTORY_LENGTH,
    ) -> None:
        """Initialize anomaly detector.

        Args:
            z_score_threshold: Z-score threshold for anomaly detection
            iqr_multiplier: IQR multiplier for outlier detection
            price_change_threshold: Max allowed price change (fraction)
            min_history_length: Minimum history length for analysis
        """
        self.z_score_threshold = z_score_threshold
        self.iqr_multiplier = iqr_multiplier
        self.price_change_threshold = price_change_threshold
        self.min_history_length = min_history_length

        # Isolation forest model (lazy initialization)
        self._isolation_forest = None

        # Historical anomalies for pattern learning
        self._anomaly_history: list[AnomalyResult] = []

    def _init_isolation_forest(self) -> bool:
        """Initialize Isolation Forest model.

        Returns:
            True if initialization succeeded, False otherwise.
        """
        if self._isolation_forest is not None:
            return True

        try:
            from sklearn.ensemble import IsolationForest

            self._isolation_forest = IsolationForest(
                n_estimators=100,
                contamination=0.1,
                random_state=42,
                n_jobs=-1,
            )
            logger.info("Isolation Forest initialized")
            return True
        except ImportError:
            logger.warning("sklearn not avAlgolable, using statistical methods only")
            return False

    def check_price_anomaly(
        self,
        current_price: float,
        historical_prices: list[float],
        item_name: str = "",
    ) -> AnomalyResult:
        """Check if price is anomalous.

        Args:
            current_price: Current price to check
            historical_prices: List of historical prices
            item_name: Item name for context

        Returns:
            AnomalyResult
        """
        if len(historical_prices) < self.min_history_length:
            return AnomalyResult(
                is_anomaly=False,
                reason="Insufficient historical data",
                score=0.0,
            )

        prices = np.array(historical_prices)

        # Calculate statistics
        mean_price = np.mean(prices)
        std_price = np.std(prices)

        # Z-score
        if std_price > 0:
            z_score = abs(current_price - mean_price) / std_price
        else:
            z_score = 0.0

        # IQR method
        q1, q3 = np.percentile(prices, [25, 75])
        iqr = q3 - q1
        lower_bound = q1 - self.iqr_multiplier * iqr
        upper_bound = q3 + self.iqr_multiplier * iqr

        # Price change from last
        if len(historical_prices) > 0:
            last_price = historical_prices[-1]
            price_change = (
                abs(current_price - last_price) / last_price if last_price > 0 else 0
            )
        else:
            price_change = 0

        # Determine anomaly
        is_anomaly = False
        anomaly_type = None
        severity = AnomalySeverity.INFO
        reasons = []

        # Check z-score
        if z_score > self.z_score_threshold:
            is_anomaly = True
            reasons.append(
                f"Z-score {z_score:.2f} exceeds threshold {self.z_score_threshold}"
            )

        # Check IQR bounds
        if current_price < lower_bound or current_price > upper_bound:
            is_anomaly = True
            reasons.append(
                f"Price ${current_price:.2f} outside IQR bounds [${lower_bound:.2f}, ${upper_bound:.2f}]"
            )

        # Check sudden change
        if price_change > self.price_change_threshold:
            is_anomaly = True
            reasons.append(
                f"Price change {price_change:.1%} exceeds threshold {self.price_change_threshold:.1%}"
            )

        # Determine type and severity
        if is_anomaly:
            if current_price > upper_bound:
                anomaly_type = AnomalyType.PRICE_SPIKE
                severity = (
                    AnomalySeverity.HIGH if z_score > 4 else AnomalySeverity.MEDIUM
                )
            elif current_price < lower_bound:
                anomaly_type = AnomalyType.PRICE_DROP
                severity = (
                    AnomalySeverity.HIGH if z_score > 4 else AnomalySeverity.MEDIUM
                )
            else:
                anomaly_type = AnomalyType.UNUSUAL_PATTERN
                severity = AnomalySeverity.LOW

        # Calculate anomaly score (0-1)
        score = min(1.0, z_score / (self.z_score_threshold * 2))

        result = AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_type=anomaly_type,
            severity=severity,
            score=score,
            reason="; ".join(reasons) if reasons else "Price within normal range",
            details={
                "item_name": item_name,
                "current_price": current_price,
                "mean_price": round(mean_price, 2),
                "std_price": round(std_price, 2),
                "z_score": round(z_score, 2),
                "iqr_bounds": [round(lower_bound, 2), round(upper_bound, 2)],
                "price_change": round(price_change, 4),
            },
        )

        if is_anomaly:
            self._record_anomaly(result)

        return result

    def check_transaction(
        self,
        item_price: float,
        market_avg: float,
        historical_prices: list[float] | None = None,
        quantity: int = 1,
        transaction_id: str | None = None,
    ) -> TransactionAnomaly:
        """Check if a transaction is anomalous.

        Args:
            item_price: Transaction price
            market_avg: Current market average price
            historical_prices: Optional historical prices
            quantity: Transaction quantity
            transaction_id: Optional transaction ID

        Returns:
            TransactionAnomaly
        """
        recommendations = []
        reasons = []
        is_anomaly = False
        severity = AnomalySeverity.INFO

        total_value = item_price * quantity

        # Check price deviation from market average
        if market_avg > 0:
            deviation = (item_price - market_avg) / market_avg

            if deviation > 0.2:  # 20% above market
                is_anomaly = True
                severity = (
                    AnomalySeverity.HIGH if deviation > 0.5 else AnomalySeverity.MEDIUM
                )
                reasons.append(f"Price {deviation:.1%} above market average")
                recommendations.append("Consider waiting for lower price")
            elif deviation < -0.2:  # 20% below market
                is_anomaly = True
                severity = AnomalySeverity.MEDIUM
                reasons.append(f"Price {abs(deviation):.1%} below market average")
                recommendations.append(
                    "Verify item condition - price is suspiciously low"
                )

        # Check agAlgonst historical prices
        if historical_prices and len(historical_prices) >= self.min_history_length:
            hist_result = self.check_price_anomaly(item_price, historical_prices)
            if hist_result.is_anomaly:
                is_anomaly = True
                severity = max(
                    severity,
                    hist_result.severity,
                    key=lambda x: list(AnomalySeverity).index(x),
                )
                reasons.append(f"Historical anomaly: {hist_result.reason}")

        # Check for manipulation patterns
        if is_anomaly and severity in {AnomalySeverity.HIGH, AnomalySeverity.CRITICAL}:
            recommendations.append(
                "Review transaction carefully - potential manipulation"
            )

        # High value transaction check
        if total_value > 100:  # $100+
            recommendations.append(
                "High value transaction - double-check before confirming"
            )

        score = 0.0
        if market_avg > 0:
            score = min(1.0, abs(item_price - market_avg) / market_avg)

        anomaly_result = AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_type=AnomalyType.SUSPICIOUS_TRANSACTION if is_anomaly else None,
            severity=severity,
            score=score,
            reason="; ".join(reasons) if reasons else "Transaction appears normal",
            details={
                "item_price": item_price,
                "market_avg": market_avg,
                "deviation": (
                    round((item_price - market_avg) / market_avg, 4)
                    if market_avg > 0
                    else 0
                ),
                "quantity": quantity,
                "total_value": total_value,
            },
        )

        return TransactionAnomaly(
            transaction_id=transaction_id,
            price=item_price,
            quantity=quantity,
            total_value=total_value,
            anomaly_result=anomaly_result,
            recommendations=recommendations,
        )

    def detect_price_manipulation(
        self,
        prices: list[float],
        volumes: list[int] | None = None,
        timestamps: list[datetime] | None = None,
    ) -> AnomalyResult:
        """Detect potential price manipulation.

        Looks for patterns like:
        - Sudden price spikes followed by drops (pump and dump)
        - Coordinated buying/selling
        - Unusual volume patterns

        Args:
            prices: Price history
            volumes: Optional volume history
            timestamps: Optional timestamps

        Returns:
            AnomalyResult
        """
        if len(prices) < 20:
            return AnomalyResult(
                is_anomaly=False,
                reason="Insufficient data for manipulation detection",
            )

        prices_arr = np.array(prices)

        # Calculate returns
        returns = np.diff(prices_arr) / prices_arr[:-1]

        # Check for pump and dump pattern
        # Pattern: large positive returns followed by large negative returns
        pump_dump_detected = False
        pump_dump_details = []

        for i in range(len(returns) - 1):
            if returns[i] > 0.15 and returns[i + 1] < -0.10:  # 15% up, then 10%+ down
                pump_dump_detected = True
                pump_dump_details.append(
                    {
                        "index": i,
                        "pump": round(returns[i], 4),
                        "dump": round(returns[i + 1], 4),
                    }
                )

        # Check volume anomalies if avAlgolable
        volume_anomaly = False
        if volumes and len(volumes) == len(prices):
            volumes_arr = np.array(volumes)
            mean_vol = np.mean(volumes_arr)
            std_vol = np.std(volumes_arr)

            if std_vol > 0:
                vol_z_scores = np.abs(volumes_arr - mean_vol) / std_vol
                volume_anomaly = np.any(vol_z_scores > 3)

        # Check for coordinated activity (unusual regularity)
        price_changes = np.abs(np.diff(prices_arr))
        regularity_score = (
            np.std(price_changes) / np.mean(price_changes)
            if np.mean(price_changes) > 0
            else 1
        )
        coordinated_suspected = regularity_score < 0.3  # Too regular = suspicious

        # Determine overall result
        is_anomaly = pump_dump_detected or coordinated_suspected
        reasons = []

        if pump_dump_detected:
            reasons.append(
                f"Pump and dump pattern detected ({len(pump_dump_details)} instances)"
            )
        if volume_anomaly:
            reasons.append("Unusual volume spikes detected")
        if coordinated_suspected:
            reasons.append("Suspiciously regular price changes (possible coordination)")

        severity = AnomalySeverity.INFO
        if pump_dump_detected:
            severity = AnomalySeverity.CRITICAL
        elif coordinated_suspected:
            severity = AnomalySeverity.HIGH
        elif volume_anomaly:
            severity = AnomalySeverity.MEDIUM

        score = 0.0
        if pump_dump_detected:
            score = 0.9
        elif coordinated_suspected:
            score = 0.6
        elif volume_anomaly:
            score = 0.4

        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_type=AnomalyType.MANIPULATION_SUSPECTED if is_anomaly else None,
            severity=severity,
            score=score,
            reason=(
                "; ".join(reasons) if reasons else "No manipulation patterns detected"
            ),
            details={
                "pump_dump_instances": pump_dump_details,
                "volume_anomaly": volume_anomaly,
                "regularity_score": round(regularity_score, 4),
                "coordinated_suspected": coordinated_suspected,
            },
        )

    def detect_api_anomaly(
        self,
        response_code: int,
        response_time_ms: float,
        expected_fields: list[str] | None = None,
        actual_fields: list[str] | None = None,
        historical_response_times: list[float] | None = None,
    ) -> AnomalyResult:
        """Detect API response anomalies.

        Args:
            response_code: HTTP response code
            response_time_ms: Response time in milliseconds
            expected_fields: Expected fields in response
            actual_fields: Actual fields received
            historical_response_times: Historical response times

        Returns:
            AnomalyResult
        """
        reasons = []
        is_anomaly = False
        severity = AnomalySeverity.INFO

        # Check response code
        if response_code >= 400:
            is_anomaly = True
            if response_code >= 500:
                severity = AnomalySeverity.CRITICAL
                reasons.append(f"Server error: HTTP {response_code}")
            else:
                severity = AnomalySeverity.HIGH
                reasons.append(f"Client error: HTTP {response_code}")

        # Check response time
        if historical_response_times and len(historical_response_times) >= 10:
            mean_time = np.mean(historical_response_times)
            std_time = np.std(historical_response_times)

            if std_time > 0:
                z_score = (response_time_ms - mean_time) / std_time
                if z_score > 3:
                    is_anomaly = True
                    severity = max(severity, AnomalySeverity.MEDIUM)
                    reasons.append(
                        f"Response time {response_time_ms}ms significantly higher than average {mean_time:.0f}ms"
                    )
        elif response_time_ms > 5000:  # 5 seconds
            is_anomaly = True
            severity = max(severity, AnomalySeverity.MEDIUM)
            reasons.append(f"Response time {response_time_ms}ms exceeds 5s threshold")

        # Check missing fields
        if expected_fields and actual_fields:
            missing = set(expected_fields) - set(actual_fields)
            if missing:
                is_anomaly = True
                severity = max(severity, AnomalySeverity.HIGH)
                reasons.append(f"Missing expected fields: {missing}")

        score = 0.0
        if response_code >= 500:
            score = 1.0
        elif response_code >= 400:
            score = 0.8
        elif is_anomaly:
            score = 0.5

        return AnomalyResult(
            is_anomaly=is_anomaly,
            anomaly_type=AnomalyType.API_ERROR if is_anomaly else None,
            severity=severity,
            score=score,
            reason="; ".join(reasons) if reasons else "API response normal",
            details={
                "response_code": response_code,
                "response_time_ms": response_time_ms,
                "missing_fields": list(
                    set(expected_fields or []) - set(actual_fields or [])
                ),
            },
        )

    def batch_detect(
        self,
        items: list[dict[str, Any]],
    ) -> list[AnomalyResult]:
        """Batch anomaly detection for multiple items.

        Args:
            items: List of items with price data

        Returns:
            List of AnomalyResult
        """
        results = []

        for item in items:
            current_price = item.get("price", 0)
            historical_prices = item.get("historical_prices", [])
            item_name = item.get("name", "unknown")

            result = self.check_price_anomaly(
                current_price=current_price,
                historical_prices=historical_prices,
                item_name=item_name,
            )
            results.append(result)

        return results

    def train_isolation_forest(
        self,
        training_data: list[list[float]],
    ) -> bool:
        """TrAlgon Isolation Forest on historical data.

        Args:
            training_data: List of feature vectors

        Returns:
            True if training successful
        """
        if not self._init_isolation_forest():
            return False

        if len(training_data) < 50:
            logger.warning("Insufficient training data (minimum 50 samples)")
            return False

        try:
            X = np.array(training_data)
            self._isolation_forest.fit(X)
            logger.info(f"Isolation Forest trained on {len(X)} samples")
            return True
        except Exception as e:
            logger.exception(f"Failed to train Isolation Forest: {e}")
            return False

    def predict_with_isolation_forest(
        self,
        features: list[float],
    ) -> tuple[bool, float]:
        """Predict anomaly using Isolation Forest.

        Args:
            features: Feature vector

        Returns:
            (is_anomaly, anomaly_score) tuple
        """
        if self._isolation_forest is None:
            return False, 0.0

        try:
            X = np.array(features).reshape(1, -1)
            prediction = self._isolation_forest.predict(X)[0]
            score = -self._isolation_forest.score_samples(X)[0]

            is_anomaly = prediction == -1
            return is_anomaly, min(1.0, max(0.0, score))
        except Exception as e:
            logger.exception(f"Isolation Forest prediction failed: {e}")
            return False, 0.0

    def _record_anomaly(self, result: AnomalyResult) -> None:
        """Record anomaly for pattern learning.

        Args:
            result: Anomaly detection result to record.
        """
        self._anomaly_history.append(result)

        # Trim history if too large
        if len(self._anomaly_history) > self.MAX_ANOMALY_HISTORY:
            self._anomaly_history = self._anomaly_history[-self.MAX_ANOMALY_HISTORY :]

    def get_anomaly_statistics(self) -> dict[str, Any]:
        """Get statistics about detected anomalies.

        Returns:
            Dictionary with anomaly statistics
        """
        if not self._anomaly_history:
            return {
                "total_anomalies": 0,
                "by_type": {},
                "by_severity": {},
                "avg_score": 0.0,
            }

        by_type: dict[str, int] = {}
        by_severity: dict[str, int] = {}
        scores = []

        for anomaly in self._anomaly_history:
            if anomaly.anomaly_type:
                by_type[anomaly.anomaly_type.value] = (
                    by_type.get(anomaly.anomaly_type.value, 0) + 1
                )
            by_severity[anomaly.severity.value] = (
                by_severity.get(anomaly.severity.value, 0) + 1
            )
            scores.append(anomaly.score)

        return {
            "total_anomalies": len(self._anomaly_history),
            "by_type": by_type,
            "by_severity": by_severity,
            "avg_score": round(np.mean(scores), 4) if scores else 0.0,
            "recent_24h": sum(
                1
                for a in self._anomaly_history
                if a.detected_at > datetime.now(UTC) - timedelta(hours=24)
            ),
        }

    def detect_data_drift(
        self,
        current_data: list[float],
        baseline_data: list[float],
        feature_name: str = "price",
    ) -> AnomalyResult:
        """Detect data drift between current and baseline distributions.

        Uses statistical tests to detect if the current data distribution
        has significantly shifted from the baseline (training) distribution.

        Args:
            current_data: Recent data points
            baseline_data: Baseline (historical/training) data points
            feature_name: Name of the feature being compared

        Returns:
            AnomalyResult indicating if drift was detected
        """
        if (
            len(current_data) < self.DRIFT_MIN_SAMPLES
            or len(baseline_data) < self.DRIFT_MIN_SAMPLES
        ):
            return AnomalyResult(
                is_anomaly=False,
                reason="Insufficient data for drift detection",
                score=0.0,
            )

        current_arr = np.array(current_data)
        baseline_arr = np.array(baseline_data)

        # Calculate distribution statistics
        current_mean = np.mean(current_arr)
        current_std = np.std(current_arr)
        baseline_mean = np.mean(baseline_arr)
        baseline_std = np.std(baseline_arr)

        # Calculate mean shift
        mean_shift = abs(current_mean - baseline_mean)
        combined_std = np.sqrt((current_std**2 + baseline_std**2) / 2)
        normalized_shift = mean_shift / combined_std if combined_std > 0 else 0

        # Calculate variance ratio
        variance_ratio = current_std / baseline_std if baseline_std > 0 else 1.0

        # Kolmogorov-Smirnov style test (simplified)
        # Compare quantiles
        quantiles = [0.25, 0.5, 0.75]
        current_quantiles = np.percentile(current_arr, [q * 100 for q in quantiles])
        baseline_quantiles = np.percentile(baseline_arr, [q * 100 for q in quantiles])

        quantile_diff = np.mean(np.abs(current_quantiles - baseline_quantiles))
        normalized_quantile_diff = (
            quantile_diff / baseline_mean if baseline_mean > 0 else 0
        )

        # Calculate drift score (0-1) using configurable weights
        drift_score = min(
            1.0,
            (
                self.DRIFT_WEIGHT_MEAN_SHIFT
                * min(1.0, normalized_shift / self.DRIFT_MEAN_SHIFT_SCALE)
                + self.DRIFT_WEIGHT_VARIANCE * min(1.0, abs(variance_ratio - 1))
                + self.DRIFT_WEIGHT_QUANTILE
                * min(1.0, normalized_quantile_diff * self.DRIFT_QUANTILE_SCALE)
            ),
        )

        # Determine if drift is significant
        is_drift = drift_score > 0.5
        severity = AnomalySeverity.INFO
        if drift_score > 0.8:
            severity = AnomalySeverity.CRITICAL
        elif drift_score > 0.6:
            severity = AnomalySeverity.HIGH
        elif drift_score > 0.5:
            severity = AnomalySeverity.MEDIUM

        reasons = []
        if normalized_shift > 1.5:
            reasons.append(f"Mean shifted by {normalized_shift:.2f} std")
        if abs(variance_ratio - 1) > 0.3:
            reasons.append(f"Variance ratio: {variance_ratio:.2f}")
        if normalized_quantile_diff > 0.1:
            reasons.append(f"Quantile shift: {normalized_quantile_diff:.1%}")

        result = AnomalyResult(
            is_anomaly=is_drift,
            anomaly_type=AnomalyType.DATA_QUALITY_ISSUE if is_drift else None,
            severity=severity,
            score=drift_score,
            reason="; ".join(reasons) if reasons else "No significant drift detected",
            details={
                "feature_name": feature_name,
                "current_mean": round(current_mean, 4),
                "baseline_mean": round(baseline_mean, 4),
                "mean_shift": round(mean_shift, 4),
                "normalized_shift": round(normalized_shift, 4),
                "variance_ratio": round(variance_ratio, 4),
                "drift_score": round(drift_score, 4),
                "current_samples": len(current_data),
                "baseline_samples": len(baseline_data),
            },
        )

        if is_drift:
            self._record_anomaly(result)
            logger.warning(
                "data_drift_detected",
                extra={
                    "feature": feature_name,
                    "drift_score": round(drift_score, 3),
                    "severity": severity.value,
                },
            )

        return result


# Factory function
def create_anomaly_detector(
    z_score_threshold: float = 3.0,
    price_change_threshold: float = 0.3,
) -> AnomalyDetector:
    """Create anomaly detector instance.

    Args:
        z_score_threshold: Z-score threshold
        price_change_threshold: Price change threshold

    Returns:
        AnomalyDetector instance
    """
    return AnomalyDetector(
        z_score_threshold=z_score_threshold,
        price_change_threshold=price_change_threshold,
    )
