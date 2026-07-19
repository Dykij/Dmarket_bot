#!/usr/bin/env python3
"""
Feedback loop system for Code Review findings.
Tracks which findings were useful (fixed) vs false positives (dismissed).
"""

import json
import os
import sys
from datetime import datetime
from pathlib import Path


FEEDBACK_FILE = Path(__file__).parent.parent / "review_feedback.jsonl"


def log_feedback(
    finding_id: str,
    agent: str,
    confidence: int,
    severity: str,
    file_path: str,
    line: int,
    was_fixed: bool | None = None,
    was_dismissed: bool | None = None,
    cross_validated: bool = False,
    cross_validated_by: list | None = None,
) -> None:
    """Log feedback for a finding."""
    entry = {
        "finding_id": finding_id,
        "agent": agent,
        "confidence": confidence,
        "severity": severity,
        "cross_validated": cross_validated,
        "cross_validated_by": cross_validated_by or [],
        "file": file_path,
        "line": line,
        "timestamp": datetime.now().isoformat(),
        "was_fixed": was_fixed,
        "was_dismissed": was_dismissed,
    }

    with open(FEEDBACK_FILE, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_feedback() -> list:
    """Load all feedback entries."""
    if not FEEDBACK_FILE.exists():
        return []

    entries = []
    with open(FEEDBACK_FILE) as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    return entries


def calculate_precision(agent: str | None = None) -> dict:
    """Calculate precision for an agent or all agents."""
    entries = load_feedback()

    if agent:
        entries = [e for e in entries if e.get("agent") == agent]

    if not entries:
        return {
            "agent": agent or "all",
            "total": 0,
            "fixed": 0,
            "dismissed": 0,
            "pending": 0,
            "precision": 0.5,  # Default when no data
        }

    fixed = sum(1 for e in entries if e.get("was_fixed") is True)
    dismissed = sum(1 for e in entries if e.get("was_dismissed") is True)
    pending = sum(1 for e in entries if e.get("was_fixed") is None and e.get("was_dismissed") is None)

    total_decided = fixed + dismissed
    precision = fixed / total_decided if total_decided > 0 else 0.5

    return {
        "agent": agent or "all",
        "total": len(entries),
        "fixed": fixed,
        "dismissed": dismissed,
        "pending": pending,
        "precision": round(precision, 3),
    }


def get_all_precisions() -> dict:
    """Calculate precision for all agents."""
    agents = [
        "correctness", "security", "performance", "architecture",
        "domain", "test_coverage", "async_safety", "db_safety",
        "api_safety", "config_safety", "error_recovery", "duplication",
    ]

    precisions = {}
    for agent in agents:
        precisions[agent] = calculate_precision(agent)

    return precisions


def get_confidence_threshold(agent: str) -> int:
    """Get confidence threshold based on agent precision."""
    precision_data = calculate_precision(agent)
    precision = precision_data["precision"]

    if precision < 0.4:
        return 90  # Low precision → raise bar
    elif precision > 0.8:
        return 70  # High precision → lower bar
    else:
        return 80  # Default


def main():
    """CLI interface for feedback system."""
    import argparse

    parser = argparse.ArgumentParser(description="Code Review feedback system")
    subparsers = parser.add_subparsers(dest="command")

    # Log feedback
    log_parser = subparsers.add_parser("log", help="Log feedback for a finding")
    log_parser.add_argument("--finding-id", required=True)
    log_parser.add_argument("--agent", required=True)
    log_parser.add_argument("--confidence", type=int, required=True)
    log_parser.add_argument("--severity", required=True)
    log_parser.add_argument("--file", required=True)
    log_parser.add_argument("--line", type=int, required=True)
    log_parser.add_argument("--fixed", action="store_true")
    log_parser.add_argument("--dismissed", action="store_true")

    # Calculate precision
    precision_parser = subparsers.add_parser("precision", help="Calculate precision")
    precision_parser.add_argument("--agent", help="Agent name (or all)")

    # Show all precisions
    subparsers.add_parser("all", help="Show all agent precisions")

    args = parser.parse_args()

    if args.command == "log":
        log_feedback(
            finding_id=args.finding_id,
            agent=args.agent,
            confidence=args.confidence,
            severity=args.severity,
            file_path=args.file,
            line=args.line,
            was_fixed=args.fixed,
            was_dismissed=args.dismissed,
        )
        print(f"Logged feedback for finding {args.finding_id}")

    elif args.command == "precision":
        result = calculate_precision(args.agent)
        print(json.dumps(result, indent=2))

    elif args.command == "all":
        precisions = get_all_precisions()
        print(json.dumps(precisions, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
