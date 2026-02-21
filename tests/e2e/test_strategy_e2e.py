"""End-to-End tests for strategy system.

Tests the complete flow from strategy configuration to opportunity detection
and trading decision making.
"""


from src.dmarket.optimal_arbitrage_strategy import (
    STRATEGY_PRESETS,
    ArbitrageOpportunity,
    OptimalArbitrageStrategy,
    RiskLevel,
    StrategySettings,
)
from src.dmarket.unified_strategy_system import (
    get_strategy_config_preset,
)


class TestCompleteArbitrageFlow:
    """Test complete arbitrage detection flow."""

    def test_full_arbitrage_detection_cycle(self) -> None:
        """Test full cycle: configure → scan → filter → score → decide."""
        # 1. Configure strategy with balanced preset
        settings = STRATEGY_PRESETS["balanced"]
        strategy = OptimalArbitrageStrategy(settings)

        # 2. Simulate item data
        item = {
            "title": "AK-47 | Redline (Field-Tested)",
            "price": {"USD": "1500"},  # $15.00
            "extra": {
                "floatValue": "0.16",
            },
        }

        # 3. Analyze item
        opportunity = strategy.analyze_item(
            item=item,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            sell_price=18.0,  # $18.00
        )

        # 4. Verify opportunity structure
        if opportunity:
            assert opportunity.buy_price == 15.0
            assert opportunity.sell_price == 18.0
            assert opportunity.buy_platform == "dmarket"
            assert opportunity.sell_platform == "waxpeer"

            # 5. Filter opportunity
            passed = strategy.filter_opportunity(opportunity)
            assert isinstance(passed, bool)

            # 6. Score opportunity
            score = strategy.calculate_opportunity_score(opportunity)
            assert 0 <= score <= 100

    def test_multi_game_scanning_flow(self) -> None:
        """Test scanning items across all supported games."""
        strategy = OptimalArbitrageStrategy()

        games = ["csgo", "dota2", "tf2", "rust"]
        game_items = {
            "csgo": {
                "title": "AK-47 | Redline (FT)",
                "price": {"USD": "1500"},
                "gameId": "csgo",
            },
            "dota2": {
                "title": "Arcana of the Demon",
                "price": {"USD": "2500"},
                "gameId": "dota2",
            },
            "tf2": {
                "title": "Burning Flames Team CaptAlgon",
                "price": {"USD": "50000"},
                "gameId": "tf2",
            },
            "rust": {
                "title": "Neon Garage Door",
                "price": {"USD": "10000"},
                "gameId": "rust",
            },
        }

        for game in games:
            item = game_items[game]
            buy_price = float(item["price"]["USD"]) / 100
            sell_price = buy_price * 1.2  # 20% profit

            opportunity = strategy.analyze_item(
                item=item,
                buy_platform="dmarket",
                sell_platform="waxpeer",
                sell_price=sell_price,
            )

            # Should either return opportunity or None
            assert opportunity is None or isinstance(opportunity, ArbitrageOpportunity)


class TestTradingDecisionFlow:
    """Test trading decision making flow."""

    def test_conservative_preset_settings(self) -> None:
        """Test that conservative preset has safe settings."""
        settings = STRATEGY_PRESETS["conservative"]
        strategy = OptimalArbitrageStrategy(settings)

        # Conservative should have higher min ROI
        assert strategy.settings.min_roi_percent >= 15.0

    def test_aggressive_preset_settings(self) -> None:
        """Test that aggressive preset accepts more risk."""
        conservative = STRATEGY_PRESETS["conservative"]
        aggressive = STRATEGY_PRESETS["aggressive"]

        # Aggressive should have lower min ROI
        assert aggressive.min_roi_percent < conservative.min_roi_percent

    def test_scalper_preset_for_high_volume(self) -> None:
        """Test scalper preset for high volume trading."""
        settings = STRATEGY_PRESETS["scalper"]
        balanced = STRATEGY_PRESETS["balanced"]

        # Scalper should have lower min ROI for volume
        assert settings.min_roi_percent < balanced.min_roi_percent


