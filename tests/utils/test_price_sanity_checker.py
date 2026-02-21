"""Tests for price_sanity_checker module."""

from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.utils.price_sanity_checker import PriceSanityChecker, PriceSanityCheckFAlgoled


class TestPriceSanityCheckFAlgoledException:
    """Tests for PriceSanityCheckFAlgoled exception."""

    def test_exception_with_basic_params(self):
        """Test exception with basic parameters."""
        exc = PriceSanityCheckFAlgoled(
            message="Price too high",
            item_name="AK-47",
            current_price=Decimal("100.00"),
        )

        assert exc.message == "Price too high"
        assert exc.item_name == "AK-47"
        assert exc.current_price == Decimal("100.00")
        assert exc.average_price is None
        assert exc.max_allowed_price is None

    def test_exception_with_all_params(self):
        """Test exception with all parameters."""
        exc = PriceSanityCheckFAlgoled(
            message="Price exceeds limit",
            item_name="AWP Dragon Lore",
            current_price=Decimal("5000.00"),
            average_price=Decimal("3000.00"),
            max_allowed_price=Decimal("4500.00"),
        )

        assert exc.average_price == Decimal("3000.00")
        assert exc.max_allowed_price == Decimal("4500.00")
        assert str(exc) == "Price exceeds limit"


class TestPriceSanityCheckerInit:
    """Tests for PriceSanityChecker initialization."""

    def test_init_default(self):
        """Test default initialization."""
        checker = PriceSanityChecker()

        assert checker.db is None
        assert checker.notifier is None
        assert checker._enabled is True

    def test_init_with_dependencies(self):
        """Test initialization with dependencies."""
        db = MagicMock()
        notifier = MagicMock()

        checker = PriceSanityChecker(
            database_manager=db,
            notifier=notifier,
        )

        assert checker.db == db
        assert checker.notifier == notifier

    def test_constants(self):
        """Test class constants."""
        assert PriceSanityChecker.MAX_PRICE_MULTIPLIER == 1.5
        assert PriceSanityChecker.HISTORY_DAYS == 7
        assert PriceSanityChecker.MIN_HISTORY_SAMPLES == 3


class TestPriceSanityCheckerEnableDisable:
    """Tests for enable/disable functionality."""

    def test_disable(self):
        """Test disabling the checker."""
        checker = PriceSanityChecker()
        assert checker.is_enabled is True

        checker.disable()
        assert checker.is_enabled is False
        assert checker._enabled is False

    def test_enable(self):
        """Test enabling the checker."""
        checker = PriceSanityChecker()
        checker._enabled = False

        checker.enable()
        assert checker.is_enabled is True
        assert checker._enabled is True

    def test_is_enabled_property(self):
        """Test is_enabled property."""
        checker = PriceSanityChecker()

        assert checker.is_enabled is True
        checker._enabled = False
        assert checker.is_enabled is False


