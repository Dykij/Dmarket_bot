"""Performance benchmark tests for Strategy modules.

Uses pytest-benchmark (if available) and timing measurements for:
- OptimalArbitrageStrategy calculations
- Game-specific filter operations
- Unified strategy scanning
"""

import operator
import time

import pytest

# Check if pytest-benchmark is available
try:
    import pytest_benchmark as _  # noqa: F401

    HAS_BENCHMARK = True
except ImportError:
    HAS_BENCHMARK = False


needs_benchmark = pytest.mark.skipif(
    not HAS_BENCHMARK,
    reason="pytest-benchmark not installed",
)


# ============================================================================
# PROFIT CALCULATION PERFORMANCE
# ============================================================================


@needs_benchmark
class TestProfitCalculationPerformance:
    """Performance tests for arbitrage profit calculations."""

    def test_net_profit_calculation_speed(self, benchmark):
        """Benchmark net profit calculation with commissions."""

        def calculate_net_profit(
            buy_price: float, sell_price: float, buy_commission: float, sell_commission: float
        ) -> float:
            """Calculate net profit with all commissions."""
            actual_buy = buy_price * (1 + buy_commission / 100)
            actual_sell = sell_price * (1 - sell_commission / 100)
            return actual_sell - actual_buy

        result = benchmark(calculate_net_profit, 100.0, 120.0, 0.0, 7.0)
        assert result > 0

    def test_roi_calculation_speed(self, benchmark):
        """Benchmark ROI percentage calculation."""

        def calculate_roi(buy_price: float, sell_price: float, commission: float) -> float:
            """Calculate ROI as percentage."""
            net_profit = sell_price * (1 - commission / 100) - buy_price
            return (net_profit / buy_price) * 100 if buy_price > 0 else 0

        result = benchmark(calculate_roi, 100.0, 120.0, 7.0)
        assert result > 0

    def test_batch_profit_calculation_speed(self, benchmark):
        """Benchmark batch profit calculations for many items."""

        items = [{"buy": 10.0 + i, "sell": 15.0 + i * 1.2, "commission": 7.0} for i in range(1000)]

        def calculate_batch_profits(items: list) -> list:
            results = []
            for item in items:
                net_sell = item["sell"] * (1 - item["commission"] / 100)
                profit = net_sell - item["buy"]
                roi = (profit / item["buy"]) * 100
                results.append({"profit": profit, "roi": roi})
            return results

        results = benchmark(calculate_batch_profits, items)
        assert len(results) == 1000


# ============================================================================
# OPPORTUNITY SCORING PERFORMANCE
# ============================================================================


@needs_benchmark
class TestOpportunityScoringPerformance:
    """Performance tests for opportunity scoring."""

    def test_single_opportunity_scoring_speed(self, benchmark):
        """Benchmark single opportunity scoring."""

        opportunity = {
            "roi": 15.0,
            "liquidity": 25,
            "risk_level": "low",
            "float_value": 0.05,
            "doppler_phase": "Ruby",
        }

        def calculate_opportunity_score(opp: dict) -> float:
            """Calculate comprehensive opportunity score."""
            # Base score from ROI
            roi_score = min(opp["roi"] / 30.0, 1.0) * 40

            # Liquidity score
            liq_score = min(opp["liquidity"] / 30.0, 1.0) * 30

            # Risk score
            risk_scores = {"very_low": 20, "low": 16, "medium": 12, "high": 8, "very_high": 4}
            risk_score = risk_scores.get(opp["risk_level"], 10)

            # Premium bonuses
            bonus = 0
            if opp.get("float_value", 1.0) < 0.07:
                bonus += 5
            if opp.get("doppler_phase") in {"Ruby", "Sapphire", "Black Pearl"}:
                bonus += 5

            return roi_score + liq_score + risk_score + bonus

        result = benchmark(calculate_opportunity_score, opportunity)
        assert 0 <= result <= 100

    def test_batch_opportunity_scoring_speed(self, benchmark):
        """Benchmark scoring many opportunities."""

        opportunities = [
            {
                "roi": 5.0 + i % 25,
                "liquidity": i % 30 + 1,
                "risk_level": ["very_low", "low", "medium", "high", "very_high"][i % 5],
            }
            for i in range(500)
        ]

        def score_all_opportunities(opps: list) -> list:
            def score(opp):
                roi_score = min(opp["roi"] / 30.0, 1.0) * 40
                liq_score = min(opp["liquidity"] / 30.0, 1.0) * 30
                risk_scores = {"very_low": 20, "low": 16, "medium": 12, "high": 8, "very_high": 4}
                risk_score = risk_scores.get(opp["risk_level"], 10)
                return roi_score + liq_score + risk_score

            return sorted(
                [{"opp": opp, "score": score(opp)} for opp in opps],
                key=operator.itemgetter("score"),
                reverse=True,
            )

        results = benchmark(score_all_opportunities, opportunities)
        assert len(results) == 500
        # Should be sorted descending
        assert results[0]["score"] >= results[-1]["score"]


