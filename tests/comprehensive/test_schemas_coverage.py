"""Comprehensive tests for src/dmarket/schemas.py.

This module provides extensive testing for Pydantic schemas
to achieve 95%+ coverage.
"""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from src.dmarket.schemas import (
    AggregatedPriceModel,
    AggregatedPricesResponse,
    AttributesModel,
    BalanceResponse,
    BuyOfferRequest,
    BuyOffersResponse,
    CreateOfferRequest,
    CreateOffersResponse,
    CreateTargetRequest,
    CreateTargetsResponse,
    DMarketAPIError,
    DMarketOffer,
    MarketItemModel,
    MarketItemsResponse,
    PriceModel,
    SaleModel,
    SalesHistoryResponse,
    TargetPriceModel,
    TargetResultModel,
    UserTargetModel,
    UserTargetsResponse,
)


class TestPriceModel:
    """Tests for PriceModel."""

    def test_create_basic_price(self) -> None:
        """Test creating basic price model."""
        price = PriceModel(USD="1000", EUR="900", DMC="500")
        assert price.usd == "1000"
        assert price.eur == "900"
        assert price.dmc == "500"

    def test_create_with_aliases(self) -> None:
        """Test creating price with lowercase aliases."""
        price = PriceModel(usd="1000")
        assert price.usd == "1000"

    def test_none_values(self) -> None:
        """Test price with None values."""
        price = PriceModel()
        assert price.usd is None
        assert price.eur is None
        assert price.dmc is None

    def test_validate_price_string_from_int(self) -> None:
        """Test price string validation from integer."""
        price = PriceModel(USD=1000)
        assert price.usd == "1000"

    def test_to_usd_decimal(self) -> None:
        """Test conversion to USD decimal (cents to dollars)."""
        price = PriceModel(USD="1000")  # 1000 cents = $10.00
        result = price.to_usd_decimal()
        assert result == Decimal("10.00")

    def test_to_usd_decimal_none(self) -> None:
        """Test to_usd_decimal with None value."""
        price = PriceModel()
        result = price.to_usd_decimal()
        assert result == Decimal("0")

    def test_to_eur_decimal(self) -> None:
        """Test conversion to EUR decimal (cents to euros)."""
        price = PriceModel(EUR="900")  # 900 cents = €9.00
        result = price.to_eur_decimal()
        assert result == Decimal("9.00")

    def test_to_eur_decimal_none(self) -> None:
        """Test to_eur_decimal with None value."""
        price = PriceModel()
        result = price.to_eur_decimal()
        assert result == Decimal("0")

    def test_extra_fields_allowed(self) -> None:
        """Test that extra fields are allowed."""
        price = PriceModel(USD="1000", extra_field="extra")
        assert price.usd == "1000"


class TestAttributesModel:
    """Tests for AttributesModel."""

    def test_create_basic_attributes(self) -> None:
        """Test creating basic attributes model."""
        attrs = AttributesModel(
            category="Rifle",
            exterior="Field-Tested",
            rarity="Covert",
        )
        assert attrs.category == "Rifle"
        assert attrs.exterior == "Field-Tested"
        assert attrs.rarity == "Covert"

    def test_float_value_alias(self) -> None:
        """Test floatValue alias."""
        attrs = AttributesModel(floatValue="0.25")
        assert attrs.float_value == "0.25"

    def test_paint_seed_alias(self) -> None:
        """Test paintSeed alias."""
        attrs = AttributesModel(paintSeed=123)
        assert attrs.paint_seed == 123

    def test_phase_attribute(self) -> None:
        """Test phase attribute for Doppler knives."""
        attrs = AttributesModel(phase="Phase 2")
        assert attrs.phase == "Phase 2"

    def test_all_none_attributes(self) -> None:
        """Test attributes with all None values."""
        attrs = AttributesModel()
        assert attrs.category is None
        assert attrs.exterior is None
        assert attrs.rarity is None
        assert attrs.float_value is None
        assert attrs.phase is None
        assert attrs.paint_seed is None


