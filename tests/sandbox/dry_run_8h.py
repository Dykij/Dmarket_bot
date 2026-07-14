"""
dry_run_8h.py — 8-hour dry run stability test.

Tests the bot pipeline for 8 hours with mock data, measuring:
- Memory stability
- Cycle throughput
- Error recovery
- DB performance

Usage: python tests/sandbox/dry_run_8h.py
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import resource
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

os.environ["DRY_RUN"] = "true"

from src.utils.logging_setup import configure_logging
configure_logging(component="dry_run", level=logging.WARNING, log_file="logs/dry_run_8h.log")
logger = logging.getLogger("DryRun")
logger.setLevel(logging.INFO)

HOUR = 3600
DURATION = 8 * HOUR
INTERVAL = 15


def mem_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


async def cycle(n):
    """Simulate a trading cycle with DB operations."""
    from src.db.price_history import price_db
    from src.config import Config

    # DB write
    price_db.save_state(f"cycle_{n % 100}", str(n))

    # DB read
    price_db.get_state(f"cycle_{n % 100}")

    # Price history write
    price_db.record_price("AK-47 | Redline (FT)", 13.0 + (n % 10) * 0.1, "dry_run")

    # Price history read
    price_db.get_latest_price("AK-47 | Redline (FT)")

    # Inventory check
    price_db.get_virtual_inventory(status="idle")


async def main():
    start = time.time()
    end = start + DURATION
    n = 0
    ok = 0
    fail = 0
    errors = []
    peak_mem = 0
    snapshots = []
    last_snap = start

    print(f"DRY RUN: {DURATION//3600}h, interval={INTERVAL}s", flush=True)
    print(f"Estimated cycles: {DURATION // INTERVAL}", flush=True)
    print(f"Start: {time.strftime('%H:%M:%S')}", flush=True)
    print("-" * 50, flush=True)

    while time.time() < end:
        n += 1
        t0 = time.time()
        try:
            await cycle(n)
            ok += 1
        except Exception as e:
            fail += 1
            errors.append(f"{type(e).__name__}: {e}")
        dt = time.time() - t0

        m = mem_mb()
        peak_mem = max(peak_mem, m)

        if n % 20 == 0:
            elapsed = time.time() - start
            rate = n / (elapsed / 60)
            print(f"  cycle={n} ok={ok} fail={fail} mem={m:.0f}MB rate={rate:.1f}/min", flush=True)

        if time.time() - last_snap >= HOUR:
            snapshots.append({
                "hour": len(snapshots) + 1,
                "cycles": n, "ok": ok, "fail": fail,
                "mem_mb": round(m, 1),
                "rate": round(n / ((time.time() - start) / 60), 1),
            })
            last_snap = time.time()

        await asyncio.sleep(INTERVAL)

    # Report
    duration = time.time() - start
    report = {
        "duration_h": round(duration / 3600, 2),
        "cycles": n, "ok": ok, "fail": fail,
        "success_pct": round(ok / max(n, 1) * 100, 2),
        "rate_per_min": round(n / (duration / 60), 1),
        "peak_mem_mb": round(peak_mem, 1),
        "errors_unique": list(set(errors))[:10],
        "hourly": snapshots,
        "verdict": {
            "stable": fail == 0 or (fail / max(n, 1)) < 0.01,
            "no_leak": peak_mem < 500,
            "ready": fail < 5 and peak_mem < 500,
        },
    }

    Path("logs/dry_run_8h_report.json").write_text(json.dumps(report, indent=2))
    print("\n" + "=" * 50)
    print("REPORT")
    print("=" * 50)
    print(f"Duration:  {report['duration_h']}h")
    print(f"Cycles:    {n} ({report['success_pct']}% ok)")
    print(f"Rate:      {report['rate_per_min']}/min")
    print(f"Peak mem:  {report['peak_mem_mb']}MB")
    print(f"Errors:    {fail}")
    print(f"Stable:    {report['verdict']['stable']}")
    print(f"No leak:   {report['verdict']['no_leak']}")
    print(f"READY:     {report['verdict']['ready']}")
    print("=" * 50)
    print(f"Report: logs/dry_run_8h_report.json")


if __name__ == "__main__":
    asyncio.run(main())
