"""Contract test: the REAL DMarketAPIClient must expose every method that
trading code calls on it.

Why this exists: commit 83f39b2 dropped `_TargetsMixin` from the client's bases.
`tests/unit/test_execution.py` mocks `client.buy_items`, and
`tests/unit/test_targets.py` tests the mixin in isolation, so neither noticed
that `DMarketAPIClient.buy_items` no longer existed. In production the
resulting AttributeError was swallowed by
`cycle_orchestrator` (`[EXECUTE] instant buys failed`).

These tests use the real client class, no mocks on the methods under test.
"""

from __future__ import annotations

import pytest

from src.api.dmarket_api_client import DMarketAPIClient
from src.api.dmarket_api_client.targets import _TargetsMixin
from src.config import Config

TARGET_METHODS = (
    "buy_items",
    "batch_create_targets",
    "batch_delete_targets",
    "get_user_targets",
)


@pytest.mark.parametrize("name", TARGET_METHODS)
def test_real_client_has_target_methods(name: str) -> None:
    assert hasattr(DMarketAPIClient, name), f"DMarketAPIClient has no {name}"
    assert callable(getattr(DMarketAPIClient, name))


def test_targets_mixin_is_in_client_bases() -> None:
    assert _TargetsMixin in DMarketAPIClient.__mro__


def test_make_request_is_not_shadowed_by_mixin_stub() -> None:
    """_TargetsMixin declares a `make_request` stub (for mypy). The real
    transport must win in the MRO, otherwise every call returns None."""
    owner = next(c for c in DMarketAPIClient.__mro__ if "make_request" in c.__dict__)
    assert owner is DMarketAPIClient


@pytest.mark.asyncio
async def test_buy_items_on_real_client_reaches_dry_run_simulation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """PATCH /exchange/v1/offers-buy through the real transport in DRY_RUN:
    must not raise AttributeError and must not touch the network."""
    monkeypatch.setattr(Config, "DRY_RUN", True)
    client = DMarketAPIClient("key", "sec")

    async def _no_network(*_a, **_kw):  # pragma: no cover - must not be called
        raise AssertionError("network session requested in DRY_RUN")

    monkeypatch.setattr(client, "get_session", _no_network)

    resp = await client.buy_items(
        [{"offerId": "o-1", "price": {"amount": "123", "currency": "USD"}}]
    )
    assert resp == {}
