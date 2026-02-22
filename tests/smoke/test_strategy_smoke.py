"""Smoke tests for new strategy modules.

Quick tests to verify critical paths work.
Run with: pytest tests/smoke/test_strategy_smoke.py -v --tb=short
"""

from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.smoke]


class TestOptimalArbitrageStrategySmoke:
    """Smoke tests for OptimalArbitrageStrategy."""

    def test_module_imports(self) -> None:
        """CRITICAL: Module must import without errors."""
        from src.dmarket.optimal_arbitrage_strategy import (
            OptimalArbitrageStrategy,
            StrategySettings,
            create_strategy,
        )

        assert OptimalArbitrageStrategy is not None
        assert StrategySettings is not None
        assert create_strategy is not None

    def test_strategy_instantiation(self) -> None:
        """CRITICAL: Strategy must be instantiable."""
        from src.dmarket.optimal_arbitrage_strategy import (
            OptimalArbitrageStrategy,
            StrategySettings,
        )

        settings = StrategySettings()
        strategy = OptimalArbitrageStrategy(settings)

        assert strategy is not None
        assert strategy.settings is not None

    def test_create_strategy_presets(self) -> None:
        """CRITICAL: All presets must work."""
        from src.dmarket.optimal_arbitrage_strategy import create_strategy

        presets = ["conservative", "balanced", "aggressive", "high_value", "scalper"]

        for preset in presets:
            strategy = create_strategy(preset)
            assert strategy is not None, f"Failed to create {preset} preset"

    def test_roi_calculation(self) -> None:
        """CRITICAL: ROI calculation must work."""
        from src.dmarket.optimal_arbitrage_strategy import (
            OptimalArbitrageStrategy,
            StrategySettings,
        )

        strategy = OptimalArbitrageStrategy(StrategySettings())

        # Use actual API signature: calculate_roi(buy_price, net_profit)
        roi = strategy.calculate_roi(
            buy_price=100.0,
            net_profit=15.0,
        )

        assert roi > 0
        assert isinstance(roi, float)


class TestUnifiedStrategySystemSmoke:
    """Smoke tests for UnifiedStrategySystem."""

    def test_module_imports(self) -> None:
        """CRITICAL: Module must import without errors."""
        from src.dmarket.unified_strategy_system import (
            StrategyType,
            get_strategy_config_preset,
        )

        assert StrategyType is not None
        assert get_strategy_config_preset is not None

    def test_preset_configs(self) -> None:
        """CRITICAL: All preset configs must work."""
        from src.dmarket.unified_strategy_system import get_strategy_config_preset

        presets = ["boost", "standard", "medium", "advanced", "pro"]

        for preset in presets:
            config = get_strategy_config_preset(preset)
            assert config is not None, f"Failed to get {preset} config"
            assert config.min_profit_percent > 0

    def test_game_configs(self) -> None:
        """CRITICAL: All game configs must work."""
        from src.dmarket.unified_strategy_system import (
            SUPPORTED_GAMES,
            get_game_specific_config,
        )

        for game in SUPPORTED_GAMES:
            config = get_game_specific_config(game)
            assert config is not None, f"Failed to get {game} config"


class TestGameSpecificFiltersSmoke:
    """Smoke tests for GameSpecificFilters."""

    def test_module_imports(self) -> None:
        """CRITICAL: Module must import without errors."""
        from src.dmarket.game_specific_filters import (
            CSGOFilter,
            Dota2Filter,
            RustFilter,
            TF2Filter,
        )

        assert CSGOFilter is not None
        assert Dota2Filter is not None
        assert TF2Filter is not None
        assert RustFilter is not None

    def test_csgo_filter_creation(self) -> None:
        """CRITICAL: CS:GO filter must be creatable."""
        from src.dmarket.game_specific_filters import (
            CSGODopplerPhase,
            CSGOFilter,
        )

        filter_obj = CSGOFilter(
            float_min=0.0,
            float_max=0.07,
            doppler_phase=CSGODopplerPhase.RUBY,
        )

        assert filter_obj is not None

    def test_dota2_filter_creation(self) -> None:
        """CRITICAL: Dota 2 filter must be creatable."""
        from src.dmarket.game_specific_filters import (
            Dota2Filter,
            Dota2Quality,
        )

        filter_obj = Dota2Filter(
            qualities=[Dota2Quality.ARCANA],
        )

        assert filter_obj is not None


