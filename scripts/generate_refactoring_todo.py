#!/usr/bin/env python3
"""Generate Phase 2 refactoring TODO list.

Creates a prioritized list of refactoring tasks based on function analysis.
Part of Phase 2 infrastructure improvements.

Usage:
    python scripts/generate_refactoring_todo.py
    python scripts/generate_refactoring_todo.py --output TODO_REFACTORING.md
"""

import argparse
import sys
from pathlib import Path
from typing import NamedTuple


class RefactoringTask(NamedTuple):
    """Refactoring task information."""

    priority: int  # 1=critical, 2=high, 3=medium, 4=low
    file_path: str
    function_name: str
    line_count: int
    estimated_hours: float
    complexity_score: int


def calculate_priority(line_count: int, file_path: str) -> int:
    """Calculate task priority based on metrics.

    Args:
        line_count: Function line count
        file_path: Path to the file

    Returns:
        Priority level (1-4)
    """
    # Critical modules (priority 1)
    critical_modules = [
        "dmarket_api.py",
        "arbitrage_scanner.py",
        "targets/manager.py",
    ]

    # High priority modules (priority 2)
    high_priority_modules = [
        "auto_seller.py",
        "portfolio_manager.py",
        "market_analysis.py",
    ]

    file_name = Path(file_path).name

    # Priority 1: Critical modules OR very long functions
    if any(mod in file_path for mod in critical_modules) or line_count > 200:
        return 1

    # Priority 2: High priority modules OR long functions
    if any(mod in file_path for mod in high_priority_modules) or line_count > 150:
        return 2

    # Priority 3: Medium length functions
    if line_count > 100:
        return 3

    # Priority 4: Shorter functions
    return 4


def estimate_hours(line_count: int) -> float:
    """Estimate refactoring hours.

    Args:
        line_count: Function line count

    Returns:
        Estimated hours
    """
    if line_count > 200:
        return 4.0
    if line_count > 150:
        return 3.0
    if line_count > 100:
        return 2.0
    if line_count > 75:
        return 1.5
    return 1.0


def calculate_complexity(line_count: int) -> int:
    """Calculate complexity score.

    Args:
        line_count: Function line count

    Returns:
        Complexity score (1-10)
    """
    # Simple linear mapping
    if line_count > 250:
        return 10
    if line_count > 200:
        return 9
    if line_count > 150:
        return 8
    if line_count > 120:
        return 7
    if line_count > 100:
        return 6
    if line_count > 80:
        return 5
    if line_count > 70:
        return 4
    if line_count > 60:
        return 3
    return 2


def generate_todo_list(output_file: str = "TODO_REFACTORING.md") -> None:
    """Generate refactoring TODO list.

    Args:
        output_file: Output markdown file path
    """
    # For now, manually create task list based on find_long_functions.py output
    # In future, can integrate with AST analysis

    tasks: list[RefactoringTask] = [
        # Priority 1: Critical (297-192 lines)
        RefactoringTask(1, "src/dmarket/dmarket_api.py", "_request", 297, 4.0, 10),
        RefactoringTask(1, "src/dmarket/api/client.py", "_request", 264, 4.0, 9),
        RefactoringTask(1, "src/dmarket/arbitrage_scanner.py", "auto_trade_items", 199, 3.0, 9),
        RefactoringTask(
            1, "src/dmarket/intramarket_arbitrage.py", "find_mispriced_rare_items", 192, 3.0, 8
        ),
        # Priority 2: High (191-150 lines)
        RefactoringTask(2, "src/dmarket/market_analysis.py", "analyze_market_depth", 191, 3.0, 8),
        RefactoringTask(2, "src/dmarket/dmarket_api.py", "direct_balance_request", 186, 3.0, 8),
        RefactoringTask(
            2, "src/dmarket/intramarket_arbitrage.py", "find_trending_items", 184, 3.0, 8
        ),
        RefactoringTask(2, "src/dmarket/arbitrage_scanner.py", "scan_game", 175, 3.0, 7),
        RefactoringTask(2, "src/dmarket/arbitrage_scanner.py", "check_user_balance", 174, 3.0, 7),
        RefactoringTask(2, "src/dmarket/dmarket_api.py", "get_balance", 170, 3.0, 7),
        RefactoringTask(
            2, "src/dmarket/intramarket_arbitrage.py", "find_price_anomalies", 170, 3.0, 7
        ),
        RefactoringTask(2, "src/dmarket/arbitrage_scanner.py", "_analyze_item", 169, 3.0, 7),
        RefactoringTask(2, "src/dmarket/api/wallet.py", "get_balance", 158, 2.5, 7),
        RefactoringTask(
            2, "src/dmarket/portfolio_manager.py", "get_rebalancing_recommendations", 154, 2.5, 7
        ),
        RefactoringTask(
            2,
            "src/dmarket/arbitrage/search.py",
            "find_arbitrage_opportunities_advanced",
            151,
            2.5,
            7,
        ),
    ]

    # Sort by priority, then by line count
    tasks.sort(key=lambda t: (t.priority, -t.line_count))

    # Generate markdown
    content = generate_markdown(tasks)

    # Write to file
    output_path = Path(output_file)
    output_path.write_text(content, encoding="utf-8")

    print(f"Generated refactoring TODO list: {output_file}")
    print(f"Total tasks: {len(tasks)}")
    print(f"Estimated total hours: {sum(t.estimated_hours for t in tasks):.1f}")


