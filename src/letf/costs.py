"""LETF cost model: fit per fund, validate out of sample, rebuild 2x and 3x returns.

Daily model for fund j (see README):

    r_LETF = L r_SP - k_j r_f - n_t (ER_{j,t} / 365 + s_j) + eps

The expense ratio is known (``data/fees.csv``), so the fit adds it back and
regresses period sums of ``r_LETF - L r_SP + n_t ER / 365`` on the period sums
of ``r_f`` and ``n_t``. The coefficients are ``-k_j`` and ``-s_j``.
"""

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd
import statsmodels.api as sm

from letf.data import FUNDS
from letf.paths import FEES_CSV

# First day each fund tracked the S&P 500 at its stated leverage.
CALIBRATION_START = {"SPXL": pd.Timestamp("2012-06-29")}
NEAR_ZERO = (pd.Timestamp("2009-01-01"), pd.Timestamp("2015-12-31"))
REBUILD_SOURCE = {2: "SSO", 3: "UPRO"}
NW_LAGS = {"M": 3, "W": 8}
OOS_TOLERANCE = 0.005  # annualized tracking difference
ROLLING_MONTHS = 24


@dataclass(frozen=True)
class Fit:
    k: float
    s_daily: float
    k_se: float
    s_se: float
    r2: float
    n_periods: int

    @property
    def s_annual(self) -> float:
        return self.s_daily * 365.0


def load_fees(path=FEES_CSV) -> pd.DataFrame:
    fees = pd.read_csv(path, parse_dates=["fy_start", "fy_end"])
    return fees.sort_values(["ticker", "fy_start"])


def daily_expense_ratio(ticker: str, dates: pd.DatetimeIndex, fees: pd.DataFrame) -> pd.Series:
    """Net expense ratio (fraction per year) in force on each date.

    Dates after the last reported fiscal year use the latest ratio.
    Dates before the first fiscal year raise.
    """
    f = fees[fees.ticker == ticker]
    if dates.min() < f.fy_start.min():
        raise ValueError(f"{ticker}: returns start {dates.min().date()} before first fee record")
    idx = np.searchsorted(f.fy_end.to_numpy(), dates.to_numpy(), side="left")
    idx = np.minimum(idx, len(f) - 1)
    return pd.Series(f.net_expense_ratio.to_numpy()[idx] / 100.0, index=dates)


def _frame(ticker: str, fund_ret: pd.Series, market: pd.DataFrame, fees: pd.DataFrame) -> pd.DataFrame:
    start = CALIBRATION_START.get(ticker, fund_ret.first_valid_index())
    r = fund_ret.loc[start:].dropna()
    df = market.reindex(r.index).assign(r_fund=r).dropna()
    lev = FUNDS[ticker].leverage
    er = daily_expense_ratio(ticker, df.index, fees)
    df["er"] = er
    df["y"] = df.r_fund - lev * df.sp_tr + df.n_days * er / 365.0
    return df


def _fit(df: pd.DataFrame, freq: str) -> Fit:
    g = df[["y", "rf", "n_days"]].groupby(df.index.to_period(freq)).sum()
    g = g[g.n_days > 0]
    model = sm.OLS(g.y, g[["rf", "n_days"]]).fit(cov_type="HAC", cov_kwds={"maxlags": NW_LAGS[freq]})
    return Fit(
        k=-model.params["rf"],
        s_daily=-model.params["n_days"],
        k_se=model.bse["rf"],
        s_se=model.bse["n_days"],
        r2=model.rsquared,
        n_periods=len(g),
    )


def _predict(df: pd.DataFrame, lev: float, fit: Fit, er: pd.Series) -> pd.Series:
    return lev * df.sp_tr - fit.k * df.rf - df.n_days * (er / 365.0 + fit.s_daily)


def _annualized(r: pd.Series) -> float:
    return float(np.exp(np.log1p(r).sum() * 252.0 / len(r)) - 1.0)


def _rolling_s(df: pd.DataFrame, k: float) -> pd.Series:
    """Spread per calendar day on rolling 24-month windows with k held at the full-sample fit."""
    g = df[["y", "rf", "n_days"]].groupby(df.index.to_period("M")).sum()
    resid = g.y + k * g.rf  # = -s * n_days + noise
    num = resid.rolling(ROLLING_MONTHS).sum()
    den = g.n_days.rolling(ROLLING_MONTHS).sum()
    return (-num / den).dropna()


