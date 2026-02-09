#!/usr/bin/env python3
"""Fast debug script for GitHub Copilot / IDE integration.

This script runs linting, type checking, and tests with optimizations
to prevent hanging when used with GitHub Copilot or IDE integration.

Usage:
    python scripts/debug_fast.py          # Full fast debug
    python scripts/debug_fast.py --lint   # Only lint
    python scripts/debug_fast.py --types  # Only types
    python scripts/debug_fast.py --tests  # Only tests
    python scripts/debug_fast.py --all    # Full debug with more output
"""

import argparse
import subprocess  # noqa: S404
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

# Timeout for each step (seconds)
LINT_TIMEOUT = 30
TYPES_TIMEOUT = 60
TESTS_TIMEOUT = 120

# Max output lines per step
MAX_OUTPUT_LINES = 50


def run_command(
    cmd: list[str], timeout: int, max_lines: int = MAX_OUTPUT_LINES
) -> tuple[bool, str]:
    """Run command with timeout and output limiting."""
    try:
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=Path(__file__).parent.parent,
            check=False,
        )
        output = result.stdout + result.stderr
        lines = output.strip().split("\n")
        if len(lines) > max_lines:
            lines = [*lines[:max_lines], f"... ({len(lines) - max_lines} more lines)"]
        return result.returncode == 0, "\n".join(lines)
    except subprocess.TimeoutExpired:
        return False, f"TIMEOUT after {timeout} seconds"
    except Exception as e:
        return False, f"ERROR: {e}"


def run_lint() -> tuple[str, bool, str, float]:
    """Run ruff linting."""
    start = time.time()
    success, output = run_command(
        ["python", "-m", "ruff", "check", "src/", "--output-format=concise", "--exit-zero"],
        LINT_TIMEOUT,
    )
    elapsed = time.time() - start
    return "Lint", success, output, elapsed


def run_types() -> tuple[str, bool, str, float]:
    """Run mypy type checking."""
    start = time.time()
    success, output = run_command(
        [
            "python",
            "-m",
            "mypy",
            "src/",
            "--config-file=config/mypy-fast.ini",
            "--cache-dir=.mypy_cache",
        ],
        TYPES_TIMEOUT,
    )
    elapsed = time.time() - start
    return "Types", success, output, elapsed


def run_tests() -> tuple[str, bool, str, float]:
    """Run pytest with fast configuration."""
    start = time.time()
    success, output = run_command(
        [
            "python",
            "-m",
            "pytest",
            "tests/core/",
            "tests/unit/",
            "-c",
            "config/pytest-fast.ini",
            "-q",
            "--timeout=10",
            "--no-cov",
            "-x",
        ],
        TESTS_TIMEOUT,
        max_lines=100,
    )
    elapsed = time.time() - start
    return "Tests", success, output, elapsed


def print_result(name: str, success: bool, output: str, elapsed: float) -> None:
    """Print formatted result."""
    status = "✅" if success else "❌"
    print(f"\n{'=' * 60}")
    print(f"{status} {name} ({elapsed:.1f}s)")
    print("=" * 60)
    if output.strip():
        print(output)
    else:
        print("No output")


def main() -> int:
    parser = argparse.ArgumentParser(description="Fast debug for GitHub Copilot / IDE")
    parser.add_argument("--lint", action="store_true", help="Only run lint")
    parser.add_argument("--types", action="store_true", help="Only run type check")
    parser.add_argument("--tests", action="store_true", help="Only run tests")
    parser.add_argument("--all", action="store_true", help="Run all with full output")
    parser.add_argument("--parallel", action="store_true", help="Run lint and types in parallel")
    args = parser.parse_args()

    # If no specific flag, run all
    run_all = not (args.lint or args.types or args.tests)

    print("=" * 60)
    print("⚡ Fast Debug for GitHub Copilot / IDE")
    print("=" * 60)

    results = []
    total_start = time.time()

    if args.parallel and run_all:
        # Run lint and types in parallel, then tests
        print("\n🔄 Running lint and types in parallel...")
        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [
                executor.submit(run_lint),
                executor.submit(run_types),
            ]
            for future in as_completed(futures):
                results.append(future.result())

        # Print parallel results
        for name, success, output, elapsed in results:
            print_result(name, success, output, elapsed)

        # Run tests sequentially
        print("\n🧪 Running tests...")
        result = run_tests()
        results.append(result)
        print_result(*result)
    else:
        # Sequential execution
        if run_all or args.lint:
            print("\n🔍 Running lint...")
            result = run_lint()
            results.append(result)
            print_result(*result)

        if run_all or args.types:
            print("\n📝 Running type check...")
            result = run_types()
            results.append(result)
            print_result(*result)

        if run_all or args.tests:
            print("\n🧪 Running tests...")
            result = run_tests()
            results.append(result)
            print_result(*result)

    # Summary
    total_elapsed = time.time() - total_start
    all_success = all(r[1] for r in results)

    print("\n" + "=" * 60)
    print(f"{'✅ ALL PASSED' if all_success else '❌ SOME FAILED'} (Total: {total_elapsed:.1f}s)")
    print("=" * 60)

    for name, success, _, elapsed in results:
        status = "✅" if success else "❌"
        print(f"  {status} {name}: {elapsed:.1f}s")

    return 0 if all_success else 1


if __name__ == "__main__":
    sys.exit(main())
