#!/usr/bin/env python3
"""
Report generator for Code Review findings.
Generates markdown report from deduped findings.
"""

import argparse
import json
import sys
from datetime import datetime


def generate_report(input_file: str, output_file: str) -> None:
    """Generate markdown report from deduped findings."""
    print(f"Loading findings from {input_file}...")

    with open(input_file) as f:
        data = json.load(f)

    findings = data.get("findings", [])
    total_raw = data.get("total_raw", 0)
    total_deduped = data.get("total_deduped", 0)

    # Separate by severity
    important = [f for f in findings if f.get("severity") == "IMPORTANT"]
    nit = [f for f in findings if f.get("severity") == "NIT"]
    pre_existing = [f for f in findings if f.get("severity") == "PRE_EXISTING"]

    # Sort by confidence (highest first)
    important.sort(key=lambda x: x.get("confidence", 0), reverse=True)
    nit.sort(key=lambda x: x.get("confidence", 0), reverse=True)

    # Generate report
    report = f"""## Deep Code Review — MiMo V2.5 Pro

**Date:** {datetime.now().strftime("%Y-%m-%d %H:%M UTC")}
**Model:** MiMo V2.5 Pro (Token Plan)
**Agents:** 12 parallel reviewers

### Summary
- Raw findings: {total_raw}
- After deduplication: {total_deduped}
- 🔴 Important: {len(important)}
- 🟡 Nit: {len(nit)}
- 🟣 Pre-existing: {len(pre_existing)}

### Severity Table

| Severity | File:Line | Issue | Confidence | Cross-validated |
|----------|-----------|-------|------------|-----------------|
"""

    # Add important findings to table
    for f in important[:10]:  # Top 10
        file_line = f"{f.get('file', '?')}:{f.get('line', '?')}"
        title = f.get('title', 'Unknown issue')[:50]
        confidence = f.get('confidence', 0)
        cross = ', '.join(f.get('cross_validated_by', []))
        if cross:
            cross = f"✅ {cross}"
        else:
            cross = "—"
        report += f"| 🔴 Important | `{file_line}` | {title} | {confidence}% | {cross} |\n"

    # Add nit findings to table
    for f in nit[:5]:  # Top 5
        file_line = f"{f.get('file', '?')}:{f.get('line', '?')}"
        title = f.get('title', 'Unknown issue')[:50]
        confidence = f.get('confidence', 0)
        cross = ', '.join(f.get('cross_validated_by', []))
        if cross:
            cross = f"✅ {cross}"
        else:
            cross = "—"
        report += f"| 🟡 Nit | `{file_line}` | {title} | {confidence}% | {cross} |\n"

    # Add pre-existing findings
    if pre_existing:
        report += f"| 🟣 Pre-existing | — | {len(pre_existing)} existing issues not introduced by this change | — | — |\n"

    report += "\n"

    # Detailed important findings
    if important:
        report += "### Confirmed Important Issues\n\n"
        for i, f in enumerate(important, 1):
            verification = f.get("verification", {})
            verdict = verification.get("verdict", "N/A")
            verdict_emoji = "✅" if verdict == "CONFIRMED" else "❌" if verdict == "FALSE_POSITIVE" else "❓"

            report += f"""**{i}. {f.get('title', 'Unknown issue')}** — `{f.get('file', '?')}:{f.get('line', '?')}` [confidence: {f.get('confidence', 0)}%]
- **Verification:** {verdict_emoji} {verdict}
- **Trigger:** {f.get('trigger', 'N/A')}
- **Impact:** {f.get('impact', 'N/A')}
- **Cross-validated by:** {', '.join(f.get('cross_validated_by', [])) or 'None'}
- **Fix:** {f.get('fix', 'N/A')}

<details>
<summary>📝 Feedback</summary>

Was this finding useful?
- [ ] ✅ Fixed in commit
- [ ] ❌ False positive (dismiss)

</details>

"""

    # Detailed nit findings
    if nit:
        report += "### Confirmed Nits\n\n"
        for i, f in enumerate(nit, 1):
            report += f"""**{i}. {f.get('title', 'Unknown issue')}** — `{f.get('file', '?')}:{f.get('line', '?')}`
- **Description:** {f.get('description', 'N/A')}
- **Fix:** {f.get('fix', 'N/A')}

"""

    # Determine verdict
    has_critical = any(
        f.get("confidence", 0) >= 90
        and len(f.get("cross_validated_by", [])) >= 2
        for f in important
    )

    if has_critical:
        verdict = "🔴 **BLOCK** — Critical issues found with high confidence and multi-agent confirmation"
    elif important:
        verdict = "🟡 **NEEDS WORK** — Important issues found, review recommended"
    else:
        verdict = "🟢 **PASS** — No critical issues found"

    report += f"### Verdict: {verdict}\n"

    # Agent statistics
    report += "\n### Agent Statistics\n\n"
    report += "| Agent | Findings | Status |\n|-------|----------|--------|\n"

    agent_counts = {}
    for f in findings:
        agent = f.get("agent", "unknown")
        agent_counts[agent] = agent_counts.get(agent, 0) + 1

    for agent in [
        "correctness", "security", "performance", "architecture",
        "domain", "test_coverage", "async_safety", "db_safety",
        "api_safety", "config_safety", "error_recovery", "duplication",
        "kelly_sizing", "fee_calculation", "drawdown_monitor",
    ]:
        count = agent_counts.get(agent, 0)
        status = "✅" if count > 0 else "❌"
        report += f"| {agent} | {count} | {status} |\n"

    report += f"""
---
*Generated by Deep Code Review v2.0 with MiMo V2.5 Pro*
*Powered by [OpenCode](https://opencode.ai)*
"""

    # Save to file
    with open(output_file, "w") as f:
        f.write(report)

    print(f"Report saved to {output_file}")
    print(f"Verdict: {verdict}")


def main():
    parser = argparse.ArgumentParser(description="Generate Code Review report")
    parser.add_argument(
        "--input",
        required=True,
        help="Input deduped JSON file",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output markdown file",
    )
    args = parser.parse_args()

    generate_report(args.input, args.output)


if __name__ == "__main__":
    main()
