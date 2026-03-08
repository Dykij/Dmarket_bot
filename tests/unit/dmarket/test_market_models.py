from datetime import UTC, datetime

from src.dmarket.models.market_models import (
    AggregatedPrice,
    Balance,
    MarketItem,
    MarketPrice,
    OfferByTitle,
    Price,
    SalesHistory,
    TargetOrder,
)


class TestPrice:
    def test_dollars_property(self):
        price = Price(Amount=1250, Currency="USD")
        assert price.dollars == 12.50

    def test_from_dollars(self):
        price = Price.from_dollars(12.50, "USD")
        assert price.Amount == 1250
        assert price.Currency == "USD"


class TestBalance:
    def test_usd_dollars_property(self):
        balance = Balance(
            usd="1250",
            usdAvAlgolableToWithdraw="1000",
            dmc="500",
            dmcAvAlgolableToWithdraw="400",
        )
        assert balance.usd_dollars == 12.50
        assert balance.avAlgolable_usd_dollars == 10.00

    def test_usd_dollars_property_with_int(self):
        balance = Balance(
            usd=1250,  # type: ignore
            usdAvAlgolableToWithdraw=1000,  # type: ignore
            dmc="500",
            dmcAvAlgolableToWithdraw="400",
        )
        assert balance.usd_dollars == 12.50
        assert balance.avAlgolable_usd_dollars == 10.00

    def test_invalid_values(self):
        balance = Balance(
            usd="invalid",
            usdAvAlgolableToWithdraw="invalid",
            dmc="500",
            dmcAvAlgolableToWithdraw="400",
        )
        assert balance.usd_dollars == 0.0
        assert balance.avAlgolable_usd_dollars == 0.0


class TestMarketItem:
    def test_price_usd_property_dict_format(self):
        item = MarketItem(
            itemId="1",
            title="Test Item",
            price={"USD": {"amount": 1250}},
            gameId="game1",
        )
        assert item.price_usd == 12.50

    def test_price_usd_property_str_format(self):
        item = MarketItem(
            itemId="1", title="Test Item", price={"USD": "12.50"}, gameId="game1"
        )
        assert item.price_usd == 12.50

    def test_suggested_price_usd(self):
        item = MarketItem(
            itemId="1",
            title="Test Item",
            price={"USD": {"amount": 1250}},
            gameId="game1",
            suggestedPrice={"USD": "1500"},
        )
        assert item.suggested_price_usd == 15.00

    def test_suggested_price_usd_none(self):
        item = MarketItem(
            itemId="1",
            title="Test Item",
            price={"USD": {"amount": 1250}},
            gameId="game1",
            suggestedPrice=None,
        )
        assert item.suggested_price_usd == 0.0


class TestAggregatedPrice:
    def test_properties(self):
        agg_price = AggregatedPrice(
            title="Test Item",
            orderBestPrice="1000",
            orderCount=5,
            offerBestPrice="1200",
            offerCount=3,
        )
        assert agg_price.order_price_usd == 10.00
        assert agg_price.offer_price_usd == 12.00
        assert agg_price.spread_usd == 2.00
        assert agg_price.spread_percent == 20.0

    def test_spread_percent_zero_order_price(self):
        agg_price = AggregatedPrice(
            title="Test Item",
            orderBestPrice="0",
            orderCount=0,
            offerBestPrice="1200",
            offerCount=3,
        )
        assert agg_price.spread_percent == 0.0


class TestTargetOrder:
    def test_price_usd(self):
        order = TargetOrder(amount=1, price="1250", title="Test Item")
        assert order.price_usd == 12.50


class TestOfferByTitle:
    def test_price_usd_float(self):
        offer = OfferByTitle(
            offerId="1", price=MarketPrice(USD="1250"), title="Test Item"
        )
        assert offer.price_usd_float == 12.50


class TestSalesHistory:
    def test_properties(self):
        history = SalesHistory(price="1250", date="2023-01-01T12:00:00+00:00")
        assert history.price_float == 12.50
        assert history.date_datetime == datetime(2023, 1, 1, 12, 0, 0, tzinfo=UTC)

    def test_invalid_date(self):
        history = SalesHistory(price="1250", date="invalid-date")
        assert history.date_datetime is None
