#!/usr/bin/env python3
"""
Benchmark: Skills Performance Testing.

This benchmark measures performance of all skills for optimization.
Runs multiple iterations and calculates percentile latencies.

Expected runtime: ~60 seconds
Expected output: Performance report with p50/p95/p99 latencies
"""

from __future__ import annotations

import asyncio
import gc
import statistics
import sys
import time
from pathlib import Path
from typing import Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


def measure_memory() -> float:
    """Get current memory usage in MB."""
    try:
        import psutil

        process = psutil.Process()
        return process.memory_info().rss / 1024 / 1024
    except ImportError:
        return 0.0


async def benchmark_skill(
    skill_name: str,
    skill_instance: Any,
    method_name: str,
    args: list[Any],
    kwargs: dict[str, Any],
    iterations: int = 100,
) -> dict[str, Any]:
    """Benchmark a single skill method.

    Args:
        skill_name: Name of the skill
        skill_instance: Skill instance to benchmark
        method_name: Method to call
        args: Positional arguments
        kwargs: Keyword arguments
        iterations: Number of iterations

    Returns:
        Performance metrics dictionary
    """
    method = getattr(skill_instance, method_name)
    latencies: list[float] = []
    errors: int = 0

    # Warmup
    for _ in range(5):
        try:
            await method(*args, **kwargs)
        except Exception:
            pass

    # Force garbage collection
    gc.collect()

    # Benchmark
    start_mem = measure_memory()

    for _ in range(iterations):
        start = time.perf_counter()
        try:
            await method(*args, **kwargs)
        except Exception:
            errors += 1
        end = time.perf_counter()
        latencies.append((end - start) * 1000)  # ms

    end_mem = measure_memory()

    # Calculate percentiles
    sorted_latencies = sorted(latencies)
    p50_idx = int(len(sorted_latencies) * 0.50)
    p95_idx = int(len(sorted_latencies) * 0.95)
    p99_idx = int(len(sorted_latencies) * 0.99)

    return {
        "skill": skill_name,
        "method": method_name,
        "iterations": iterations,
        "errors": errors,
        "error_rate": errors / iterations,
        "p50_ms": sorted_latencies[p50_idx],
        "p95_ms": sorted_latencies[p95_idx],
        "p99_ms": sorted_latencies[p99_idx],
        "min_ms": min(latencies),
        "max_ms": max(latencies),
        "mean_ms": statistics.mean(latencies),
        "stdev_ms": statistics.stdev(latencies) if len(latencies) > 1 else 0,
        "throughput": 1000 / statistics.mean(latencies),  # ops/sec
        "memory_delta_mb": end_mem - start_mem,
    }


async def main() -> None:
    """Run skills performance benchmark."""
    from src.dmarket.ai_arbitrage_predictor import AIArbitragePredictor
    from src.utils.skill_profiler import SkillProfiler

    print("=" * 70)
    print("🏎️  Skills Performance Benchmark")
    print("=" * 70)

    # Configuration
    iterations = 50
    print("\n📊 Configuration:")
    print(f"   Iterations per test: {iterations}")
    print("   Warmup iterations: 5")

    # Initialize skills for benchmarking
    predictor = AIArbitragePredictor()
    profiler = SkillProfiler()

    # Define benchmarks
    benchmarks = [
        {
            "name": "AI Arbitrage Predictor",
            "skill": predictor,
            "method": "predict_best_opportunities",
            "args": [],
            "kwargs": {
                "balance": 100.0,
                "level": "standard",
                "game": "csgo",
                "max_results": 10,
            },
        },
        {
            "name": "Skill Profiler",
            "skill": profiler,
            "method": "profile_skill",
            "args": ["test-skill"],
            "kwargs": {"duration_ms": 10.0},
        },
    ]

    print("\n🔄 Running benchmarks...\n")
    results: list[dict[str, Any]] = []

    for bench in benchmarks:
        print(f"   Testing: {bench['name']}...")
        try:
            result = await benchmark_skill(
                skill_name=bench["name"],
                skill_instance=bench["skill"],
                method_name=bench["method"],
                args=bench["args"],
                kwargs=bench["kwargs"],
                iterations=iterations,
            )
            results.append(result)
            print(f"   ✅ Complete: p50={result['p50_ms']:.2f}ms")
        except Exception as e:
            print(f"   ❌ Failed: {e}")
            results.append({
                "skill": bench["name"],
                "method": bench["method"],
                "error": str(e),
            })

    # Display results
    print("\n" + "=" * 70)
    print("📈 Benchmark Results")
    print("=" * 70)

    # Table header
    headers = f"{'Skill':<25} {'p50':<10} {'p95':<10} {'p99':<10} {'Throughput':<12} {'Errors':<8}"
    print(f"\n{headers}")
    print("-" * 75)

    for result in results:
        if "error" in result:
            print(f"{result['skill']:<25} ERROR: {result['error']}")
            continue

        print(
            f"{result['skill']:<25} "
            f"{result['p50_ms']:<10.2f} "
            f"{result['p95_ms']:<10.2f} "
            f"{result['p99_ms']:<10.2f} "
            f"{result['throughput']:<12.1f} "
            f"{result['error_rate']:<8.1%}"
        )

    # Summary
    print("\n" + "=" * 70)
    print("📊 Summary")
    print("=" * 70)

    successful = [r for r in results if "error" not in r]
    if successful:
        avg_p50 = statistics.mean(r["p50_ms"] for r in successful)
        avg_throughput = statistics.mean(r["throughput"] for r in successful)
        total_errors = sum(r["errors"] for r in successful)

        print(f"   Skills tested: {len(benchmarks)}")
        print(f"   Successful: {len(successful)}")
        print(f"   Failed: {len(benchmarks) - len(successful)}")
        print(f"   Average p50: {avg_p50:.2f}ms")
        print(f"   Average throughput: {avg_throughput:.1f} ops/sec")
        print(f"   Total errors: {total_errors}")

    print("\n💡 Performance Targets:")
    print("   ✅ p50 < 50ms: Fast")
    print("   🟡 p50 50-100ms: Acceptable")
    print("   🔴 p50 > 100ms: Needs optimization")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