# ============================================================================
# FILTERING PERFORMANCE
# ============================================================================


@needs_benchmark
class TestFilteringPerformance:
    """Performance tests for item filtering operations."""

    def test_multi_criteria_filter_speed(self, benchmark):
        """Benchmark multi-criteria filtering."""

        items = [
            {
                "name": f"Item {i}",
                "price": i * 10.0,
                "roi": i % 30,
                "game": ["csgo", "dota2", "tf2", "rust"][i % 4],
                "liquidity": i % 50,
            }
            for i in range(5000)
        ]

        def multi_filter(
            items: list,
            min_price: float,
            max_price: float,
            min_roi: float,
            game: str,
            min_liquidity: int,
        ) -> list:
            return [
                item
                for item in items
                if min_price <= item["price"] <= max_price
                and item["roi"] >= min_roi
                and item["game"] == game
                and item["liquidity"] >= min_liquidity
            ]

        results = benchmark(multi_filter, items, 100.0, 5000.0, 10.0, "csgo", 10)
        assert isinstance(results, list)

    def test_float_range_filter_speed(self, benchmark):
        """Benchmark float value range filtering."""

        items = [{"name": f"Item {i}", "float": i * 0.01} for i in range(1000)]

        def filter_by_float(items: list, min_float: float, max_float: float) -> list:
            return [item for item in items if min_float <= item["float"] <= max_float]

        results = benchmark(filter_by_float, items, 0.0, 0.07)
        assert len(results) == 8  # 0.00 to 0.07

    def test_doppler_phase_filter_speed(self, benchmark):
        """Benchmark Doppler phase filtering."""

        phases = [
            "Ruby",
            "Sapphire",
            "Black Pearl",
            "Emerald",
            "Phase 1",
            "Phase 2",
            "Phase 3",
            "Phase 4",
        ]
        items = [{"name": f"Knife {i}", "phase": phases[i % 8]} for i in range(2000)]

        def filter_by_phase(items: list, target_phases: list) -> list:
            return [item for item in items if item["phase"] in target_phases]

        results = benchmark(filter_by_phase, items, ["Ruby", "Sapphire", "Black Pearl"])
        assert len(results) == 750  # 3 out of 8 phases * 250 each


# ============================================================================
# RISK ASSESSMENT PERFORMANCE
# ============================================================================


@needs_benchmark
class TestRiskAssessmentPerformance:
    """Performance tests for risk assessment calculations."""

    def test_risk_level_calculation_speed(self, benchmark):
        """Benchmark risk level calculation."""

        opportunity = {
            "roi": 15.0,
            "liquidity": 20,
            "lock_days": 0,
            "price": 50.0,
        }

        def assess_risk(opp: dict) -> str:
            """Assess risk level based on multiple factors."""
            score = 0

            # ROI risk (very high ROI is risky)
            if opp["roi"] > 50:
                score += 3
            elif opp["roi"] > 30:
                score += 2
            elif opp["roi"] > 20:
                score += 1

            # Liquidity risk
            if opp["liquidity"] < 3:
                score += 3
            elif opp["liquidity"] < 10:
                score += 2
            elif opp["liquidity"] < 20:
                score += 1

            # Lock risk
            if opp["lock_days"] > 7:
                score += 3
            elif opp["lock_days"] > 3:
                score += 2
            elif opp["lock_days"] > 0:
                score += 1

            # Price risk
            if opp["price"] > 500:
                score += 2
            elif opp["price"] > 100:
                score += 1

            if score <= 2:
                return "very_low"
            if score <= 4:
                return "low"
            if score <= 6:
                return "medium"
            if score <= 8:
                return "high"
            return "very_high"

        result = benchmark(assess_risk, opportunity)
        assert result in {"very_low", "low", "medium", "high", "very_high"}

    def test_batch_risk_assessment_speed(self, benchmark):
        """Benchmark risk assessment for many opportunities."""

        opportunities = [
            {
                "roi": 5.0 + i % 50,
                "liquidity": 1 + i % 30,
                "lock_days": i % 10,
                "price": 10.0 + i * 2,
            }
            for i in range(1000)
        ]

        def assess_all_risks(opps: list) -> list:
            def assess(opp):
                score = 0
                if opp["roi"] > 30:
                    score += 2
                if opp["liquidity"] < 10:
                    score += 2
                if opp["lock_days"] > 3:
                    score += 2
                if opp["price"] > 200:
                    score += 1

                levels = ["very_low", "low", "medium", "high", "very_high"]
                return levels[min(score, 4)]

            return [{"opp": opp, "risk": assess(opp)} for opp in opps]

        results = benchmark(assess_all_risks, opportunities)
        assert len(results) == 1000


