"""
Diverse-category calibration run — v2 methodology on non-AK titles.

Selection logic:
- 2 stickers/capsules: 10 Year Birthday Sticker Capsule (8377 OBI), 2021 Community Sticker Capsule (5259 OBI)
- 1 agent: 1st Lieutenant Farlow | SWAT (8377 OBI)  
- 1 pin: Aces High Pin (8869 OBI)
- 1 RMR capsule: 2020 RMR Challengers (8377 OBI)

No knives/gloves exist in the dataset at all (0 records).
"""

import json
import sqlite3
import sys

import numpy as np
import pandas as pd
import statsmodels.api as sm
from arch import arch_model


MIN_SIGNALS_FOR_SHARPE = 20
GAP_THRESHOLD_SEC = 30 * 60
GARCH_BETA_DEGEN = 0.01

DIVERSE_TITLES = [
    "10 Year Birthday Sticker Capsule",      # Sticker Capsule
    "2021 Community Sticker Capsule",         # Sticker Capsule
    "Aces High Pin",                          # Pin
    "1st Lieutenant Farlow | SWAT",           # Agent
    "2020 RMR Challengers",                   # RMR Capsule
]


def classify_ou(theta: float, p_value: float) -> str:
    if theta < 0:
        return "NO_REVERSION"
    if p_value >= 0.05:
        return "INSIGNIFICANT"
    return "SIGNIFICANT"