class TestFloatValueArbitrageSmoke:
    """Smoke tests for FloatValueArbitrage."""

    def test_module_imports(self) -> None:
        """CRITICAL: Module must import without errors."""
        from src.dmarket.float_value_arbitrage import (
            FloatQuality,
            FloatValueArbitrage,
        )

        assert FloatValueArbitrage is not None
        assert FloatQuality is not None

    def test_arbitrage_instantiation(self) -> None:
        """CRITICAL: FloatValueArbitrage must be instantiable."""
        from src.dmarket.float_value_arbitrage import FloatValueArbitrage

        mock_api = MagicMock()
        arb = FloatValueArbitrage(api_client=mock_api)
        assert arb is not None

    def test_premium_calculation(self) -> None:
        """CRITICAL: Premium calculation must work."""
        from src.dmarket.float_value_arbitrage import FloatValueArbitrage

        mock_api = MagicMock()
        arb = FloatValueArbitrage(api_client=mock_api)

        premium = arb.calculate_float_premium(
            item_title="AK-47 | Redline (Field-Tested)",
            float_value=0.15,
            base_market_price=50.0,
        )

        assert premium is not None
        assert premium.premium_multiplier >= 1.0


class TestAdvancedOrderSystemSmoke:
    """Smoke tests for AdvancedOrderSystem."""

    def test_module_imports(self) -> None:
        """CRITICAL: Module must import without errors."""
        from src.dmarket.advanced_order_system import (
            AdvancedOrderManager,
            DopplerPhase,
        )

        assert AdvancedOrderManager is not None
        assert DopplerPhase is not None

    def test_order_creation(self) -> None:
        """CRITICAL: Order creation must work."""
        from src.dmarket.advanced_order_system import create_float_order

        order = create_float_order(
            item_title="Test Item",
            float_min=0.0,
            float_max=0.07,
            max_price=100.0,
            expected_sell=120.0,
        )

        assert order is not None
        assert order.item_title == "Test Item"

    def test_doppler_order_creation(self) -> None:
        """CRITICAL: Doppler order creation must work."""
        from src.dmarket.advanced_order_system import (
            DopplerPhase,
            create_doppler_order,
        )

        order = create_doppler_order(
            item_title="Karambit | Doppler",
            phase=DopplerPhase.RUBY,
            max_price=500.0,
        )

        assert order is not None
        assert order.filter.phase == DopplerPhase.RUBY


class TestCriticalPathsSmoke:
    """Smoke tests for critical integration paths."""

    def test_strategy_with_filter(self) -> None:
        """CRITICAL: Strategy + Filter integration must work."""
        from src.dmarket.game_specific_filters import CSGOFilter
        from src.dmarket.optimal_arbitrage_strategy import create_strategy

        strategy = create_strategy("balanced")
        filter_obj = CSGOFilter(float_min=0.0, float_max=0.07)

        # Both should be usable together
        assert strategy is not None
        assert filter_obj is not None
        assert hasattr(strategy, "calculate_roi")
        assert hasattr(filter_obj, "matches")

    def test_float_arb_with_order(self) -> None:
        """CRITICAL: Float arb + Order system integration must work."""
        from src.dmarket.advanced_order_system import create_float_order
        from src.dmarket.float_value_arbitrage import FloatValueArbitrage

        mock_api = MagicMock()
        arb = FloatValueArbitrage(api_client=mock_api)
        order = create_float_order(
            item_title="AK-47 | Redline",
            float_min=0.15,
            float_max=0.18,
            max_price=60.0,
            expected_sell=70.0,
        )

        # Both should work together
        premium = arb.calculate_float_premium(
            item_title="AK-47 | Redline (FT)",
            float_value=0.16,
            base_market_price=50.0,
        )

        assert premium is not None
        assert order is not None
