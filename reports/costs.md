# Cost model fit

Monthly sums of daily tracking differences (expense ratio added back), regressed on accrued financing and calendar days; Newey-West standard errors. A stale fund price (exactly 0% while the index moved more than 0.5%) is assigned to the period of the next day, which catches it up. R² is centered.

| Fund | L | Window | k (se) | k − (L−1) t | s %/yr (se) | centered R² | Weekly k | Weekly s %/yr | OOS TD pp/yr | OOS |
|---|---|---|---|---|---|---|---|---|---|---|
| RYNVX | 1.5 | 1993-07-13 to 2026-10-01 | 0.687 (0.058) | 3.22 | 0.24 (0.17) | 0.187 | 0.679 | 0.26 | -0.10 | pass |
| ULPIX | 2.0 | 1997-12-01 to 2026-10-01 | 0.858 (0.109) | -1.31 | 1.34 (0.28) | 0.187 | 0.880 | 1.19 | +0.05 | pass |
| SSO | 2.0 | 2006-06-20 to 2026-10-01 | 1.041 (0.023) | 1.82 | 0.55 (0.06) | 0.923 | 1.044 | 0.54 | -0.44 | pass |
| SPXL | 3.0 | 2012-06-29 to 2026-10-01 | 2.002 (0.123) | 0.02 | 1.74 (0.46) | 0.391 | 2.037 | 1.67 | -0.01 | pass |
| UPRO | 3.0 | 2009-06-24 to 2026-10-01 | 2.203 (0.034) | 5.96 | 0.91 (0.09) | 0.954 | 2.205 | 0.91 | -0.13 | pass |

## Near-zero rates, 2009 to 2015

| Fund | k | s %/yr | drag beyond expense ratio %/yr |
|---|---|---|---|
| RYNVX | 0.495 | 0.10 | -0.02 |
| ULPIX | 10.309 | 0.11 | 1.47 |
| SSO | 1.040 | 0.39 | 0.53 |
| SPXL | 13.855 | -0.03 | 1.67 |
| UPRO | -1.907 | 1.25 | 1.02 |

## Rolling 24-month spread (k fixed at full-sample fit)

| Fund | min %/yr | max %/yr | days with abs(tracking diff) > 3% | stale prices merged into next day |
|---|---|---|---|---|
| RYNVX | -1.59 | 1.85 | 5 | 26 |
| ULPIX | -0.04 | 3.00 | 50 | 58 |
| SSO | 0.19 | 0.87 | 0 | 0 |
| SPXL | 0.73 | 3.56 | 0 | 0 |
| UPRO | 0.49 | 1.44 | 0 | 0 |

## Rebuild parameters

- 2x from `SSO`: k = 1.041, s = 0.55%/yr, expense ratio = 0.84%/yr
- 3x from `UPRO`: k = 2.203, s = 0.91%/yr, expense ratio = 0.88%/yr
