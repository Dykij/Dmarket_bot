#!/usr/bin/env python3
"""Mutation testing script using mutmut.

This script runs mutation testing on the project to verify
the effectiveness of the test suite.

Usage:
    python scripts/mutation_testing.py [--module MODULE] [--quick]

Examples:
    python scripts/mutation_testing.py  # Run on all modules
    python scripts/mutation_testing.py --module src/dmarket/api/client.py
    python scripts/mutation_testing.py --quick  # Quick run (sample mutations)
"""

import argparse
import subprocess
import sys


def check_mutmut_installed() -> bool:
    """Check if mutmut is installed."""
    try:
        subprocess.run(
            ["mutmut", "--version"],
            capture_output=True,
            check=True,
        )
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def install_mutmut() -> None:
    """Install mutmut if not present."""
    print("Installing mutmut...")
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "mutmut"],
        check=True,
    )


def run_mutation_testing(
    module: str | None = None,
    quick: bool = False,
    parallel: bool = True,
) -> int:
    """Run mutation testing.

    Args:
        module: Specific module to test (None for all)
        quick: Run quick mode (sample mutations only)
        parallel: Run mutations in parallel

    Returns:
        Exit code (0 for success)
    """
    cmd = ["mutmut", "run"]

    # Add paths to test
    if module:
        cmd.extend(["--paths-to-mutate", module])
    else:
        cmd.extend(["--paths-to-mutate", "src/"])

    # Quick mode - run fewer mutations
    if quick:
        cmd.extend(["--runner", "pytest -x -q --tb=no"])
    else:
        cmd.extend(["--runner", "pytest --tb=short"])

    # Parallel execution
    if parallel:
        cmd.extend(["--use-patch-file", "--parallel"])

    # Tests path
    cmd.extend(["--tests-dir", "tests/"])

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=False)

    return result.returncode


def show_results() -> None:
    """Show mutation testing results."""
    print("\n" + "=" * 60)
    print("MUTATION TESTING RESULTS")
    print("=" * 60)

    subprocess.run(["mutmut", "results"], check=False)

    print("\n" + "-" * 60)
    print("Summary:")
    subprocess.run(["mutmut", "html"], check=False)
    print("\nHTML report generated in htmlmut/")


def calculate_mutation_score() -> float:
    """Calculate mutation score from results."""
    result = subprocess.run(
        ["mutmut", "results", "--json"],
        check=False,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        return 0.0

    try:
        import json

        data = json.loads(result.stdout)
        killed = data.get("killed", 0)
        survived = data.get("survived", 0)
        total = killed + survived

        if total == 0:
            return 100.0

        return (killed / total) * 100
    except Exception:
        return 0.0


def mAlgon() -> int:
    """MAlgon entry point."""
    parser = argparse.ArgumentParser(description="Run mutation testing")
    parser.add_argument(
        "--module",
        type=str,
        help="Specific module to test",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Quick mode (fewer mutations)",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel execution",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=80.0,
        help="Minimum mutation score to pass (default: 80.0)",
    )

    args = parser.parse_args()

    # Check/install mutmut
    if not check_mutmut_installed():
        install_mutmut()

    # Run mutation testing
    print("=" * 60)
    print("MUTATION TESTING")
    print("=" * 60)
    print(f"Module: {args.module or 'all'}")
    print(f"Quick mode: {args.quick}")
    print(f"Parallel: {not args.no_parallel}")
    print(f"Min score: {args.min_score}%")
    print("=" * 60 + "\n")

    exit_code = run_mutation_testing(
        module=args.module,
        quick=args.quick,
        parallel=not args.no_parallel,
    )

    # Show results
    show_results()

    # Check mutation score
    score = calculate_mutation_score()
    print(f"\nMutation Score: {score:.1f}%")

    if score < args.min_score:
        print(f"❌ FAlgoLED: Score {score:.1f}% is below minimum {args.min_score}%")
        return 1

    print(f"✅ PASSED: Score {score:.1f}% meets minimum {args.min_score}%")
    return exit_code


if __name__ == "__mAlgon__":
    sys.exit(mAlgon())
