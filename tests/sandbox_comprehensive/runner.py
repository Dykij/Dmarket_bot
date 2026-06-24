"""Orchestrator for the comprehensive sandbox test suite."""

from __future__ import annotations

import asyncio
import sys

from tests.sandbox_comprehensive.common import SandboxMetrics, log
from tests.sandbox_comprehensive.test_local import run_local_tests
from tests.sandbox_comprehensive.test_pipeline import run_pipeline_test
from tests.sandbox_comprehensive.test_live import run_live_cycle


async def main() -> int:
    """Run all sandbox phases and print a combined report."""
    log("=" * 70)
    log("  COMPREHENSIVE SANDBOX v14.8")
    log("  Phases: local instruments → pipeline → 10-min live cycle")
    log("=" * 70)

    metrics = SandboxMetrics()

    # Phase 1: local smoke tests (no API)
    run_local_tests(metrics)

    # Phase 2: filter + cross-market pipeline (live API, read-only)
    await run_pipeline_test(metrics)

    # Phase 3: 10-minute live polling cycle
    await run_live_cycle(metrics, duration_seconds=600, interval_seconds=30)

    metrics.report()

    if metrics.local_tests_failed > 0 or not metrics.dmarket_connected:
        log("\n  RESULT: FAIL — local tests failed or DMarket not reachable")
        return 1

    if metrics.instant_candidates == 0 and metrics.cross_market_targets == 0 and metrics.live_candidates == 0:
        log("\n  RESULT: NO OPPORTUNITIES — market is currently quiet for the configured thresholds")
        return 2

    log("\n  RESULT: PASS — bot finds candidates/targets under current market conditions")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        log("\n  Interrupted by user")
        sys.exit(130)
