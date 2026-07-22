"""Tests for oracle modules — CSFloat, Waxpeer."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

from src.api.csfloat_oracle import CSFloatOracle
from src.api.waxpeer_oracle import WaxpeerOracle


class TestCSFloatOracle:

    def test_init(self):
        oracle = CSFloatOracle(api_key="test_key")
        assert oracle.api_key == "test_key"

    def test_init_default(self):
        oracle = CSFloatOracle()
        assert oracle.api_key == ""


class TestWaxpeerOracle:

    def test_init(self):
        oracle = WaxpeerOracle()
        assert oracle is not None
