import os
import json
import logging
import platform
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

logger = logging.getLogger(__name__)


def generate_final_report(
    benchmark_results: Dict[str, Any] = None,
    http2_status: bool = False,
    backlog_items: List[str] = None,
    commit_hash: str = "Unknown"
) -> str:
    """
    Generates a structured Markdown summary of the session's achievements.
    MUST be called before exit.
    """
    if benchmark_results is None:
        benchmark_results = {}
    if backlog_items is None:
        backlog_items = []

    report = []
    report.append("# ABSOLUTE AUTONOMY & TELEMETRY REPORT")
    report.append(f"**Date:** {datetime.utcnow().isoformat()} UTC")
    report.append(f"**Host:** {platform.node()} ({platform.system()} {platform.release()})")
    report.append(f"**Commit Hash:** `{commit_hash}`")

    report.append("\n## 1. Rust vs Python Benchmark")
    if benchmark_results:
        report.append("| Metric | Python (ms) | Rust (ms) | Speedup |")
        report.append("|---|---|---|---|")
        # Assuming benchmark_results structure: {"python_avg": float, "rust_avg": float}
        py_avg = benchmark_results.get("python_avg", 0)
        rs_avg = benchmark_results.get("rust_avg", 0)
        speedup = f"{py_avg / rs_avg:.2f}x" if rs_avg > 0 else "N/A"
        report.append(f"| Average Latency | {py_avg:.4f} | {rs_avg:.4f} | **{speedup}** |")
    else:
        report.append("No benchmark results available.")

    report.append("\n## 2. HTTP/2 Status")
    status_icon = "[OK]" if http2_status else "[FAIL]"
    report.append(f"- **HTTP/2 Enabled:** {status_icon}")

    report.append("\n## 3. Autonomous Backlog (Top 3)")
    if backlog_items:
        for item in backlog_items[:3]:
            report.append(f"- {item}")
    else:
        report.append("- No critical backlog items identified.")

    final_report = "\n".join(report)

    # Log report
    logger.info("Final Report Generated:\n%s", final_report)

    # Save to file as artifact
    report_path = Path("final_report.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(final_report)

    return final_report