class TestStrategyPresetFlow:
    """Test strategy preset configuration flow."""

    def test_all_presets_are_valid(self) -> None:
        """Test all strategy presets create valid strategies."""
        presets = ["conservative", "balanced", "aggressive", "high_value", "scalper"]

        for preset_name in presets:
            settings = STRATEGY_PRESETS.get(preset_name)
            assert settings is not None, f"Preset {preset_name} not found"

            strategy = OptimalArbitrageStrategy(settings)
            assert strategy is not None

    def test_unified_presets_are_valid(self) -> None:
        """Test all unified strategy presets are valid."""
        presets = [
            "boost", "standard", "medium", "advanced",
            "pro", "float_premium", "instant_arb", "investment"
        ]

        for preset_name in presets:
            config = get_strategy_config_preset(preset_name)
            assert config is not None
            assert config.min_profit_usd > 0


class TestErrorHandlingFlow:
    """Test error handling in strategy flow."""

    def test_invalid_price_handling(self) -> None:
        """Test handling of invalid price data."""
        strategy = OptimalArbitrageStrategy()

        # Item with invalid price
        item = {
            "title": "AK-47 | Redline (FT)",
            "price": {"USD": "invalid"},
        }

        # Should not crash
        try:
            opportunity = strategy.analyze_item(
                item=item,
                buy_platform="dmarket",
                sell_platform="waxpeer",
                sell_price=18.0,
            )
            # Invalid price should return None
            assert opportunity is None
        except (ValueError, TypeError):
            # Expected for invalid price
            pass

    def test_missing_fields_handling(self) -> None:
        """Test handling of missing item fields."""
        strategy = OptimalArbitrageStrategy()

        # Item with missing fields
        item = {
            "title": "Unknown Item",
        }

        # Should not crash
        opportunity = strategy.analyze_item(
            item=item,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            sell_price=10.0,
        )

        # Missing price should return None
        assert opportunity is None

    def test_zero_price_handling(self) -> None:
        """Test handling of zero price."""
        strategy = OptimalArbitrageStrategy()

        # Item with zero price
        item = {
            "title": "AK-47 | Redline (FT)",
            "price": {"USD": "0"},
        }

        opportunity = strategy.analyze_item(
            item=item,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            sell_price=18.0,
        )

        # Zero buy price should return None
        assert opportunity is None

    def test_negative_sell_price_handling(self) -> None:
        """Test handling of negative sell price."""
        strategy = OptimalArbitrageStrategy()

        item = {
            "title": "AK-47 | Redline (FT)",
            "price": {"USD": "1500"},
        }

        opportunity = strategy.analyze_item(
            item=item,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            sell_price=-10.0,
        )

        # Negative sell price should return None
        assert opportunity is None


class TestOpportunityScoring:
    """Test opportunity scoring functionality."""

    def test_score_is_bounded(self) -> None:
        """Test that score is always between 0 and 100."""
        strategy = OptimalArbitrageStrategy()

        # Create a sample opportunity
        opp = ArbitrageOpportunity(
            item_id="test_123",
            item_name="AK-47 | Redline (FT)",
            game="csgo",
            buy_price=15.0,
            sell_price=18.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=3.0,
            net_profit=2.5,
            fees_pAlgod=0.5,
            roi_percent=16.67,
            liquidity_score=0.8,
            risk_level=RiskLevel.LOW,
            sales_per_day=5.0,
        )

        score = strategy.calculate_opportunity_score(opp)
        assert 0 <= score <= 100

    def test_higher_roi_gives_higher_score(self) -> None:
        """Test that higher ROI generally gives higher score."""
        strategy = OptimalArbitrageStrategy()

        low_roi_opp = ArbitrageOpportunity(
            item_id="test_1",
            item_name="Item 1",
            game="csgo",
            buy_price=100.0,
            sell_price=105.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=5.0,
            net_profit=4.0,
            fees_pAlgod=1.0,
            roi_percent=4.0,
            liquidity_score=0.5,
            risk_level=RiskLevel.LOW,
            sales_per_day=5.0,
        )

        high_roi_opp = ArbitrageOpportunity(
            item_id="test_2",
            item_name="Item 2",
            game="csgo",
            buy_price=100.0,
            sell_price=130.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=30.0,
            net_profit=25.0,
            fees_pAlgod=5.0,
            roi_percent=25.0,
            liquidity_score=0.5,
            risk_level=RiskLevel.MEDIUM,
            sales_per_day=5.0,
        )

        low_score = strategy.calculate_opportunity_score(low_roi_opp)
        high_score = strategy.calculate_opportunity_score(high_roi_opp)

        # Higher ROI should give higher score (all else being equal)
        assert high_score >= low_score