class TestMarketItemModel:
    """Tests for MarketItemModel."""

    def test_create_basic_item(self) -> None:
        """Test creating basic market item."""
        item = MarketItemModel(
            itemId="item_123",
            title="AK-47 | Redline",
            price=PriceModel(USD="1000"),
        )
        assert item.item_id == "item_123"
        assert item.title == "AK-47 | Redline"
        assert item.price.usd == "1000"

    def test_item_with_suggested_price(self) -> None:
        """Test item with suggested price."""
        item = MarketItemModel(
            itemId="item_123",
            title="Test Item",
            price=PriceModel(USD="1000"),
            suggestedPrice=PriceModel(USD="1200"),
        )
        assert item.suggested_price is not None
        assert item.suggested_price.usd == "1200"

    def test_item_with_attributes(self) -> None:
        """Test item with attributes."""
        item = MarketItemModel(
            itemId="item_123",
            title="Test Item",
            price=PriceModel(USD="1000"),
            attributes=AttributesModel(exterior="Factory New"),
        )
        assert item.attributes is not None
        assert item.attributes.exterior == "Factory New"

    def test_item_with_game_id(self) -> None:
        """Test item with game ID."""
        item = MarketItemModel(
            itemId="item_123",
            title="Test Item",
            price=PriceModel(USD="1000"),
            gameId="a8db",
        )
        assert item.game_id == "a8db"


class TestMarketItemsResponse:
    """Tests for MarketItemsResponse."""

    def test_create_empty_response(self) -> None:
        """Test creating empty market items response."""
        response = MarketItemsResponse()
        assert response.objects == []
        assert response.total == 0
        assert response.cursor is None

    def test_create_with_items(self) -> None:
        """Test creating response with items."""
        items = [
            MarketItemModel(
                itemId=f"item_{i}",
                title=f"Item {i}",
                price=PriceModel(USD="1000"),
            )
            for i in range(3)
        ]
        response = MarketItemsResponse(objects=items, total=3)
        assert len(response.objects) == 3
        assert response.total == 3

    def test_validate_total_from_string(self) -> None:
        """Test total validation from string."""
        response = MarketItemsResponse(total="100")
        assert response.total == 100

    def test_validate_total_from_dict(self) -> None:
        """Test total validation from dict (DMarket API format)."""
        response = MarketItemsResponse(total={"items": 50, "offers": 30})
        assert response.total == 80

    def test_validate_total_from_invalid_string(self) -> None:
        """Test total validation from invalid string."""
        response = MarketItemsResponse(total="invalid")
        assert response.total == 0

    def test_cursor_for_pagination(self) -> None:
        """Test cursor for pagination."""
        response = MarketItemsResponse(cursor="abc123")
        assert response.cursor == "abc123"


class TestTargetPriceModel:
    """Tests for TargetPriceModel."""

    def test_create_basic_target_price(self) -> None:
        """Test creating basic target price."""
        price = TargetPriceModel(amount=1000, currency="USD")
        assert price.amount == 1000
        assert price.currency == "USD"

    def test_validate_amount_from_string(self) -> None:
        """Test amount validation from string."""
        price = TargetPriceModel(amount="1500", currency="USD")
        assert price.amount == 1500

    def test_validate_amount_invalid_string(self) -> None:
        """Test amount validation from invalid string."""
        price = TargetPriceModel(amount="invalid", currency="USD")
        assert price.amount == 0

    def test_default_currency(self) -> None:
        """Test default currency is USD."""
        price = TargetPriceModel(amount=1000)
        assert price.currency == "USD"


class TestCreateTargetRequest:
    """Tests for CreateTargetRequest."""

    def test_create_basic_target_request(self) -> None:
        """Test creating basic target request."""
        request = CreateTargetRequest(
            Title="AK-47 | Redline",
            Amount=1,
            Price=TargetPriceModel(amount=1000, currency="USD"),
        )
        assert request.title == "AK-47 | Redline"
        assert request.amount == 1
        assert request.price.amount == 1000

    def test_target_with_attrs(self) -> None:
        """Test target with additional attributes."""
        request = CreateTargetRequest(
            Title="Test Item",
            Amount=5,
            Price=TargetPriceModel(amount=500, currency="USD"),
            Attrs={"exterior": "Factory New"},
        )
        assert request.attrs == {"exterior": "Factory New"}

    def test_amount_validation_min(self) -> None:
        """Test amount minimum validation."""
        with pytest.raises(ValidationError):
            CreateTargetRequest(
                Title="Test",
                Amount=0,  # Should be >= 1
                Price=TargetPriceModel(amount=100),
            )

    def test_amount_validation_max(self) -> None:
        """Test amount maximum validation."""
        with pytest.raises(ValidationError):
            CreateTargetRequest(
                Title="Test",
                Amount=101,  # Should be <= 100
                Price=TargetPriceModel(amount=100),
            )


