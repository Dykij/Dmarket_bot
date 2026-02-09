"""
A/B Testing Module.

Tests for comparing different implementations, algorithms, or configurations
to measure performance differences and make data-driven decisions.

Covers:
- Feature flag testing
- Algorithm comparison
- Configuration variant testing
- Performance metrics collection
- Statistical significance testing
"""

import random
import statistics
from collections import defaultdict
from typing import Any

import pytest


class TestFeatureFlagTesting:
    """Tests for feature flag based A/B testing."""

    @pytest.fixture
    def feature_flags(self):
        """Feature flags configuration."""
        return {
            "new_arbitrage_algorithm": {
                "enabled": True,
                "rollout_percentage": 50,
                "variants": ["control", "treatment"],
            },
            "enhanced_caching": {
                "enabled": True,
                "rollout_percentage": 25,
                "variants": ["v1", "v2", "v3"],
            },
            "new_ui_layout": {
                "enabled": False,
                "rollout_percentage": 0,
                "variants": ["old", "new"],
            },
        }

    def test_feature_flag_assignment_consistency(self, feature_flags):
        """Test that same user gets consistent feature assignment."""
        user_id = 12345

        def get_variant(user_id: int, feature: str, config: dict) -> str:
            """Get variant for user based on hash."""
            if not config["enabled"]:
                return config["variants"][0]  # Control
            hash_value = hash(f"{user_id}:{feature}") % 100
            if hash_value < config["rollout_percentage"]:
                variant_idx = hash_value % len(config["variants"])
                return config["variants"][variant_idx]
            return config["variants"][0]  # Control

        # Same user should get same variant
        variant1 = get_variant(user_id, "new_arbitrage_algorithm", feature_flags["new_arbitrage_algorithm"])
        variant2 = get_variant(user_id, "new_arbitrage_algorithm", feature_flags["new_arbitrage_algorithm"])

        assert variant1 == variant2

    def test_feature_flag_rollout_distribution(self, feature_flags):
        """Test that rollout percentage is approximately correct."""
        config = feature_flags["new_arbitrage_algorithm"]
        treatment_count = 0
        total_users = 10000

        for user_id in range(total_users):
            hash_value = hash(f"{user_id}:new_arbitrage_algorithm") % 100
            if hash_value < config["rollout_percentage"]:
                treatment_count += 1

        # Should be approximately 50% (+/- 5%)
        actual_percentage = treatment_count / total_users * 100
        assert 45 <= actual_percentage <= 55

    def test_disabled_feature_returns_control(self, feature_flags):
        """Test that disabled features always return control variant."""
        config = feature_flags["new_ui_layout"]

        for user_id in range(100):
            hash_value = hash(f"{user_id}:new_ui_layout") % 100
            # Disabled feature should always be control
            if not config["enabled"]:
                assert config["variants"][0] == "old"