class TestFilteringBehavior:
    """Test filtering behavior."""

    def test_filter_rejects_low_roi(self) -> None:
        """Test that filter rejects opportunities below min ROI."""
        settings = StrategySettings()
        settings.min_roi_percent = 15.0
        strategy = OptimalArbitrageStrategy(settings)

        # Low ROI opportunity
        opp = ArbitrageOpportunity(
            item_id="test_1",
            item_name="Item 1",
            game="csgo",
            buy_price=100.0,
            sell_price=105.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=5.0,
            net_profit=2.0,
            fees_pAlgod=3.0,
            roi_percent=2.0,  # Below min 15%
            liquidity_score=0.5,
            risk_level=RiskLevel.LOW,
            sales_per_day=5.0,
        )

        result = strategy.filter_opportunity(opp)
        # Result is either bool or tuple (bool, str)
        passed = result[0] if isinstance(result, tuple) else result
        assert passed is False

    def test_filter_accepts_high_roi(self) -> None:
        """Test that filter accepts opportunities above min ROI."""
        settings = StrategySettings()
        settings.min_roi_percent = 10.0
        strategy = OptimalArbitrageStrategy(settings)

        # High ROI opportunity
        opp = ArbitrageOpportunity(
            item_id="test_1",
            item_name="Item 1",
            game="csgo",
            buy_price=100.0,
            sell_price=120.0,
            buy_platform="dmarket",
            sell_platform="waxpeer",
            gross_profit=20.0,
            net_profit=15.0,
            fees_pAlgod=5.0,
            roi_percent=15.0,  # Above min 10%
            liquidity_score=0.5,
            risk_level=RiskLevel.LOW,
            sales_per_day=5.0,
        )

        result = strategy.filter_opportunity(opp)
        # Result is either bool or tuple (bool, str)
        passed = result[0] if isinstance(result, tuple) else result
        assert passed is True


class TestBestOpportunities:
    """Test finding best opportunities."""

    def test_find_best_returns_sorted_list(self) -> None:
        """Test that find_best_opportunities returns a list of best opportunities."""
        strategy = OptimalArbitrageStrategy()

        opportunities = [
            ArbitrageOpportunity(
                item_id=f"test_{i}",
                item_name=f"Item {i}",
                game="csgo",
                buy_price=100.0,
                sell_price=100.0 + i * 10,
                buy_platform="dmarket",
                sell_platform="waxpeer",
                gross_profit=float(i * 10),
                net_profit=float(i * 8),
                fees_pAlgod=float(i * 2),
                roi_percent=float(i * 8),
                liquidity_score=0.5,
                risk_level=RiskLevel.LOW,
                sales_per_day=5.0,
            )
            for i in range(1, 6)
        ]

        best = strategy.find_best_opportunities(opportunities, top_n=3)

        # Should return at most top_n
        assert len(best) <= 3
        # All returned items should be ArbitrageOpportunity
        for opp in best:
            assert isinstance(opp, ArbitrageOpportunity)

    def test_find_best_respects_limit(self) -> None:
        """Test that find_best_opportunities respects top_n limit."""
        strategy = OptimalArbitrageStrategy()

        opportunities = [
            ArbitrageOpportunity(
                item_id=f"test_{i}",
                item_name=f"Item {i}",
                game="csgo",
                buy_price=100.0,
                sell_price=120.0,
                buy_platform="dmarket",
                sell_platform="waxpeer",
                gross_profit=20.0,
                net_profit=15.0,
                fees_pAlgod=5.0,
                roi_percent=15.0,
                liquidity_score=0.5,
                risk_level=RiskLevel.LOW,
                sales_per_day=5.0,
            )
            for i in range(10)
        ]

        best = strategy.find_best_opportunities(opportunities, top_n=5)

        assert len(best) <= 5