def generate_markdown(tasks: list[RefactoringTask]) -> str:
    """Generate markdown TODO list.

    Args:
        tasks: List of refactoring tasks

    Returns:
        Markdown content
    """
    lines = [
        "# Phase 2 Refactoring TODO List",
        "",
        "> **Generated**: 2026-01-01",
        "> **Status**: In Progress",
        "> **Target**: Complete by February 11, 2026",
        "",
        "---",
        "",
        "## Overview",
        "",
        f"**Total Tasks**: {len(tasks)}",
        f"**Estimated Hours**: {sum(t.estimated_hours for t in tasks):.1f}h",
        f"**Average Complexity**: {sum(t.complexity_score for t in tasks) / len(tasks):.1f}/10",
        "",
        "### Progress",
        "",
        "```",
        f"Critical:  [ ] {len([t for t in tasks if t.priority == 1])}/116 functions",
        f"High:      [ ] {len([t for t in tasks if t.priority == 2])}/116 functions",
        f"Medium:    [ ] {len([t for t in tasks if t.priority == 3])}/116 functions",
        f"Low:       [ ] {len([t for t in tasks if t.priority == 4])}/116 functions",
        "```",
        "",
        "---",
        "",
        "## Priority 1: Critical (MUST DO) 🔴",
        "",
        "_Functions > 190 lines OR in critical modules_",
        "",
    ]

    # Add priority 1 tasks
    p1_tasks = [t for t in tasks if t.priority == 1]
    for idx, task in enumerate(p1_tasks, 1):
        lines.extend([
            f"### {idx}. `{task.function_name}()` - {task.line_count} lines",
            "",
            f"- **File**: `{task.file_path}`",
            f"- **Lines**: {task.line_count}",
            f"- **Complexity**: {task.complexity_score}/10",
            f"- **Estimated Time**: {task.estimated_hours}h",
            "- **Status**: ⏳ Not Started",
            "",
            "**Actions**:",
            "- [ ] Write tests for current behavior",
            "- [ ] Identify logical sections",
            "- [ ] Extract helper functions (<50 lines each)",
            "- [ ] Apply early returns pattern",
            "- [ ] Run tests to verify",
            "- [ ] Update documentation",
            "",
        ])

    # Add priority 2 tasks
    lines.extend([
        "---",
        "",
        "## Priority 2: High 🟠",
        "",
        "_Functions 150-190 lines OR high-priority modules_",
        "",
    ])

    p2_tasks = [t for t in tasks if t.priority == 2]
    for idx, task in enumerate(p2_tasks, 1):
        lines.extend([
            f"### {len(p1_tasks) + idx}. `{task.function_name}()` - {task.line_count} lines",
            "",
            f"- **File**: `{task.file_path}`",
            f"- **Complexity**: {task.complexity_score}/10",
            f"- **Estimated**: {task.estimated_hours}h",
            "- **Status**: ⏳ Not Started",
            "",
        ])

    # Add guidelines
    lines.extend([
        "---",
        "",
        "## Guidelines",
        "",
        "### Before Refactoring",
        "",
        "1. ✅ Write tests for existing behavior",
        "2. ✅ Run tests to establish baseline",
        "3. ✅ Understand function's purpose",
        "4. ✅ Identify logical sections",
        "",
        "### During Refactoring",
        "",
        "1. ✅ Extract one section at a time",
        "2. ✅ Name functions descriptively",
        "3. ✅ Keep functions < 50 lines",
        "4. ✅ Apply early returns",
        "5. ✅ Add docstrings",
        "6. ✅ Run tests after each change",
        "",
        "### After Refactoring",
        "",
        "1. ✅ Verify all tests pass",
        "2. ✅ Check coverage mAlgontAlgoned/improved",
        "3. ✅ Run linters (ruff, mypy)",
        "4. ✅ Update CHANGELOG.md",
        "5. ✅ Mark task as complete",
        "",
        "---",
        "",
        "## Resources",
        "",
        "- **Refactoring Guide**: `docs/PHASE_2_REFACTORING_GUIDE.md`",
        "- **Examples**: `docs/refactoring_examples/`",
        "- **Copilot Instructions**: `.github/copilot-instructions.md` v5.0",
        "- **Find Long Functions**: `python scripts/find_long_functions.py --threshold 50`",
        "",
        "---",
        "",
        "**Next Update**: January 7, 2026",
        "**Target Completion**: February 11, 2026",
    ])

    return "\n".join(lines)


def mAlgon() -> int:
    """MAlgon entry point.

    Returns:
        Exit code
    """
    parser = argparse.ArgumentParser(description="Generate Phase 2 refactoring TODO list")
    parser.add_argument(
        "--output",
        type=str,
        default="TODO_REFACTORING.md",
        help="Output file path (default: TODO_REFACTORING.md)",
    )

    args = parser.parse_args()

    try:
        generate_todo_list(args.output)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__mAlgon__":
    sys.exit(mAlgon())