def calibrate_title(df: pd.DataFrame, title: str) -> dict:
    result = {"title": title}

    prices, obis, ofis, timestamps = [], [], [], []
    for _, row in df.iterrows():
        try:
            data = json.loads(row["details"])
            # Handle both JSON formats:
            # AK-47 items: {"price": 1.42, "obi_norm": 0.5, ...}
            # Capsules/Pins/Agents: {"best_bid": 0.6, "best_ask": 0.84, "obi_norm": -0.02, ...}
            price = float(data.get("price", 0))
            if price == 0:
                bid = float(data.get("best_bid", 0))
                ask = float(data.get("best_ask", 0))
                if bid > 0 and ask > 0:
                    price = (bid + ask) / 2.0
                elif ask > 0:
                    price = ask
            prices.append(price)
            obis.append(float(data.get("obi_norm", 0)))
            ofis.append(float(data.get("ofi", 0)))
            timestamps.append(float(row["timestamp"]))
        except Exception:
            prices.append(0)
            obis.append(0)
            ofis.append(0)
            timestamps.append(float(row["timestamp"]))

    df = df.copy()
    df["price"] = prices
    df["obi"] = obis
    df["ofi"] = ofis
    df["ts"] = timestamps
    df = df[df["price"] > 0].reset_index(drop=True)

    df["dt"] = df["ts"].diff()
    gap_mask = df["dt"] > GAP_THRESHOLD_SEC
    n_gaps = gap_mask.sum()
    result["n_observations"] = len(df)
    result["n_gaps_gt_30min"] = int(n_gaps)

    if len(df) > 1:
        median_dt = df["dt"].iloc[1:].median()
        max_dt = df["dt"].iloc[1:].max()
        result["median_interval_sec"] = round(float(median_dt), 1)
        result["max_interval_sec"] = round(float(max_dt), 1)

    # Compute log returns, EXCLUDE returns across gaps
    df["log_ret"] = np.log(df["price"] / df["price"].shift(1))
    df.loc[gap_mask, "log_ret"] = np.nan
    df = df.dropna(subset=["log_ret"]).reset_index(drop=True)

    n = len(df)
    result["n_valid_returns"] = n

    # Price range statistics
    if n > 0:
        result["price_min"] = round(float(df["price"].min()), 4)
        result["price_max"] = round(float(df["price"].max()), 4)
        result["price_mean"] = round(float(df["price"].mean()), 4)
        result["obi_mean"] = round(float(df["obi"].mean()), 4)
        result["obi_std"] = round(float(df["obi"].std()), 4)

    if n < 100:
        result["status"] = f"INSUFFICIENT_DATA (n={n})"
        return result

    split = int(n * 0.7)
    train = df.iloc[:split].copy()
    test = df.iloc[split:].copy()

    # OU Calibration
    x = train["price"].iloc[:-1].values
    y = np.diff(train["price"].values)
    x_sm = sm.add_constant(x)
    ou_model = sm.OLS(y, x_sm).fit()
    a_coeff, b_coeff = ou_model.params

    theta = -b_coeff
    t_stat_theta = float(ou_model.tvalues[1])
    p_value_theta = float(ou_model.pvalues[1])
    ou_category = classify_ou(theta, p_value_theta)

    result["ou_theta"] = round(float(theta), 6)
    result["ou_theta_stderr"] = round(float(ou_model.bse[1]), 6)
    result["ou_theta_tstat"] = round(t_stat_theta, 4)
    result["ou_theta_pvalue"] = round(p_value_theta, 6)
    result["ou_category"] = ou_category
    if theta > 0:
        result["ou_mu"] = round(float(a_coeff / theta), 6)
    else:
        result["ou_mu"] = None

    # OBI Regression
    x_obi = sm.add_constant(train["obi"].values)
    obi_model = sm.OLS(train["log_ret"].values, x_obi).fit()
    alpha_coeff, beta_coeff = obi_model.params
    result["obi_alpha"] = round(float(alpha_coeff), 8)
    result["obi_beta"] = round(float(beta_coeff), 8)
    result["obi_beta_stderr"] = round(float(obi_model.bse[1]), 8)
    result["obi_beta_pvalue"] = round(float(obi_model.pvalues[1]), 6)
    result["obi_r_squared"] = round(float(obi_model.rsquared), 6)

    # GARCH(1,1)
    scaled_ret = train["log_ret"].values * 100
    am = arch_model(scaled_ret, p=1, q=1, rescale=False)
    try:
        garch_res = am.fit(update_freq=0, disp="off")
        g_omega = float(garch_res.params["omega"])
        g_alpha = float(garch_res.params["alpha[1]"])
        g_beta = float(garch_res.params["beta[1]"])
        result["garch_omega"] = round(g_omega, 6)
        result["garch_alpha"] = round(g_alpha, 6)
        result["garch_beta"] = round(g_beta, 6)
        result["garch_persistence"] = round(g_alpha + g_beta, 6)
        result["garch_degenerate"] = g_beta < GARCH_BETA_DEGEN
    except Exception as e:
        result["garch_error"] = str(e)
        result["garch_degenerate"] = True

    # Walk-Forward
    test = test.copy()
    test["pred_ret"] = alpha_coeff + beta_coeff * test["obi"]
    mse = float(np.mean((test["log_ret"] - test["pred_ret"]) ** 2))
    result["test_mse"] = round(mse, 10)
    result["test_n"] = len(test)

    test["signal"] = np.where(
        test["obi"] > 0.5, 1, np.where(test["obi"] < -0.5, -1, 0)
    )
    n_nonzero_signals = int((test["signal"] != 0).sum())
    result["test_n_nonzero_signals"] = n_nonzero_signals

    test["strategy_ret"] = test["signal"].shift(1) * test["log_ret"]
    strat_returns = test["strategy_ret"].dropna()
    n_actual_trades = int((strat_returns != 0).sum())
    result["test_n_actual_trades"] = n_actual_trades

    if len(strat_returns) > 0 and strat_returns.std() > 0:
        sharpe = float(
            np.sqrt(len(strat_returns))
            * (strat_returns.mean() / strat_returns.std())
        )
        result["test_sharpe"] = round(sharpe, 4)
        result["sharpe_reliable"] = n_actual_trades >= MIN_SIGNALS_FOR_SHARPE
    else:
        result["test_sharpe"] = None
        result["sharpe_reliable"] = False

    issues = []
    if ou_category == "NO_REVERSION":
        issues.append("OU: negative theta (no mean-reversion)")
    elif ou_category == "INSIGNIFICANT":
        issues.append(f"OU: theta not significant (p={p_value_theta:.4f})")
    if result.get("garch_degenerate"):
        issues.append(
            f"GARCH: degenerate (beta={result.get('garch_beta', 'N/A')})"
        )
    if not result.get("sharpe_reliable"):
        issues.append(
            f"Sharpe unreliable ({n_actual_trades} trades < {MIN_SIGNALS_FOR_SHARPE})"
        )
    if result.get("test_sharpe") is not None and result["test_sharpe"] < 0:
        issues.append(f"Sharpe negative ({result['test_sharpe']})")

    result["issues"] = issues
    result["status"] = "PASS" if not issues else "FAIL"
    return result


