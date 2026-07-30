"""obi_regression.py — OLS regression for OBI threshold calibration.

v17.6: Reads decision_logs from SQLite and computes optimal thresholds
for OBI, OFI, and Z-score via OLS regression on forward returns.

Usage:
    python -m src.analysis.backtest.obi_regression

Requires: decision_logs table with at least 100 observations.
Run after 2+ weeks of dry-run data collection.

Academic basis:
- Forward return = α + β1*OBI + β2*OFI + β3*Z-score + ε
- Optimal threshold = point where predicted return > fees + min_spread
"""

from __future__ import annotations

import json
import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger("OBIRegression")


def load_decision_logs(db_path: str = "data/dmarket_state.db") -> list[dict]:
    """Load decision_logs entries with demand_strategy details."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT hash_name, decision, reason, details, timestamp "
        "FROM decision_logs "
        "WHERE reason LIKE '%demand%' OR reason LIKE '%OBI%' "
        "ORDER BY timestamp"
    ).fetchall()
    conn.close()

    entries = []
    for row in rows:
        try:
            details = json.loads(row["details"]) if row["details"] else {}
            entries.append({
                "title": row["hash_name"],
                "decision": row["decision"],
                "timestamp": row["timestamp"],
                "obi_norm": details.get("obi_norm", 0),
                "ofi": details.get("ofi", 0),
                "z_score": details.get("z_score", 0),
                "demand_ratio": details.get("demand_ratio", 0),
                "score": details.get("score", 0),
                "price": details.get("price", 0),
            })
        except (json.JSONDecodeError, TypeError):
            continue
    return entries


def run_ols_regression(entries: list[dict]) -> dict:
    """Run OLS regression: decision_pass ~ obi + ofi + z_score.

    Returns dict with coefficients, p-values, and recommended thresholds.
    """
    if len(entries) < 50:
        return {"error": f"Need >= 50 observations, got {len(entries)}"}

    try:
        import numpy as np
    except ImportError:
        return {"error": "numpy not installed"}

    # Prepare data
    y = np.array([1 if e["decision"] == "pass" else 0 for e in entries])
    X = np.column_stack([
        np.array([e["obi_norm"] for e in entries]),
        np.array([e["ofi"] for e in entries]),
        np.array([e["z_score"] for e in entries]),
        np.ones(len(entries)),  # intercept
    ])

    # OLS: β = (X'X)^-1 X'y
    try:
        XtX = X.T @ X
        Xty = X.T @ y
        beta = np.linalg.solve(XtX, Xty)
    except np.linalg.LinAlgError:
        return {"error": "Singular matrix — insufficient variation in data"}

    # Predictions and residuals
    y_pred = X @ beta
    residuals = y - y_pred
    r_squared = 1 - np.sum(residuals**2) / np.sum((y - np.mean(y))**2)

    # Standard errors
    n, k = X.shape
    mse = np.sum(residuals**2) / (n - k)
    try:
        se = np.sqrt(np.diag(mse * np.linalg.inv(XtX)))
    except np.linalg.LinAlgError:
        se = np.zeros(k)

    # t-statistics and approximate p-values
    t_stats = beta / np.where(se > 0, se, 1)
    # Approximate p-values using normal distribution
    from math import erfc, sqrt
    p_values = [erfc(abs(t) / sqrt(2)) for t in t_stats]

    # Recommended thresholds
    # OBI threshold: where predicted pass rate > 50%
    obi_threshold = -beta[3] / beta[0] if abs(beta[0]) > 0.001 else 0.5
    ofi_threshold = -beta[3] / beta[1] if abs(beta[1]) > 0.001 else 0.1

    return {
        "n_observations": len(entries),
        "coefficients": {
            "obi": float(beta[0]),
            "ofi": float(beta[1]),
            "z_score": float(beta[2]),
            "intercept": float(beta[3]),
        },
        "standard_errors": {
            "obi": float(se[0]),
            "ofi": float(se[1]),
            "z_score": float(se[2]),
        },
        "t_statistics": {
            "obi": float(t_stats[0]),
            "ofi": float(t_stats[1]),
            "z_score": float(t_stats[2]),
        },
        "p_values": {
            "obi": float(p_values[0]),
            "ofi": float(p_values[1]),
            "z_score": float(p_values[2]),
        },
        "r_squared": float(r_squared),
        "recommended_thresholds": {
            "obi_threshold": round(float(max(0, min(1, obi_threshold))), 3),
            "ofi_threshold": round(float(max(-1, min(1, ofi_threshold))), 3),
        },
    }


def main():
    """Run OBI regression analysis on collected decision logs."""
    logger.info("Loading decision logs...")
    entries = load_decision_logs()
    logger.info(f"Loaded {len(entries)} entries")

    if len(entries) < 50:
        logger.warning(f"Need >= 50 entries for regression, got {len(entries)}")
        logger.info("Collect more data by running the bot for 1-2 weeks")
        return

    logger.info("Running OLS regression...")
    results = run_ols_regression(entries)

    if "error" in results:
        logger.error(f"Regression failed: {results['error']}")
        return

    print("\n" + "=" * 60)
    print("OBI REGRESSION ANALYSIS RESULTS")
    print("=" * 60)
    print(f"Observations: {results['n_observations']}")
    print(f"R-squared: {results['r_squared']:.4f}")
    print()
    print("Coefficients:")
    for k, v in results["coefficients"].items():
        se = results["standard_errors"].get(k, 0)
        t = results["t_statistics"].get(k, 0)
        p = results["p_values"].get(k, 0)
        sig = "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""
        print(f"  {k:<12} β={v:+.4f}  SE={se:.4f}  t={t:+.2f}  p={p:.4f} {sig}")
    print()
    print("Recommended thresholds:")
    for k, v in results["recommended_thresholds"].items():
        print(f"  {k}: {v}")
    print("=" * 60)


if __name__ == "__main__":
    main()