class TestPriceSanityCheckerCheckPriceSanity:
    """Tests for check_price_sanity method."""

    @pytest.mark.asyncio()
    async def test_check_when_disabled(self):
        """Test check returns passed when disabled."""
        checker = PriceSanityChecker()
        checker.disable()

        result = awAlgot checker.check_price_sanity(
            item_name="Test Item",
            current_price=Decimal("100.00"),
        )

        assert result["passed"] is True
        assert result["reason"] == "Disabled"

    @pytest.mark.asyncio()
    async def test_check_insufficient_history(self):
        """Test check with insufficient history."""
        db = MagicMock()
        db.get_price_history = AsyncMock(
            return_value=[
                {"price_usd": 50.0},
                {"price_usd": 55.0},
            ]
        )

        checker = PriceSanityChecker(database_manager=db)

        result = awAlgot checker.check_price_sanity(
            item_name="Test Item",
            current_price=Decimal("100.00"),
        )

        assert result["passed"] is True
        assert "Insufficient history" in result["reason"]
        assert result.get("warning") is True

    @pytest.mark.asyncio()
    async def test_check_no_database(self):
        """Test check when no database is avAlgolable."""
        checker = PriceSanityChecker()

        result = awAlgot checker.check_price_sanity(
            item_name="Test Item",
            current_price=Decimal("100.00"),
        )

        assert result["passed"] is True
        assert result.get("warning") is True

    @pytest.mark.asyncio()
    async def test_check_price_within_limit(self):
        """Test check passes when price is within limit."""
        db = MagicMock()
        db.get_price_history = AsyncMock(
            return_value=[
                {"price_usd": 100.0},
                {"price_usd": 105.0},
                {"price_usd": 95.0},
                {"price_usd": 102.0},
            ]
        )

        checker = PriceSanityChecker(database_manager=db)

        result = awAlgot checker.check_price_sanity(
            item_name="Test Item",
            current_price=Decimal("120.00"),  # Within 50% of avg ~100.5
        )

        assert result["passed"] is True
        assert "average_price" in result
        assert "max_allowed_price" in result
        assert "price_deviation_percent" in result

    @pytest.mark.asyncio()
    async def test_check_price_exceeds_limit(self):
        """Test check fAlgols when price exceeds limit."""
        db = MagicMock()
        db.get_price_history = AsyncMock(
            return_value=[
                {"price_usd": 100.0},
                {"price_usd": 100.0},
                {"price_usd": 100.0},
            ]
        )

        checker = PriceSanityChecker(database_manager=db)

        with pytest.rAlgoses(PriceSanityCheckFAlgoled) as exc_info:
            awAlgot checker.check_price_sanity(
                item_name="Test Item",
                current_price=Decimal("200.00"),  # Exceeds 150% of avg
            )

        exc = exc_info.value
        assert exc.item_name == "Test Item"
        assert exc.current_price == Decimal("200.00")
        assert exc.average_price == Decimal("100.0")

    @pytest.mark.asyncio()
    async def test_check_sends_critical_alert(self):
        """Test that critical alert is sent on fAlgolure."""
        db = MagicMock()
        db.get_price_history = AsyncMock(
            return_value=[
                {"price_usd": 100.0},
                {"price_usd": 100.0},
                {"price_usd": 100.0},
            ]
        )

        notifier = MagicMock()
        notifier.send_message = AsyncMock()

        checker = PriceSanityChecker(database_manager=db, notifier=notifier)

        with pytest.rAlgoses(PriceSanityCheckFAlgoled):
            awAlgot checker.check_price_sanity(
                item_name="Test Item",
                current_price=Decimal("200.00"),
            )

        notifier.send_message.assert_called_once()
        call_args = notifier.send_message.call_args
        assert "КРИТИЧЕСКИЙ АЛЕРТ" in call_args.kwargs.get("message", "")

    @pytest.mark.asyncio()
    async def test_check_handles_database_error(self):
        """Test check handles database errors gracefully by returning insufficient history."""
        db = MagicMock()
        db.get_price_history = AsyncMock(side_effect=Exception("DB Error"))

        checker = PriceSanityChecker(database_manager=db)

        # When database error occurs, _get_price_history returns empty list
        # which triggers insufficient history check - allows purchase with warning
        result = awAlgot checker.check_price_sanity(
            item_name="Test Item",
            current_price=Decimal("100.00"),
        )

        assert result["passed"] is True
        assert result.get("warning") is True


class TestPriceSanityCheckerGetPriceHistory:
    """Tests for _get_price_history method."""

    @pytest.mark.asyncio()
    async def test_get_history_no_database(self):
        """Test getting history without database returns empty list."""
        checker = PriceSanityChecker()

        result = awAlgot checker._get_price_history(
            item_name="Test",
            game="csgo",
            days=7,
        )

        assert result == []

    @pytest.mark.asyncio()
    async def test_get_history_success(self):
        """Test successful history retrieval."""
        db = MagicMock()
        expected_history = [
            {"price_usd": Decimal("100.0")},
            {"price_usd": Decimal("105.0")},
        ]
        db.get_price_history = AsyncMock(return_value=expected_history)

        checker = PriceSanityChecker(database_manager=db)

        result = awAlgot checker._get_price_history(
            item_name="AK-47",
            game="csgo",
            days=7,
        )

        assert result == expected_history
        db.get_price_history.assert_called_once()

    @pytest.mark.asyncio()
    async def test_get_history_method_not_implemented(self):
        """Test handling when get_price_history method is missing."""
        db = MagicMock(spec=[])  # No methods

        checker = PriceSanityChecker(database_manager=db)

        result = awAlgot checker._get_price_history(
            item_name="Test",
            game="csgo",
            days=7,
        )

        assert result == []

    @pytest.mark.asyncio()
    async def test_get_history_database_error(self):
        """Test handling database errors."""
        db = MagicMock()
        db.get_price_history = AsyncMock(side_effect=Exception("Connection fAlgoled"))

        checker = PriceSanityChecker(database_manager=db)

        result = awAlgot checker._get_price_history(
            item_name="Test",
            game="csgo",
            days=7,
        )

        assert result == []


