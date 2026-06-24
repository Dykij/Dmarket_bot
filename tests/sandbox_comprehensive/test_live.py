"""10-minute live polling cycle against real DMarket aggregated prices."""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, Dict

from src.config import Config
from src.api.dmarket_api_client import DMarketAPIClient

from tests.sandbox_comprehensive.common import log, log_err, log_info, log_ok, with_timeout

if TYPE_CHECKING:
    from tests.sandbox_comprehensive.common import SandboxMetrics


async def _run_single_cycle(
    dmarket: DMarketAPIClient,
    metrics: "SandboxMetrics",
    prev_agg: Dict[str, Any],
) -> Dict[str, Any]:
    """Run one polling cycle: fetch aggregated prices and count candidates."""
    t0 = time.time()
    metrics.cycles += 1
    try:
        agg = await with_timeout(20, dmarket.get_aggregated_prices(Config.GAME_ID), f"cycle {metrics.cycles}")
    except Exception as e:
        log_err(f"Cycle {metrics.cycles}: {e}")
        metrics.live_errors += 1
        metrics.cycle_times.append(time.time() - t0)
        return prev_agg

    if not agg:
        metrics.cycle_times.append(time.time() - t0)
        return prev_agg

    cycle_candidates = 0
    for title, a in agg.items():
        bid = a.get("best_bid", 0) or 0
        ask = a.get("best_ask", 0) or 0
        ac = a.get("ask_count", 0) or 0
        bc = a.get("bid_count", 0) or 0
        if bid <= 0 or ask <= 0 or ac < 1 or bc < 1:
            continue
        spread_pct = (bid - ask) / ask * 100
        # Relaxed threshold matching current config intent
        if spread_pct < Config.MIN_SPREAD_PCT:
            continue
        cycle_candidates += 1

    metrics.live_candidates += cycle_candidates
    metrics.cycle_times.append(time.time() - t0)
    log_info(
        f"Cycle {metrics.cycles:3d} | {len(agg):4d} titles | "
        f"{cycle_candidates:3d} candidates | {time.time() - t0:4.1f}s"
    )
    return agg


async def run_live_cycle(
    metrics: "SandboxMetrics",
    duration_seconds: int = 600,
    interval_seconds: int = 30,
) -> None:
    """Run live polling loop for the requested duration."""
    log("\n" + "=" * 70)
    log(f"  LIVE CYCLE — {duration_seconds // 60} minutes @ {interval_seconds}s interval")
    log("=" * 70)

    dmarket = DMarketAPIClient(Config.PUBLIC_KEY, Config.SECRET_KEY)
    try:
        balance = await with_timeout(10, dmarket.get_real_balance(), "balance")
        if balance is not None:
            metrics.balance = balance
            log_ok(f"Balance: ${balance:.2f}")
        else:
            log_err("Balance fetch failed")
            return

        start = time.time()
        max_cycles = duration_seconds // interval_seconds
        prev: Dict[str, Any] = {}
        for i in range(max_cycles):
            prev = await _run_single_cycle(dmarket, metrics, prev)
            elapsed = time.time() - start
            if elapsed >= duration_seconds:
                break
            remaining = duration_seconds - elapsed
            sleep_for = min(interval_seconds, remaining)
            if sleep_for > 0:
                await asyncio.sleep(sleep_for)

        log_ok(f"Live cycle complete: {metrics.cycles} cycles, {metrics.live_candidates} total candidates")
    finally:
        await dmarket.close()
