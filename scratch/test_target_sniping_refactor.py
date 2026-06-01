"""Smoke test for refactored target_sniping package — no live API calls."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.core.target_sniping import SnipingLoop
from src.core.target_sniping import (
    _PricingMixin,
    _ResaleMixin,
    _InventoryMixin,
    _SandboxMixin,
    _FilterMixin,
    _ExecutionMixin,
)


def test_imports():
    assert SnipingLoop is not None
    # Mixins are exposed
    assert _PricingMixin
    assert _ResaleMixin
    assert _InventoryMixin
    assert _SandboxMixin
    assert _FilterMixin
    assert _ExecutionMixin
    print("[OK] all imports work (SnipingLoop + 6 mixins)")


def test_mixin_composition():
    """SnipingLoop inherits from all 6 mixins."""
    from src.core.target_sniping.core import SnipingLoop
    bases = SnipingLoop.__mro__
    for mixin in [_PricingMixin, _ResaleMixin, _InventoryMixin, _SandboxMixin, _FilterMixin, _ExecutionMixin]:
        assert mixin in bases, f"{mixin.__name__} not in MRO"
    print(f"[OK] mixin composition works ({len([m for m in bases if 'Mixin' in m.__name__])} mixins in MRO)")


def test_float_premium():
    """Float premium calculation (pure function)."""
    # FN-0
    assert SnipingLoop._calculate_float_premium({"floatPartValue": "0.005"}) == 1.20
    # FN
    assert SnipingLoop._calculate_float_premium({"floatPartValue": "0.05"}) == 1.10
    # MW
    assert SnipingLoop._calculate_float_premium({"floatPartValue": "0.10"}) == 1.0
    # FT-0
    assert SnipingLoop._calculate_float_premium({"floatPartValue": "0.16"}) == 1.15
    # WW
    assert SnipingLoop._calculate_float_premium({"floatPartValue": "0.40"}) == 0.95
    # BS
    assert SnipingLoop._calculate_float_premium({"floatPartValue": "0.50"}) == 0.90
    # No float
    assert SnipingLoop._calculate_float_premium({}) == 1.0
    # Invalid float
    assert SnipingLoop._calculate_float_premium({"floatPartValue": "abc"}) == 1.0
    # None
    assert SnipingLoop._calculate_float_premium({"floatPartValue": None}) == 1.0
    print("[OK] float premium calculation (7 cases)")


def test_simulate_competition():
    """Sandbox competition model works (probabilistic)."""
    # Use a client mock so we don't need a real DMarketAPIClient
    from unittest.mock import MagicMock
    os.environ["DRY_RUN"] = "true"
    loop = SnipingLoop(MagicMock())

    # High margin (>0.40) should fail 90% of the time → set seed to force fail
    import random
    random.seed(0)
    fails = sum(1 for _ in range(100) if not loop._simulate_competition(0.5))
    assert 80 <= fails <= 100, f"Expected ~90% fail at 0.5 margin, got {fails}%"

    # Production (DRY_RUN=false) always wins
    os.environ["DRY_RUN"] = "false"
    assert all(loop._simulate_competition(0.5) for _ in range(50))
    os.environ["DRY_RUN"] = "true"  # restore
    print("[OK] simulate_competition (high margin fails ~90%)")


def test_sandbox_helpers():
    """Sandbox mixin helpers exist and are no-ops in production."""
    from unittest.mock import MagicMock
    loop = SnipingLoop(MagicMock())

    # In production, _maybe_inject_error should never raise
    os.environ["DRY_RUN"] = "false"
    for _ in range(100):
        loop._maybe_inject_error("test")  # Must not raise

    # In sandbox, _simulate_network_latency should not raise (sleeps briefly)
    os.environ["DRY_RUN"] = "true"
    import asyncio
    asyncio.run(loop._simulate_network_latency())
    print("[OK] sandbox helpers work in both modes")


if __name__ == "__main__":
    test_imports()
    test_mixin_composition()
    test_float_premium()
    test_simulate_competition()
    test_sandbox_helpers()
    print("\n[ALL PASS] target_sniping refactor: 5/5 smoke tests passed")