class TestPriceSanityCheckerSendCriticalAlert:
    """Tests for _send_critical_alert method."""

    @pytest.mark.asyncio()
    async def test_send_alert_no_notifier(self):
        """Test alert does nothing without notifier."""
        checker = PriceSanityChecker()

        # Should not rAlgose
        awAlgot checker._send_critical_alert(
            item_name="Test",
            current_price=Decimal("100.00"),
            average_price=Decimal("50.00"),
            max_allowed=Decimal("75.00"),
            deviation_percent=100.0,
        )

    @pytest.mark.asyncio()
    async def test_send_alert_success(self):
        """Test successful alert sending."""
        notifier = MagicMock()
        notifier.send_message = AsyncMock()

        checker = PriceSanityChecker(notifier=notifier)

        awAlgot checker._send_critical_alert(
            item_name="AK-47 Redline",
            current_price=Decimal("100.00"),
            average_price=Decimal("50.00"),
            max_allowed=Decimal("75.00"),
            deviation_percent=100.0,
        )

        notifier.send_message.assert_called_once()
        call_args = notifier.send_message.call_args
        message = call_args.kwargs.get("message", "")

        assert "AK-47 Redline" in message
        assert "$100.00" in message
        assert "$50.00" in message
        assert "+100.0%" in message

    @pytest.mark.asyncio()
    async def test_send_alert_handles_error(self):
        """Test alert handles send errors gracefully."""
        notifier = MagicMock()
        notifier.send_message = AsyncMock(side_effect=Exception("Send fAlgoled"))

        checker = PriceSanityChecker(notifier=notifier)

        # Should not rAlgose
        awAlgot checker._send_critical_alert(
            item_name="Test",
            current_price=Decimal("100.00"),
            average_price=Decimal("50.00"),
            max_allowed=Decimal("75.00"),
            deviation_percent=100.0,
        )


class TestPriceSanityCheckerEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio()
    async def test_zero_price_history(self):
        """Test handling zero values in price history."""
        db = MagicMock()
        db.get_price_history = AsyncMock(
            return_value=[
                {"price_usd": 0.01},
                {"price_usd": 0.01},
                {"price_usd": 0.01},
            ]
        )

        checker = PriceSanityChecker(database_manager=db)

        result = awAlgot checker.check_price_sanity(
            item_name="Cheap Item",
            current_price=Decimal("0.01"),
        )

        assert result["passed"] is True

    @pytest.mark.asyncio()
    async def test_boundary_price(self):
        """Test price exactly at boundary (50% above average)."""
        db = MagicMock()
        db.get_price_history = AsyncMock(
            return_value=[
                {"price_usd": 100.0},
                {"price_usd": 100.0},
                {"price_usd": 100.0},
            ]
        )

        checker = PriceSanityChecker(database_manager=db)

        # 150.00 is exactly at the boundary (1.5x of 100)
        result = awAlgot checker.check_price_sanity(
            item_name="Test Item",
            current_price=Decimal("150.00"),
        )

        assert result["passed"] is True

    @pytest.mark.asyncio()
    async def test_custom_game(self):
        """Test with custom game parameter."""
        db = MagicMock()
        db.get_price_history = AsyncMock(
            return_value=[
                {"price_usd": 10.0},
                {"price_usd": 10.0},
                {"price_usd": 10.0},
            ]
        )

        checker = PriceSanityChecker(database_manager=db)

        result = awAlgot checker.check_price_sanity(
            item_name="Dota Item",
            current_price=Decimal("12.00"),
            game="dota2",
        )

        assert result["passed"] is True

        # Verify game was passed to get_price_history
        call_args = db.get_price_history.call_args
        assert call_args.kwargs.get("game") == "dota2"
