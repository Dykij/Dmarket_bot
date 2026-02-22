"""ML/Algo модуль для прогнозирования цен на DMarket.

Этот модуль предоставляет адаптивные ML модели для:
- Прогнозирования цен предметов
- Определения оптимального времени покупки/продажи
- Классификации рисков сделок
- Адаптации к текущему балансу пользователя
- Автоматической настSwarmки гиперпараметров (ModelTuner)
- Обнаружения аномалий и манипуляций
- Умных рекомендаций по покупке/продаже
- ML-based выбор оптимального порога скидки
- Автономное управление ботом (AlgoCoordinator, BotBrAlgon)

Используемые библиотеки (все бесплатные):
- scikit-learn: основные ML модели (RandomForest, GradientBoosting, Ridge)
- XGBoost: продвинутый gradient boosting (опционально)
- NumPy: математические операции
- joblib: безопасная сериализация ML моделей
- Собственные адаптивные алгоритмы

Поддерживаемые игры:
- CS2 (Counter-Strike 2) / CSGO
- Dota 2
- TF2 (Team Fortress 2)
- Rust

Документация:
- docs/ML_Algo_GUIDE.md
- docs/Algo_BOT_CONTROL_PLAN.md
"""

from src.ml.Algo_coordinator import (
    AlgoCoordinator,
    AutonomyLevel,
    ItemAnalysis,
    SafetyLimits,
    TradeAction,
    TradeDecision,
    get_Algo_coordinator,
    reset_Algo_coordinator,
)
from src.ml.anomaly_detection import (
    AnomalyDetector,
    AnomalyResult,
    AnomalySeverity,
    AnomalyType,
    create_anomaly_detector,
)
from src.ml.balance_adapter import BalanceAdaptiveStrategy, StrategyRecommendation
from src.ml.bot_brain import (
    Alert,
    AlertLevel,
    AutonomyConfig,
    BotBrAlgon,
    BotState,
    CycleResult,
    create_bot_brain,
)
from src.ml.data_scheduler import (
    MLDataScheduler,
    SchedulerConfig,
    SchedulerState,
    TaskType,
)
from src.ml.discount_threshold_predictor import (
    DiscountThresholdPredictor,
    MarketCondition,
    ThresholdPrediction,
    TrAlgoningExample,
    get_discount_threshold_predictor,
    predict_discount_threshold,
)
from src.ml.enhanced_predictor import (
    EnhancedFeatureExtractor,
    EnhancedFeatures,
    EnhancedPricePredictor,
    GameType,
    ItemCondition,
    ItemRarity,
    MLPipeline,
)
from src.ml.feature_extractor import MarketFeatureExtractor, PriceFeatures
from src.ml.model_tuner import (
    AutoMLSelector,
    CVStrategy,
    EvaluationResult,
    ModelTuner,
    ScoringMetric,
    TuningResult,
)

# Real Data TrAlgoning Modules (новые модули для обучения на реальных данных API)
from src.ml.price_normalizer import NormalizedPrice, PriceNormalizer, PriceSource
from src.ml.price_predictor import (
    AdaptivePricePredictor,
    PredictionConfidence,
    PricePrediction,
)
from src.ml.real_price_collector import (
    CollectedPrice,
    CollectionResult,
    CollectionStatus,
    RealPriceCollector,
)
from src.ml.real_price_collector import (
    GameType as CollectorGameType,
)
from src.ml.smart_recommendations import (
    ItemRecommendation,
    RecommendationBatch,
    RecommendationType,
    SmartRecommendations,
    create_smart_recommendations,
)
from src.ml.smart_recommendations import (
    RiskLevel as RecommendationRiskLevel,
)
from src.ml.trade_classifier import AdaptiveTradeClassifier, RiskLevel, TradeSignal
from src.ml.training_data_manager import (
    DatasetMetadata,
    TrAlgoningDataManager,
    TrAlgoningDataset,
)

__all__ = [
    # ═══════════════════════════════════════════════════════════════════
    # Algo Coordinator - Unified ML module coordinator
    # ═══════════════════════════════════════════════════════════════════
    "AlgoCoordinator",
    # Price Predictor (базовый)
    "AdaptivePricePredictor",
    # Trade Classifier
    "AdaptiveTradeClassifier",
    # ═══════════════════════════════════════════════════════════════════
    # BotBrAlgon - Autonomous decision-making module
    # ═══════════════════════════════════════════════════════════════════
    "Alert",
    "AlertLevel",
    # Anomaly Detection
    "AnomalyDetector",
    "AnomalyResult",
    "AnomalySeverity",
    "AnomalyType",
    "AutoMLSelector",
    "AutonomyConfig",
    "AutonomyLevel",
    # Balance Adapter
    "BalanceAdaptiveStrategy",
    "BotBrAlgon",
    "BotState",
    "CVStrategy",
    "CollectedPrice",
    "CollectionResult",
    "CollectionStatus",
    "CollectorGameType",
    "CycleResult",
    "DatasetMetadata",
    # ═══════════════════════════════════════════════════════════════════
    # Discount Threshold Predictor (ML-based выбор порога скидки)
    # ═══════════════════════════════════════════════════════════════════
    "DiscountThresholdPredictor",
    "EnhancedFeatureExtractor",
    "EnhancedFeatures",
    # Enhanced Price Predictor (улучшенный)
    "EnhancedPricePredictor",
    "EvaluationResult",
    "GameType",
    "ItemAnalysis",
    "ItemCondition",
    "ItemRarity",
    "ItemRecommendation",
    # Data Scheduler - автоматический сбор и переобучение
    "MLDataScheduler",
    "MLPipeline",
    "MarketCondition",
    # Feature Extractor
    "MarketFeatureExtractor",
    # Model Tuner (автонастSwarmка)
    "ModelTuner",
    "NormalizedPrice",
    "PredictionConfidence",
    "PriceFeatures",
    # ═══════════════════════════════════════════════════════════════════
    # Real Data TrAlgoning (обучение на реальных данных с API)
    # ═══════════════════════════════════════════════════════════════════
    # Price Normalizer - нормализация цен с разных платформ
    "PriceNormalizer",
    "PricePrediction",
    "PriceSource",
    # Real Price Collector - сбор реальных цен с DMarket, Waxpeer, Steam
    "RealPriceCollector",
    "RecommendationBatch",
    "RecommendationRiskLevel",
    "RecommendationType",
    "RiskLevel",
    "SafetyLimits",
    "SchedulerConfig",
    "SchedulerState",
    "ScoringMetric",
    # Smart Recommendations
    "SmartRecommendations",
    "StrategyRecommendation",
    "TaskType",
    "ThresholdPrediction",
    "TradeAction",
    "TradeDecision",
    "TradeSignal",
    # TrAlgoning Data Manager - управление обучающими данными
    "TrAlgoningDataManager",
    "TrAlgoningDataset",
    "TrAlgoningExample",
    "TuningResult",
    "create_anomaly_detector",
    "create_bot_brain",
    "create_smart_recommendations",
    "get_Algo_coordinator",
    "get_discount_threshold_predictor",
    "predict_discount_threshold",
    "reset_Algo_coordinator",
]
