"""
Тесты для модуля liquidity_rules.py.

Тестирует правила и константы для анализа ликвидности предметов.
"""

import pytest

from src.dmarket.liquidity_rules import (
    AGGRESSIVE_RULES,
    BALANCED_RULES,
    CONSERVATIVE_RULES,
    LIQUIDITY_RECOMMENDATIONS,
    LIQUIDITY_SCORE_WEIGHTS,
    LIQUIDITY_THRESHOLDS,
    LiquidityRules,
    get_liquidity_category,
    get_liquidity_recommendation,
)


class TestLiquidityRulesDataclass:
    """Тесты для dataclass LiquidityRules."""

    def test_default_values(self):
        """Проверка значений по умолчанию."""
        rules = LiquidityRules()

        assert rules.min_sales_per_week == 10.0
        assert rules.max_time_to_sell_days == 7.0
        assert rules.max_active_offers == 50
        assert rules.min_price_stability == 0.85
        assert rules.min_liquidity_score == 60.0

    def test_custom_values(self):
        """Проверка создания с кастомными значениями."""
        rules = LiquidityRules(
            min_sales_per_week=20.0,
            max_time_to_sell_days=3.0,
            max_active_offers=100,
            min_price_stability=0.95,
            min_liquidity_score=80.0,
        )

        assert rules.min_sales_per_week == 20.0
        assert rules.max_time_to_sell_days == 3.0
        assert rules.max_active_offers == 100
        assert rules.min_price_stability == 0.95
        assert rules.min_liquidity_score == 80.0

    def test_partial_custom_values(self):
        """Проверка создания с частично кастомными значениями."""
        rules = LiquidityRules(min_sales_per_week=25.0)

        assert rules.min_sales_per_week == 25.0
        assert rules.max_time_to_sell_days == 7.0  # default

    def test_edge_values_zero(self):
        """Тест с нулевыми значениями."""
        rules = LiquidityRules(
            min_sales_per_week=0.0,
            min_price_stability=0.0,
            min_liquidity_score=0.0,
        )

        assert rules.min_sales_per_week == 0.0
        assert rules.min_price_stability == 0.0
        assert rules.min_liquidity_score == 0.0


class TestPresetRules:
    """Тесты для предустановленных профилей правил."""

    def test_conservative_rules(self):
        """Проверка консервативных правил."""
        assert CONSERVATIVE_RULES.min_sales_per_week == 15.0
        assert CONSERVATIVE_RULES.max_time_to_sell_days == 5.0
        assert CONSERVATIVE_RULES.max_active_offers == 30
        assert CONSERVATIVE_RULES.min_price_stability == 0.90
        assert CONSERVATIVE_RULES.min_liquidity_score == 70.0

    def test_balanced_rules(self):
        """Проверка сбалансированных правил."""
        assert BALANCED_RULES.min_sales_per_week == 10.0
        assert BALANCED_RULES.max_time_to_sell_days == 7.0
        assert BALANCED_RULES.max_active_offers == 50
        assert BALANCED_RULES.min_price_stability == 0.85
        assert BALANCED_RULES.min_liquidity_score == 60.0

    def test_aggressive_rules(self):
        """Проверка агрессивных правил."""
        assert AGGRESSIVE_RULES.min_sales_per_week == 5.0
        assert AGGRESSIVE_RULES.max_time_to_sell_days == 10.0
        assert AGGRESSIVE_RULES.max_active_offers == 70
        assert AGGRESSIVE_RULES.min_price_stability == 0.75
        assert AGGRESSIVE_RULES.min_liquidity_score == 50.0

    def test_conservative_stricter_than_balanced(self):
        """Консервативные правила должны быть строже сбалансированных."""
        assert CONSERVATIVE_RULES.min_sales_per_week > BALANCED_RULES.min_sales_per_week
        assert (
            CONSERVATIVE_RULES.max_time_to_sell_days
            < BALANCED_RULES.max_time_to_sell_days
        )
        assert CONSERVATIVE_RULES.max_active_offers < BALANCED_RULES.max_active_offers
        assert (
            CONSERVATIVE_RULES.min_price_stability > BALANCED_RULES.min_price_stability
        )
        assert (
            CONSERVATIVE_RULES.min_liquidity_score > BALANCED_RULES.min_liquidity_score
        )

    def test_balanced_stricter_than_aggressive(self):
        """Сбалансированные правила должны быть строже агрессивных."""
        assert BALANCED_RULES.min_sales_per_week > AGGRESSIVE_RULES.min_sales_per_week
        assert (
            BALANCED_RULES.max_time_to_sell_days
            < AGGRESSIVE_RULES.max_time_to_sell_days
        )
        assert BALANCED_RULES.max_active_offers < AGGRESSIVE_RULES.max_active_offers
        assert BALANCED_RULES.min_price_stability > AGGRESSIVE_RULES.min_price_stability
        assert BALANCED_RULES.min_liquidity_score > AGGRESSIVE_RULES.min_liquidity_score


