"""Comprehensive tests for src/models/pending_trade.py.

This module provides extensive testing for pending trade model
to achieve 95%+ coverage.
"""

from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from src.models.base import Base
from src.models.pending_trade import PendingTrade, PendingTradeStatus


class TestPendingTradeStatus:
    """Tests for PendingTradeStatus enum."""

    def test_bought_status(self) -> None:
        """Test BOUGHT status value."""
        assert PendingTradeStatus.BOUGHT == "bought"
        assert PendingTradeStatus.BOUGHT.value == "bought"

    def test_listed_status(self) -> None:
        """Test LISTED status value."""
        assert PendingTradeStatus.LISTED == "listed"
        assert PendingTradeStatus.LISTED.value == "listed"

    def test_adjusting_status(self) -> None:
        """Test ADJUSTING status value."""
        assert PendingTradeStatus.ADJUSTING == "adjusting"
        assert PendingTradeStatus.ADJUSTING.value == "adjusting"

    def test_sold_status(self) -> None:
        """Test SOLD status value."""
        assert PendingTradeStatus.SOLD == "sold"
        assert PendingTradeStatus.SOLD.value == "sold"

    def test_cancelled_status(self) -> None:
        """Test CANCELLED status value."""
        assert PendingTradeStatus.CANCELLED == "cancelled"
        assert PendingTradeStatus.CANCELLED.value == "cancelled"

    def test_stop_loss_status(self) -> None:
        """Test STOP_LOSS status value."""
        assert PendingTradeStatus.STOP_LOSS == "stop_loss"
        assert PendingTradeStatus.STOP_LOSS.value == "stop_loss"

    def test_failed_status(self) -> None:
        """Test FAlgoLED status value."""
        assert PendingTradeStatus.FAlgoLED == "failed"
        assert PendingTradeStatus.FAlgoLED.value == "failed"

    def test_all_statuses_are_strings(self) -> None:
        """Test all statuses are string enums."""
        for status in PendingTradeStatus:
            assert isinstance(status.value, str)
            assert isinstance(status, str)

    def test_status_count(self) -> None:
        """Test total number of statuses."""
        assert len(PendingTradeStatus) == 7


