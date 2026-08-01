"""Tests for oracle modules — CSFloat, Waxpeer."""

from __future__ import annotations

import time
from unittest.mock import AsyncMock, patch

import pytest

# v17.2: Oracle tests skipped — oracles not used in demand strategy
# These tests are preserved for legacy oracle_discount strategy
pytestmark = pytest.mark.skip(reason="Legacy oracle test — v17.2 uses OBI demand strategy")

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