class TestTargetResultModel:
    """Tests for TargetResultModel."""

    def test_create_target_result(self) -> None:
        """Test creating target result."""
        result = TargetResultModel(
            TargetID="target_123",
            Title="Test Item",
            Status="success",
        )
        assert result.target_id == "target_123"
        assert result.title == "Test Item"
        assert result.status == "success"

    def test_target_result_without_title(self) -> None:
        """Test target result without title."""
        result = TargetResultModel(
            TargetID="target_123",
            Status="success",
        )
        assert result.title is None


class TestCreateTargetsResponse:
    """Tests for CreateTargetsResponse."""

    def test_create_empty_response(self) -> None:
        """Test creating empty targets response."""
        response = CreateTargetsResponse()
        assert response.result == []

    def test_create_with_results(self) -> None:
        """Test creating response with results."""
        results = [
            TargetResultModel(TargetID="t1", Status="success"),
            TargetResultModel(TargetID="t2", Status="success"),
        ]
        response = CreateTargetsResponse(Result=results)
        assert len(response.result) == 2


class TestUserTargetModel:
    """Tests for UserTargetModel."""

    def test_create_user_target(self) -> None:
        """Test creating user target."""
        target = UserTargetModel(
            TargetID="target_123",
            Title="AK-47 | Redline",
            Amount=5,
            Price=TargetPriceModel(amount=1000),
            Status="Active",
            CreatedAt=1704067200,
        )
        assert target.target_id == "target_123"
        assert target.title == "AK-47 | Redline"
        assert target.amount == 5
        assert target.status == "Active"
        assert target.created_at == 1704067200


class TestUserTargetsResponse:
    """Tests for UserTargetsResponse."""

    def test_create_empty_response(self) -> None:
        """Test creating empty targets response."""
        response = UserTargetsResponse()
        assert response.items == []
        # Note: total may be "0" (string) or 0 (int) depending on Pydantic version
        assert str(response.total) == "0" or response.total == 0
        assert response.cursor is None

    def test_validate_total_from_string(self) -> None:
        """Test total validation from string."""
        response = UserTargetsResponse(Total="50")
        assert response.total == 50

    def test_validate_total_invalid(self) -> None:
        """Test total validation with invalid value."""
        response = UserTargetsResponse(Total="invalid")
        assert response.total == 0


class TestDMarketOffer:
    """Tests for DMarketOffer."""

    def test_create_basic_offer(self) -> None:
        """Test creating basic offer."""
        offer = DMarketOffer(
            offerId="offer_123",
            price="1000",
            title="Test Item",
        )
        assert offer.offer_id == "offer_123"
        assert offer.price_usd == "1000"
        assert offer.item_name == "Test Item"

    def test_offer_with_asset_id(self) -> None:
        """Test offer with asset ID."""
        offer = DMarketOffer(
            offerId="offer_123",
            price="1000",
            title="Test Item",
            assetId="asset_456",
        )
        assert offer.asset_id == "asset_456"

    def test_get_price_decimal(self) -> None:
        """Test get_price_decimal conversion."""
        offer = DMarketOffer(
            offerId="offer_123",
            price="1000",  # 1000 cents = $10.00
            title="Test Item",
        )
        result = offer.get_price_decimal()
        assert result == Decimal("10.00")


class TestCreateOfferRequest:
    """Tests for CreateOfferRequest."""

    def test_create_offer_request(self) -> None:
        """Test creating offer request."""
        request = CreateOfferRequest(
            AssetID="asset_123",
            Price=TargetPriceModel(amount=1000),
        )
        assert request.asset_id == "asset_123"
        assert request.price.amount == 1000


class TestCreateOffersResponse:
    """Tests for CreateOffersResponse."""

    def test_create_empty_response(self) -> None:
        """Test creating empty offers response."""
        response = CreateOffersResponse()
        assert response.result == []

    def test_create_with_results(self) -> None:
        """Test creating response with results."""
        response = CreateOffersResponse(
            Result=[{"offerId": "o1", "status": "success"}]
        )
        assert len(response.result) == 1