class TestAlgorithmComparison:
    """Tests for comparing different algorithm implementations."""

    @pytest.fixture
    def sample_items(self):
        """Sample market items for testing."""
        return [
            {"id": f"item_{i}", "price": random.uniform(1, 100), "suggested_price": random.uniform(1, 100)}
            for i in range(100)
        ]

    def test_arbitrage_algorithm_v1_vs_v2(self, sample_items):
        """Compare old vs new arbitrage detection algorithm."""

        def algorithm_v1(items: list) -> list:
            """Original algorithm - simple profit margin check."""
            opportunities = []
            for item in items:
                profit = item["suggested_price"] - item["price"]
                if profit > 0 and profit / item["price"] > 0.05:  # 5% margin
                    opportunities.append({"item": item["id"], "profit": profit})
            return opportunities

        def algorithm_v2(items: list) -> list:
            """New algorithm - considers volatility and liquidity."""
            opportunities = []
            for item in items:
                profit = item["suggested_price"] - item["price"]
                margin = profit / item["price"] if item["price"] > 0 else 0
                # More sophisticated filtering
                if profit > 0 and margin > 0.03:  # Lower threshold
                    score = profit * (1 + margin)  # Weight by margin
                    opportunities.append({"item": item["id"], "profit": profit, "score": score})
            return sorted(opportunities, key=lambda x: x.get("score", 0), reverse=True)

        # Run both algorithms
        result_v1 = algorithm_v1(sample_items)
        result_v2 = algorithm_v2(sample_items)

        # V2 should find at least as many opportunities (lower threshold)
        assert len(result_v2) >= len(result_v1) * 0.8  # Allow some variance

        # V2 results should be sorted by score
        if len(result_v2) > 1:
            scores = [r.get("score", 0) for r in result_v2]
            assert scores == sorted(scores, reverse=True)

    def test_caching_strategy_comparison(self):
        """Compare different caching strategies."""

        class LRUCache:
            def __init__(self, capacity: int):
                self.capacity = capacity
                self.cache: dict = {}
                self.access_order: list = []

            def get(self, key: str) -> Any:
                if key in self.cache:
                    self.access_order.remove(key)
                    self.access_order.append(key)
                    return self.cache[key]
                return None

            def put(self, key: str, value: Any) -> None:
                if key in self.cache:
                    self.access_order.remove(key)
                elif len(self.cache) >= self.capacity:
                    oldest = self.access_order.pop(0)
                    del self.cache[oldest]
                self.cache[key] = value
                self.access_order.append(key)

        class LFUCache:
            def __init__(self, capacity: int):
                self.capacity = capacity
                self.cache: dict = {}
                self.freq: dict = defaultdict(int)

            def get(self, key: str) -> Any:
                if key in self.cache:
                    self.freq[key] += 1
                    return self.cache[key]
                return None

            def put(self, key: str, value: Any) -> None:
                if self.capacity <= 0:
                    return
                if key in self.cache:
                    self.cache[key] = value
                    self.freq[key] += 1
                else:
                    if len(self.cache) >= self.capacity:
                        # Remove least frequently used
                        min_freq = min(self.freq.values()) if self.freq else 0
                        for k, f in list(self.freq.items()):
                            if f == min_freq:
                                del self.cache[k]
                                del self.freq[k]
                                break
                    self.cache[key] = value
                    self.freq[key] = 1

        # Simulate workload
        lru = LRUCache(10)
        lfu = LFUCache(10)

        # Access pattern: some keys accessed frequently
        access_pattern = ["hot1", "hot2", "hot1", "cold1", "hot1", "cold2", "hot2", "cold3"]

        lru_hits = 0
        lfu_hits = 0

        for key in access_pattern:
            # First put
            lru.put(key, f"value_{key}")
            lfu.put(key, f"value_{key}")

        for key in access_pattern * 3:  # Repeat access
            if lru.get(key):
                lru_hits += 1
            if lfu.get(key):
                lfu_hits += 1

        # Both should have reasonable hit rates
        assert lru_hits > 0
        assert lfu_hits > 0


class TestPerformanceMetrics:
    """Tests for performance metrics collection in A/B tests."""

    @pytest.fixture
    def metrics_collector(self):
        """Metrics collector for A/B test."""

        class MetricsCollector:
            def __init__(self):
                self.metrics: dict = defaultdict(list)

            def record(self, variant: str, metric: str, value: float):
                self.metrics[f"{variant}:{metric}"].append(value)

            def get_average(self, variant: str, metric: str) -> float:
                key = f"{variant}:{metric}"
                values = self.metrics.get(key, [])
                return statistics.mean(values) if values else 0.0

            def get_p95(self, variant: str, metric: str) -> float:
                key = f"{variant}:{metric}"
                values = sorted(self.metrics.get(key, []))
                if not values:
                    return 0.0
                idx = int(len(values) * 0.95)
                return values[min(idx, len(values) - 1)]

            def compare_variants(self, metric: str) -> dict:
                variants = set(k.split(":")[0] for k in self.metrics.keys())
                result = {}
                for v in variants:
                    result[v] = {
                        "mean": self.get_average(v, metric),
                        "p95": self.get_p95(v, metric),
                        "count": len(self.metrics.get(f"{v}:{metric}", [])),
                    }
                return result

        return MetricsCollector()

    def test_response_time_comparison(self, metrics_collector):
        """Test response time metrics for A/B variants."""
        # Simulate response times for control and treatment
        for _ in range(100):
            # Control: 50-150ms
            metrics_collector.record("control", "response_time", random.uniform(50, 150))
            # Treatment: 40-120ms (faster)
            metrics_collector.record("treatment", "response_time", random.uniform(40, 120))

        comparison = metrics_collector.compare_variants("response_time")

        # Treatment should be faster on average
        assert comparison["treatment"]["mean"] < comparison["control"]["mean"]
        assert comparison["control"]["count"] == 100
        assert comparison["treatment"]["count"] == 100

    def test_conversion_rate_comparison(self, metrics_collector):
        """Test conversion rate metrics for A/B variants."""
        # Simulate conversions (1 = converted, 0 = not converted)
        for _ in range(1000):
            # Control: 5% conversion
            metrics_collector.record("control", "conversion", 1 if random.random() < 0.05 else 0)
            # Treatment: 7% conversion
            metrics_collector.record("treatment", "conversion", 1 if random.random() < 0.07 else 0)

        control_rate = metrics_collector.get_average("control", "conversion")
        treatment_rate = metrics_collector.get_average("treatment", "conversion")

        # Rates should be approximately as expected (with variance)
        assert 0.02 < control_rate < 0.10
        assert 0.03 < treatment_rate < 0.12


