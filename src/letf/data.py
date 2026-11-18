"""Daily market and fund series.

``build_market`` returns one row per S&P 500 trading day from 4 March 1957 with:

- ``sp_tr``: S&P 500 total return (Shiller dividends before 1988, official index after),
- ``rf``: federal funds rate accrued over the calendar days since the previous trading day,
- ``infl``: CPI inflation over the same calendar days,
- ``n_days``: calendar days since the previous trading day.

``build_funds`` returns daily NAV total returns of the calibration funds.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd

from letf import sources

START = pd.Timestamp("1957-03-04")
TR_START = pd.Timestamp("1988-01-04")  # first day of the official total return index


@dataclass(frozen=True)
class Fund:
    ticker: str
    leverage: float
    nav_source: str  # "proshares" | "yahoo_adj"
    note: str = ""


FUNDS = {
    "RYNVX": Fund("RYNVX", 1.5, "yahoo_adj", "mutual fund, investor class; daily price is NAV"),
    "ULPIX": Fund("ULPIX", 2.0, "yahoo_adj", "mutual fund, investor class; daily price is NAV"),
    "SSO": Fund("SSO", 2.0, "proshares", "ProShares NAV history plus Yahoo distributions"),
    "SPXL": Fund("SPXL", 3.0, "yahoo_adj", "no NAV history found; adjusted market close"),
    "UPRO": Fund("UPRO", 3.0, "proshares", "ProShares NAV history plus Yahoo distributions"),
}


def _dividend_return(price: pd.Series, shiller: pd.DataFrame) -> pd.Series:
    """Daily dividend yield: Shiller's monthly dividend spread over the month's trading days."""
    month = price.index.to_period("M")
    days_in_month = pd.Series(1, index=price.index).groupby(month).transform("size")
    monthly_div = shiller["D"].copy() / 12.0
    monthly_div.index = monthly_div.index.to_period("M")
    div_today = monthly_div.reindex(month).to_numpy() / days_in_month.to_numpy()
    return pd.Series(div_today, index=price.index) / price.shift(1)


def _accrued(calendar_rate: pd.Series, dates: pd.DatetimeIndex) -> np.ndarray:
    """Sum a per-calendar-day rate over [previous trading day, trading day)."""
    cum = calendar_rate.cumsum()
    # value of the cumulative sum just before each trading date
    before = cum.shift(1, fill_value=0.0).reindex(dates).to_numpy()
    return np.diff(before, prepend=np.nan)


TR_GLITCH = 0.002  # daily gap between total and price return no dividend explains


def _repair_total_return(official: pd.Series, price_ret: pd.Series) -> tuple[pd.Series, list]:
    """Replace bad prints in the official total return index.

    A bad print shows up as two consecutive days whose total-minus-price gaps have
    opposite signs, one above ``TR_GLITCH`` and the other above half of it. Those days get the price return plus the month's
    median gap.
    """
    gap = official - price_ret
    big = gap.abs() > TR_GLITCH
    half = gap.abs() > TR_GLITCH / 2
    nxt = lambda x: x.shift(-1, fill_value=False)
    opposite = np.sign(gap) != np.sign(gap.shift(-1))
    pair_starts = opposite & ((big & nxt(half)) | (half & nxt(big)))
    bad = pair_starts | pair_starts.shift(1, fill_value=False)
    month = gap.index.to_period("M")
    typical = gap.where(~bad).groupby(month).transform("median")
    repaired = official.where(~bad, price_ret + typical)
    return repaired, [str(d.date()) for d in gap.index[bad]]


def _missing(series: pd.Series, freq: str, start, end) -> list[str]:
    expected = pd.date_range(start, end, freq=freq)
    return [str(d.date()) for d in expected.difference(series.index)]


def build_market(refresh: bool = False) -> tuple[pd.DataFrame, dict]:
    """Daily market frame and a dict of data checks."""
    gspc = sources.yahoo("^GSPC", refresh)["Close"].astype(float)
    tr = sources.yahoo("^SP500TR", refresh)["Close"].astype(float)
    shiller = sources.shiller(refresh)
    dff = sources.fred("DFF", refresh)
    cpi = sources.fred("CPIAUCNS", refresh)

    # One trading day before START so the first return exists.
    gspc = gspc[gspc.index >= gspc.index[gspc.index < START][-1]]
    dates = gspc.index

    price_ret = gspc.pct_change()
    div_ret = _dividend_return(gspc, shiller)
    recon = price_ret + div_ret
    official, tr_repaired = _repair_total_return(tr.pct_change().reindex(dates), price_ret)
    sp_tr = recon.where(dates <= TR_START, official)

    calendar = pd.date_range(dates[0], dates[-1] + pd.Timedelta(days=1), freq="D")
    dff_daily = dff.reindex(calendar).ffill() / 100.0 / 360.0
    rf = _accrued(dff_daily, dates)

    # Geometric interpolation: interpolate log CPI, anchored at the first of each month.
    log_cpi = np.log(cpi).reindex(calendar.union(cpi.index)).interpolate(method="time")
    log_cpi = log_cpi.reindex(calendar)
    last_cpi = cpi.index[-1]
    log_cpi[calendar > last_cpi] = np.nan
    infl = np.exp(np.diff(log_cpi.reindex(dates).to_numpy(), prepend=np.nan)) - 1.0

    n_days = np.diff(dates.to_numpy()).astype("timedelta64[D]").astype(float)
    market = pd.DataFrame(
        {
            "sp_tr": sp_tr.to_numpy(),
            "rf": rf,
            "infl": infl,
            "n_days": np.concatenate([[np.nan], n_days]),
        },
        index=dates,
    ).iloc[1:]

    complete = market.dropna()
    end = complete.index[-1]
    gaps = market.loc[:end].isna().any(axis=1)
    if gaps.any():
        raise ValueError(f"missing market values inside sample: {list(market.index[gaps][:10])}")
    market = market.loc[:end]

    checks = _market_checks(recon, official, shiller, market, last_cpi)
    checks["tr_repaired_days"] = [d for d in tr_repaired if d <= str(end.date())]
    checks["cpi_missing_months"] = _missing(cpi, "MS", cpi.index[0], last_cpi)
    checks["cpi_missing_months"] = [d for d in checks["cpi_missing_months"] if d >= str(START.date())]
    checks["dff_missing_days"] = _missing(dff, "D", START, end)
    return market, checks


def _annualized(r: pd.Series) -> float:
    return float(np.exp(np.log1p(r).sum() * 252.0 / len(r)) - 1.0)


def _market_checks(recon, official, shiller, market, last_cpi) -> dict:
    last_div = shiller["D"].dropna().index[-1] + pd.offsets.MonthEnd(0)
    overlap = recon.index[(recon.index > TR_START) & (recon.index <= last_div)]
    overlap = overlap[official.loc[overlap].notna()]
    rec_ann = _annualized(recon.loc[overlap])
    off_ann = _annualized(official.loc[overlap])
    yearly = pd.DataFrame(
        {
            "reconstructed": (1 + recon.loc[overlap]).groupby(overlap.year).prod() - 1,
            "official": (1 + official.loc[overlap]).groupby(overlap.year).prod() - 1,
        }
    )
    return {
        "sample_start": str(market.index[0].date()),
        "sample_end": str(market.index[-1].date()),
        "trading_days": len(market),
        "last_cpi_month": str(last_cpi.date()),
        "tr_check_window": f"{overlap[0].date()} to {overlap[-1].date()}",
        "tr_check_reconstructed_ann": rec_ann,
        "tr_check_official_ann": off_ann,
        "tr_check_diff_pp": 100 * (rec_ann - off_ann),
        "tr_check_pass": abs(rec_ann - off_ann) <= 0.0025,
        "tr_check_yearly": yearly,
    }


def _fund_returns(fund: Fund, refresh: bool) -> tuple[pd.Series, dict]:
    hist = sources.yahoo(fund.ticker, refresh)
    yahoo_ret = hist["Adj Close"].astype(float).pct_change()
    if fund.nav_source == "yahoo_adj":
        return yahoo_ret.dropna(), {"source": "Yahoo adjusted close"}
    nav = sources.proshares_nav(fund.ticker, refresh)
    divs = hist["Dividends"].reindex(nav.index, fill_value=0.0)
    ret = ((nav + divs) / nav.shift(1) - 1.0).dropna()
    common = ret.index.intersection(yahoo_ret.dropna().index)
    diff = (ret.loc[common] - yahoo_ret.loc[common]).abs()
    info = {
        "source": "ProShares NAV + Yahoo distributions",
        "max_abs_diff_vs_yahoo_adj": float(diff.max()),
        "dividends_matched": int((divs > 0).sum()),
        "dividends_in_yahoo": int((hist["Dividends"] > 0).sum()),
    }
    return ret, info


def build_funds(refresh: bool = False) -> tuple[pd.DataFrame, dict]:
    """Daily total returns per calibration fund (columns) and per-fund source notes."""
    series, info = {}, {}
    for ticker, fund in FUNDS.items():
        series[ticker], info[ticker] = _fund_returns(fund, refresh)
    return pd.DataFrame(series).sort_index(), info
