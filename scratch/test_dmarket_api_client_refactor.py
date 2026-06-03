"""Smoke test for refactored dmarket_api_client package — no live API calls."""

import sys
import os
import asyncio
import unittest.mock as mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.api.dmarket_api_client import DMarketAPIClient, SecurityViolation
from src.api.dmarket_api_client import core, market, account, offers, targets, fees, exceptions


def test_imports():
    assert DMarketAPIClient is core.DMarketAPIClient
    assert SecurityViolation is exceptions.SecurityViolation
    # Mixins exist
    assert market._MarketMixin
    assert account._AccountMixin
    assert offers._OffersMixin
    assert targets._TargetsMixin
    assert fees._FeesMixin
    print("[OK] all imports work")


def test_mixin_composition():
    client = DMarketAPIClient(public_key="abc", secret_key="0" * 64)
    # From market
    assert hasattr(client, "get_market_items_v2")
    assert hasattr(client, "get_aggregated_prices")
    assert hasattr(client, "get_last_sales")
    assert hasattr(client, "get_low_fee_items")
    # From account
    assert hasattr(client, "get_real_balance")
    assert hasattr(client, "get_user_inventory")
    assert hasattr(client, "get_user_inventory_detailed")
    assert hasattr(client, "get_transaction_history")
    # From offers
    assert hasattr(client, "get_user_offers")
    assert hasattr(client, "create_offer")
    assert hasattr(client, "batch_create_offers")
    assert hasattr(client, "delete_offers")
    assert hasattr(client, "edit_offer")
    assert hasattr(client, "batch_create_offers_v2")
    assert hasattr(client, "batch_edit_offers_v2")
    assert hasattr(client, "batch_delete_offers_v2")
    assert hasattr(client, "get_user_offers_v2")
    # From targets
    assert hasattr(client, "batch_create_targets")
    assert hasattr(client, "batch_delete_targets")
    assert hasattr(client, "buy_items")
    assert hasattr(client, "get_user_targets")
    # From fees
    assert hasattr(client, "get_item_fee")
    assert hasattr(client, "get_item_fee_bulk")
    print("[OK] mixin composition works (5 mixins)")


def test_dry_run_guard():
    """DRY_RUN=true POST returns simulated success."""
    os.environ["DRY_RUN"] = "true"
    client = DMarketAPIClient(public_key="abc", secret_key="0" * 64)

    async def run():
        # POST should be simulated
        res = await client.make_request("POST", "/exchange/v1/user-offers/batch-create",
                                        body={"offers": []})
        return res

    result = asyncio.run(run())
    assert result.get("status") == "success"
    assert result.get("simulated") is True
    print("[OK] DRY_RUN guard works (POST simulated)")


def test_signature_generation():
    """Signature generation works for all methods (no network)."""
    client = DMarketAPIClient(public_key="abc", secret_key="0" * 64)
    sig = client._generate_signature("GET", "/v1/test", "", "1234567890")
    assert isinstance(sig, str)
    assert len(sig) == 128  # Ed25519 hex
    sig2 = client._generate_signature("POST", "/v1/test?x=1", "{}", "1234567890")
    assert isinstance(sig2, str)
    assert sig != sig2  # Different inputs → different sigs
    print(f"[OK] signature generation (sig len={len(sig)})")


def test_fee_cache_init():
    """Fee cache is initialized in __init__."""
    client = DMarketAPIClient(public_key="abc", secret_key="0" * 64)
    assert hasattr(client, "_fee_cache")
    assert isinstance(client._fee_cache, dict)
    assert client._fee_cache_ttl == 43200  # 12h
    print("[OK] fee cache initialized")


def test_safety_allowlist_exception():
    """SecurityViolation is importable and is an Exception."""
    assert issubclass(SecurityViolation, Exception)
    err = SecurityViolation("test violation")
    assert str(err) == "test violation"
    print("[OK] SecurityViolation usable")


if __name__ == "__main__":
    test_imports()
    test_mixin_composition()
    test_dry_run_guard()
    test_signature_generation()
    test_fee_cache_init()
    test_safety_allowlist_exception()
    print("\n[ALL PASS] dmarket_api_client refactor: 6/6 smoke tests passed")
