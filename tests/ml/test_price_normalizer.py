"""Tests for PriceNormalizer module.

This module tests price normalization across platforms:
- DMarket: prices in cents (divide by 100)
- Waxpeer: prices in mils (divide by 1000)
- Steam: prices in USD (no conversion)
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from src.ml.price_normalizer import (
    NormalizedPrice,
    PriceNormalizer,
    PriceSource,
    get_normalizer,
    normalize_price,
)


class TestPriceSource:
    """Tests for PriceSource enum."""

    def test_price_source_values(self) -> None:
        """Test that PriceSource enum has correct values."""
        assert PriceSource.DMARKET.value == "dmarket"
        assert PriceSource.WAXPEER.value == "waxpeer"
        assert PriceSource.STEAM.value == "steam"

    def test_price_source_only_three_sources(self) -> None:
        """Test that only three price sources exist."""
        sources = list(PriceSource)
        assert len(sources) == 3
        assert PriceSource.DMARKET in sources
        assert PriceSource.WAXPEER in sources
        assert PriceSource.STEAM in sources


class TestNormalizedPrice:
    """Tests for NormalizedPrice dataclass."""

    def test_normalized_price_creation(self) -> None:
        """Test NormalizedPrice dataclass creation with required fields."""
        now = datetime.now(UTC)
        price = NormalizedPrice(
            price_usd=10.50,
            source=PriceSource.DMARKET,
            original_value=1050,
            timestamp=now,
        )
        assert price.price_usd == 10.50
        assert price.source == PriceSource.DMARKET
        assert price.original_value == 1050
        assert price.timestamp == now
        assert price.item_name is None
        assert price.game is None
        assert price.is_valid is True
        assert price.error_message is None

    def test_normalized_price_with_optional_fields(self) -> None:
        """Test NormalizedPrice with all optional fields."""
        now = datetime.now(UTC)
        price = NormalizedPrice(
            price_usd=25.00,
            source=PriceSource.WAXPEER,
            original_value=25000,
            timestamp=now,
            item_name="AK-47 | Redline",
            game="csgo",
            is_valid=True,
            error_message=None,
        )
        assert price.price_usd == 25.00
        assert price.item_name == "AK-47 | Redline"
        assert price.game == "csgo"
        assert price.is_valid is True

    def test_normalized_price_invalid(self) -> None:
        """Test NormalizedPrice with invalid state."""
        now = datetime.now(UTC)
        price = NormalizedPrice(
            price_usd=0.0,
            source=PriceSource.STEAM,
            original_value=-100,
            timestamp=now,
            is_valid=False,
            error_message="Negative price",
        )
        assert price.is_valid is False
        assert price.error_message == "Negative price"


class TestPriceNormalizer:
    """Tests for PriceNormalizer class."""

    @pytest.fixture()
    def normalizer(self) -> PriceNormalizer:
        """Create a fresh PriceNormalizer instance."""
        return PriceNormalizer()

    # --- normalize() tests ---

    def test_normalize_dmarket_price(self, normalizer: PriceNormalizer) -> None:
        """Test normalizing DMarket price (cents to USD)."""
        result = normalizer.normalize(1050, PriceSource.DMARKET)
        assert result.price_usd == pytest.approx(10.50, rel=1e-2)
        assert result.source == PriceSource.DMARKET
        assert result.original_value == 1050
        assert result.is_valid is True

    def test_normalize_waxpeer_price(self, normalizer: PriceNormalizer) -> None:
        """Test normalizing Waxpeer price (mils to USD)."""
        result = normalizer.normalize(25000, PriceSource.WAXPEER)
        assert result.price_usd == pytest.approx(25.00, rel=1e-2)
        assert result.source == PriceSource.WAXPEER
        assert result.original_value == 25000
        assert result.is_valid is True

    def test_normalize_steam_price(self, normalizer: PriceNormalizer) -> None:
        """Test normalizing Steam price (already USD)."""
        result = normalizer.normalize(15.99, PriceSource.STEAM)
        assert result.price_usd == pytest.approx(15.99, rel=1e-2)
        assert result.source == PriceSource.STEAM
        assert result.original_value == 15.99
        assert result.is_valid is True

    def test_normalize_with_item_name(self, normalizer: PriceNormalizer) -> None:
        """Test normalize with item_name parameter."""
        result = normalizer.normalize(500, PriceSource.DMARKET, item_name="AWP | Asiimov")
        assert result.item_name == "AWP | Asiimov"
        assert result.price_usd == pytest.approx(5.00, rel=1e-2)

    def test_normalize_with_game(self, normalizer: PriceNormalizer) -> None:
        """Test normalize with game parameter."""
        result = normalizer.normalize(1000, PriceSource.DMARKET, game="csgo")
        assert result.game == "csgo"

    def test_normalize_zero_price(self, normalizer: PriceNormalizer) -> None:
        """Test normalizing zero price."""
        result = normalizer.normalize(0, PriceSource.DMARKET)
        assert result.price_usd == 0.0
        # Zero price might be valid or invalid depending on implementation
        assert result.original_value == 0

    def test_normalize_negative_price(self, normalizer: PriceNormalizer) -> None:
        """Test normalizing negative price returns invalid."""
        result = normalizer.normalize(-100, PriceSource.DMARKET)
        assert result.is_valid is False
        assert result.error_message is not None

    def test_normalize_string_source(self, normalizer: PriceNormalizer) -> None:
        """Test normalize accepts string source name."""
        result = normalizer.normalize(1000, "dmarket")
        assert result.source == PriceSource.DMARKET
        assert result.price_usd == pytest.approx(10.00, rel=1e-2)

    # --- normalize_batch() tests ---

    def test_normalize_batch_same_source(self, normalizer: PriceNormalizer) -> None:
        """Test batch normalization with same source."""
        prices = [
            {"title": "Item1", "price": 100},
            {"title": "Item2", "price": 200},
            {"title": "Item3", "price": 300},
            {"title": "Item4", "price": 400},
            {"title": "Item5", "price": 500},
        ]
        results = normalizer.normalize_batch(prices, PriceSource.DMARKET)
        assert len(results) == 5
        assert results[0].price_usd == pytest.approx(1.00, rel=1e-2)
        assert results[4].price_usd == pytest.approx(5.00, rel=1e-2)

    def test_normalize_batch_empty(self, normalizer: PriceNormalizer) -> None:
        """Test batch normalization with empty list."""
        results = normalizer.normalize_batch([], PriceSource.DMARKET)
        assert results == []

    # --- calculate_net_price() tests ---

    def test_calculate_net_price_dmarket(self, normalizer: PriceNormalizer) -> None:
        """Test net price calculation for DMarket (7% commission)."""
        net = normalizer.calculate_net_price(100.0, PriceSource.DMARKET)
        expected = 100.0 * (1 - PriceNormalizer.DMARKET_COMMISSION)
        assert net == pytest.approx(expected, rel=1e-2)

    def test_calculate_net_price_waxpeer(self, normalizer: PriceNormalizer) -> None:
        """Test net price calculation for Waxpeer (6% commission)."""
        net = normalizer.calculate_net_price(100.0, PriceSource.WAXPEER)
        expected = 100.0 * (1 - PriceNormalizer.WAXPEER_COMMISSION)
        assert net == pytest.approx(expected, rel=1e-2)

    def test_calculate_net_price_steam(self, normalizer: PriceNormalizer) -> None:
        """Test net price calculation for Steam (15% commission)."""
        net = normalizer.calculate_net_price(100.0, PriceSource.STEAM)
        expected = 100.0 * (1 - PriceNormalizer.STEAM_COMMISSION)
        assert net == pytest.approx(expected, rel=1e-2)

    # --- calculate_arbitrage_profit() tests ---

    def test_calculate_arbitrage_profit_positive(self, normalizer: PriceNormalizer) -> None:
        """Test arbitrage profit calculation with profit."""
        # Buy at DMarket for $10 (1000 cents), sell at Waxpeer for $15 (15000 mils)
        result = normalizer.calculate_arbitrage_profit(
            buy_price=1000,  # DMarket cents ($10)
            buy_source=PriceSource.DMARKET,
            sell_price=15000,  # Waxpeer mils ($15)
            sell_source=PriceSource.WAXPEER,
        )
        # Net sell = $15 * 0.94 = $14.10, profit = $14.10 - $10.00 = $4.10
        assert result["is_profitable"] is True
        assert result["net_profit"] == pytest.approx(4.10, rel=1e-2)

    def test_calculate_arbitrage_profit_negative(self, normalizer: PriceNormalizer) -> None:
        """Test arbitrage profit calculation with loss."""
        # Buy at DMarket for $20 (2000 cents), sell at Waxpeer for $15 (15000 mils)
        result = normalizer.calculate_arbitrage_profit(
            buy_price=2000,  # DMarket cents ($20)
            buy_source=PriceSource.DMARKET,
            sell_price=15000,  # Waxpeer mils ($15)
            sell_source=PriceSource.WAXPEER,
        )
        # Net sell = $15 * 0.94 = $14.10, loss = $14.10 - $20.00 = -$5.90
        assert result["is_profitable"] is False
        assert result["net_profit"] < 0

    # --- to_platform_price() tests ---

    def test_to_platform_price_dmarket(self, normalizer: PriceNormalizer) -> None:
        """Test converting USD to DMarket cents."""
        platform_price = normalizer.to_platform_price(10.50, PriceSource.DMARKET)
        assert platform_price == pytest.approx(1050, rel=1e-2)

    def test_to_platform_price_waxpeer(self, normalizer: PriceNormalizer) -> None:
        """Test converting USD to Waxpeer mils."""
        platform_price = normalizer.to_platform_price(25.0, PriceSource.WAXPEER)
        assert platform_price == pytest.approx(25000, rel=1e-2)

    def test_to_platform_price_steam(self, normalizer: PriceNormalizer) -> None:
        """Test converting USD to Steam (stays USD)."""
        platform_price = normalizer.to_platform_price(15.99, PriceSource.STEAM)
        assert platform_price == pytest.approx(15.99, rel=1e-2)

    # --- get_statistics() and reset_statistics() tests ---

    def test_get_statistics_initial(self, normalizer: PriceNormalizer) -> None:
        """Test initial statistics are empty or zero."""
        stats = normalizer.get_statistics()
        assert isinstance(stats, dict)
        assert stats.get("total_conversions", 0) == 0

    def test_get_statistics_after_normalize(self, normalizer: PriceNormalizer) -> None:
        """Test statistics update after normalization."""
        normalizer.normalize(1000, PriceSource.DMARKET)
        normalizer.normalize(2000, PriceSource.WAXPEER)
        stats = normalizer.get_statistics()
        assert stats.get("total_conversions", 0) >= 2

    def test_reset_statistics(self, normalizer: PriceNormalizer) -> None:
        """Test resetting statistics."""
        normalizer.normalize(1000, PriceSource.DMARKET)
        normalizer.reset_statistics()
        stats = normalizer.get_statistics()
        assert stats.get("total_conversions", 0) == 0


class TestPriceNormalizerEdgeCases:
    """Edge case tests for PriceNormalizer."""

    @pytest.fixture()
    def normalizer(self) -> PriceNormalizer:
        """Create a fresh PriceNormalizer instance."""
        return PriceNormalizer()

    def test_very_large_price(self, normalizer: PriceNormalizer) -> None:
        """Test normalizing very large prices."""
        # 1 million dollars in cents
        result = normalizer.normalize(100_000_000, PriceSource.DMARKET)
        assert result.price_usd == pytest.approx(1_000_000.0, rel=1e-2)

    def test_very_small_price(self, normalizer: PriceNormalizer) -> None:
        """Test normalizing very small prices."""
        # 1 cent
        result = normalizer.normalize(1, PriceSource.DMARKET)
        assert result.price_usd == pytest.approx(0.01, rel=1e-2)

    def test_fractional_price(self, normalizer: PriceNormalizer) -> None:
        """Test normalizing prices with decimals."""
        result = normalizer.normalize(10.5, PriceSource.STEAM)
        assert result.price_usd == pytest.approx(10.5, rel=1e-2)

    def test_conversion_constants(self) -> None:
        """Test that conversion constants are correct."""
        assert PriceNormalizer.DMARKET_DIVISOR == 100
        assert PriceNormalizer.WAXPEER_DIVISOR == 1000
        assert pytest.approx(0.07, rel=1e-2) == PriceNormalizer.DMARKET_COMMISSION
        assert pytest.approx(0.06, rel=1e-2) == PriceNormalizer.WAXPEER_COMMISSION
        assert pytest.approx(0.15, rel=1e-2) == PriceNormalizer.STEAM_COMMISSION

    def test_round_trip_conversion(self, normalizer: PriceNormalizer) -> None:
        """Test converting USD to platform and back."""
        original_usd = 25.50
        # USD -> DMarket cents
        platform_price = normalizer.to_platform_price(original_usd, PriceSource.DMARKET)
        # DMarket cents -> USD
        result = normalizer.normalize(platform_price, PriceSource.DMARKET)
        assert result.price_usd == pytest.approx(original_usd, rel=1e-2)


class TestGlobalNormalizerFunctions:
    """Tests for global normalizer functions."""

    def test_get_normalizer_returns_instance(self) -> None:
        """Test get_normalizer returns a PriceNormalizer instance."""
        normalizer = get_normalizer()
        assert isinstance(normalizer, PriceNormalizer)

    def test_get_normalizer_singleton(self) -> None:
        """Test get_normalizer returns same instance (singleton pattern)."""
        n1 = get_normalizer()
        n2 = get_normalizer()
        assert n1 is n2

    def test_normalize_price_function(self) -> None:
        """Test global normalize_price convenience function."""
        result = normalize_price(1000, PriceSource.DMARKET)
        assert isinstance(result, NormalizedPrice)
        assert result.price_usd == pytest.approx(10.0, rel=1e-2)
