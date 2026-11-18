# Cost model fit

Monthly sums of daily tracking differences (expense ratio added back), regressed on accrued financing and calendar days; Newey-West standard errors.

| Fund | L | Window | k (se) | k − (L−1) t | s %/yr (se) | R² | Weekly k | Weekly s %/yr | OOS TD pp/yr | OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| RYNVX | 1.5 | 1993-07-13 to 2026-10-01 | 0.672 (0.147) | 1.17 | 0.26 (0.24) | 0.058 | 0.675 | 0.29 | -0.09 | pass |
| ULPIX | 2.0 | 1997-12-01 to 2026-10-01 | 0.851 (0.132) | -1.13 | 1.36 (0.33) | 0.271 | 0.962 | 0.97 | +0.05 | pass |
| SSO | 2.0 | 2006-06-20 to 2026-10-01 | 1.042 (0.023) | 1.85 | 0.55 (0.06) | 0.966 | 1.045 | 0.55 | -0.45 | pass |
| SPXL | 3.0 | 2012-06-29 to 2026-10-01 | 2.004 (0.123) | 0.03 | 1.74 (0.46) | 0.647 | 2.039 | 1.68 | +0.12 | pass |
| UPRO | 3.0 | 2009-06-24 to 2026-10-01 | 2.205 (0.034) | 5.99 | 0.92 (0.09) | 0.977 | 2.207 | 0.91 | -0.14 | pass |

## Near-zero rates, 2009 to 2015

| Fund | k | s %/yr | drag beyond expense ratio %/yr |
|---|---|---|---|
| RYNVX | -10.583 | 1.37 | -0.02 |
| ULPIX | 10.432 | 0.07 | 1.47 |
| SSO | 1.047 | 0.39 | 0.53 |
| SPXL | 13.838 | -0.04 | 1.66 |
| UPRO | -1.900 | 1.25 | 1.02 |

## Rolling 24-month spread (k fixed at full-sample fit)

| Fund | min %/yr | max %/yr | days with abs(tracking diff) > 3% |
|---|---|---|---|
| RYNVX | -4.15 | 5.93 | 5 |
| ULPIX | 0.00 | 3.42 | 50 |
| SSO | 0.19 | 0.87 | 0 |
| SPXL | 0.77 | 3.56 | 0 |
| UPRO | 0.48 | 1.44 | 0 |

## Rebuild parameters

- 2x from `SSO`: k = 1.042, s = 0.55%/yr, expense ratio = 0.84%/yr
- 3x from `UPRO`: k = 2.205, s = 0.92%/yr, expense ratio = 0.88%/yr
