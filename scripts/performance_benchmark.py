#!/usr/bin/env python3
"""Performance benchmark script for tests.

This script measures test execution time and identifies slow tests
that could benefit from optimization.

Usage:
    python scripts/performance_benchmark.py
    python scripts/performance_benchmark.py --threshold 1.0  # Tests taking >1s
    python scripts/performance_benchmark.py --output report.json

Examples:
    python scripts/performance_benchmark.py --top 20
    python scripts/performance_benchmark.py --module tests/dmarket/
"""

import argparse
import json
import operator
import subprocess
import sys
from datetime import datetime


def run_pytest_with_timing(
    test_path: str = "tests/",
    threshold: float = 0.5,
) -> dict:
    """Run pytest and collect timing information.

    Args:
        test_path: Path to tests
        threshold: Minimum duration to report (seconds)

    Returns:
        Dictionary with timing results
    """
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        test_path,
        "--durations=0",  # Show all durations
        "--durations-min=0.01",  # Minimum duration to show
        "-q",  # Quiet mode
        "--no-cov",  # Disable coverage for speed
        "--tb=no",  # No tracebacks
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)

    # Parse durations from output
    lines = result.stdout.split("\n")
    durations = []

    in_durations = False
    for line in lines:
        if "slowest" in line.lower() or "durations" in line.lower():
            in_durations = True
            continue

        if in_durations and line.strip():
            # Parse lines like "0.15s call tests/test_something.py::test_name"
            parts = line.strip().split()
            if len(parts) >= 3 and parts[0].endswith("s"):
                try:
                    duration = float(parts[0][:-1])
                    phase = parts[1]
                    test_name = parts[2]
                    if duration >= threshold:
                        durations.append({
                            "duration": duration,
                            "phase": phase,
                            "test": test_name,
                        })
                except ValueError:
                    continue

    # Sort by duration (slowest first)
    durations.sort(key=operator.itemgetter("duration"), reverse=True)

    return {
        "timestamp": datetime.now().isoformat(),
        "test_path": test_path,
        "threshold": threshold,
        "total_tests": len(durations),
        "durations": durations,
        "total_time": sum(d["duration"] for d in durations),
    }


def analyze_results(results: dict, top: int = 10) -> None:
    """Analyze and display benchmark results.

    Args:
        results: Results from run_pytest_with_timing
        top: Number of slowest tests to show
    """
    print("\n" + "=" * 70)
    print("PERFORMANCE BENCHMARK RESULTS")
    print("=" * 70)
    print(f"Timestamp: {results['timestamp']}")
    print(f"Test path: {results['test_path']}")
    print(f"Threshold: {results['threshold']}s")
    print(f"Tests above threshold: {results['total_tests']}")
    print(f"Total time: {results['total_time']:.2f}s")
    print("=" * 70)

    durations = results["durations"]

    if not durations:
        print("\nNo tests exceeded the threshold.")
        return

    print(f"\n[CHART] TOP {top} SLOWEST TESTS")
    print("-" * 70)
    print(f"{'Duration':>10} {'Phase':>8} Test")
    print("-" * 70)

    for item in durations[:top]:
        duration_str = f"{item['duration']:.2f}s"
        print(f"{duration_str:>10} {item['phase']:>8} {item['test']}")

    # Group by module
    print("\n[PACKAGE] SLOWEST MODULES")
    print("-" * 70)

    module_times: dict[str, float] = {}
    for item in durations:
        # Extract module from test path
        test_path = item["test"]
        module = test_path.split("::")[0] if "::" in test_path else test_path
        module_times[module] = module_times.get(module, 0) + item["duration"]

    sorted_modules = sorted(module_times.items(), key=operator.itemgetter(1), reverse=True)

    for module, total in sorted_modules[:10]:
        print(f"{total:>10.2f}s {module}")

    # Recommendations
    print("\n[TIP] RECOMMENDATIONS")
    print("-" * 70)

    slow_tests = [d for d in durations if d["duration"] > 2.0]
    if slow_tests:
        print(f"[!] {len(slow_tests)} tests take more than 2s each")
        print("   Consider:")
        print("   - Using mocks instead of real I/O")
        print("   - Reducing test data size")
        print("   - Parallelizing with pytest-xdist")

    integration_tests = [d for d in durations if "integration" in d["test"].lower()]
    if integration_tests:
        print(f"\n[i] {len(integration_tests)} integration tests detected")
        print("   Run separately with: pytest -m integration")

    if results["total_time"] > 120:
        print("\n[CLOCK] Total time exceeds 2 minutes")
        print("   Consider using pytest-xdist for parallel execution:")
        print("   pytest -n auto tests/")


def save_results(results: dict, output_path: str) -> None:
    """Save results to JSON file.

    Args:
        results: Results dictionary
        output_path: Output file path
    """
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"\n📄 Results saved to: {output_path}")


def compare_with_baseline(results: dict, baseline_path: str) -> None:
    """Compare current results with baseline.

    Args:
        results: Current results
        baseline_path: Path to baseline JSON file
    """
    try:
        with open(baseline_path, encoding="utf-8") as f:
            baseline = json.load(f)
    except FileNotFoundError:
        print(f"\n⚠️  Baseline not found: {baseline_path}")
        return

    print("\n📈 COMPARISON WITH BASELINE")
    print("-" * 70)

    current_time = results["total_time"]
    baseline_time = baseline["total_time"]
    diff = current_time - baseline_time
    percent = (diff / baseline_time * 100) if baseline_time > 0 else 0

    if diff > 0:
        print(f"⚠️  Total time increased by {diff:.2f}s ({percent:+.1f}%)")
    else:
        print(f"✅ Total time decreased by {abs(diff):.2f}s ({percent:.1f}%)")

    print(f"   Baseline: {baseline_time:.2f}s")
    print(f"   Current:  {current_time:.2f}s")


def main() -> int:
    """MAlgon entry point."""
    parser = argparse.ArgumentParser(description="Test performance benchmarks")
    parser.add_argument(
        "--module",
        type=str,
        default="tests/",
        help="Test path to benchmark (default: tests/)",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.1,
        help="Minimum duration threshold in seconds (default: 0.1)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Number of slowest tests to show (default: 20)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Save results to JSON file",
    )
    parser.add_argument(
        "--baseline",
        type=str,
        help="Compare with baseline JSON file",
    )

    args = parser.parse_args()

    print("=" * 70)
    print("RUNNING PERFORMANCE BENCHMARKS")
    print("=" * 70)

    results = run_pytest_with_timing(
        test_path=args.module,
        threshold=args.threshold,
    )

    analyze_results(results, top=args.top)

    if args.output:
        save_results(results, args.output)

    if args.baseline:
        compare_with_baseline(results, args.baseline)

    # Return 1 if tests are too slow
    if results["total_time"] > 300:  # 5 minutes
        print("\n❌ FAlgoLED: Test suite takes more than 5 minutes")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