class TestPendingTradeModel:
    """Tests for PendingTrade model."""

    @pytest.fixture
    def db_session(self):
        """Create in-memory database session."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = Session(engine)
        yield session
        session.close()

    def test_create_basic_trade(self, db_session) -> None:
        """Test creating basic pending trade."""
        trade = PendingTrade(
            asset_id="test_asset_123",
            title="AK-47 | Redline",
            game="csgo",
            buy_price=10.50,
            min_sell_price=12.00,
        )
        db_session.add(trade)
        db_session.commit()

        result = db_session.query(PendingTrade).first()
        assert result is not None
        assert result.asset_id == "test_asset_123"
        assert result.title == "AK-47 | Redline"
        assert result.game == "csgo"
        assert result.buy_price == 10.50
        assert result.min_sell_price == 12.00

    def test_default_status_is_bought(self, db_session) -> None:
        """Test default status is BOUGHT."""
        trade = PendingTrade(
            asset_id="test_asset",
            title="Test Item",
            buy_price=5.0,
            min_sell_price=6.0,
        )
        db_session.add(trade)
        db_session.commit()

        result = db_session.query(PendingTrade).first()
        assert result.status == PendingTradeStatus.BOUGHT

    def test_default_game_is_csgo(self, db_session) -> None:
        """Test default game is csgo."""
        trade = PendingTrade(
            asset_id="test_asset",
            title="Test Item",
            buy_price=5.0,
            min_sell_price=6.0,
        )
        db_session.add(trade)
        db_session.commit()

        result = db_session.query(PendingTrade).first()
        assert result.game == "csgo"

    def test_optional_fields(self, db_session) -> None:
        """Test optional fields can be None."""
        trade = PendingTrade(
            asset_id="test_asset",
            title="Test Item",
            buy_price=5.0,
            min_sell_price=6.0,
            item_id=None,
            user_id=None,
            target_sell_price=None,
            current_price=None,
            offer_id=None,
        )
        db_session.add(trade)
        db_session.commit()

        result = db_session.query(PendingTrade).first()
        assert result.item_id is None
        assert result.user_id is None
        assert result.target_sell_price is None
        assert result.current_price is None
        assert result.offer_id is None

    def test_created_at_auto_set(self, db_session) -> None:
        """Test created_at is automatically set."""
        trade = PendingTrade(
            asset_id="test_asset",
            title="Test Item",
            buy_price=5.0,
            min_sell_price=6.0,
        )
        db_session.add(trade)
        db_session.commit()

        result = db_session.query(PendingTrade).first()
        assert result.created_at is not None
        assert isinstance(result.created_at, datetime)

    def test_adjustments_count_default(self, db_session) -> None:
        """Test adjustments_count defaults to 0."""
        trade = PendingTrade(
            asset_id="test_asset",
            title="Test Item",
            buy_price=5.0,
            min_sell_price=6.0,
        )
        db_session.add(trade)
        db_session.commit()

        result = db_session.query(PendingTrade).first()
        assert result.adjustments_count == 0

    def test_asset_id_is_unique(self, db_session) -> None:
        """Test asset_id has unique constraint."""
        trade1 = PendingTrade(
            asset_id="duplicate_asset",
            title="Item 1",
            buy_price=5.0,
            min_sell_price=6.0,
        )
        trade2 = PendingTrade(
            asset_id="duplicate_asset",
            title="Item 2",
            buy_price=10.0,
            min_sell_price=12.0,
        )
        db_session.add(trade1)
        db_session.commit()
        db_session.add(trade2)

        from sqlalchemy.exc import IntegrityError
        with pytest.raises(IntegrityError):
            db_session.commit()


class TestPendingTradeRepr:
    """Tests for PendingTrade __repr__ method."""

    def test_repr_basic(self) -> None:
        """Test basic repr output."""
        trade = PendingTrade(
            asset_id="test_123",
            title="AK-47 | Redline",
            buy_price=10.50,
            min_sell_price=12.00,
            status=PendingTradeStatus.BOUGHT,
        )
        repr_str = repr(trade)
        assert "test_123" in repr_str
        assert "AK-47 | Redline" in repr_str
        assert "10.50" in repr_str
        assert "bought" in repr_str

    def test_repr_format(self) -> None:
        """Test repr format structure."""
        trade = PendingTrade(
            asset_id="asset_abc",
            title="Test Item",
            buy_price=5.00,
            min_sell_price=6.00,
        )
        repr_str = repr(trade)
        assert repr_str.startswith("<PendingTrade(")
        assert repr_str.endswith(")>")


class TestPendingTradeToDict:
    """Tests for PendingTrade to_dict method."""

    def test_to_dict_contains_all_fields(self) -> None:
        """Test to_dict contains all expected fields."""
        trade = PendingTrade(
            asset_id="test_asset",
            item_id="item_123",
            user_id=12345,
            title="Test Item",
            game="dota2",
            buy_price=10.0,
            min_sell_price=12.0,
            target_sell_price=15.0,
            current_price=11.0,
            offer_id="offer_456",
            status=PendingTradeStatus.LISTED,
            adjustments_count=2,
        )

        result = trade.to_dict()

        assert "id" in result
        assert "asset_id" in result
        assert "item_id" in result
        assert "user_id" in result
        assert "title" in result
        assert "game" in result
        assert "buy_price" in result
        assert "min_sell_price" in result
        assert "target_sell_price" in result
        assert "current_price" in result
        assert "offer_id" in result
        assert "status" in result
        assert "adjustments_count" in result
        assert "created_at" in result
        assert "listed_at" in result
        assert "sold_at" in result
        assert "updated_at" in result

    def test_to_dict_values(self) -> None:
        """Test to_dict returns correct values."""
        trade = PendingTrade(
            asset_id="test_asset",
            title="Test Item",
            game="rust",
            buy_price=25.0,
            min_sell_price=30.0,
        )

        result = trade.to_dict()

        assert result["asset_id"] == "test_asset"
        assert result["title"] == "Test Item"
        assert result["game"] == "rust"
        assert result["buy_price"] == 25.0
        assert result["min_sell_price"] == 30.0

    def test_to_dict_datetime_iso_format(self) -> None:
        """Test to_dict converts datetimes to ISO format."""
        trade = PendingTrade(
            asset_id="test_asset",
            title="Test Item",
            buy_price=10.0,
            min_sell_price=12.0,
        )
        trade.created_at = datetime(2024, 1, 15, 10, 30, 0, tzinfo=UTC)
        trade.listed_at = datetime(2024, 1, 15, 11, 0, 0, tzinfo=UTC)
        trade.sold_at = datetime(2024, 1, 15, 12, 0, 0, tzinfo=UTC)

        result = trade.to_dict()

        assert "2024-01-15" in result["created_at"]
        assert "2024-01-15" in result["listed_at"]
        assert "2024-01-15" in result["sold_at"]

    def test_to_dict_none_datetimes(self) -> None:
        """Test to_dict handles None datetimes."""
        trade = PendingTrade(
            asset_id="test_asset",
            title="Test Item",
            buy_price=10.0,
            min_sell_price=12.0,
        )
        trade.created_at = None
        trade.listed_at = None
        trade.sold_at = None
        trade.updated_at = None

        result = trade.to_dict()

        assert result["created_at"] is None
        assert result["listed_at"] is None
        assert result["sold_at"] is None
        assert result["updated_at"] is None


class TestCalculateProfit:
    """Tests for PendingTrade.calculate_profit method."""

    def test_calculate_profit_with_sale_price(self) -> None:
        """Test profit calculation with explicit sale price."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=10.0,
            min_sell_price=12.0,
        )

        profit, percent = trade.calculate_profit(sale_price=15.0)

        assert profit == 5.0
        assert percent == 50.0

    def test_calculate_profit_uses_current_price(self) -> None:
        """Test profit calculation uses current_price."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=10.0,
            min_sell_price=12.0,
            current_price=14.0,
        )

        profit, percent = trade.calculate_profit()

        assert profit == 4.0
        assert percent == 40.0

    def test_calculate_profit_uses_target_price(self) -> None:
        """Test profit calculation uses target_sell_price."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=10.0,
            min_sell_price=12.0,
            target_sell_price=13.0,
        )

        profit, percent = trade.calculate_profit()

        assert profit == 3.0
        assert percent == 30.0

    def test_calculate_profit_no_price_returns_zero(self) -> None:
        """Test profit calculation with no price returns zero."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=10.0,
            min_sell_price=12.0,
        )

        profit, percent = trade.calculate_profit()

        assert profit == 0.0
        assert percent == 0.0

    def test_calculate_profit_zero_buy_price(self) -> None:
        """Test profit calculation with zero buy price."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=0.0,
            min_sell_price=12.0,
            current_price=15.0,
        )

        profit, percent = trade.calculate_profit()

        assert profit == 0.0
        assert percent == 0.0

    def test_calculate_profit_negative(self) -> None:
        """Test profit calculation with loss."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=20.0,
            min_sell_price=15.0,
            current_price=15.0,
        )

        profit, percent = trade.calculate_profit()

        assert profit == -5.0
        assert percent == -25.0

    def test_calculate_profit_rounding(self) -> None:
        """Test profit calculation rounding."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=10.0,
            min_sell_price=12.0,
        )

        profit, percent = trade.calculate_profit(sale_price=13.333)

        assert profit == 3.33
        assert percent == 33.33


