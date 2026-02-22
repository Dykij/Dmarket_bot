#!/usr/bin/env python3
"""Script to find long functions in Python codebase.

Part of Phase 2 refactoring initiative.
Identifies functions exceeding line count threshold for refactoring.

Usage:
    python scripts/find_long_functions.py --threshold 50
    python scripts/find_long_functions.py --threshold 50 --path src/dmarket
"""

import argparse
import ast
import operator
import sys
from pathlib import Path
from typing import NamedTuple


class FunctionInfo(NamedTuple):
    """Information about a function."""

    name: str
    file_path: str
    line_start: int
    line_end: int
    line_count: int
    is_async: bool


class LongFunctionFinder(ast.NodeVisitor):
    """AST visitor to find long functions."""

    def __init__(self, file_path: str, threshold: int = 50):
        """Initialize finder.

        Args:
            file_path: Path to the Python file being analyzed
            threshold: Maximum allowed lines per function
        """
        self.file_path = file_path
        self.threshold = threshold
        self.long_functions: list[FunctionInfo] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """Visit function definition."""
        self._check_function(node, is_async=False)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        """Visit async function definition."""
        self._check_function(node, is_async=True)
        self.generic_visit(node)

    def _check_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef, is_async: bool) -> None:
        """Check if function exceeds line threshold.

        Args:
            node: AST node representing the function
            is_async: Whether this is an async function
        """
        line_start = node.lineno
        line_end = node.end_lineno or line_start
        line_count = line_end - line_start + 1

        if line_count > self.threshold:
            func_info = FunctionInfo(
                name=node.name,
                file_path=self.file_path,
                line_start=line_start,
                line_end=line_end,
                line_count=line_count,
                is_async=is_async,
            )
            self.long_functions.append(func_info)


def find_long_functions_in_file(file_path: Path, threshold: int) -> list[FunctionInfo]:
    """Find long functions in a single file.

    Args:
        file_path: Path to Python file
        threshold: Maximum allowed lines

    Returns:
        List of function information for functions exceeding threshold
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        tree = ast.parse(content, filename=str(file_path))

        finder = LongFunctionFinder(str(file_path), threshold)
        finder.visit(tree)

        return finder.long_functions
    except SyntaxError as e:
        print(f"Warning: Syntax error in {file_path}: {e}", file=sys.stderr)
        return []
    except Exception as e:
        print(f"Warning: Error processing {file_path}: {e}", file=sys.stderr)
        return []


def find_long_functions_in_directory(directory: Path, threshold: int) -> list[FunctionInfo]:
    """Find long functions in all Python files in directory.

    Args:
        directory: Root directory to search
        threshold: Maximum allowed lines

    Returns:
        List of all long functions found
    """
    all_functions: list[FunctionInfo] = []

    # Find all Python files
    python_files = directory.rglob("*.py")

    for file_path in python_files:
        # Skip test files for now (they can be longer)
        if "test_" in file_path.name or file_path.parent.name == "tests":
            continue

        long_functions = find_long_functions_in_file(file_path, threshold)
        all_functions.extend(long_functions)

    return all_functions


def print_results(functions: list[FunctionInfo], threshold: int) -> None:
    """Print results in a formatted way.

    Args:
        functions: List of long functions found
        threshold: Threshold used for detection
    """
    if not functions:
        print(f"OK: No functions longer than {threshold} lines found!")
        return

    # Sort by line count (longest first)
    functions.sort(key=lambda f: f.line_count, reverse=True)

    print(f"\nFound {len(functions)} functions exceeding {threshold} lines:\n")
    print("=" * 80)

    for func in functions:
        async_marker = "async " if func.is_async else ""

        print(f"\nFile: {func.file_path}")
        print(f"   {async_marker}def {func.name}() - {func.line_count} lines")
        print(f"   Lines {func.line_start}-{func.line_end}")
        print(f"   WARNING: Exceeds threshold by {func.line_count - threshold} lines")

    print("\n" + "=" * 80)
    print("\nSummary:")
    print(f"   Total functions: {len(functions)}")
    print(f"   Average lines: {sum(f.line_count for f in functions) // len(functions)}")
    print(f"   Longest: {functions[0].name} ({functions[0].line_count} lines)")

    # Files with most violations
    files_count: dict[str, int] = {}
    for func in functions:
        files_count[func.file_path] = files_count.get(func.file_path, 0) + 1

    top_files = sorted(files_count.items(), key=operator.itemgetter(1), reverse=True)[:5]

    print("\nFiles needing most refactoring:")
    for file_path, count in top_files:
        print(f"   {Path(file_path).name}: {count} functions")


def main() -> int:
    """MAlgon entry point.

    Returns:
        Exit code (0 = success, 1 = violations found)
    """
    parser = argparse.ArgumentParser(
        description="Find functions exceeding line count threshold (Phase 2)"
    )
    parser.add_argument(
        "--threshold", type=int, default=50, help="Maximum allowed lines per function (default: 50)"
    )
    parser.add_argument("--path", type=str, default="src", help="Path to analyze (default: src)")
    parser.add_argument(
        "--fail", action="store_true", help="Exit with error code if violations found"
    )

    args = parser.parse_args()

    # Validate path
    search_path = Path(args.path)
    if not search_path.exists():
        print(f"Error: Path '{args.path}' does not exist", file=sys.stderr)
        return 1

    print(f"Scanning {search_path} for functions > {args.threshold} lines...\n")

    # Find long functions
    if search_path.is_file():
        long_functions = find_long_functions_in_file(search_path, args.threshold)
    else:
        long_functions = find_long_functions_in_directory(search_path, args.threshold)

    # Print results
    print_results(long_functions, args.threshold)

    # Return appropriate exit code
    if args.fail and long_functions:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
