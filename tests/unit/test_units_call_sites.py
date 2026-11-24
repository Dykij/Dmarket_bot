"""Characterization tests catching lost cents <-> usd conversions."""

from typing import Any
import pytest

from src.api.dmarket_api_client.offers import _OffersMixin
from src.api.dmarket_parser import (
    parse_aggregated_prices,
    parse_aggregated_prices_from_dict,
)


class _OffersClient(_OffersMixin):
    def __init__(self) -> None:
        self.sent: dict[str, Any] = {}

    async def make_request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        self.sent = {"method": method, "path": path, "body": body}
        return {}


def test_parse_aggregated_prices_bid_cents_to_usd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.api.dmarket_parser.HAS_RUST_PARSER", False)
    raw = '{"aggregatedPrices": [{"title": "T", "orderBestPrice": {"Amount": "1550"}}]}'
    res = parse_aggregated_prices(raw)
    assert res[0]["best_bid"] == 15.5


def test_parse_aggregated_prices_ask_cents_to_usd(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("src.api.dmarket_parser.HAS_RUST_PARSER", False)
    raw = '{"aggregatedPrices": [{"title": "T", "offerBestPrice": {"Amount": "2575"}}]}'
    res = parse_aggregated_prices(raw)
    assert res[0]["best_ask"] == 25.75


def test_parse_aggregated_prices_from_dict_bid_cents_to_usd() -> None:
    data = {"aggregatedPrices": [{"title": "T", "orderBestPrice": {"Amount": "1420"}}]}
    res = parse_aggregated_prices_from_dict(data)
    assert res[0]["best_bid"] == 14.2


def test_parse_aggregated_prices_from_dict_ask_cents_to_usd() -> None:
    data = {"aggregatedPrices": [{"title": "T", "offerBestPrice": {"Amount": "3180"}}]}
    res = parse_aggregated_prices_from_dict(data)
    assert res[0]["best_ask"] == 31.8


@pytest.mark.asyncio
async def test_batch_edit_offers_v2_usd_to_cents() -> None:
    c = _OffersClient()
    await c.batch_edit_offers_v2([{"offer_id": "off_1", "new_price_usd": 15.99}])
    assert c.sent["path"] == "/marketplace-api/v2/offers:batchUpdate"
    assert c.sent["body"] == {
        "requests": [{"offerId": "off_1", "priceCents": 1599}]
    }
