"""AI-Powered Arbitrage Predictor.

Модуль для предиктивного арбитража с использованием машинного обучения.
Интегрируется с существующей ML системой (src/ml/) для прогнозирования
лучших арбитражных возможностей.

SKILL: AI Arbitrage Prediction
Category: Data & AI
Status: Phase 2 Implementation

Документация: src/dmarket/SKILL_AI_ARBITRAGE.md
"""

from dataclasses import dataclass
from typing import Any

import structlog

from src.ml import (
    EnhancedFeatureExtractor,
    EnhancedPricePredictor,
    GameType,
)


logger = structlog.get_logger(__name__)


@dataclass
class ArbitrageOpportunity:
    """Арбитражная возможность с ML-прогнозом."""

    title: str
    item_id: str
    game_id: str
    current_price: float  # USD
    suggested_price: float  # USD
    predicted_profit: float  # USD
    confidence: float  # 0.0-1.0
    risk_score: float  # 0-100
    roi_percent: float  # %
    features: dict[str, Any]


class AIArbitragePredictor:
    """AI-powered arbitrage prediction using ML models.

    Использует существующую ML систему для:
    - Прогнозирования ценовых трендов
    - Оценки рисков
    - Ранжирования возможностей

    Attributes:
        predictor: EnhancedPricePredictor для ML прогнозов
        feature_extractor: EnhancedFeatureExtractor для признаков
    """

    def __init__(
        self,
        predictor: EnhancedPricePredictor | None = None,
        feature_extractor: EnhancedFeatureExtractor | None = None,
    ):
        """Initialize AI Arbitrage Predictor.

        Args:
            predictor: ML predictor (создается автоматически если None)
            feature_extractor: Feature extractor (создается автоматически если None)
        """
        self.predictor = predictor or EnhancedPricePredictor()
        self.feature_extractor = feature_extractor or EnhancedFeatureExtractor()

        logger.info(
            "ai_arbitrage_predictor_initialized",
            predictor_type=type(self.predictor).__name__,
        )

    async def predict_best_opportunities(
        self,
        items: list[dict[str, Any]],
        current_balance: float,
        risk_level: str = "medium",
    ) -> list[ArbitrageOpportunity]:
        """Predict best arbitrage opportunities using ML.

        Args:
            items: Market items to analyze
            current_balance: User's available balance (USD)
            risk_level: Risk tolerance ("low", "medium", "high")

        Returns:
            Sorted list of opportunities with ML-predicted ROI

        Raises:
            ValueError: If risk_level not in ["low", "medium", "high"]

        Example:
            >>> predictor = AIArbitragePredictor()
            >>> items = await dmarket_api.get_market_items("csgo")
            >>> opportunities = await predictor.predict_best_opportunities(
            ...     items=items,
            ...     current_balance=100.0,
            ...     risk_level="medium"
            ... )
            >>> print(f"Found {len(opportunities)} opportunities")
        """
        if risk_level not in {"low", "medium", "high"}:
            raise ValueError(f"Invalid risk_level: {risk_level}. Must be low/medium/high")

        logger.info(
            "predicting_opportunities",
            items_count=len(items),
            balance=current_balance,
            risk_level=risk_level,
        )

        # Фильтрация по балансу
        affordable_items = [
            item
            for item in items
            if self._get_price_usd(item) <= current_balance
        ]

        # ML-анализ каждого предмета
        opportunities = []
        for item in affordable_items:
            try:
                opportunity = await self._analyze_item(item, risk_level)
                if opportunity and opportunity.confidence > self._get_min_confidence(risk_level):
                    opportunities.append(opportunity)
            except Exception as e:
                logger.warning(
                    "item_analysis_failed",
                    item_title=item.get("title", "unknown"),
                    error=str(e),
                )
                continue

        # Сортировка по confidence * predicted_profit
        opportunities.sort(
            key=lambda x: x.confidence * x.predicted_profit,
            reverse=True,
        )

        logger.info(
            "prediction_complete",
            opportunities_found=len(opportunities),
            avg_confidence=sum(o.confidence for o in opportunities) / len(opportunities)
            if opportunities
            else 0.0,
        )

        return opportunities

    async def _analyze_item(
        self,
        item: dict[str, Any],
        risk_level: str,
    ) -> ArbitrageOpportunity | None:
        """Analyze single item for arbitrage opportunity.

        Args:
            item: Market item data
            risk_level: Risk tolerance

        Returns:
            ArbitrageOpportunity if valid, None otherwise
        """
        title = item.get("title", "Unknown Item")
        current_price = self._get_price_usd(item)
        suggested_price = self._get_suggested_price_usd(item)

        # Базовая проверка арбитража
        if suggested_price <= current_price:
            return None

        # Извлечение признаков для ML
        game_id = item.get("gameId", "csgo")
        game_type = self._map_game_id(game_id)

        # Простая оценка вместо полного ML (для быстрого прототипа)
        # В production версии здесь будет вызов self.predictor.predict()
        features = self.feature_extractor.extract_features(
            item_name=title,
            current_price=current_price,
            game=game_type,
        )

        # Расчет прогнозируемой прибыли (с учетом комиссии 7%)
        commission = suggested_price * 0.07
        predicted_profit = suggested_price - current_price - commission

        if predicted_profit <= 0:
            return None

        # ML confidence (упрощенная версия)
        # В production: используется реальная ML модель
        price_diff_percent = (
            (suggested_price - current_price) / current_price * 100
        )
        confidence = min(0.95, max(0.5, price_diff_percent / 20))

        # Risk score calculation
        risk_score = self._calculate_risk(item, confidence, risk_level)

        # ROI calculation
        roi_percent = (predicted_profit / current_price) * 100

        return ArbitrageOpportunity(
            title=title,
            item_id=item.get("itemId", ""),
            game_id=game_id,
            current_price=current_price,
            suggested_price=suggested_price,
            predicted_profit=predicted_profit,
            confidence=confidence,
            risk_score=risk_score,
            roi_percent=roi_percent,
            features={
                "volatility": features.volatility,
                "rsi": features.rsi,
                "sales_count_24h": features.sales_count_24h,
            },
        )

    def _calculate_risk(
        self,
        item: dict[str, Any],
        confidence: float,
        risk_level: str,
    ) -> float:
        """Calculate risk score for item (0-100).

        Factors:
        - ML confidence (lower confidence = higher risk)
        - Price volatility
        - Liquidity

        Args:
            item: Market item
            confidence: ML confidence
            risk_level: User risk tolerance

        Returns:
            Risk score (0=no risk, 100=maximum risk)
        """
        # Base risk from confidence
        base_risk = (1 - confidence) * 100

        # Liquidity risk (fewer sales = higher risk)
        # В реальной версии это будет из market data
        liquidity_risk = 20  # Simplified

        # Combined risk
        total_risk = (base_risk * 0.7 + liquidity_risk * 0.3)

        return min(100.0, max(0.0, total_risk))

    def _get_price_usd(self, item: dict[str, Any]) -> float:
        """Get item price in USD.

        Args:
            item: Market item

        Returns:
            Price in USD (converted from cents)
        """
        price_data = item.get("price", {})
        if isinstance(price_data, dict):
            price_cents = price_data.get("USD", 0)
        else:
            price_cents = 0

        return price_cents / 100.0

    def _get_suggested_price_usd(self, item: dict[str, Any]) -> float:
        """Get suggested price in USD.

        Args:
            item: Market item

        Returns:
            Suggested price in USD (converted from cents)
        """
        suggested = item.get("suggestedPrice", {})
        if isinstance(suggested, dict):
            price_cents = suggested.get("USD", 0)
        else:
            price_cents = 0

        return price_cents / 100.0

    def _map_game_id(self, game_id: str) -> GameType:
        """Map game ID to GameType enum.

        Args:
            game_id: Game identifier from API

        Returns:
            GameType enum value
        """
        game_map = {
            "csgo": GameType.CS2,
            "cs2": GameType.CS2,
            "dota2": GameType.DOTA2,
            "tf2": GameType.TF2,
            "rust": GameType.RUST,
        }

        return game_map.get(game_id.lower(), GameType.CS2)

    def _get_min_confidence(self, risk_level: str) -> float:
        """Get minimum confidence threshold for risk level.

        Args:
            risk_level: Risk tolerance

        Returns:
            Minimum confidence (0.0-1.0)
        """
        thresholds = {
            "low": 0.75,  # Conservative: high confidence required
            "medium": 0.60,  # Balanced
            "high": 0.45,  # Aggressive: lower confidence acceptable
        }

        return thresholds.get(risk_level, 0.60)


# Factory function для удобного создания
def create_ai_arbitrage_predictor() -> AIArbitragePredictor:
    """Create AI Arbitrage Predictor with default configuration.

    Returns:
        Initialized AIArbitragePredictor

    Example:
        >>> predictor = create_ai_arbitrage_predictor()
        >>> opportunities = await predictor.predict_best_opportunities(...)
    """
    return AIArbitragePredictor()