class TestBalanceResponse:
    """Tests for BalanceResponse."""

    def test_create_basic_balance(self) -> None:
        """Test creating basic balance response."""
        balance = BalanceResponse(
            usd="10000",
            dmc="5000",
        )
        assert balance.usd == "10000"
        assert balance.dmc == "5000"

    def test_default_values(self) -> None:
        """Test default balance values."""
        balance = BalanceResponse()
        assert balance.usd == "0"
        assert balance.usd_avAlgolable_to_withdraw == "0"
        assert balance.dmc == "0"
        assert balance.dmc_avAlgolable_to_withdraw == "0"

    def test_get_usd_decimal(self) -> None:
        """Test get_usd_decimal conversion."""
        balance = BalanceResponse(usd="10000")  # 10000 cents = $100.00
        result = balance.get_usd_decimal()
        assert result == Decimal("100.00")

    def test_get_avAlgolable_usd_decimal(self) -> None:
        """Test get_avAlgolable_usd_decimal conversion."""
        balance = BalanceResponse(usdAvAlgolableToWithdraw="5000")
        result = balance.get_avAlgolable_usd_decimal()
        assert result == Decimal("50.00")


class TestAggregatedPriceModel:
    """Tests for AggregatedPriceModel."""

    def test_create_basic_aggregated_price(self) -> None:
        """Test creating basic aggregated price."""
        price = AggregatedPriceModel(
            title="AK-47 | Redline",
            orderBestPrice={"Currency": "USD", "Amount": "1000"},
            orderCount=5,
            offerBestPrice={"Currency": "USD", "Amount": "1200"},
            offerCount=10,
        )
        assert price.title == "AK-47 | Redline"
        assert price.order_count == 5
        assert price.offer_count == 10

    def test_get_order_price_decimal_dict(self) -> None:
        """Test get_order_price_decimal with dict format."""
        price = AggregatedPriceModel(
            title="Test Item",
            orderBestPrice={"Currency": "USD", "Amount": "1000"},
        )
        result = price.get_order_price_decimal()
        assert result == Decimal("10.00")

    def test_get_order_price_decimal_string(self) -> None:
        """Test get_order_price_decimal with string format (old API)."""
        price = AggregatedPriceModel(
            title="Test Item",
            orderBestPrice="1000",
        )
        result = price.get_order_price_decimal()
        assert result == Decimal("10.00")

    def test_get_order_price_decimal_none(self) -> None:
        """Test get_order_price_decimal with None."""
        price = AggregatedPriceModel(title="Test Item")
        result = price.get_order_price_decimal()
        assert result is None

    def test_get_offer_price_decimal_dict(self) -> None:
        """Test get_offer_price_decimal with dict format."""
        price = AggregatedPriceModel(
            title="Test Item",
            offerBestPrice={"Currency": "USD", "Amount": "1200"},
        )
        result = price.get_offer_price_decimal()
        assert result == Decimal("12.00")

    def test_get_offer_price_decimal_string(self) -> None:
        """Test get_offer_price_decimal with string format."""
        price = AggregatedPriceModel(
            title="Test Item",
            offerBestPrice="1200",
        )
        result = price.get_offer_price_decimal()
        assert result == Decimal("12.00")

    def test_get_offer_price_decimal_none(self) -> None:
        """Test get_offer_price_decimal with None."""
        price = AggregatedPriceModel(title="Test Item")
        result = price.get_offer_price_decimal()
        assert result is None


class TestAggregatedPricesResponse:
    """Tests for AggregatedPricesResponse."""

    def test_create_empty_response(self) -> None:
        """Test creating empty response."""
        response = AggregatedPricesResponse()
        assert response.aggregated_prices == []
        assert response.next_cursor is None

    def test_create_with_prices(self) -> None:
        """Test creating response with prices."""
        prices = [
            AggregatedPriceModel(title=f"Item {i}")
            for i in range(3)
        ]
        response = AggregatedPricesResponse(aggregatedPrices=prices)
        assert len(response.aggregated_prices) == 3

    def test_next_cursor(self) -> None:
        """Test next cursor for pagination."""
        response = AggregatedPricesResponse(nextCursor="cursor_123")
        assert response.next_cursor == "cursor_123"


