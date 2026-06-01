"""Integration tests for strategy system modules.

Tests the integration between:
- OptimalArbitrageStrategy
- UnifiedStrategySystem
- GameSpecificFilters
- FloatValueArbitrage
- AdvancedOrderSystem
"""

from unittest.mock import MagicMock

import pytest

pytestmark = [pytest.mark.integration]


class TestFloatArbitrageWithStrategy:
    """Test FloatValueArbitrage with OptimalArbitrageStrategy."""

    def test_float_arbitrage_premium_calculation(self) -> None:
        """Test float premium calculation."""
        from src.dmarket.float_value_arbitrage import FloatValueArbitrage

        mock_api = MagicMock()
        float_arb = FloatValueArbitrage(api_client=mock_api)

        # Calculate premium
        premium = float_arb.calculate_float_premium(
            item_title="AK-47 | Redline (Field-Tested)",
            float_value=0.15,
            base_market_price=50.0,
        )

        assert premium is not None
        assert premium.premium_multiplier >= 1.0


class TestAdvancedOrdersWithStrategy:
    """Test AdvancedOrderSystem with strategies."""

    def test_create_float_order_integration(self) -> None:
        """Test creating float range order."""
        from src.dmarket.advanced_order_system import create_float_order

        order = create_float_order(
            item_title="AK-47 | Redline (Field-Tested)",
            float_min=0.15,
            float_max=0.18,
            max_price=55.0,
            expected_sell=65.0,
        )

        assert order is not None
        assert order.filter.float_min == 0.15
        assert order.filter.float_max == 0.18
        assert order.max_price_usd == 55.0

    def test_create_doppler_order_integration(self) -> None:
        """Test creating Doppler phase order."""
        from src.dmarket.advanced_order_system import (
            DopplerPhase,
            create_doppler_order,
        )

        order = create_doppler_order(
            item_title="Karambit | Doppler (Factory New)",
            phase=DopplerPhase.RUBY,
            max_price=500.0,
        )

        assert order is not None
        assert order.filter.phase == DopplerPhase.RUBY


class TestPresetConfigIntegration:
    """Test preset configurations work together."""

    def test_unified_presets_valid(self) -> None:
        """Test all unified strategy presets are valid."""
        from src.dmarket.unified_strategy_system import get_strategy_config_preset

        presets = [
            "boost", "standard", "medium", "advanced",
            "pro", "float_premium", "instant_arb", "investment",
        ]

        for preset_name in presets:
            config = get_strategy_config_preset(preset_name)
            assert config is not None
            assert config.min_profit_percent > 0
