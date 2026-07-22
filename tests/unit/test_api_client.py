"""Tests for DMarket API client — rate limiter."""

from __future__ import annotations

import asyncio

import pytest

from src.api.dmarket_api_client.rate_limiter import TokenBucket, EndpointRateLimiter


class TestTokenBucket:

    def test_init(self):
        tb = TokenBucket(rate=10.0, capacity=20.0)
        assert tb.rate == 10.0
        assert tb.capacity == 20.0

    @pytest.mark.asyncio
    async def test_acquire_returns_delay(self):
        tb = TokenBucket(rate=10.0, capacity=5.0)
        delay = await tb.acquire()
        assert delay >= 0.0

    @pytest.mark.asyncio
    async def test_multiple_acquires(self):
        tb = TokenBucket(rate=10.0, capacity=2.0)
        d1 = await tb.acquire()
        d2 = await tb.acquire()
        assert d1 >= 0.0
        assert d2 >= 0.0


class TestEndpointRateLimiter:

    def test_init(self):
        erl = EndpointRateLimiter()
        assert erl is not None

    def test_status(self):
        erl = EndpointRateLimiter()
        status = erl.status()
        assert isinstance(status, dict)
