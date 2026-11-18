# Data checks

- Sample: 1957-03-04 to 2026-10-01 (17513 trading days).
- Sample end is set by the last CPI month available: 2026-10-01.
- Reconstructed total return vs official S&P 500 total return index, 1988-01-05 to 2023-06-30: 10.68% vs 10.74% a year, difference -0.056 pp (pass, limit 0.25 pp).
- Official total return days replaced as bad prints (price return plus the month's median dividend gap): 1988-03-01, 1988-03-02, 1989-06-22, 1989-06-23, 1990-01-24, 1990-01-25, 2014-12-09, 2014-12-10, 2019-03-12, 2019-03-13, 2019-07-03, 2019-07-05.
- CPI months missing on FRED, interpolated geometrically from neighbouring months: 2025-10-01.
- Federal funds rate calendar days missing (filled with the previous day's rate): none.

## Fund return sources

- `RYNVX` (1.5x): Yahoo adjusted close. mutual fund, investor class; daily price is NAV.
- `ULPIX` (2.0x): Yahoo adjusted close. mutual fund, investor class; daily price is NAV.
- `SSO` (2.0x): ProShares NAV + Yahoo distributions. ProShares NAV history plus Yahoo distributions. max_abs_diff_vs_yahoo_adj = 0.04858, dividends_matched = 70, dividends_in_yahoo = 70.
- `SPXL` (3.0x): Yahoo adjusted close. no NAV history found; adjusted market close.
- `UPRO` (3.0x): ProShares NAV + Yahoo distributions. ProShares NAV history plus Yahoo distributions. max_abs_diff_vs_yahoo_adj = 0.03563, dividends_matched = 47, dividends_in_yahoo = 47.
- `SPXL` tracked the Russell 1000 until 2012-06-28; its calibration starts 2012-06-29.

## Reconstruction vs official, by year

|   Date |   reconstructed |   official |   diff_pp |
|-------:|----------------:|-----------:|----------:|
|   1988 |          0.1235 |     0.125  |   -0.1575 |
|   1989 |          0.3143 |     0.317  |   -0.2722 |
|   1990 |         -0.0324 |    -0.0313 |   -0.1122 |
|   1991 |          0.3047 |     0.3047 |    0.0073 |
|   1992 |          0.0761 |     0.0762 |   -0.0083 |
|   1993 |          0.1006 |     0.1008 |   -0.0136 |
|   1994 |          0.0125 |     0.0132 |   -0.0696 |
|   1995 |          0.375  |     0.3758 |   -0.0788 |
|   1996 |          0.2288 |     0.2296 |   -0.0844 |
|   1997 |          0.3333 |     0.3336 |   -0.0351 |
|   1998 |          0.2855 |     0.2858 |   -0.0295 |
|   1999 |          0.2103 |     0.2104 |   -0.0146 |
|   2000 |         -0.0909 |    -0.091  |    0.0151 |
|   2001 |         -0.1187 |    -0.1189 |    0.0118 |
|   2002 |         -0.2212 |    -0.221  |   -0.0165 |
|   2003 |          0.2857 |     0.2868 |   -0.1119 |
|   2004 |          0.1081 |     0.1088 |   -0.0764 |
|   2005 |          0.0481 |     0.0491 |   -0.1048 |
|   2006 |          0.1568 |     0.1579 |   -0.1115 |
|   2007 |          0.0539 |     0.0549 |   -0.099  |
|   2008 |         -0.3699 |    -0.37   |    0.01   |
|   2009 |          0.2688 |     0.2646 |    0.4128 |
|   2010 |          0.1501 |     0.1506 |   -0.054  |
|   2011 |          0.0196 |     0.0211 |   -0.1551 |
|   2012 |          0.1579 |     0.16   |   -0.2113 |
|   2013 |          0.3227 |     0.3239 |   -0.122  |
|   2014 |          0.1358 |     0.1369 |   -0.1128 |
|   2015 |          0.0131 |     0.0138 |   -0.0757 |
|   2016 |          0.119  |     0.1196 |   -0.0621 |
|   2017 |          0.2176 |     0.2183 |   -0.0741 |
|   2018 |         -0.0446 |    -0.0438 |   -0.0791 |
|   2019 |          0.314  |     0.3144 |   -0.0479 |
|   2020 |          0.1844 |     0.184  |    0.0391 |
|   2021 |          0.2865 |     0.2871 |   -0.0509 |
|   2022 |         -0.1817 |    -0.1811 |   -0.0561 |
|   2023 |          0.1688 |     0.1689 |   -0.0167 |