class TestLiquidityScoreWeights:
    """Тесты для весов расчета liquidity score."""

    def test_weights_sum_to_one(self):
        """Сумма весов должна быть равна 1.0."""
        total = sum(LIQUIDITY_SCORE_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_all_weights_positive(self):
        """Все веса должны быть положительными."""
        for weight in LIQUIDITY_SCORE_WEIGHTS.values():
            assert weight > 0

    def test_expected_weight_categories(self):
        """Проверка наличия ожидаемых категорий весов."""
        expected_keys = {
            "sales_volume",
            "time_to_sell",
            "price_stability",
            "demand_supply",
            "market_depth",
        }
        assert set(LIQUIDITY_SCORE_WEIGHTS.keys()) == expected_keys

    def test_sales_volume_has_highest_weight(self):
        """Sales volume должен иметь наибольший вес."""
        max_weight = max(LIQUIDITY_SCORE_WEIGHTS.values())
        assert LIQUIDITY_SCORE_WEIGHTS["sales_volume"] == max_weight


class TestLiquidityThresholds:
    """Тесты для порогов ликвидности."""

    def test_threshold_values(self):
        """Проверка значений порогов."""
        assert LIQUIDITY_THRESHOLDS["very_high"] == 80.0
        assert LIQUIDITY_THRESHOLDS["high"] == 60.0
        assert LIQUIDITY_THRESHOLDS["medium"] == 40.0
        assert LIQUIDITY_THRESHOLDS["low"] == 20.0
        assert LIQUIDITY_THRESHOLDS["very_low"] == 0.0

    def test_thresholds_decreasing_order(self):
        """Пороги должны быть в порядке убывания."""
        assert LIQUIDITY_THRESHOLDS["very_high"] > LIQUIDITY_THRESHOLDS["high"]
        assert LIQUIDITY_THRESHOLDS["high"] > LIQUIDITY_THRESHOLDS["medium"]
        assert LIQUIDITY_THRESHOLDS["medium"] > LIQUIDITY_THRESHOLDS["low"]
        assert LIQUIDITY_THRESHOLDS["low"] > LIQUIDITY_THRESHOLDS["very_low"]


class TestLiquidityRecommendations:
    """Тесты для рекомендаций по ликвидности."""

    def test_all_categories_have_recommendations(self):
        """Все категории должны иметь рекомендации."""
        expected_categories = {"very_high", "high", "medium", "low", "very_low"}
        assert set(LIQUIDITY_RECOMMENDATIONS.keys()) == expected_categories

    def test_recommendations_not_empty(self):
        """Все рекомендации не должны быть пустыми."""
        for recommendation in LIQUIDITY_RECOMMENDATIONS.values():
            assert len(recommendation) > 0

    def test_positive_recommendations_contain_checkmark(self):
        """Положительные рекомендации должны содержать ✅."""
        assert "✅" in LIQUIDITY_RECOMMENDATIONS["very_high"]
        assert "✅" in LIQUIDITY_RECOMMENDATIONS["high"]

    def test_negative_recommendations_contain_warning(self):
        """Негативные рекомендации должны содержать ⚠️ или ❌."""
        assert (
            "⚠️" in LIQUIDITY_RECOMMENDATIONS["medium"]
            or "❌" in LIQUIDITY_RECOMMENDATIONS["medium"]
        )
        assert "❌" in LIQUIDITY_RECOMMENDATIONS["low"]
        assert "❌" in LIQUIDITY_RECOMMENDATIONS["very_low"]


class TestGetLiquidityCategory:
    """Тесты для функции get_liquidity_category."""

    @pytest.mark.parametrize(
        ("score", "expected_category"),
        (
            (100.0, "very_high"),
            (90.0, "very_high"),
            (80.0, "very_high"),
            (79.9, "high"),
            (70.0, "high"),
            (60.0, "high"),
            (59.9, "medium"),
            (50.0, "medium"),
            (40.0, "medium"),
            (39.9, "low"),
            (30.0, "low"),
            (20.0, "low"),
            (19.9, "very_low"),
            (10.0, "very_low"),
            (0.0, "very_low"),
        ),
    )
    def test_category_by_score(self, score: float, expected_category: str):
        """Тест определения категории по score."""
        assert get_liquidity_category(score) == expected_category

    def test_boundary_very_high(self):
        """Тест границы very_high."""
        assert get_liquidity_category(80.0) == "very_high"
        assert get_liquidity_category(79.99) == "high"

    def test_boundary_high(self):
        """Тест границы high."""
        assert get_liquidity_category(60.0) == "high"
        assert get_liquidity_category(59.99) == "medium"

    def test_boundary_medium(self):
        """Тест границы medium."""
        assert get_liquidity_category(40.0) == "medium"
        assert get_liquidity_category(39.99) == "low"

    def test_boundary_low(self):
        """Тест границы low."""
        assert get_liquidity_category(20.0) == "low"
        assert get_liquidity_category(19.99) == "very_low"

    def test_negative_score(self):
        """Тест с отрицательным score."""
        assert get_liquidity_category(-10.0) == "very_low"

    def test_extreme_high_score(self):
        """Тест с очень высоким score."""
        assert get_liquidity_category(999.0) == "very_high"


class TestGetLiquidityRecommendation:
    """Тесты для функции get_liquidity_recommendation."""

    def test_very_high_recommendation(self):
        """Тест рекомендации для very_high."""
        recommendation = get_liquidity_recommendation(90.0)
        assert "✅" in recommendation
        assert "Отличный" in recommendation

    def test_high_recommendation(self):
        """Тест рекомендации для high."""
        recommendation = get_liquidity_recommendation(70.0)
        assert "✅" in recommendation
        assert "Хороший" in recommendation

    def test_medium_recommendation(self):
        """Тест рекомендации для medium."""
        recommendation = get_liquidity_recommendation(50.0)
        assert "⚠️" in recommendation
        assert "Осторожно" in recommendation

    def test_low_recommendation(self):
        """Тест рекомендации для low."""
        recommendation = get_liquidity_recommendation(25.0)
        assert "❌" in recommendation
        assert "Не рекомендуется" in recommendation

    def test_very_low_recommendation(self):
        """Тест рекомендации для very_low."""
        recommendation = get_liquidity_recommendation(5.0)
        assert "❌" in recommendation
        assert "Избегать" in recommendation

    @pytest.mark.parametrize("score", (0.0, 25.0, 50.0, 75.0, 100.0))
    def test_recommendation_is_string(self, score: float):
        """Рекомендация должна быть непустой строкой."""
        recommendation = get_liquidity_recommendation(score)
        assert isinstance(recommendation, str)
        assert len(recommendation) > 10

    def test_recommendation_consistency_with_category(self):
        """Рекомендация должна соответствовать категории."""
        for score in [5.0, 25.0, 50.0, 70.0, 90.0]:
            category = get_liquidity_category(score)
            recommendation = get_liquidity_recommendation(score)
            assert recommendation == LIQUIDITY_RECOMMENDATIONS[category]
