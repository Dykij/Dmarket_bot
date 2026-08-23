# Memory Evidence (RAW Logs)

<details>
<summary>git show 21e489a --stat</summary>

```
$ git show 21e489a --stat
commit 21e489add9f2ca35d2db2487aea618657614f366
Author: DMarket Bot <bot@dmarket.local>
Date:   Sun Aug 23 15:09:07 2026 +0300

    fix: remove tautological has_reference_discount check (cs_price always 0 post-oracle-removal)
    ...
 src/core/target_sniping/filter.py | 10 +++-------
 1 file changed, 3 insertions(+), 7 deletions(-)
```
</details>

<details>
<summary>git branch --contains 21e489a</summary>

```
$ git branch --contains 21e489a
* feature/remove-oracles-formula-audit
```
</details>

<details>
<summary>git log --oneline main -5</summary>

```
$ git log --oneline main -5
c0a8f47 fix: add GitHub Secrets for API keys to data collection workflow
eb78443 fix: ensure sqlite3 is available on runner
41194f7 fix: filter CREATE TABLE from seed dump to avoid conflict
43ca8ae fix: remove Python indentation from seed step, use sqlite3 directly
3c7af28 fix: seed decision_logs even with cache hit, use INSERT OR IGNORE
```
</details>

<details>
<summary>Calibration OBI Results</summary>

```
$ cat docs/reports/calibration_final_report.md | grep -E "Observations|R²"
Observations: 8377 total, 8375 valid returns
OBI Regression: alpha=-9.7e-06, beta=0.00052171, stderr_beta=0.00026751, p-value_beta=0.051196, R²=0.000649
Observations: 5259 total, 5257 valid returns
OBI Regression: alpha=-7.03e-06, beta=-9.42e-06, stderr_beta=4.797e-05, p-value_beta=0.844324, R²=1e-05
Observations: 14757 total, 14755 valid returns
OBI Regression: alpha=-0.00071454, beta=0.00076776, stderr_beta=0.00393312, p-value_beta=0.845239, R²=6e-06
Observations: 4614 total, 4612 valid returns
OBI Regression: alpha=-1.338e-05, beta=9.772e-05, stderr_beta=0.0001233, p-value_beta=0.42811, R²=0.000107
Observations: 6252 total, 6250 valid returns
OBI Regression: alpha=-6.583e-05, beta=8.488e-05, stderr_beta=0.00096573, p-value_beta=0.929968, R²=1e-06
```
(Total observations: 39,259 across 5 titles)
</details>

<details>
<summary>Oracle Removal Evidence (Commit 2b8dcc0)</summary>

```
$ git show 2b8dcc0 --stat | grep -i -E "waxpeer|market_csgo|csfloat|steam.*oracle"
 src/_archived/oracles/csfloat_oracle.py          | 257 --------------
 src/_archived/oracles/market_csgo_oracle.py      | 163 ---------
 src/_archived/oracles/steam_oracle.py            | 158 ---------
 src/_archived/oracles/waxpeer_oracle.py          | 180 ----------
 tests/unit/api/test_csfloat_oracle.py            | 313 -----------------
 tests/unit/api/test_market_csgo_oracle.py        | 193 ----------
 tests/unit/api/test_steam_oracle.py              | 219 ------------
 tests/unit/api/test_waxpeer_oracle.py            | 202 -----------
 tests/unit/test_csfloat_oracle.py                | 430 -----------------------
 tests/unit/test_market_csgo_oracle.py            | 334 ------------------
 tests/unit/test_steam_oracle.py                  | 306 ----------------
 tests/unit/test_waxpeer_oracle.py                | 331 -----------------
```
</details>

<details>
<summary>Oracle Absence in Source</summary>

```
$ grep -rn "Market.CSGO\|Waxpeer\|CSFloat\|Steam" src/core/ || echo "No matches found"
No matches found
```
</details>

<details>
<summary>filter.py Fix Evidence (agg_prices)</summary>

```
$ grep -n "agg_prices" src/core/target_sniping/filter.py | head -n 3
51:        agg_prices: dict[str, dict[str, Any]],
54:        return rank_candidates_by_spread(items, agg_prices, max_price_usd)
61:        agg_prices: dict[str, dict[str, Any]],
```
</details>

<details>
<summary>garch-ou-calibration Branch Status</summary>

```
$ git log --oneline main..feature/garch-ou-calibration | wc -l
16
```
(16 commits ahead of main, confirming it's not merged into main)
</details>
