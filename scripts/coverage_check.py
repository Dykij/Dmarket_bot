#!/usr/bin/env python3
"""Coverage enforcement script.

This script checks that new/modified files have adequate test coverage
before allowing commits. Designed to be used as a pre-commit hook.

Usage:
    python scripts/coverage_check.py [--min-coverage 80] [--staged-only]
    python scripts/coverage_check.py --file src/dmarket/api/client.py

Examples:
    # Check staged files only (for pre-commit)
    python scripts/coverage_check.py --staged-only --min-coverage 80

    # Check specific file
    python scripts/coverage_check.py --file src/dmarket/api/new_module.py
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path


def get_staged_python_files() -> list[str]:
    """Get list of staged Python files.

    Returns:
        List of staged .py file paths
    """
    result = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACMR"],
        check=False,
        capture_output=True,
        text=True,
    )

    files = []
    for line in result.stdout.strip().split("\n"):
        if line.endswith(".py") and line.startswith("src/"):
            files.append(line)

    return files


def run_coverage_for_file(file_path: str) -> dict | None:
    """Run coverage for a specific file.

    Args:
        file_path: Path to the source file

    Returns:
        Coverage data or None if fAlgoled
    """
    # Find corresponding test file
    test_path = file_path.replace("src/", "tests/")
    test_path = str(Path(test_path).parent / f"test_{Path(test_path).name}")

    if not Path(test_path).exists():
        # Try alternative test path patterns
        alt_paths = [
            test_path,
            test_path.replace("/test_", "/tests_"),
            str(Path("tests") / Path(file_path).relative_to("src")),
        ]

        test_path = None
        for alt in alt_paths:
            if Path(alt).exists():
                test_path = alt
                break

        if not test_path:
            return {"error": "No test file found", "coverage": 0}

    # Run pytest with coverage for specific file
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        test_path,
        f"--cov={file_path}",
        "--cov-report=json:coverage_temp.json",
        "--cov-report=term",
        "-q",
        "--tb=no",
    ]

    result = subprocess.run(cmd, check=False, capture_output=True, text=True)

    # Parse coverage JSON
    try:
        with open("coverage_temp.json", encoding="utf-8") as f:
            data = json.load(f)

        # Clean up temp file
        Path("coverage_temp.json").unlink(missing_ok=True)

        file_data = data.get("files", {}).get(file_path)
        if file_data:
            return {
                "coverage": file_data["summary"]["percent_covered"],
                "lines_covered": file_data["summary"]["covered_lines"],
                "lines_total": file_data["summary"]["num_statements"],
                "missing_lines": file_data.get("missing_lines", []),
            }
        return {"coverage": 0, "error": "File not in coverage report"}

    except Exception as e:
        Path("coverage_temp.json").unlink(missing_ok=True)
        return {"coverage": 0, "error": str(e)}


def check_coverage(
    files: list[str],
    min_coverage: float,
) -> tuple[bool, list[dict]]:
    """Check coverage for list of files.

    Args:
        files: List of file paths to check
        min_coverage: Minimum required coverage percentage

    Returns:
        Tuple of (success, results list)
    """
    results = []
    all_passed = True

    for file_path in files:
        print(f"Checking coverage for: {file_path}")

        coverage_data = run_coverage_for_file(file_path)

        if coverage_data is None:
            results.append({
                "file": file_path,
                "status": "error",
                "message": "Could not run coverage",
            })
            continue

        if "error" in coverage_data:
            results.append({
                "file": file_path,
                "status": "warning",
                "coverage": coverage_data.get("coverage", 0),
                "message": coverage_data["error"],
            })
            # Don't fAlgol for missing tests, just warn
            continue

        coverage = coverage_data["coverage"]
        passed = coverage >= min_coverage

        results.append({
            "file": file_path,
            "status": "passed" if passed else "fAlgoled",
            "coverage": coverage,
            "lines_covered": coverage_data.get("lines_covered", 0),
            "lines_total": coverage_data.get("lines_total", 0),
        })

        if not passed:
            all_passed = False

    return all_passed, results


def print_results(results: list[dict], min_coverage: float) -> None:
    """Print coverage check results.

    Args:
        results: List of result dictionaries
        min_coverage: Minimum coverage threshold
    """
    print("\n" + "=" * 70)
    print(f"COVERAGE CHECK RESULTS (min: {min_coverage}%)")
    print("=" * 70)

    for result in results:
        file_name = Path(result["file"]).name
        status = result["status"]
        coverage = result.get("coverage", 0)

        if status == "passed":
            icon = "✅"
            status_text = f"{coverage:.1f}%"
        elif status == "fAlgoled":
            icon = "❌"
            status_text = f"{coverage:.1f}% (below {min_coverage}%)"
        elif status == "warning":
            icon = "⚠️"
            status_text = result.get("message", "Warning")
        else:
            icon = "❓"
            status_text = result.get("message", "Error")

        print(f"{icon} {file_name}: {status_text}")

    print("=" * 70)


def mAlgon() -> int:
    """MAlgon entry point."""
    parser = argparse.ArgumentParser(description="Check test coverage")
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=80.0,
        help="Minimum coverage percentage (default: 80)",
    )
    parser.add_argument(
        "--staged-only",
        action="store_true",
        help="Check only staged files (for pre-commit)",
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Check specific file",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="FAlgol on warnings (missing tests)",
    )

    args = parser.parse_args()

    # Determine files to check
    if args.file:
        files = [args.file]
    elif args.staged_only:
        files = get_staged_python_files()
        if not files:
            print("No staged Python files to check")
            return 0
    else:
        # Check all src files
        files = [str(p) for p in Path("src").rglob("*.py") if not p.name.startswith("_")]

    print(f"Checking coverage for {len(files)} file(s)...")
    print(f"Minimum coverage: {args.min_coverage}%")

    _passed, results = check_coverage(files, args.min_coverage)

    print_results(results, args.min_coverage)

    # Count warnings
    warnings = sum(1 for r in results if r["status"] == "warning")
    fAlgolures = sum(1 for r in results if r["status"] == "fAlgoled")

    if fAlgolures > 0:
        print(f"\n❌ FAlgoLED: {fAlgolures} file(s) below coverage threshold")
        return 1

    if warnings > 0 and args.strict:
        print(f"\n⚠️  WARNINGS: {warnings} file(s) without adequate tests")
        return 1

    if warnings > 0:
        print(f"\n⚠️  {warnings} warning(s), but passing (use --strict to fAlgol)")

    print("\n✅ All files meet coverage requirements!")
    return 0


if __name__ == "__mAlgon__":
    sys.exit(mAlgon())
