"""Unit tests for msgspec market models (v15.7)."""

from __future__ import annotations

import msgspec
import pytest

from src.models.market import (
    AggregatedPrice,
    CycleStats,
    MarketItem,
    OracleResult,
    PriceAmount,
    PriceSnapshot,
    RiskSnapshot,
    TradeCandidate,
    decode_struct,
    encode_struct,
)


class TestPriceAmount:
    """Tests for PriceAmount Struct."""

    def test_usd_conversion(self) -> None:
        p = PriceAmount(amount="1234", currency="USD")
        assert p.usd == pytest.approx(12.34)

    def test_zero_amount(self) -> None:
        p = PriceAmount(amount="0")
        assert p.usd == 0.0

    def test_empty_amount(self) -> None:
        p = PriceAmount()
        assert p.usd == 0.0

    def test_invalid_amount(self) -> None:
        p = PriceAmount(amount="abc")
        assert p.usd == 0.0

    def test_encode_decode(self) -> None:
        p = PriceAmount(amount="500", currency="USD")
        data = msgspec.json.encode(p)
        p2 = msgspec.json.decode(data, type=PriceAmount)
        assert p2.amount == "500"
        assert p2.usd == pytest.approx(5.0)


class TestMarketItem:
    """Tests for MarketItem Struct."""

    def test_basic_creation(self) -> None:
        item = MarketItem(
            itemId="abc123",
            title="AK-47 | Redline (FT)",
            price=PriceAmount(amount="1250", currency="USD"),
        )
        assert item.base_price == pytest.approx(12.50)
        assert item.title == "AK-47 | Redline (FT)"

    def test_default_values(self) -> None:
        item = MarketItem()
        assert item.itemId == ""
        assert item.base_price == 0.0

    def test_json_roundtrip(self) -> None:
        item = MarketItem(
            itemId="test123",
            title="AWP | Asiimov (FT)",
            price=PriceAmount(amount="3500"),
        )
        data = encode_struct(item)
        item2 = decode_struct(data, MarketItem)
        assert item2.itemId == "test123"
        assert item2.base_price == pytest.approx(35.0)


class TestAggregatedPrice:
    """Tests for AggregatedPrice Struct."""

    def test_creation(self) -> None:
        ap = AggregatedPrice(
            market_hash_name="AK-47 | Redline (FT)",
            best_bid=10.0,
            best_ask=12.0,
            bid_count=5,
            ask_count=3,
        )
        assert ap.market_hash_name == "AK-47 | Redline (FT)"
        assert ap.best_bid == 10.0
        assert ap.bid_count == 5


class TestPriceSnapshot:
    """Tests for PriceSnapshot Struct."""

    def test_has_data_true(self) -> None:
        ps = PriceSnapshot(title="test", min_price=10.0, sources_count=3)
        assert ps.has_data is True

    def test_has_data_false_no_sources(self) -> None:
        ps = PriceSnapshot(title="test", min_price=10.0, sources_count=0)
        assert ps.has_data is False

    def test_has_data_false_no_price(self) -> None:
        ps = PriceSnapshot(title="test", min_price=0.0, sources_count=3)
        assert ps.has_data is False


class TestTradeCandidate:
    """Tests for TradeCandidate Struct."""

    def test_margin_pct(self) -> None:
        tc = TradeCandidate(
            best_bid=12.0,
            best_ask=10.0,
            base_price=10.0,
            list_price=11.5,
        )
        assert tc.margin_pct == pytest.approx(20.0)

    def test_margin_pct_zero_ask(self) -> None:
        tc = TradeCandidate(best_bid=12.0, best_ask=0.0)
        assert tc.margin_pct == 0.0

    def test_net_margin_pct(self) -> None:
        tc = TradeCandidate(
            base_price=10.0,
            list_price=12.0,
            fee_rate=0.05,
        )
        # sell_net = 12 * 0.95 = 11.4, margin = (11.4 - 10) / 10 = 14%
        assert tc.net_margin_pct == pytest.approx(14.0)

    def test_default_strategy(self) -> None:
        tc = TradeCandidate()
        assert tc.strategy == "intra_spread"
        assert tc.is_rare is False

    def test_json_roundtrip(self) -> None:
        tc = TradeCandidate(
            title="test",
            base_price=10.0,
            is_rare=True,
            premium_mult=2.5,
        )
        data = encode_struct(tc)
        tc2 = decode_struct(data, TradeCandidate)
        assert tc2.title == "test"
        assert tc2.is_rare is True
        assert tc2.premium_mult == pytest.approx(2.5)


class TestCycleStats:
    """Tests for CycleStats Struct."""

    def test_creation(self) -> None:
        cs = CycleStats(
            cycle_id=42,
            game_id="a8db",
            duration_s=1.23,
            items_scanned=100,
            trades_executed=3,
        )
        assert cs.cycle_id == 42
        assert cs.trades_executed == 3


class TestOracleResult:
    """Tests for OracleResult Struct."""

    def test_creation(self) -> None:
        or_ = OracleResult(
            title="AK-47 | Redline (FT)",
            fair_price=12.50,
            sources_used=4,
            confidence=0.85,
        )
        assert or_.fair_price == pytest.approx(12.50)
        assert or_.sources_used == 4


class TestRiskSnapshot:
    """Tests for RiskSnapshot Struct."""

    def test_defaults(self) -> None:
        rs = RiskSnapshot()
        assert rs.win_rate == pytest.approx(0.55)
        assert rs.drawdown_freeze_active is False
        assert rs.consecutive_losses == 0

    def test_json_roundtrip(self) -> None:
        rs = RiskSnapshot(
            daily_realized_pnl=5.50,
            current_drawdown_pct=3.2,
            win_rate=0.60,
        )
        data = encode_struct(rs)
        rs2 = decode_struct(data, RiskSnapshot)
        assert rs2.daily_realized_pnl == pytest.approx(5.50)
        assert rs2.win_rate == pytest.approx(0.60)


class TestEncodeDecodeHelpers:
    """Tests for encode_struct / decode_struct helpers."""

    def test_encode_returns_bytes(self) -> None:
        cs = CycleStats(cycle_id=1)
        data = encode_struct(cs)
        assert isinstance(data, bytes)

    def test_decode_from_bytes(self) -> None:
        cs = CycleStats(cycle_id=1)
        data = encode_struct(cs)
        cs2 = decode_struct(data, CycleStats)
        assert cs2.cycle_id == 1

    def test_decode_from_string(self) -> None:
        cs = CycleStats(cycle_id=1)
        data = encode_struct(cs).decode("utf-8")
        cs2 = decode_struct(data, CycleStats)
        assert cs2.cycle_id == 1

    def test_decode_validation_error(self) -> None:
        with pytest.raises(msgspec.ValidationError):
            decode_struct(b'{"cycle_id": "not_an_int"}', CycleStats)
