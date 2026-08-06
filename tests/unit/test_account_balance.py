"""Tests for account.py — balance response format handling."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from src.api.dmarket_api_client.account import _AccountMixin


class FakeAccount(_AccountMixin):
    """Concrete stub for testing the mixin."""

    def __init__(self):
        self._cached_balance = None
        self._cached_balance_ts = 0.0


class TestGetRealBalance:

    @pytest.mark.asyncio
    async def test_legacy_usd_field(self):
        """Legacy API: returns {'usd': 4391} → $43.91."""
        account = FakeAccount()
        account.make_request = AsyncMock(return_value={"usd": 4391})

        with patch("src.api.dmarket_api_client.account.Config") as mock_cfg:
            mock_cfg.DRY_RUN = True
            result = await account.get_real_balance()

        assert result == 43.91

    @pytest.mark.asyncio
    async def test_new_balance_field(self):
        """New API: returns {'balance': 43.91} → $43.91."""
        account = FakeAccount()
        account.make_request = AsyncMock(return_value={"balance": 43.91})

        with patch("src.api.dmarket_api_client.account.Config") as mock_cfg:
            mock_cfg.DRY_RUN = True
            result = await account.get_real_balance()

        assert result == 43.91

    @pytest.mark.asyncio
    async def test_both_fields_balance_takes_precedence(self):
        """When both fields present, 'balance' (new format) takes precedence."""
        account = FakeAccount()
        account.make_request = AsyncMock(return_value={"usd": 5000, "balance": 50.0})

        with patch("src.api.dmarket_api_client.account.Config") as mock_cfg:
            mock_cfg.DRY_RUN = True
            result = await account.get_real_balance()

        assert result == 50.0

    @pytest.mark.asyncio
    async def test_neither_field_returns_zero(self):
        """When neither field present, returns 0.0."""
        account = FakeAccount()
        account.make_request = AsyncMock(return_value={})

        with patch("src.api.dmarket_api_client.account.Config") as mock_cfg:
            mock_cfg.DRY_RUN = True
            result = await account.get_real_balance()

        assert result == 0.0

    @pytest.mark.asyncio
    async def test_api_failure_uses_cache(self):
        """On API failure, cached balance is returned if fresh."""
        account = FakeAccount()
        type(account)._cached_balance = 42.0
        type(account)._cached_balance_ts = time.monotonic()
        account.make_request = AsyncMock(side_effect=Exception("API down"))

        result = await account.get_real_balance()
        assert result == 42.0

    @pytest.mark.asyncio
    async def test_api_failure_uses_dry_run_fallback(self):
        """On API failure with no cache in DRY_RUN, uses env fallback."""
        account = FakeAccount()
        type(account)._cached_balance = None
        type(account)._cached_balance_ts = 0.0
        account.make_request = AsyncMock(side_effect=Exception("API down"))

        with patch("src.api.dmarket_api_client.account.Config") as mock_cfg:
            mock_cfg.DRY_RUN = True
            result = await account.get_real_balance()

        assert result == 1000.0