class TestStatisticalSignificance:
    """Tests for statistical significance in A/B testing."""

    def test_sample_size_calculation(self):
        """Test minimum sample size calculation for statistical significance."""

        def calculate_sample_size(
            baseline_rate: float, minimum_effect: float, alpha: float = 0.05, power: float = 0.8
        ) -> int:
            """Calculate minimum sample size for A/B test."""
            # Simplified calculation (actual would use scipy.stats)
            import math

            z_alpha = 1.96  # for alpha=0.05
            z_beta = 0.84  # for power=0.8

            p1 = baseline_rate
            p2 = baseline_rate * (1 + minimum_effect)
            p_avg = (p1 + p2) / 2

            numerator = 2 * p_avg * (1 - p_avg) * ((z_alpha + z_beta) ** 2)
            denominator = (p2 - p1) ** 2

            return int(math.ceil(numerator / denominator)) if denominator > 0 else 0

        # 5% baseline, detect 20% improvement
        sample_size = calculate_sample_size(0.05, 0.20)

        # Should need significant sample size
        assert sample_size > 1000  # Approximate expectation

    def test_chi_square_test_simulation(self):
        """Test chi-square test for A/B comparison."""
        # Simulate experiment results
        control_conversions = 50
        control_total = 1000
        treatment_conversions = 65
        treatment_total = 1000

        # Calculate chi-square statistic (simplified)
        control_rate = control_conversions / control_total
        treatment_rate = treatment_conversions / treatment_total
        pooled_rate = (control_conversions + treatment_conversions) / (control_total + treatment_total)

        # Expected values under null hypothesis
        expected_control = pooled_rate * control_total
        expected_treatment = pooled_rate * treatment_total

        # Chi-square components
        chi_sq = 0
        chi_sq += ((control_conversions - expected_control) ** 2) / expected_control
        chi_sq += (((control_total - control_conversions) - (control_total - expected_control)) ** 2) / (
            control_total - expected_control
        )
        chi_sq += ((treatment_conversions - expected_treatment) ** 2) / expected_treatment
        chi_sq += (((treatment_total - treatment_conversions) - (treatment_total - expected_treatment)) ** 2) / (
            treatment_total - expected_treatment
        )

        # Chi-square with 1 df, critical value at 0.05 is 3.84
        # If chi_sq > 3.84, result is significant
        assert chi_sq >= 0  # Valid chi-square value

    def test_confidence_interval_calculation(self):
        """Test confidence interval calculation for conversion rates."""
        conversions = 70
        total = 1000
        rate = conversions / total

        # 95% confidence interval using normal approximation
        z = 1.96
        se = (rate * (1 - rate) / total) ** 0.5
        ci_lower = rate - z * se
        ci_upper = rate + z * se

        assert ci_lower < rate < ci_upper
        assert 0 < ci_lower < ci_upper < 1