def fit_fund(ticker: str, fund_ret: pd.Series, market: pd.DataFrame, fees: pd.DataFrame) -> dict:
    df = _frame(ticker, fund_ret, market, fees)
    lev = FUNDS[ticker].leverage
    monthly = _fit(df, "M")
    weekly = _fit(df, "W")

    zero = df.loc[NEAR_ZERO[0] : NEAR_ZERO[1]]
    zero_fit = _fit(zero, "M") if len(zero) > 250 else None
    zero_drag = float(-zero.y.sum() / zero.n_days.sum() * 365.0) if len(zero) else None

    months = df.index.to_period("M").unique()
    split = months[len(months) // 2]
    first, second = df[df.index.to_period("M") < split], df[df.index.to_period("M") >= split]
    oos_fit = _fit(first, "M")
    pred = _predict(second, lev, oos_fit, second.er)
    oos_td = _annualized(second.r_fund) - _annualized(pred)

    rolling = _rolling_s(df, monthly.k) * 365.0
    big = (df.y.abs() > 0.03).sum()

    return {
        "ticker": ticker,
        "leverage": lev,
        "start": str(df.index[0].date()),
        "end": str(df.index[-1].date()),
        "days": len(df),
        "monthly": asdict(monthly) | {"s_annual": monthly.s_annual},
        "weekly": asdict(weekly) | {"s_annual": weekly.s_annual},
        "k_minus_theory_t": (monthly.k - (lev - 1)) / monthly.k_se,
        "near_zero_fit": (asdict(zero_fit) | {"s_annual": zero_fit.s_annual}) if zero_fit else None,
        "near_zero_annual_drag_ex_er": zero_drag,
        "oos_split_month": str(split),
        "oos_tracking_diff": oos_td,
        "oos_pass": abs(oos_td) <= OOS_TOLERANCE,
        "rolling_s_min": float(rolling.min()) if len(rolling) else None,
        "rolling_s_max": float(rolling.max()) if len(rolling) else None,
        "latest_er": float(df.er.iloc[-1]),
        "days_abs_y_over_3pct": int(big),
    }


def fit_all(funds: pd.DataFrame, market: pd.DataFrame, fees: pd.DataFrame | None = None) -> dict:
    fees = load_fees() if fees is None else fees
    return {t: fit_fund(t, funds[t], market, fees) for t in FUNDS}


def letf_params(fits: dict, spread_shift: str = "fitted") -> dict:
    """Rebuild parameters per leverage. ``spread_shift`` is 'fitted', 'min', or 'max'."""
    out = {}
    for lev, ticker in REBUILD_SOURCE.items():
        f = fits[ticker]
        s_annual = {
            "fitted": f["monthly"]["s_annual"],
            "min": f["rolling_s_min"],
            "max": f["rolling_s_max"],
        }[spread_shift]
        out[lev] = {"k": f["monthly"]["k"], "s_annual": s_annual, "er": f["latest_er"], "source": ticker}
    return out


def rebuild(market: pd.DataFrame, params: dict) -> pd.DataFrame:
    """Daily rebuilt LETF returns for each leverage over the whole market sample."""
    cols = {}
    for lev, p in params.items():
        cols[f"letf{lev}"] = (
            lev * market.sp_tr - p["k"] * market.rf - market.n_days * (p["er"] + p["s_annual"]) / 365.0
        )
    return pd.DataFrame(cols, index=market.index)


def report(fits: dict, params: dict) -> str:
    lines = ["# Cost model fit", ""]
    lines.append(
        "Monthly sums of daily tracking differences (expense ratio added back), "
        "regressed on accrued financing and calendar days; Newey-West standard errors."
    )
    lines += [
        "",
        "| Fund | L | Window | k (se) | k − (L−1) t | s %/yr (se) | R² | Weekly k | Weekly s %/yr | OOS TD pp/yr | OOS |",
        "|---|---|---|---|---|---|---|---|---|---|---|",
    ]
    for t, f in fits.items():
        m, w = f["monthly"], f["weekly"]
        lines.append(
            f"| {t} | {f['leverage']} | {f['start']} to {f['end']} | {m['k']:.3f} ({m['k_se']:.3f}) | "
            f"{f['k_minus_theory_t']:.2f} | {100 * m['s_annual']:.2f} ({100 * m['s_se'] * 365:.2f}) | "
            f"{m['r2']:.3f} | {w['k']:.3f} | {100 * w['s_annual']:.2f} | "
            f"{100 * f['oos_tracking_diff']:+.2f} | {'pass' if f['oos_pass'] else 'FAIL'} |"
        )
    lines += ["", "## Near-zero rates, 2009 to 2015", ""]
    lines += ["| Fund | k | s %/yr | drag beyond expense ratio %/yr |", "|---|---|---|---|"]
    for t, f in fits.items():
        z = f["near_zero_fit"]
        if z:
            lines.append(
                f"| {t} | {z['k']:.3f} | {100 * z['s_annual']:.2f} | "
                f"{100 * f['near_zero_annual_drag_ex_er']:.2f} |"
            )
    lines += ["", "## Rolling 24-month spread (k fixed at full-sample fit)", ""]
    lines += ["| Fund | min %/yr | max %/yr | days with abs(tracking diff) > 3% |", "|---|---|---|---|"]
    for t, f in fits.items():
        lines.append(
            f"| {t} | {100 * f['rolling_s_min']:.2f} | {100 * f['rolling_s_max']:.2f} | "
            f"{f['days_abs_y_over_3pct']} |"
        )
    lines += ["", "## Rebuild parameters", ""]
    for lev, p in params.items():
        lines.append(
            f"- {lev}x from `{p['source']}`: k = {p['k']:.3f}, s = {100 * p['s_annual']:.2f}%/yr, "
            f"expense ratio = {100 * p['er']:.2f}%/yr"
        )
    return "\n".join(lines) + "\n"
