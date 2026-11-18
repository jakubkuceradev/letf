# letf

This repository holds the analysis behind an article on whether leveraged ETFs (LETFs) belong in a long-term portfolio. It compares a 100% S&P 500 portfolio with portfolios that move part of the allocation into a daily-reset S&P 500 LETF, using daily US market history from 1957 to today. All results are in real, inflation-adjusted US dollars.

The analysis works in three steps:

1. It fits a cost model to the returns of real LETFs.
2. It uses the model to rebuild LETF returns back to the launch of the S&P 500 in March 1957.
3. It resamples that history with a circular block bootstrap and compares the outcomes of each allocation over horizons from 1 to 50 years.

The headline result is the LETF allocation that maximizes the 5th percentile of real terminal wealth at a 30-year horizon. An interactive chart lets readers choose any other percentile and horizon.

## Data

LETFs reset their leverage every trading day, so the analysis uses daily data throughout:

- **Index:** the daily S&P 500 price index from 4 March 1957.
- **Dividends:** Shiller's monthly dividend yield, spread evenly over each month's trading days, until 1988. From 1988 the official S&P 500 total return index replaces the reconstruction.
- **Financing rate:** the daily effective federal funds rate (FRED series [`DFF`](https://fred.stlouisfed.org/series/DFF)), the closest long-running match to the overnight rate LETFs pay on their swaps. It accrues over calendar days, so a Monday return carries three days of financing.
- **Inflation:** the monthly US CPI for all urban consumers (FRED series [`CPIAUCNS`](https://fred.stlouisfed.org/series/CPIAUCNS)), interpolated geometrically to daily values. Every return is deflated by it.

## LETF cost model

The model is calibrated on the longest-running daily S&P 500 funds:

| Fund | Leverage | Daily returns from |
|---|---|---|
| Rydex Nova (`RYNVX`, mutual fund) | 1.5x | 12 Jul 1993 |
| ProFunds UltraBull (`ULPIX`, mutual fund) | 2x | 26 Nov 1997 |
| ProShares Ultra S&P 500 (`SSO`) | 2x | June 2006 |
| Direxion Daily S&P 500 Bull 3X (`SPXL`) | 3x | 5 Nov 2008 |
| ProShares UltraPro S&P 500 (`UPRO`) | 3x | June 2009 |

The fit uses each fund's NAV total return with distributions reinvested, not its market price. For the mutual funds it uses the investor share class.

An LETF with leverage $L$ holds $L$ times the index, borrows the extra $L - 1$ at an overnight rate plus a spread, and charges an expense ratio. The model gives the daily return of fund $j$ as:

```math
r_{\text{LETF}} = L \, r_{\text{SP}} - k_j \, r_f - n_t \left( \frac{\text{ER}_{j,t}}{365} + s_j \right) + \varepsilon
```

- $r_{\text{SP}}$ is the daily S&P 500 total return and $r_f$ is the federal funds rate accrued since the previous trading day.
- $n_t$ is the number of calendar days since the previous trading day.
- $L$ is the fund's stated leverage.
- $k_j$ is the fund's financing coefficient. Theory puts it at $L - 1$.
- $\text{ER}_{j,t}$ is the fund's realized net expense ratio for the fiscal year that contains the date. It comes from the "ratio of expenses to average net assets" in the financial highlights of the fund's annual reports on [SEC EDGAR](https://www.sec.gov/edgar/search/), net of fee waivers.
- $s_j$ is the fund's remaining drag per calendar day: the borrowing spread and trading costs inside the fund.
- $\varepsilon$ is the tracking error.

The expense ratio is known, so the regression estimates only $k_j$ and $s_j$. Daily tracking errors are too noisy to separate the two, so the fit adds the expense ratio back, sums the result into monthly tracking differences, and regresses those on the accrued financing rate, fund by fund. A weekly fit checks the result. The years from 2009 to 2015, when the federal funds rate stayed near zero, show each fund's costs with almost no financing component.

The fit is validated out of sample: the model fitted on the first half of each fund's history predicts the second half within ±0.5 percentage points of annual tracking difference. The rebuilt 2x series uses the fitted coefficients and latest fiscal-year expense ratio of `SSO`, and the rebuilt 3x series uses those of `UPRO`. The simulation uses rebuilt returns over the whole sample, including the years when the real funds existed.

## Simulation

The circular block bootstrap (Politis and Romano, 1992) builds synthetic histories from randomly chosen blocks of consecutive trading days. A block can start on any trading day, so blocks overlap, and a block that runs past the end of the sample continues from its start. Each block carries the index, financing rate, inflation, and rebuilt LETF returns from the same dates, so borrowing costs and inflation match the period drawn. Blocks are one year long, which keeps the volatility clustering that drives the daily-reset drag and the sharpest phase of most bear markets inside one block.

Every allocation runs on the same 10,000 paths per horizon, so differences between allocations come from the allocation and not from sampling noise.

## Portfolios

Each portfolio starts from a single lump sum. It holds a fraction $w$ in the LETF and $1 - w$ in an S&P 500 index fund that charges 0.03% a year, and rebalances to $w$ once a year. The analysis covers every combination of these settings:

| Setting | Values |
|---|---|
| LETF | 2x, 3x |
| LETF allocation $w$ | 0% to 100%, step 5 points |
| Horizon | 1 to 50 years |

Sensitivity runs replace annual rebalancing, the one-year block length, or the fitted spread, one at a time:

| Setting | Values |
|---|---|
| Rebalancing | quarterly, none |
| Block length | 1 month, 6 months, 2 years, 5 years, 10 years |
| Financing spread | lowest and highest spread fitted over rolling two-year windows |

## Results

For each setting, the analysis reports:

- Real terminal wealth and real CAGR at every percentile from 1 to 99.
- The allocation $w^*$ that maximizes real terminal wealth at a chosen percentile.
- The crossover percentiles, where the terminal wealth distributions of a mix and the 100% S&P 500 baseline cross. A crossover compares the two distributions, not outcomes on the same path.
- The probability that a mix ends ahead of the baseline on the same path.
- Mean and median real terminal wealth, and the mean real log return.
- The probability of ending below the starting real value.
- Maximum real drawdown and the longest time under water.
- The probability that the LETF sleeve loses 90% or more of its value.

## Interactive chart

The supplementary interactive chart reads the precomputed results and lets readers set the percentile cutoff, horizon, LETF, and each sensitivity setting. It shows three linked views:

1. Real terminal wealth at the selected percentile against $w$, with $w^*$ marked.
2. Real terminal wealth across all percentiles for the baseline and a selected mix, with crossovers marked.
3. A heatmap of $w^*$ by horizon and percentile cutoff.

## Limitations

- The bootstrap only recombines observed history. Its left tail comes from a few crises: 1973 to 1974, 1987, 2000 to 2002, and 2008. The sample contains no crash as deep as 1929 to 1932, and no day falls far enough to wipe out a 3x fund.
- The bootstrap breaks any dependence longer than one block, such as valuations reverting over decades.
- The sample covers about 69 years, so 50-year paths reuse the same blocks heavily.
- The borrowing spread is fitted on 1993 onward. Funding spreads in the 1970s and early 1980s were probably wider than any spread in the calibration window.
- The dividend reconstruction before 1988 assumes dividends accrue evenly within each month.
- The model leaves out taxes, trading costs, and the risk that a fund closes.