def print_result(r: dict) -> None:
    print(f"\n{'=' * 60}")
    print(f"Title: {r['title']}")
    print(f"Status: {r['status']}")

    if "n_observations" in r:
        print(
            f"Observations: {r['n_observations']} total, "
            f"{r['n_valid_returns']} valid returns"
        )
        if "median_interval_sec" in r:
            print(
                f"Time-series gaps (>30min): {r['n_gaps_gt_30min']}, "
                f"median_dt={r.get('median_interval_sec', '?')}s, "
                f"max_dt={r.get('max_interval_sec', '?')}s"
            )
        if "price_mean" in r:
            print(
                f"Price: min={r['price_min']}, max={r['price_max']}, "
                f"mean={r['price_mean']}"
            )
            print(f"OBI: mean={r['obi_mean']}, std={r['obi_std']}")

    if r["status"].startswith("INSUFFICIENT"):
        return

    print(
        f"\nOU (Price): theta={r['ou_theta']}, "
        f"stderr={r['ou_theta_stderr']}, "
        f"t-stat={r['ou_theta_tstat']}, "
        f"p-value={r['ou_theta_pvalue']}, "
        f"category={r['ou_category']}, "
        f"mu={r['ou_mu']}"
    )

    print(
        f"OBI Regression: alpha={r['obi_alpha']}, "
        f"beta={r['obi_beta']}, "
        f"stderr_beta={r['obi_beta_stderr']}, "
        f"p-value_beta={r['obi_beta_pvalue']}, "
        f"R²={r['obi_r_squared']}"
    )

    if "garch_error" in r:
        print(f"GARCH: FAILED ({r['garch_error']})")
    else:
        print(
            f"GARCH(1,1): omega={r['garch_omega']}, "
            f"alpha={r['garch_alpha']}, "
            f"beta={r['garch_beta']}, "
            f"persistence={r['garch_persistence']}, "
            f"degenerate={'YES' if r['garch_degenerate'] else 'no'}"
        )

    print(
        f"\nWalk-Forward Test (n={r['test_n']}): "
        f"MSE={r['test_mse']}"
    )
    print(
        f"Signals: {r['test_n_nonzero_signals']} non-zero in test, "
        f"{r['test_n_actual_trades']} actual trades after shift"
    )
    sharpe_str = (
        f"{r['test_sharpe']}" if r["test_sharpe"] is not None else "N/A"
    )
    reliable_str = "RELIABLE" if r["sharpe_reliable"] else "UNRELIABLE"
    print(f"Sharpe: {sharpe_str} ({reliable_str})")

    if r["issues"]:
        print(f"\n⚠ Issues:")
        for issue in r["issues"]:
            print(f"  - {issue}")


def main(db_path: str) -> None:
    conn = sqlite3.connect(db_path)

    print("=" * 60)
    print("DIVERSE-CATEGORY CALIBRATION (non-AK-47 titles)")
    print("=" * 60)
    print(f"Titles selected: {DIVERSE_TITLES}")

    results = []
    for title in DIVERSE_TITLES:
        df = pd.read_sql_query(
            "SELECT timestamp, details FROM decision_logs "
            "WHERE hash_name = ? AND details LIKE '%\"obi_norm\"%' "
            "ORDER BY timestamp ASC",
            conn,
            params=(title,),
        )
        if len(df) == 0:
            print(f"\n{'=' * 60}")
            print(f"Title: {title}")
            print(f"Status: NO_OBI_DATA (0 records with obi_norm)")
            results.append({"title": title, "status": "NO_OBI_DATA"})
            continue

        r = calibrate_title(df, title)
        print_result(r)
        results.append(r)

    # Summary
    print(f"\n{'=' * 60}")
    print("DIVERSE CALIBRATION SUMMARY")
    print(f"{'=' * 60}")
    passed = [r for r in results if r["status"] == "PASS"]
    failed = [r for r in results if r["status"] == "FAIL"]
    insuff = [
        r
        for r in results
        if r["status"].startswith("INSUFF") or r["status"] == "NO_OBI_DATA"
    ]

    print(
        f"PASS: {len(passed)}, FAIL: {len(failed)}, "
        f"INSUFFICIENT/NO_DATA: {len(insuff)}"
    )

    if failed:
        print("\nFailed titles and reasons:")
        for r in failed:
            print(f"  {r['title']}:")
            for issue in r.get("issues", []):
                print(f"    - {issue}")

    if passed:
        print("\nPassed titles:")
        for r in passed:
            print(
                f"  {r['title']}: "
                f"Sharpe={r.get('test_sharpe', 'N/A')}, "
                f"theta={r.get('ou_theta', 'N/A')}, "
                f"GARCH_persist={r.get('garch_persistence', 'N/A')}"
            )
    else:
        print(
            "\n*** No diverse titles passed all checks. ***"
        )

    conn.close()


if __name__ == "__main__":
    main(sys.argv[1])
