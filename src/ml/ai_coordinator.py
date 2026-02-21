"""AI Coordinator - Unified ML Module Coordinator.

This module provides a single entry point for all ML/AI functionality.
It coordinates:
- Price prediction
- Trade signal classification
- Discount threshold prediction
- Anomaly detection
- Smart recommendations
- Llama LLM integration

Usage:
    ```python
    from src.ml.ai_coordinator import get_ai_coordinator

    ai = get_ai_coordinator()

    # Get comprehensive analysis for an item
    analysis = await ai.analyze_item(item_data)

    # Make trading decision
    decision = await ai.make_decision(item_data, balance=100.0)

    # Run autonomous scan
    opportunities = await ai.scan_and_decide(game="csgo")
    ```

Created: January 2026
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from src.ml.anomaly_detection import AnomalyDetector, AnomalyResult
from src.ml.discount_threshold_predictor import (
    DiscountThresholdPredictor,
    MarketCondition,
    ThresholdPrediction,
    get_discount_threshold_predictor,
)
from src.ml.smart_recommendations import RecommendationType, RiskLevel

if TYPE_CHECKING:
    from src.dmarket.dmarket_api import DMarketAPI
    from src.ml.enhanced_predictor import EnhancedPricePredictor
    from src.ml.llama_integration import LlamaIntegration
    from src.ml.trade_classifier import AdaptiveTradeClassifier


logger = logging.getLogger(__name__)


class AutonomyLevel(StrEnum):
    """Levels of bot autonomy."""

    MANUAL = "manual"  # All decisions require user confirmation
    SEMI_AUTO = "semi_auto"  # Small trades auto, large need confirmation
    AUTO = "auto"  # Fully autonomous within limits


class TradeAction(StrEnum):
    """Possible trade actions."""

    BUY = "buy"
    SELL = "sell"
    CREATE_TARGET = "create_target"
    HOLD = "hold"
    SKIP = "skip"


@dataclass
class SafetyLimits:
    """Safety limits for autonomous trading."""

    max_single_trade_usd: float = 50.0
    max_daily_volume_usd: float = 200.0
    max_position_percent: float = 30.0
    min_confidence_auto: float = 0.80
    max_trades_per_hour: int = 10
    loss_cooldown_minutes: int = 30
    dry_run: bool = True  # Default to dry run for safety


@dataclass
class TradeDecision:
    """A trading decision made by the AI."""

    action: TradeAction
    item_name: str
    item_id: str
    game: str

    # Price info
    current_price: float
    predicted_price: float
    expected_profit: float
    expected_profit_percent: float

    # Confidence and risk
    confidence: float  # 0-1
    risk_level: RiskLevel
    discount_threshold_used: float

    # Model outputs
    price_prediction_confidence: float
    signal_probability: float
    anomaly_score: float

    # Reasoning
    reasoning: list[str] = field(default_factory=list)

    # Execution
    requires_confirmation: bool = True
    executed: bool = False
    execution_result: dict[str, Any] | None = None

    # Metadata
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "action": self.action.value,
            "item_name": self.item_name,
            "item_id": self.item_id,
            "game": self.game,
            "current_price": round(self.current_price, 2),
            "predicted_price": round(self.predicted_price, 2),
            "expected_profit": round(self.expected_profit, 2),
            "expected_profit_percent": round(self.expected_profit_percent, 2),
            "confidence": round(self.confidence, 3),
            "risk_level": self.risk_level.value,
            "discount_threshold_used": round(self.discount_threshold_used, 2),
            "reasoning": self.reasoning,
            "requires_confirmation": self.requires_confirmation,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ItemAnalysis:
    """Comprehensive analysis of an item."""

    item_name: str
    item_id: str
    game: str
    current_price: float

    # Price prediction
    predicted_price_1h: float
    predicted_price_24h: float
    predicted_price_7d: float
    price_confidence: float

    # Trade signal
    signal: str  # buy, sell, hold
    signal_probability: float

    # Discount analysis
    actual_discount: float
    ml_threshold: float
    is_undervalued: bool

    # Anomaly check
    is_anomaly: bool
    anomaly_score: float
    anomaly_reason: str | None

    # Risk assessment
    risk_level: RiskLevel
    risk_factors: list[str]

    # Recommendation
    recommendation: RecommendationType
    recommendation_reason: str

    # LLM analysis (optional)
    llm_analysis: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "item_name": self.item_name,
            "item_id": self.item_id,
            "game": self.game,
            "current_price": self.current_price,
            "predicted_price_1h": self.predicted_price_1h,
            "predicted_price_24h": self.predicted_price_24h,
            "predicted_price_7d": self.predicted_price_7d,
            "price_confidence": self.price_confidence,
            "signal": self.signal,
            "signal_probability": self.signal_probability,
            "actual_discount": self.actual_discount,
            "ml_threshold": self.ml_threshold,
            "is_undervalued": self.is_undervalued,
            "is_anomaly": self.is_anomaly,
            "anomaly_score": self.anomaly_score,
            "risk_level": self.risk_level.value,
            "recommendation": self.recommendation.value,
            "recommendation_reason": self.recommendation_reason,
            "llm_analysis": self.llm_analysis,
        }


class AICoordinator:
    """Unified coordinator for all AI/ML modules.

    This class provides a single interface to:
    - Analyze items using all available models
    - Make trading decisions
    - Control bot autonomy
    - Train models on real data

    Attributes:
        autonomy_level: Current level of autonomous operation.
        safety_limits: Safety limits for trading.
        user_balance: Current user balance in USD.

    Example:
        >>> ai = AICoordinator(autonomy_level=AutonomyLevel.SEMI_AUTO)
        >>> analysis = await ai.analyze_item(item_data)
        >>> decision = await ai.make_decision(item_data)
    """

    # Default model weights for ensemble decision (must sum to 1.0)
    DEFAULT_MODEL_WEIGHTS = {
        "price_prediction": 0.30,
        "signal_classification": 0.25,
        "discount_threshold": 0.20,
        "anomaly_check": 0.15,
        "balance_fit": 0.10,
    }

    # Model version for tracking and drift detection
    MODEL_VERSION = "1.1.0"

    # Drift detection thresholds
    DRIFT_DETECTION_WINDOW = 100  # Number of decisions to track
    DRIFT_ACCURACY_THRESHOLD = 0.60  # Below this triggers drift alert
    DRIFT_MIN_SAMPLES = (
        50  # Minimum samples before drift detection (DRIFT_DETECTION_WINDOW // 2)
    )
    DRIFT_RECOVERY_OFFSET = 0.05  # Hysteresis offset to prevent oscillation

    def __init__(
        self,
        autonomy_level: AutonomyLevel = AutonomyLevel.MANUAL,
        safety_limits: SafetyLimits | None = None,
        user_balance: float = 100.0,
        model_weights: dict[str, float] | None = None,
    ) -> None:
        """Initialize AI Coordinator.

        Args:
            autonomy_level: Level of autonomous operation
            safety_limits: Safety limits for trading
            user_balance: Current user balance in USD
            model_weights: Custom weights for ensemble models (must sum to 1.0)
        """
        self.autonomy_level = autonomy_level
        self.safety_limits = safety_limits or SafetyLimits()
        self.user_balance = user_balance

        # Configurable model weights with validation
        self._model_weights = self._validate_weights(
            model_weights or self.DEFAULT_MODEL_WEIGHTS.copy()
        )

        # ML Modules (lazy initialization)
        self._price_predictor: EnhancedPricePredictor | None = None
        self._trade_classifier: AdaptiveTradeClassifier | None = None
        self._discount_predictor: DiscountThresholdPredictor | None = None
        self._anomaly_detector: AnomalyDetector | None = None
        self._llama: LlamaIntegration | None = None

        # Market condition
        self._market_condition = MarketCondition.STABLE

        # Statistics with enhanced metrics
        self._stats = {
            "decisions_made": 0,
            "trades_executed": 0,
            "successful_trades": 0,
            "total_profit": 0.0,
            "daily_volume": 0.0,
            "last_reset": datetime.now(UTC),
            # New: Performance tracking
            "model_version": self.MODEL_VERSION,
            "avg_confidence": 0.0,
            "avg_processing_time_ms": 0.0,
        }

        # Trade history for learning
        self._trade_history: list[dict[str, Any]] = []

        # New: Drift detection tracking
        self._prediction_outcomes: list[bool] = []  # True = correct, False = incorrect
        self._drift_detected = False

        # New: Performance metrics
        self._processing_times: list[float] = []
        self._confidence_scores: list[float] = []

        logger.info(
            "ai_coordinator_initialized",
            extra={
                "autonomy_level": autonomy_level.value,
                "dry_run": self.safety_limits.dry_run,
                "model_version": self.MODEL_VERSION,
                "weights": self._model_weights,
            },
        )

    def _validate_weights(self, weights: dict[str, float]) -> dict[str, float]:
        """Validate that model weights sum to 1.0.

        Creates a copy of weights to avoid modifying the input.
        """
        # Create a copy to avoid modifying input
        result = weights.copy()
        total = sum(result.values())
        if abs(total - 1.0) > 0.01:
            logger.warning(
                "model_weights_invalid_sum",
                extra={"sum": total, "expected": 1.0},
            )
            # Normalize weights
            for key in result:
                result[key] /= total
        return result

    @property
    def model_weights(self) -> dict[str, float]:
        """Get current model weights."""
        return self._model_weights.copy()

    def set_model_weights(self, weights: dict[str, float]) -> None:
        """Update model weights for ensemble.

        Args:
            weights: New weights (will be normalized if they don't sum to 1.0)
        """
        self._model_weights = self._validate_weights(weights)
        logger.info("model_weights_updated", extra={"weights": self._model_weights})

    def _get_price_predictor(self) -> EnhancedPricePredictor:
        """Get or initialize price predictor."""
        if self._price_predictor is None:
            from src.ml.enhanced_predictor import EnhancedPricePredictor

            self._price_predictor = EnhancedPricePredictor(
                user_balance=self.user_balance,
            )
        return self._price_predictor

    def _get_trade_classifier(self) -> AdaptiveTradeClassifier:
        """Get or initialize trade classifier."""
        if self._trade_classifier is None:
            from src.ml.trade_classifier import AdaptiveTradeClassifier

            self._trade_classifier = AdaptiveTradeClassifier(
                user_balance=self.user_balance,
            )
        return self._trade_classifier

    def _get_discount_predictor(self) -> DiscountThresholdPredictor:
        """Get or initialize discount threshold predictor."""
        if self._discount_predictor is None:
            self._discount_predictor = get_discount_threshold_predictor()
        return self._discount_predictor

    def _get_anomaly_detector(self) -> AnomalyDetector:
        """Get or initialize anomaly detector."""
        if self._anomaly_detector is None:
            self._anomaly_detector = AnomalyDetector()
        return self._anomaly_detector

    async def _get_llama(self) -> LlamaIntegration | None:
        """Get or initialize Llama integration."""
        if self._llama is None:
            try:
                from src.ml.llama_integration import LlamaIntegration

                self._llama = LlamaIntegration()
                if not await self._llama.check_availability():
                    logger.info("Llama not available, will use ML models only")
                    self._llama = None
            except ImportError:
                logger.debug("Llama integration not available")
                self._llama = None
        return self._llama

    def set_autonomy_level(self, level: AutonomyLevel) -> None:
        """Set autonomy level."""
        old_level = self.autonomy_level
        self.autonomy_level = level
        logger.info(
            "autonomy_level_changed",
            extra={"old": old_level.value, "new": level.value},
        )

    def set_user_balance(self, balance: float) -> None:
        """Update user balance."""
        self.user_balance = max(0.0, balance)

        # Update in sub-modules
        if self._price_predictor:
            self._price_predictor.set_user_balance(balance)
        if self._trade_classifier:
            self._trade_classifier.set_user_balance(balance)

    def update_market_condition(self, condition: MarketCondition) -> None:
        """Update market condition for adaptive thresholds."""
        self._market_condition = condition
        if self._discount_predictor:
            self._discount_predictor.update_market_condition(condition)

    async def analyze_item(
        self,
        item_data: dict[str, Any],
        include_llm: bool = False,
    ) -> ItemAnalysis:
        """Perform comprehensive analysis of an item.

        Args:
            item_data: Item data from API
            include_llm: Whether to include LLM analysis

        Returns:
            ItemAnalysis with all model outputs
        """
        item_name = item_data.get("title", item_data.get("name", "unknown"))
        item_id = item_data.get("itemId", item_data.get("id", ""))
        game = item_data.get("gameId", item_data.get("game", "csgo"))

        # Extract price
        price_data = item_data.get("price", {})
        if isinstance(price_data, dict):
            current_price = float(price_data.get("USD", 0)) / 100
        else:
            current_price = float(price_data) / 100 if price_data else 0.0

        # Extract suggested price for discount calculation
        suggested_data = item_data.get("suggestedPrice", {})
        if isinstance(suggested_data, dict):
            suggested_price = float(suggested_data.get("USD", 0)) / 100
        else:
            suggested_price = float(suggested_data) / 100 if suggested_data else 0.0

        # Calculate actual discount
        actual_discount = 0.0
        if suggested_price > 0:
            actual_discount = (
                (suggested_price - current_price) / suggested_price
            ) * 100

        # Get historical prices if available
        historical_prices = item_data.get("priceHistory", [])

        # 1. Price prediction
        predictor = self._get_price_predictor()
        price_pred = predictor.predict(
            item_name=item_name,
            current_price=current_price,
            price_history=[(datetime.now(UTC), p) for p in historical_prices[-30:]],
        )

        # 2. Trade signal classification
        classifier = self._get_trade_classifier()
        signal = classifier.classify(
            item_name=item_name,
            current_price=current_price,
            expected_price=price_pred.get("predicted_price_24h", current_price),
        )

        # 3. ML discount threshold
        discount_pred = self._get_discount_predictor()
        threshold_result: ThresholdPrediction = discount_pred.predict(game=game)
        ml_threshold = threshold_result.optimal_threshold

        # 4. Anomaly detection
        anomaly_detector = self._get_anomaly_detector()
        anomaly_result: AnomalyResult = anomaly_detector.check_price_anomaly(
            current_price=current_price,
            historical_prices=historical_prices,
            item_name=item_name,
        )

        # 5. LLM analysis (optional)
        llm_analysis = None
        if include_llm:
            llama = await self._get_llama()
            if llama:
                try:
                    llm_result = await llama.evaluate_item(
                        item_name=item_name,
                        current_price=current_price,
                        item_data=item_data,
                    )
                    if llm_result.success:
                        llm_analysis = llm_result.response
                except Exception as e:
                    logger.warning(
                        "llama_evaluation_failed",
                        extra={"item_name": item_name, "error": str(e)},
                    )

        # Determine recommendation
        is_undervalued = actual_discount >= ml_threshold
        recommendation = self._determine_recommendation(
            is_undervalued=is_undervalued,
            signal=signal,
            anomaly_result=anomaly_result,
            price_pred=price_pred,
        )

        return ItemAnalysis(
            item_name=item_name,
            item_id=item_id,
            game=game,
            current_price=current_price,
            predicted_price_1h=price_pred.get("predicted_price_1h", current_price),
            predicted_price_24h=price_pred.get("predicted_price_24h", current_price),
            predicted_price_7d=price_pred.get("predicted_price_7d", current_price),
            price_confidence=price_pred.get("confidence_score", 0.5),
            signal=signal.signal.value if hasattr(signal, "signal") else "hold",
            signal_probability=(
                signal.profit_probability
                if hasattr(signal, "profit_probability")
                else 0.5
            ),
            actual_discount=actual_discount,
            ml_threshold=ml_threshold,
            is_undervalued=is_undervalued,
            is_anomaly=anomaly_result.is_anomaly,
            anomaly_score=anomaly_result.score,
            anomaly_reason=anomaly_result.reason if anomaly_result.is_anomaly else None,
            risk_level=(
                signal.risk_level if hasattr(signal, "risk_level") else RiskLevel.MEDIUM
            ),
            risk_factors=signal.reasoning if hasattr(signal, "reasoning") else [],
            recommendation=recommendation,
            recommendation_reason=self._get_recommendation_reason(
                recommendation, is_undervalued, signal
            ),
            llm_analysis=llm_analysis,
        )

    def _determine_recommendation(
        self,
        is_undervalued: bool,
        signal: Any,
        anomaly_result: AnomalyResult,
        price_pred: dict[str, Any],
    ) -> RecommendationType:
        """Determine recommendation based on all model outputs."""
        # Skip if anomaly
        if anomaly_result.is_anomaly and anomaly_result.score > 0.7:
            return RecommendationType.AVOID

        # Check signal
        signal_value = signal.signal.value if hasattr(signal, "signal") else "hold"

        if signal_value in {"strong_buy", "buy"} and is_undervalued:
            return RecommendationType.BUY
        if signal_value in {"strong_sell", "sell"}:
            return RecommendationType.SELL
        if is_undervalued:
            return RecommendationType.WATCHLIST

        return RecommendationType.HOLD

    def _get_recommendation_reason(
        self,
        recommendation: RecommendationType,
        is_undervalued: bool,
        signal: Any,
    ) -> str:
        """Generate recommendation reason."""
        reasons = []

        if is_undervalued:
            reasons.append("Price below ML threshold")
        if hasattr(signal, "signal") and signal.signal.value in {"strong_buy", "buy"}:
            reasons.append("Positive trade signal")
        if hasattr(signal, "profit_probability") and signal.profit_probability > 0.7:
            reasons.append(f"High profit probability ({signal.profit_probability:.1%})")

        return "; ".join(reasons) if reasons else "No strong signals"

    async def make_decision(
        self,
        item_data: dict[str, Any],
    ) -> TradeDecision:
        """Make a trading decision for an item.

        Args:
            item_data: Item data from API

        Returns:
            TradeDecision with action and reasoning
        """
        # Get comprehensive analysis
        analysis = await self.analyze_item(item_data)

        # Calculate ensemble confidence
        confidence = self._calculate_ensemble_confidence(analysis)

        # Determine action
        action = self._determine_action(analysis, confidence)

        # Check if confirmation required
        requires_confirmation = self._requires_confirmation(
            action=action,
            amount=analysis.current_price,
            confidence=confidence,
        )

        # Build reasoning
        reasoning = self._build_reasoning(analysis, action)

        decision = TradeDecision(
            action=action,
            item_name=analysis.item_name,
            item_id=analysis.item_id,
            game=analysis.game,
            current_price=analysis.current_price,
            predicted_price=analysis.predicted_price_24h,
            expected_profit=analysis.predicted_price_24h - analysis.current_price,
            expected_profit_percent=(
                (analysis.predicted_price_24h - analysis.current_price)
                / analysis.current_price
                * 100
                if analysis.current_price > 0
                else 0
            ),
            confidence=confidence,
            risk_level=analysis.risk_level,
            discount_threshold_used=analysis.ml_threshold,
            price_prediction_confidence=analysis.price_confidence,
            signal_probability=analysis.signal_probability,
            anomaly_score=analysis.anomaly_score,
            reasoning=reasoning,
            requires_confirmation=requires_confirmation,
        )

        self._stats["decisions_made"] += 1
        return decision

    def _calculate_ensemble_confidence(self, analysis: ItemAnalysis) -> float:
        """Calculate weighted confidence from all models.

        Uses configurable model weights for ensemble decision.
        Also tracks confidence for drift detection.
        """
        # Avoid division by zero
        balance_fit = 0.5  # Default neutral value
        if analysis.current_price > 0:
            balance_fit = min(1.0, self.user_balance / (analysis.current_price * 3))

        scores = {
            "price_prediction": analysis.price_confidence,
            "signal_classification": analysis.signal_probability,
            "discount_threshold": 1.0 if analysis.is_undervalued else 0.3,
            "anomaly_check": 1.0 - analysis.anomaly_score,
            "balance_fit": balance_fit,
        }

        # Use configurable weights
        confidence = sum(
            self._model_weights[k] * scores.get(k, 0.5) for k in self._model_weights
        )

        confidence = float(min(1.0, max(0.0, confidence)))

        # Track confidence for metrics
        self._confidence_scores.append(confidence)
        if len(self._confidence_scores) > 1000:
            self._confidence_scores = self._confidence_scores[-1000:]

        # Update average confidence in stats
        if self._confidence_scores:
            self._stats["avg_confidence"] = sum(self._confidence_scores) / len(
                self._confidence_scores
            )

        return confidence

    def _determine_action(
        self,
        analysis: ItemAnalysis,
        confidence: float,
    ) -> TradeAction:
        """Determine trade action based on analysis."""
        # Skip if anomaly
        if analysis.is_anomaly and analysis.anomaly_score > 0.7:
            return TradeAction.SKIP

        # Check recommendation
        if analysis.recommendation == RecommendationType.BUY:
            if confidence >= 0.6:
                return TradeAction.BUY
            if confidence >= 0.4:
                return TradeAction.CREATE_TARGET
        elif analysis.recommendation == RecommendationType.SELL:
            return TradeAction.SELL
        elif analysis.recommendation == RecommendationType.AVOID:
            return TradeAction.SKIP

        return TradeAction.HOLD

    def _requires_confirmation(
        self,
        action: TradeAction,
        amount: float,
        confidence: float,
    ) -> bool:
        """Check if action requires user confirmation."""
        if action in {TradeAction.HOLD, TradeAction.SKIP}:
            return False

        if self.autonomy_level == AutonomyLevel.MANUAL:
            return True

        if self.autonomy_level == AutonomyLevel.AUTO:
            return (
                amount > self.safety_limits.max_single_trade_usd
                or confidence < self.safety_limits.min_confidence_auto
            )

        # SEMI_AUTO
        return amount > 10.0 or confidence < 0.8

    def _build_reasoning(
        self,
        analysis: ItemAnalysis,
        action: TradeAction,
    ) -> list[str]:
        """Build reasoning for decision."""
        reasoning = []

        if action == TradeAction.BUY:
            reasoning.append(
                f"Discount {analysis.actual_discount:.1f}% above ML threshold {analysis.ml_threshold:.1f}%"
            )
        elif action == TradeAction.SKIP:
            if analysis.is_anomaly:
                reasoning.append(f"Anomaly detected: {analysis.anomaly_reason}")

        if analysis.signal in {"strong_buy", "buy"}:
            reasoning.append(
                f"Signal: {analysis.signal} ({analysis.signal_probability:.1%})"
            )

        reasoning.extend(
            (
                f"Price prediction: ${analysis.predicted_price_24h:.2f} (24h)",
                f"Risk level: {analysis.risk_level.value}",
            )
        )

        return reasoning

    async def train_all_models(
        self,
        dmarket_api: DMarketAPI,
        games: list[str] | None = None,
        items_per_game: int = 200,
    ) -> dict[str, Any]:
        """Train all ML models on real API data.

        Args:
            dmarket_api: DMarket API client
            games: List of games to train on
            items_per_game: Items to collect per game

        Returns:
            Training results for each model
        """
        games = games or ["csgo", "dota2", "tf2", "rust"]
        results = {}

        logger.info(
            "training_all_models",
            extra={"games": games, "items_per_game": items_per_game},
        )

        # 1. Train discount threshold predictor
        try:
            discount_pred = self._get_discount_predictor()
            for game in games:
                train_result = await discount_pred.train_from_api(
                    api_client=dmarket_api,
                    game=game,
                )
                results[f"discount_threshold_{game}"] = {
                    "success": train_result > 0,
                    "samples": train_result,
                }
        except Exception as e:
            logger.exception("discount_threshold_training_failed", error=str(e))
            results["discount_threshold"] = {"success": False, "error": str(e)}

        # 2. Train price predictor
        try:
            predictor = self._get_price_predictor()
            train_result = await predictor.train_from_real_data(
                game_types=games,
                items_per_game=items_per_game,
                dmarket_api=dmarket_api,
            )
            results["price_predictor"] = train_result
        except Exception as e:
            logger.exception("price_predictor_training_failed", error=str(e))
            results["price_predictor"] = {"success": False, "error": str(e)}

        logger.info("all_models_trained", extra={"results": results})
        return results

    def add_trade_outcome(
        self,
        decision: TradeDecision,
        actual_profit: float,
        was_profitable: bool,
    ) -> None:
        """Record trade outcome for learning.

        Args:
            decision: The original decision
            actual_profit: Actual profit in USD
            was_profitable: Whether trade was profitable
        """
        # Add to history
        self._trade_history.append(
            {
                "decision": decision.to_dict(),
                "actual_profit": actual_profit,
                "was_profitable": was_profitable,
                "timestamp": datetime.now(UTC).isoformat(),
            }
        )

        # Update stats
        if was_profitable:
            self._stats["successful_trades"] += 1
        self._stats["total_profit"] += actual_profit

        # Track for drift detection
        self._prediction_outcomes.append(was_profitable)
        if len(self._prediction_outcomes) > self.DRIFT_DETECTION_WINDOW:
            self._prediction_outcomes = self._prediction_outcomes[
                -self.DRIFT_DETECTION_WINDOW :
            ]

        # Check for concept drift
        self._check_concept_drift()

        # Add to discount predictor for continuous learning
        discount_pred = self._get_discount_predictor()
        discount_pred.add_training_example(
            item_name=decision.item_name,
            game=decision.game,
            current_price=decision.current_price,
            historical_avg_price=decision.predicted_price,
            actual_discount=decision.discount_threshold_used,
            was_profitable=was_profitable,
            profit_percent=(
                (actual_profit / decision.current_price * 100)
                if decision.current_price > 0
                else 0
            ),
        )

    def _check_concept_drift(self) -> None:
        """Check for concept drift in model predictions.

        Concept drift occurs when the model's accuracy degrades over time,
        indicating that the underlying data distribution has changed.
        """
        if len(self._prediction_outcomes) < self.DRIFT_MIN_SAMPLES:
            return

        # Calculate recent accuracy
        recent_accuracy = sum(self._prediction_outcomes) / len(
            self._prediction_outcomes
        )

        if recent_accuracy < self.DRIFT_ACCURACY_THRESHOLD:
            if not self._drift_detected:
                self._drift_detected = True
                logger.warning(
                    "concept_drift_detected",
                    extra={
                        "accuracy": round(recent_accuracy, 3),
                        "threshold": self.DRIFT_ACCURACY_THRESHOLD,
                        "window_size": len(self._prediction_outcomes),
                        "recommendation": "Consider retraining models",
                    },
                )
        elif (
            self._drift_detected
            and recent_accuracy
            >= self.DRIFT_ACCURACY_THRESHOLD + self.DRIFT_RECOVERY_OFFSET
        ):
            # Drift recovered (with hysteresis to prevent oscillation)
            self._drift_detected = False
            logger.info(
                "concept_drift_recovered",
                extra={"accuracy": round(recent_accuracy, 3)},
            )

    def get_drift_status(self) -> dict[str, Any]:
        """Get concept drift detection status.

        Returns:
            Dictionary with drift status and metrics
        """
        recent_accuracy = 0.0
        if self._prediction_outcomes:
            recent_accuracy = sum(self._prediction_outcomes) / len(
                self._prediction_outcomes
            )

        return {
            "drift_detected": self._drift_detected,
            "recent_accuracy": round(recent_accuracy, 3),
            "accuracy_threshold": self.DRIFT_ACCURACY_THRESHOLD,
            "samples_tracked": len(self._prediction_outcomes),
            "window_size": self.DRIFT_DETECTION_WINDOW,
        }

    def get_statistics(self) -> dict[str, Any]:
        """Get coordinator statistics with enhanced metrics."""
        win_rate = 0.0
        if self._stats["trades_executed"] > 0:
            win_rate = self._stats["successful_trades"] / self._stats["trades_executed"]

        return {
            **self._stats,
            "win_rate": round(win_rate, 3),
            "autonomy_level": self.autonomy_level.value,
            "market_condition": self._market_condition.value,
            "user_balance": self.user_balance,
            "model_weights": self._model_weights,
            "drift_status": self.get_drift_status(),
            "models_status": {
                "price_predictor": self._price_predictor is not None,
                "trade_classifier": self._trade_classifier is not None,
                "discount_predictor": self._discount_predictor is not None,
                "anomaly_detector": self._anomaly_detector is not None,
                "llama": self._llama is not None,
            },
        }

    async def scan_and_decide(
        self,
        items: list[dict[str, Any]],
        max_decisions: int = 10,
    ) -> list[TradeDecision]:
        """Scan items and make decisions.

        Args:
            items: List of items to analyze
            max_decisions: Maximum decisions to return

        Returns:
            List of TradeDecision sorted by confidence
        """
        decisions = []

        # Process items concurrently (in batches to avoid overload)
        batch_size = 20
        for i in range(0, len(items), batch_size):
            batch = items[i : i + batch_size]
            tasks = [self.make_decision(item) for item in batch]
            batch_decisions = await asyncio.gather(*tasks, return_exceptions=True)

            for idx, decision in enumerate(batch_decisions):
                if isinstance(decision, Exception):
                    # Log the exception for debugging
                    item_name = batch[idx].get(
                        "title", batch[idx].get("name", "unknown")
                    )
                    logger.warning(
                        "batch_decision_failed",
                        extra={"item_name": item_name, "error": str(decision)},
                    )
                elif isinstance(decision, TradeDecision):
                    if decision.action not in {TradeAction.HOLD, TradeAction.SKIP}:
                        decisions.append(decision)

        # Sort by confidence and return top N
        decisions.sort(key=lambda d: d.confidence, reverse=True)
        return decisions[:max_decisions]


# Global instance
_coordinator: AICoordinator | None = None


def get_ai_coordinator(
    autonomy_level: AutonomyLevel = AutonomyLevel.MANUAL,
    user_balance: float = 100.0,
) -> AICoordinator:
    """Get or create global AI coordinator instance.

    Args:
        autonomy_level: Initial autonomy level
        user_balance: Initial user balance

    Returns:
        AICoordinator instance
    """
    global _coordinator
    if _coordinator is None:
        _coordinator = AICoordinator(
            autonomy_level=autonomy_level,
            user_balance=user_balance,
        )
    return _coordinator


def reset_ai_coordinator() -> None:
    """Reset global AI coordinator (for testing)."""
    global _coordinator
    _coordinator = None