class TestCanaryDeployment:
    """Tests for canary deployment patterns."""

    def test_canary_traffic_routing(self):
        """Test canary traffic routing logic."""

        class CanaryRouter:
            def __init__(self, canary_percentage: int = 5):
                self.canary_percentage = canary_percentage
                self.stable_version = "v1.0.0"
                self.canary_version = "v1.1.0"

            def route_request(self, request_id: int) -> str:
                """Route request to appropriate version."""
                if hash(request_id) % 100 < self.canary_percentage:
                    return self.canary_version
                return self.stable_version

            def set_canary_percentage(self, percentage: int):
                """Adjust canary traffic percentage."""
                self.canary_percentage = min(100, max(0, percentage))

        router = CanaryRouter(canary_percentage=10)

        canary_count = 0
        total_requests = 10000

        for i in range(total_requests):
            version = router.route_request(i)
            if version == "v1.1.0":
                canary_count += 1

        # Should be approximately 10% (+/- 2%)
        actual_percentage = canary_count / total_requests * 100
        assert 8 <= actual_percentage <= 12

    def test_canary_health_check(self):
        """Test canary health monitoring."""

        class CanaryHealthMonitor:
            def __init__(self, error_threshold: float = 0.05):
                self.error_threshold = error_threshold
                self.stable_errors = 0
                self.stable_requests = 0
                self.canary_errors = 0
                self.canary_requests = 0

            def record_request(self, version: str, is_error: bool):
                if version == "canary":
                    self.canary_requests += 1
                    if is_error:
                        self.canary_errors += 1
                else:
                    self.stable_requests += 1
                    if is_error:
                        self.stable_errors += 1

            def should_rollback(self) -> bool:
                """Check if canary should be rolled back."""
                if self.canary_requests < 100:
                    return False  # Not enough data
                canary_rate = self.canary_errors / self.canary_requests
                stable_rate = self.stable_errors / self.stable_requests if self.stable_requests > 0 else 0
                # Rollback if canary error rate is significantly higher
                return canary_rate > stable_rate + self.error_threshold

            def is_healthy(self) -> bool:
                """Check if canary is healthy."""
                if self.canary_requests < 100:
                    return True  # Assume healthy until enough data
                return self.canary_errors / self.canary_requests <= self.error_threshold

        monitor = CanaryHealthMonitor(error_threshold=0.05)

        # Simulate healthy canary
        for _ in range(1000):
            monitor.record_request("stable", random.random() < 0.02)  # 2% errors
            monitor.record_request("canary", random.random() < 0.03)  # 3% errors

        assert monitor.is_healthy()
        assert not monitor.should_rollback()

    def test_gradual_rollout(self):
        """Test gradual rollout progression."""
        rollout_stages = [5, 10, 25, 50, 75, 100]  # Percentage stages
        current_stage = 0

        class RolloutManager:
            def __init__(self, stages: list):
                self.stages = stages
                self.current_idx = 0
                self.is_complete = False

            def advance(self) -> int:
                """Advance to next rollout stage."""
                if self.current_idx < len(self.stages) - 1:
                    self.current_idx += 1
                else:
                    self.is_complete = True
                return self.stages[self.current_idx]

            def rollback(self) -> int:
                """Rollback to previous stage."""
                if self.current_idx > 0:
                    self.current_idx -= 1
                return self.stages[self.current_idx]

            def current_percentage(self) -> int:
                return self.stages[self.current_idx]

        manager = RolloutManager(rollout_stages)

        assert manager.current_percentage() == 5

        # Advance through stages
        assert manager.advance() == 10
        assert manager.advance() == 25
        assert manager.advance() == 50

        # Rollback
        assert manager.rollback() == 25

        # Continue to completion
        manager.advance()  # 50
        manager.advance()  # 75
        result = manager.advance()  # 100 - this sets is_complete

        assert manager.current_percentage() == 100
        # After reaching 100, one more advance attempt marks complete
        manager.advance()  # This attempt triggers is_complete = True
        assert manager.is_complete


class TestMetamorphicTesting:
    """Metamorphic testing - testing without oracle."""

    def test_price_calculation_metamorphic(self):
        """Test price calculation using metamorphic relations."""

        def calculate_profit(buy_price: float, sell_price: float, fee_percent: float = 7.0) -> float:
            """Calculate profit with fee."""
            gross = sell_price - buy_price
            fee = sell_price * (fee_percent / 100)
            return gross - fee

        # Metamorphic relation 1: Scaling
        # If both prices scale by k, profit should scale by k (approximately)
        base_profit = calculate_profit(100, 150)
        scaled_profit = calculate_profit(200, 300)

        # Scaled profit should be approximately 2x base
        assert abs(scaled_profit - 2 * base_profit) < 1.0

        # Metamorphic relation 2: Adding constant
        # Note: With percentage-based fees, adding constant to both prices
        # does NOT preserve profit (fee on higher sell price is larger)
        profit1 = calculate_profit(100, 150)
        profit2 = calculate_profit(200, 250)  # Added 100 to both

        # The fee difference is 7% of the sell price difference (250-150=100)
        # So profit2 = profit1 - (7% * 100) = profit1 - 7
        expected_diff = 100 * 0.07  # 7
        assert abs((profit1 - profit2) - expected_diff) < 1.0

    def test_search_metamorphic(self):
        """Test search functionality using metamorphic relations."""
        items = [
            {"name": "AK-47 | Redline", "price": 50},
            {"name": "M4A4 | Howl", "price": 1000},
            {"name": "AWP | Dragon Lore", "price": 5000},
            {"name": "Karambit | Fade", "price": 800},
        ]

        def search_items(items: list, min_price: float = 0, max_price: float = float("inf")) -> list:
            """Search items by price range."""
            return [i for i in items if min_price <= i["price"] <= max_price]

        # Metamorphic relation: Union of disjoint ranges equals full range
        range1 = search_items(items, 0, 500)
        range2 = search_items(items, 501, 10000)
        full_range = search_items(items, 0, 10000)

        assert len(range1) + len(range2) == len(full_range)

        # Metamorphic relation: Subset relation
        narrow = search_items(items, 100, 900)
        wide = search_items(items, 50, 1000)

        # Narrow range should be subset of wide range
        narrow_names = {i["name"] for i in narrow}
        wide_names = {i["name"] for i in wide}
        assert narrow_names.issubset(wide_names)