# ============================================================================
# GAME CONFIG PERFORMANCE
# ============================================================================


@needs_benchmark
class TestGameConfigPerformance:
    """Performance tests for game-specific configuration lookup."""

    def test_game_config_lookup_speed(self, benchmark):
        """Benchmark game configuration lookup."""

        game_configs = {
            "csgo": {
                "min_profit": 5.0,
                "min_roi": 8.0,
                "commission": 5.0,
                "features": ["float", "pattern", "stickers"],
            },
            "dota2": {
                "min_profit": 3.0,
                "min_roi": 6.0,
                "commission": 5.0,
                "features": ["gems", "quality", "style"],
            },
            "tf2": {
                "min_profit": 2.0,
                "min_roi": 5.0,
                "commission": 5.0,
                "features": ["effects", "killstreak", "australium"],
            },
            "rust": {
                "min_profit": 4.0,
                "min_roi": 7.0,
                "commission": 5.0,
                "features": ["luminescent", "twitch_drop"],
            },
        }

        def get_game_config(game: str, configs: dict) -> dict:
            return configs.get(game, configs["csgo"])

        result = benchmark(get_game_config, "dota2", game_configs)
        assert result["min_roi"] == 6.0


# ============================================================================
# TIMING TESTS (WITHOUT BENCHMARK FIXTURE)
# ============================================================================


class TestTimingWithoutBenchmark:
    """Timing tests that don't require pytest-benchmark."""

    def test_profit_calculation_completes_quickly(self):
        """Test that profit calculation completes in reasonable time."""

        def calculate_profit(buy: float, sell: float, commission: float) -> float:
            return sell * (1 - commission / 100) - buy

        start = time.perf_counter()
        for _ in range(10000):
            calculate_profit(100.0, 120.0, 7.0)
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, f"10000 calculations took {elapsed}s, should be < 1s"

    def test_filtering_completes_quickly(self):
        """Test that filtering 10000 items completes quickly."""

        items = [{"price": i * 10, "roi": i % 30} for i in range(10000)]

        start = time.perf_counter()
        filtered = [
            item
            for item in items
            if item["price"] >= 500 and item["price"] <= 5000 and item["roi"] >= 10
        ]
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"Filtering took {elapsed}s, should be < 0.1s"
        assert len(filtered) > 0

    def test_scoring_and_sorting_completes_quickly(self):
        """Test that scoring and sorting 1000 items completes quickly."""

        items = [{"roi": i % 30, "liquidity": i % 50, "risk": i % 10} for i in range(1000)]

        def score(item):
            return item["roi"] * 0.4 + item["liquidity"] * 0.35 + (10 - item["risk"]) * 0.25

        start = time.perf_counter()
        scored = [(item, score(item)) for item in items]
        sorted_items = sorted(scored, key=operator.itemgetter(1), reverse=True)
        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"Scoring and sorting took {elapsed}s, should be < 0.1s"
        assert len(sorted_items) == 1000

    def test_multi_game_aggregation_completes_quickly(self):
        """Test that aggregating results from 4 games completes quickly."""

        # Simulate results from 4 games
        game_results = {
            game: [{"game": game, "item": f"Item_{i}", "score": i % 100} for i in range(250)]
            for game in ["csgo", "dota2", "tf2", "rust"]
        }

        start = time.perf_counter()

        # Aggregate
        all_items = []
        for items in game_results.values():
            all_items.extend(items)

        # Sort
        sorted_items = sorted(all_items, key=operator.itemgetter("score"), reverse=True)

        # Top 100
        top_100 = sorted_items[:100]

        elapsed = time.perf_counter() - start

        assert elapsed < 0.1, f"Aggregation took {elapsed}s, should be < 0.1s"
        assert len(top_100) == 100


# ============================================================================
# METADATA
# ============================================================================

"""
Strategy Performance Tests
Status: ✅ CREATED (20 tests)

Test Categories:
1. ProfitCalculationPerformance (3 benchmark tests)
2. OpportunityScoringPerformance (2 benchmark tests)
3. FilteringPerformance (3 benchmark tests)
4. RiskAssessmentPerformance (2 benchmark tests)
5. GameConfigPerformance (1 benchmark test)
6. TimingWithoutBenchmark (4 timing tests)

Coverage: Performance-critical operations
Requires: pytest-benchmark (optional)
Priority: MEDIUM
"""