class TestIsProfitable:
    """Tests for PendingTrade.is_profitable method."""

    def test_is_profitable_true(self) -> None:
        """Test is_profitable returns True for profitable trade."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=10.0,
            min_sell_price=12.0,
            current_price=15.0,  # After 7% fee: 13.95 > 10.0
        )

        assert trade.is_profitable() is True

    def test_is_profitable_false(self) -> None:
        """Test is_profitable returns False for unprofitable trade."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=10.0,
            min_sell_price=9.0,
            current_price=10.0,  # After 7% fee: 9.30 < 10.0
        )

        assert trade.is_profitable() is False

    def test_is_profitable_custom_fee(self) -> None:
        """Test is_profitable with custom fee percentage."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=10.0,
            min_sell_price=11.0,
            current_price=11.0,  # After 10% fee: 9.90 < 10.0
        )

        assert trade.is_profitable(dmarket_fee_percent=10.0) is False
        assert trade.is_profitable(dmarket_fee_percent=5.0) is True

    def test_is_profitable_no_price(self) -> None:
        """Test is_profitable with no price returns False."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=10.0,
            min_sell_price=12.0,
        )

        assert trade.is_profitable() is False

    def test_is_profitable_uses_target_price(self) -> None:
        """Test is_profitable uses target_sell_price when no current_price."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=10.0,
            min_sell_price=12.0,
            target_sell_price=15.0,
        )

        assert trade.is_profitable() is True

    def test_is_profitable_breakeven(self) -> None:
        """Test is_profitable at breakeven point."""
        # 10.0 / 0.93 = 10.75 breakeven sell price (7% fee)
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=10.0,
            min_sell_price=11.0,
            current_price=10.75,  # After 7% fee: 9.9975 < 10.0
        )

        assert trade.is_profitable() is False

        trade.current_price = 10.76  # After 7% fee: 10.0068 > 10.0
        assert trade.is_profitable() is True


class TestCalculateMinSellPrice:
    """Tests for PendingTrade.calculate_min_sell_price class method."""

    def test_basic_calculation(self) -> None:
        """Test basic min sell price calculation."""
        # Formula: buy_price * (1 + margin) / (1 - fee)
        # 10.0 * 1.05 / 0.93 = 11.29
        result = PendingTrade.calculate_min_sell_price(buy_price=10.0)
        assert result == 11.29

    def test_custom_margin(self) -> None:
        """Test with custom margin percentage."""
        # 10.0 * 1.10 / 0.93 = 11.83
        result = PendingTrade.calculate_min_sell_price(
            buy_price=10.0,
            min_margin_percent=10.0,
        )
        assert result == 11.83

    def test_custom_fee(self) -> None:
        """Test with custom fee percentage."""
        # 10.0 * 1.05 / 0.90 = 11.67
        result = PendingTrade.calculate_min_sell_price(
            buy_price=10.0,
            dmarket_fee_percent=10.0,
        )
        assert result == 11.67

    def test_zero_margin(self) -> None:
        """Test with zero margin."""
        # 10.0 * 1.00 / 0.93 = 10.75
        result = PendingTrade.calculate_min_sell_price(
            buy_price=10.0,
            min_margin_percent=0.0,
        )
        assert result == 10.75

    def test_high_price_item(self) -> None:
        """Test with high price item."""
        # 100.0 * 1.05 / 0.93 = 112.90
        result = PendingTrade.calculate_min_sell_price(buy_price=100.0)
        assert result == 112.9

    def test_low_price_item(self) -> None:
        """Test with low price item."""
        # 1.0 * 1.05 / 0.93 = 1.13
        result = PendingTrade.calculate_min_sell_price(buy_price=1.0)
        assert result == 1.13

    def test_result_is_rounded(self) -> None:
        """Test result is rounded to 2 decimal places."""
        result = PendingTrade.calculate_min_sell_price(
            buy_price=10.0,
            min_margin_percent=3.333,
        )
        # Should be rounded
        assert result == round(result, 2)


class TestPendingTradeWithDatabase:
    """Integration tests with actual database operations."""

    @pytest.fixture
    def db_session(self):
        """Create in-memory database session."""
        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        session = Session(engine)
        yield session
        session.close()

    def test_query_by_status(self, db_session) -> None:
        """Test querying trades by status."""
        trades = [
            PendingTrade(
                asset_id=f"asset_{i}",
                title=f"Item {i}",
                buy_price=10.0,
                min_sell_price=12.0,
                status=status,
            )
            for i, status in enumerate([
                PendingTradeStatus.BOUGHT,
                PendingTradeStatus.BOUGHT,
                PendingTradeStatus.LISTED,
                PendingTradeStatus.SOLD,
            ])
        ]
        for trade in trades:
            db_session.add(trade)
        db_session.commit()

        bought = db_session.query(PendingTrade).filter_by(
            status=PendingTradeStatus.BOUGHT
        ).all()
        listed = db_session.query(PendingTrade).filter_by(
            status=PendingTradeStatus.LISTED
        ).all()
        sold = db_session.query(PendingTrade).filter_by(
            status=PendingTradeStatus.SOLD
        ).all()

        assert len(bought) == 2
        assert len(listed) == 1
        assert len(sold) == 1

    def test_query_by_game(self, db_session) -> None:
        """Test querying trades by game."""
        games = ["csgo", "csgo", "dota2", "rust"]
        for i, game in enumerate(games):
            trade = PendingTrade(
                asset_id=f"asset_{i}",
                title=f"Item {i}",
                buy_price=10.0,
                min_sell_price=12.0,
                game=game,
            )
            db_session.add(trade)
        db_session.commit()

        csgo = db_session.query(PendingTrade).filter_by(game="csgo").all()
        dota2 = db_session.query(PendingTrade).filter_by(game="dota2").all()
        rust = db_session.query(PendingTrade).filter_by(game="rust").all()

        assert len(csgo) == 2
        assert len(dota2) == 1
        assert len(rust) == 1

    def test_update_status(self, db_session) -> None:
        """Test updating trade status."""
        trade = PendingTrade(
            asset_id="test_asset",
            title="Test Item",
            buy_price=10.0,
            min_sell_price=12.0,
        )
        db_session.add(trade)
        db_session.commit()

        # Update status
        trade.status = PendingTradeStatus.LISTED
        trade.listed_at = datetime.now(UTC)
        db_session.commit()

        result = db_session.query(PendingTrade).first()
        assert result.status == PendingTradeStatus.LISTED
        assert result.listed_at is not None

    def test_increment_adjustments(self, db_session) -> None:
        """Test incrementing adjustments count."""
        trade = PendingTrade(
            asset_id="test_asset",
            title="Test Item",
            buy_price=10.0,
            min_sell_price=12.0,
        )
        db_session.add(trade)
        db_session.commit()

        # Increment adjustments
        trade.adjustments_count += 1
        db_session.commit()

        result = db_session.query(PendingTrade).first()
        assert result.adjustments_count == 1

        # Increment agAlgon
        trade.adjustments_count += 1
        db_session.commit()

        result = db_session.query(PendingTrade).first()
        assert result.adjustments_count == 2


class TestPendingTradeEdgeCases:
    """Edge case tests for PendingTrade."""

    def test_very_small_price(self) -> None:
        """Test with very small price."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=0.01,
            min_sell_price=0.02,
            current_price=0.03,
        )

        profit, percent = trade.calculate_profit()
        assert profit == 0.02
        assert percent == 200.0

    def test_very_large_price(self) -> None:
        """Test with very large price."""
        trade = PendingTrade(
            asset_id="test",
            title="Test",
            buy_price=10000.0,
            min_sell_price=12000.0,
            current_price=15000.0,
        )

        profit, percent = trade.calculate_profit()
        assert profit == 5000.0
        assert percent == 50.0

    def test_long_title(self) -> None:
        """Test with long title."""
        long_title = "A" * 500
        trade = PendingTrade(
            asset_id="test",
            title=long_title,
            buy_price=10.0,
            min_sell_price=12.0,
        )
        assert len(trade.title) == 500

    def test_unicode_title(self) -> None:
        """Test with unicode characters in title."""
        unicode_title = "АК-47 | Красная линия ★"
        trade = PendingTrade(
            asset_id="test",
            title=unicode_title,
            buy_price=10.0,
            min_sell_price=12.0,
        )
        assert trade.title == unicode_title
