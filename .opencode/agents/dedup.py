#!/usr/bin/env python3
"""
Deduplication engine for Code Review findings.
Groups findings by file:line, boosts confidence for multi-agent confirmation.
"""

import argparse
import json
import sys
from collections import defaultdict


def load_findings(input_files: list) -> list:
    """Load findings from multiple agent output files."""
    all_findings = []

    for filepath in input_files:
        try:
            with open(filepath) as f:
                data = json.load(f)
                agent_name = data.get("agent", "unknown")
                findings = data.get("findings", [])

                for finding in findings:
                    finding["agent"] = agent_name
                    all_findings.append(finding)

                print(f"  [{agent_name}] Loaded {len(findings)} findings")
        except Exception as e:
            print(f"  ERROR loading {filepath}: {e}")

    return all_findings


def group_by_file_line(findings: list) -> dict:
    """Group findings by (file, line_range) for deduplication."""
    clusters = defaultdict(list)

    for finding in findings:
        file = finding.get("file", "unknown")
        line = finding.get("line", 0)

        # Group by file and line range (±3 lines for overlap)
        key = (file, max(0, line - 3), line + 3)
        clusters[key].append(finding)

    return clusters


def deduplicate_clusters(clusters: dict) -> list:
    """Deduplicate findings within each cluster."""
    deduped = []

    for (file, line_start, line_end), group in clusters.items():
        if len(group) == 1:
            # Single finding, keep as-is
            finding = group[0]
            finding["cross_validated"] = False
            finding["cross_validated_by"] = []
            deduped.append(finding)
        else:
            # Multiple findings on same file:line
            # Keep the one with highest confidence
            best = max(group, key=lambda x: x.get("confidence", 0))

            # Boost confidence: +10 per confirming agent (max +30)
            boost = min(30, 10 * (len(group) - 1))
            best["confidence"] = min(100, best.get("confidence", 0) + boost)

            # Mark as cross-validated
            best["cross_validated"] = True
            best["cross_validated_by"] = [
                f["agent"] for f in group if f != best
            ]

            # Severity escalation: if ANY agent says IMPORTANT → IMPORTANT
            if any(f.get("severity") == "IMPORTANT" for f in group):
                best["severity"] = "IMPORTANT"

            deduped.append(best)

    return deduped


def detect_pre_existing(findings: list) -> list:
    """Mark findings as PRE_EXISTING if not in diff."""
    for finding in findings:
        in_diff = finding.get("in_diff", "YES")
        if in_diff == "NO":
            finding["severity"] = "PRE_EXISTING"
    return findings


def deduplicate(input_files: list, output_file: str) -> None:
    """Main deduplication pipeline."""
    print("Loading findings...")
    all_findings = load_findings(input_files)
    print(f"Total raw findings: {len(all_findings)}")

    print("Grouping by file:line...")
    clusters = group_by_file_line(all_findings)
    print(f"Found {len(clusters)} unique locations")

    print("Deduplicating...")
    deduped = deduplicate_clusters(clusters)
    print(f"After deduplication: {len(deduped)} findings")

    print("Detecting pre-existing...")
    deduped = detect_pre_existing(deduped)

    # Count by severity
    important = sum(1 for f in deduped if f.get("severity") == "IMPORTANT")
    nit = sum(1 for f in deduped if f.get("severity") == "NIT")
    pre_existing = sum(1 for f in deduped if f.get("severity") == "PRE_EXISTING")
    error = sum(1 for f in deduped if f.get("severity") == "ERROR")

    print(f"Summary: {important} IMPORTANT, {nit} NIT, {pre_existing} PRE_EXISTING, {error} ERROR")

    # Save to file
    result = {
        "total_raw": len(all_findings),
        "total_deduped": len(deduped),
        "important": important,
        "nit": nit,
        "pre_existing": pre_existing,
        "error": error,
        "findings": deduped,
    }

    with open(output_file, "w") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    print(f"Saved to {output_file}")


def main():
    parser = argparse.ArgumentParser(description="Deduplicate Code Review findings")
    parser.add_argument(
        "--input",
        nargs="+",
        required=True,
        help="Input JSON files from agents",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output deduped JSON file",
    )
    args = parser.parse_args()

    deduplicate(args.input, args.output)


if __name__ == "__main__":
    main()
