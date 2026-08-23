Top 5 titles with OBI data: ['AK-47 | Elite Build (Battle-Scarred)', 'AK-47 | Elite Build (Minimal Wear)', 'AK-47 | Emerald Pinstripe (Well-Worn)', 'AK-47 | Breakthrough (Battle-Scarred)', 'AK-47 | Emerald Pinstripe (Battle-Scarred)']

============================================================
Title: AK-47 | Elite Build (Battle-Scarred)
Status: PASS
Observations: 18422 total, 18415 valid returns
Time-series gaps (>30min): 6, median_dt=2.4s, max_dt=425949.1s

OU (Price): theta=0.236043, stderr=0.005683, t-stat=-41.5334, p-value=0.0, category=SIGNIFICANT, mu=1.423922
OBI Regression: alpha=-3.485e-05, beta=5.201e-05, stderr_beta=0.00493219, R²=0.0
GARCH(1,1): omega=0.046217, alpha=0.934506, beta=0.064571, persistence=0.999076, degenerate=no

Walk-Forward Test (n=5525): MSE=3.8951e-06
Signals: 5525 non-zero in test, 436 actual trades after shift
Sharpe: 0.0 (RELIABLE)

============================================================
Title: AK-47 | Elite Build (Minimal Wear)
Status: PASS
Observations: 17184 total, 17178 valid returns
Time-series gaps (>30min): 5, median_dt=30.7s, max_dt=425949.1s

OU (Price): theta=1.24085, stderr=0.008852, t-stat=-140.1727, p-value=0.0, category=SIGNIFICANT, mu=2.90114
OBI Regression: alpha=0.00013296, beta=-0.00020236, stderr_beta=0.01867463, R²=0.0
GARCH(1,1): omega=0.091111, alpha=0.855421, beta=0.144579, persistence=1.0, degenerate=no

Walk-Forward Test (n=5154): MSE=0.0018823162
Signals: 5154 non-zero in test, 3756 actual trades after shift
Sharpe: 0.0196 (RELIABLE)

============================================================
Title: AK-47 | Emerald Pinstripe (Well-Worn)
Status: FAIL
Observations: 14747 total, 14730 valid returns
Time-series gaps (>30min): 16, median_dt=2.7s, max_dt=425949.1s

OU (Price): theta=4.7e-05, stderr=0.000114, t-stat=-0.4107, p-value=0.681299, category=INSIGNIFICANT, mu=1.938448
OBI Regression: alpha=-0.00010057, beta=0.00014865, stderr_beta=7.232e-05, R²=0.00041
GARCH(1,1): omega=0.00072, alpha=0.01, beta=0.49, persistence=0.5, degenerate=no

Walk-Forward Test (n=4419): MSE=4.7e-09
Signals: 4419 non-zero in test, 1 actual trades after shift
Sharpe: 1.0 (UNRELIABLE)

⚠ Issues:
  - OU: theta not significant (p=0.6813)
  - Sharpe unreliable (1 trades < 20)

============================================================
Title: AK-47 | Breakthrough (Battle-Scarred)
Status: FAIL
Observations: 9133 total, 9112 valid returns
Time-series gaps (>30min): 20, median_dt=34.8s, max_dt=518444.9s

OU (Price): theta=0.005164, stderr=0.000949, t-stat=-5.4438, p-value=0.0, category=SIGNIFICANT, mu=1.600033
OBI Regression: alpha=6.288e-05, beta=-7.693e-05, stderr_beta=0.00014404, R²=4.5e-05
GARCH(1,1): omega=0.004958, alpha=0.581266, beta=0.0, persistence=0.581266, degenerate=YES

Walk-Forward Test (n=2734): MSE=7.112e-07
Signals: 2734 non-zero in test, 2 actual trades after shift
Sharpe: 1.1344 (UNRELIABLE)

⚠ Issues:
  - GARCH: degenerate (beta=0.0)
  - Sharpe unreliable (2 trades < 20)

============================================================
Title: AK-47 | Emerald Pinstripe (Battle-Scarred)
Status: FAIL
Observations: 7008 total, 6974 valid returns
Time-series gaps (>30min): 33, median_dt=11.7s, max_dt=425949.1s

OU (Price): theta=-5.3e-05, stderr=0.000213, t-stat=0.2474, p-value=0.804589, category=NO_REVERSION, mu=None
OBI Regression: alpha=-7.266e-05, beta=9.609e-05, stderr_beta=5.74e-05, R²=0.000574
GARCH(1,1): omega=0.000852, alpha=0.101135, beta=0.0, persistence=0.101135, degenerate=YES

Walk-Forward Test (n=2093): MSE=1.06469e-05
Signals: 2093 non-zero in test, 914 actual trades after shift
Sharpe: -0.461 (RELIABLE)

⚠ Issues:
  - OU: negative theta (no mean-reversion)
  - GARCH: degenerate (beta=0.0)
  - Sharpe negative (-0.461)

============================================================
SUMMARY
============================================================
PASS: 2, FAIL: 3, INSUFFICIENT: 0

Failed titles and reasons:
  AK-47 | Emerald Pinstripe (Well-Worn):
    - OU: theta not significant (p=0.6813)
    - Sharpe unreliable (1 trades < 20)
  AK-47 | Breakthrough (Battle-Scarred):
    - GARCH: degenerate (beta=0.0)
    - Sharpe unreliable (2 trades < 20)
  AK-47 | Emerald Pinstripe (Battle-Scarred):
    - OU: negative theta (no mean-reversion)
    - GARCH: degenerate (beta=0.0)
    - Sharpe negative (-0.461)

Passed titles:
  AK-47 | Elite Build (Battle-Scarred): Sharpe=0.0, theta=0.236043, GARCH_persist=0.999076
  AK-47 | Elite Build (Minimal Wear): Sharpe=0.0196, theta=1.24085, GARCH_persist=1.0
