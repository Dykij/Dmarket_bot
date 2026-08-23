============================================================
DIVERSE-CATEGORY CALIBRATION (non-AK-47 titles)
============================================================
Titles selected: ['10 Year Birthday Sticker Capsule', '2021 Community Sticker Capsule', 'Aces High Pin', '1st Lieutenant Farlow | SWAT', '2020 RMR Challengers']

============================================================
Title: 10 Year Birthday Sticker Capsule
Status: FAIL
Observations: 8377 total, 8375 valid returns
Time-series gaps (>30min): 1, median_dt=163.8s, max_dt=7038.5s
Price: min=0.715, max=0.8, mean=0.7493
OBI: mean=0.097, std=0.1338

OU (Price): theta=0.002073, stderr=0.000817, t-stat=-2.5386, p-value=0.011155, category=SIGNIFICANT, mu=0.752436
OBI Regression: alpha=-9.7e-06, beta=0.00052171, stderr_beta=0.00026751, p-value_beta=0.051196, R²=0.000649
GARCH(1,1): omega=0.027342, alpha=0.680958, beta=0.13945, persistence=0.820408, degenerate=no

Walk-Forward Test (n=2513): MSE=5.3112e-06
Signals: 0 non-zero in test, 0 actual trades after shift
Sharpe: N/A (UNRELIABLE)

⚠ Issues:
  - Sharpe unreliable (0 trades < 20)

============================================================
Title: 2021 Community Sticker Capsule
Status: FAIL
Observations: 5259 total, 5257 valid returns
Time-series gaps (>30min): 1, median_dt=163.6s, max_dt=7038.5s
Price: min=0.85, max=0.855, mean=0.8548
OBI: mean=-0.7525, std=0.246

OU (Price): theta=0.490493, stderr=0.014192, t-stat=-34.561, p-value=0.0, category=SIGNIFICANT, mu=0.854921
OBI Regression: alpha=-7.03e-06, beta=-9.42e-06, stderr_beta=4.797e-05, p-value_beta=0.844324, R²=1e-05
GARCH(1,1): omega=0.001541, alpha=0.207906, beta=0.495608, persistence=0.703514, degenerate=no

Walk-Forward Test (n=1578): MSE=5.232e-07
Signals: 1194 non-zero in test, 18 actual trades after shift
Sharpe: -0.0 (UNRELIABLE)

⚠ Issues:
  - Sharpe unreliable (18 trades < 20)

============================================================
Title: Aces High Pin
Status: PASS
Observations: 8869 total, 8864 valid returns
Time-series gaps (>30min): 4, median_dt=163.5s, max_dt=425949.1s
Price: min=6.66, max=8.575, mean=7.1789
OBI: mean=0.9337, std=0.02

OU (Price): theta=0.053812, stderr=0.004067, t-stat=-13.2299, p-value=0.0, category=SIGNIFICANT, mu=6.945103
OBI Regression: alpha=-0.00071454, beta=0.00076776, stderr_beta=0.00393312, p-value_beta=0.845239, R²=6e-06
GARCH(1,1): omega=0.007893, alpha=0.25489, beta=0.641778, persistence=0.896668, degenerate=no

Walk-Forward Test (n=2660): MSE=2.49994e-05
Signals: 2660 non-zero in test, 385 actual trades after shift
Sharpe: 0.3254 (RELIABLE)

============================================================
Title: 1st Lieutenant Farlow | SWAT
Status: FAIL
Observations: 8377 total, 8375 valid returns
Time-series gaps (>30min): 1, median_dt=163.8s, max_dt=7038.5s
Price: min=7.85, max=8.565, mean=8.2665
OBI: mean=0.0741, std=0.0428

OU (Price): theta=0.000763, stderr=0.000517, t-stat=-1.4768, p-value=0.13977, category=INSIGNIFICANT, mu=8.312209
OBI Regression: alpha=-1.338e-05, beta=9.772e-05, stderr_beta=0.0001233, p-value_beta=0.42811, R²=0.000107
GARCH(1,1): omega=0.000393, alpha=0.04249, beta=0.768614, persistence=0.811104, degenerate=no

Walk-Forward Test (n=2513): MSE=9.51e-07
Signals: 0 non-zero in test, 0 actual trades after shift
Sharpe: N/A (UNRELIABLE)

⚠ Issues:
  - OU: theta not significant (p=0.1398)
  - Sharpe unreliable (0 trades < 20)

============================================================
Title: 2020 RMR Challengers
Status: FAIL
Observations: 8377 total, 8375 valid returns
Time-series gaps (>30min): 1, median_dt=163.8s, max_dt=7038.5s
Price: min=0.22, max=0.25, mean=0.2337
OBI: mean=0.7352, std=0.0195

OU (Price): theta=0.001041, stderr=0.000613, t-stat=-1.6989, p-value=0.089384, category=INSIGNIFICANT, mu=0.23642
OBI Regression: alpha=-6.583e-05, beta=8.488e-05, stderr_beta=0.00096573, p-value_beta=0.929968, R²=1e-06
GARCH(1,1): omega=0.02617, alpha=0.0, beta=0.000209, persistence=0.000209, degenerate=YES

Walk-Forward Test (n=2513): MSE=7.862e-07
Signals: 2513 non-zero in test, 1 actual trades after shift
Sharpe: -1.0 (UNRELIABLE)

⚠ Issues:
  - OU: theta not significant (p=0.0894)
  - GARCH: degenerate (beta=0.000209)
  - Sharpe unreliable (1 trades < 20)
  - Sharpe negative (-1.0)

============================================================
DIVERSE CALIBRATION SUMMARY
============================================================
PASS: 1, FAIL: 4, INSUFFICIENT/NO_DATA: 0

Failed titles and reasons:
  10 Year Birthday Sticker Capsule:
    - Sharpe unreliable (0 trades < 20)
  2021 Community Sticker Capsule:
    - Sharpe unreliable (18 trades < 20)
  1st Lieutenant Farlow | SWAT:
    - OU: theta not significant (p=0.1398)
    - Sharpe unreliable (0 trades < 20)
  2020 RMR Challengers:
    - OU: theta not significant (p=0.0894)
    - GARCH: degenerate (beta=0.000209)
    - Sharpe unreliable (1 trades < 20)
    - Sharpe negative (-1.0)

Passed titles:
  Aces High Pin: Sharpe=0.3254, theta=0.053812, GARCH_persist=0.896668