class TestSaleModel:
    """Tests for SaleModel."""

    def test_create_basic_sale(self) -> None:
        """Test creating basic sale."""
        sale = SaleModel(
            price="1000",
            date=1704067200,
        )
        assert sale.price == "1000"
        assert sale.date == 1704067200

    def test_sale_with_tx_type(self) -> None:
        """Test sale with transaction type."""
        sale = SaleModel(
            price="1000",
            date=1704067200,
            txOperationType="Target",
        )
        assert sale.tx_operation_type == "Target"

    def test_get_price_decimal(self) -> None:
        """Test get_price_decimal conversion."""
        sale = SaleModel(price="1000", date=1704067200)
        result = sale.get_price_decimal()
        assert result == Decimal("10.00")

    def test_get_datetime(self) -> None:
        """Test get_datetime conversion."""
        sale = SaleModel(price="1000", date=1704067200)
        result = sale.get_datetime()
        assert result.year == 2024
        assert result.month == 1


class TestSalesHistoryResponse:
    """Tests for SalesHistoryResponse."""

    def test_create_empty_response(self) -> None:
        """Test creating empty response."""
        response = SalesHistoryResponse()
        assert response.sales == []

    def test_create_with_sales(self) -> None:
        """Test creating response with sales."""
        sales = [
            SaleModel(price=f"{i}000", date=1704067200 + i)
            for i in range(5)
        ]
        response = SalesHistoryResponse(sales=sales)
        assert len(response.sales) == 5


class TestBuyOfferRequest:
    """Tests for BuyOfferRequest."""

    def test_create_buy_offer_request(self) -> None:
        """Test creating buy offer request."""
        request = BuyOfferRequest(
            offerId="offer_123",
            price={"amount": "1000", "currency": "USD"},
        )
        assert request.offer_id == "offer_123"
        assert request.price["amount"] == "1000"


class TestBuyOffersResponse:
    """Tests for BuyOffersResponse."""

    def test_create_buy_offers_response(self) -> None:
        """Test creating buy offers response."""
        response = BuyOffersResponse(
            orderId="order_123",
            status="success",
            txId="tx_456",
        )
        assert response.order_id == "order_123"
        assert response.status == "success"
        assert response.tx_id == "tx_456"

    def test_optional_fields(self) -> None:
        """Test optional fields."""
        response = BuyOffersResponse(status="pending")
        assert response.order_id is None
        assert response.tx_id is None
        assert response.dm_offers_status is None


class TestDMarketAPIError:
    """Tests for DMarketAPIError."""

    def test_create_basic_error(self) -> None:
        """Test creating basic API error."""
        error = DMarketAPIError(
            error={"message": "Invalid request"},
            code="INVALID_REQUEST",
            message="Invalid request",
            status_code=400,
        )
        assert error.error["message"] == "Invalid request"
        assert error.code == "INVALID_REQUEST"
        assert error.message == "Invalid request"
        assert error.status_code == 400

    def test_validate_error_from_string(self) -> None:
        """Test error validation from string."""
        error = DMarketAPIError(error="Something went wrong")
        assert error.error["message"] == "Something went wrong"

    def test_validate_error_from_dict(self) -> None:
        """Test error validation from dict."""
        error = DMarketAPIError(error={"code": "ERR_001", "details": "test"})
        assert error.error["code"] == "ERR_001"


class TestSchemasEdgeCases:
    """Edge case tests for schemas."""

    def test_price_model_with_zero(self) -> None:
        """Test price model with zero value."""
        price = PriceModel(USD="0")
        assert price.to_usd_decimal() == Decimal("0")

    def test_large_price_values(self) -> None:
        """Test schemas with large price values."""
        price = PriceModel(USD="100000000")  # $1,000,000
        result = price.to_usd_decimal()
        assert result == Decimal("1000000.00")

    def test_unicode_titles(self) -> None:
        """Test schemas with unicode titles."""
        item = MarketItemModel(
            itemId="test",
            title="АК-47 | Красная линия",
            price=PriceModel(USD="1000"),
        )
        assert item.title == "АК-47 | Красная линия"

    def test_empty_string_values(self) -> None:
        """Test schemas with empty string values."""
        price = PriceModel(USD="")
        # Empty string should still be allowed
        assert price.usd == ""

    def test_market_items_with_extra_field(self) -> None:
        """Test market items response with extra fields."""
        response = MarketItemsResponse(
            objects=[],
            total=0,
            unknown_field="test",
        )
        assert response.total == 0
