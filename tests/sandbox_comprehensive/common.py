"""Common fixtures and helpers for the comprehensive sandbox suite."""

from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure project root is on path
BASE_DIR = str(Path(__file__).resolve().parent.parent.parent)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Sandbox must stay read-only
os.environ["DRY_RUN"] = "true"
os.environ.setdefault("ENCRYPTION_KEY", "test-key-for-sandbox-reads-only")

import logging

logging.basicConfig(level=logging.WARNING)

from src.config import Config
from src.api.dmarket_api_client import DMarketAPIClient
from src.api.oracle_factory import OracleFactory
from src.api.multi_source_oracle import MultiSourceOracle


def log(msg: str = "") -> None:
    """Print with flush — no buffering delays."""
    print(msg, flush=True)


def log_ok(msg: str) -> None:
    log(f"  ✅ {msg}")


def log_warn(msg: str) -> None:
    log(f"  ⚠️ {msg}")


def log_err(msg: str) -> None:
    log(f"  ❌ {msg}")


def log_info(msg: str) -> None:
    log(f"  ℹ️ {msg}")


async def with_timeout(seconds: float, coro, label: str) -> Any:
    """Run coro with timeout. Returns result or None on timeout/error."""
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        log_err(f"{label}: timed out after {seconds}s")
        return None
    except Exception as e:
        log_err(f"{label}: {e}")
        return None


@dataclass
class SandboxMetrics:
    """Shared metrics collected across all sandbox phases."""

    # Connectivity
    dmarket_connected: bool = False
    oracle_connected: bool = False
    balance: float = 0.0

    # Prices
    agg_titles: int = 0
    agg_with_bids: int = 0
    oracle_asks: int = 0
    oracle_bids: int = 0

    # Pipeline
    listings_fetched: int = 0
    instant_candidates: int = 0
    cross_market_targets: int = 0
    dmarket_underpriced: int = 0
    low_fee_candidates: int = 0
    filter_reasons: Dict[str, int] = field(default_factory=dict)

    # Live cycle
    cycles: int = 0
    live_candidates: int = 0
    live_errors: int = 0
    cycle_times: List[float] = field(default_factory=list)

    # Instruments
    local_tests_passed: int = 0
    local_tests_failed: int = 0

    def report(self) -> None:
        """Print final summary."""
        log("\n" + "=" * 70)
        log("  COMPREHENSIVE SANDBOX REPORT v14.8")
        log("=" * 70)
        log(f"  DMarket connected:    {self.dmarket_connected}")
        log(f"  Oracle connected:     {self.oracle_connected}")
        log(f"  Balance:              ${self.balance:.2f}")
        log(f"  Aggregated titles:    {self.agg_titles} ({self.agg_with_bids} with bids)")
        log(f"  Oracle snapshots:     {self.oracle_asks} asks, {self.oracle_bids} bids")
        log(f"  Listings fetched:     {self.listings_fetched}")
        log(f"  Instant candidates:   {self.instant_candidates}")
        log(f"  Cross-market targets: {self.cross_market_targets}")
        log(f"  DMarket underpriced:  {self.dmarket_underpriced}")
        log(f"  Low-fee candidates:   {self.low_fee_candidates}")
        log(f"  Live cycles:          {self.cycles}")
        log(f"  Live candidates:      {self.live_candidates}")
        log(f"  Live errors:          {self.live_errors}")
        if self.cycle_times:
            avg = sum(self.cycle_times) / len(self.cycle_times)
            log(f"  Avg cycle time:       {avg:.2f}s")
        log(f"  Local tests passed:   {self.local_tests_passed}")
        log(f"  Local tests failed:   {self.local_tests_failed}")
        if self.filter_reasons:
            log("  Filter reasons:")
            for reason, count in sorted(self.filter_reasons.items(), key=lambda x: -x[1]):
                log(f"    {reason}: {count}")
        log("=" * 70)


async def setup_clients() -> tuple[DMarketAPIClient, Optional[MultiSourceOracle]]:
    """Initialize DMarket + Oracle clients."""
    dmarket = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
    oracle = OracleFactory.get_oracle(Config.GAME_ID)
    return dmarket, oracle
