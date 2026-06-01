"""
Multi-Run Variance Test — runs v12.1 sandbox 5 times with different seeds
to show the realistic range of outcomes.
"""

import asyncio
import sys
sys.path.insert(0, "/tmp/opencode/Dmarket_bot")

import random
from scratch.sandbox_v12_1 import SandboxV12_1


async def run_single(seed: int) -> dict:
    """Run one simulation and return key metrics."""
    random.seed(seed)
    sandbox = SandboxV12_1()
    await sandbox.run_week()
    return {
        "seed": seed,
        "profit": sandbox.realized,
        "items_bought": sum(s.items_bought for s in sandbox.daily_stats),
        "items_sold": sum(s.items_sold for s in sandbox.daily_stats),
        "items_expired": sum(s.items_expired for s in sandbox.daily_stats),
        "win_rate": (sum(1 for it in sandbox.sold_items if it.profit > 0) /
                     max(1, len(sandbox.sold_items)) * 100),
        "fees": sandbox.total_fees,
        "final_cash": sandbox.cash,
        "final_locked": sandbox.locked,
        "final_equity": sandbox.total_equity,
    }


async def main():
    print("="*72)
    print("MULTI-RUN VARIANCE TEST — 5 different seeds, 7 days each")
    print("="*72)
    print()

    results = []
    for seed in [42, 123, 456, 789, 1024]:
        result = await run_single(seed)
        results.append(result)
        equity_change = result["final_equity"] - 44.00
        roi_pct = equity_change / 44.00 * 100
        print(
            f"Seed {seed:>5}: profit=${result['profit']:>+5.2f} | "
            f"bought={result['items_bought']:>2} | "
            f"sold={result['items_sold']:>2} | "
            f"expired={result['items_expired']:>2} | "
            f"win={result['win_rate']:>4.1f}% | "
            f"equity=${result['final_equity']:>5.2f} | "
            f"ROI={roi_pct:>+5.1f}%"
        )

    print()
    print("="*72)
    print("STATISTICAL SUMMARY (5 runs, 7 days each)")
    print("="*72)

    profits = [r["profit"] for r in results]
    equities = [r["final_equity"] for r in results]
    rois = [(r["final_equity"] - 44.00) / 44.00 * 100 for r in results]

    print(f"  Weekly profit:    min=${min(profits):+.2f}  max=${max(profits):+.2f}  avg=${sum(profits)/len(profits):+.2f}")
    print(f"  Final equity:     min=${min(equities):.2f}  max=${max(equities):.2f}  avg=${sum(equities)/len(equities):.2f}")
    print(f"  Weekly ROI:       min={min(rois):+.1f}%  max={max(rois):+.1f}%  avg={sum(rois)/len(rois):+.1f}%")

    avg_daily = sum(profits) / len(profits) / 7
    avg_monthly = avg_daily * 30
    avg_yearly = avg_daily * 365

    print()
    print("PROJECTIONS (based on average across 5 runs):")
    print(f"  Daily:    ${avg_daily:+.2f}")
    print(f"  Monthly:  ${avg_monthly:+.2f} ({(avg_monthly/44*100):+.1f}%)")
    print(f"  Yearly:   ${avg_yearly:+.2f} ({(avg_yearly/44*100):+.1f}%)")
    print("="*72)


if __name__ == "__main__":
    asyncio.run(main())
