"""Data for the article's method figures and the borrowing-cost comparison.

``method_figures`` returns plain lists so ``scripts/build_site.py`` can write them to
``site/data/method.json``. Series are sampled at month ends to keep the file small.
"""

import numpy as np
import pandas as pd

from letf import costs
from letf.data import FUNDS

FIGURE_FUNDS = ("SSO", "UPRO")

# Spreads of other ways to borrow for stock exposure, in percentage points over the short-term
# rate (federal funds or SOFR, which trade close together), as of the dates noted. These are
# quoted market and broker rates, not fitted by this pipeline; update them with the article.
BORROWING_ALTERNATIVES = [
    {
        "name": "S&P 500 futures",
        "low": 0.3,
        "high": 0.8,
        "note": "E-mini roll financing over 3-month SOFR; about +0.4 in 2025, +0.8 in June 2026 (CME)",
    },
    {
        "name": "SPX box spread",
        "low": 0.3,
        "high": 0.7,
        "note": "box implied rate over SOFR; about +0.3 on average, +0.7 in August 2026 (Cboe)",
    },
    {
        "name": "Broker margin, low-cost (IBKR Pro)",
        "low": 0.5,
        "high": 1.5,
        "note": "benchmark plus 0.5 to 1.5 points depending on balance (Interactive Brokers, 2026)",
    },
    {
        "name": "Broker margin, low-cost tier (IBKR Lite)",
        "low": 2.5,
        "high": 2.5,
        "note": "benchmark plus 2.5 points (Interactive Brokers, 2026)",
    },
]
# Large US brokers quote a total rate, not a spread (Schwab and Fidelity, September 2026).
BIG_BROKER_TOTAL = {"name": "Broker margin, large US brokers", "low": 10.0, "high": 12.1}


def _monthly_last(series: pd.Series) -> pd.Series:
    return series.groupby(series.index.to_period("M")).last()


def _dates(index) -> list[str]:
    return [str(p.to_timestamp(how="end").date()) for p in index]


def tracking_points(ticker: str, funds: pd.DataFrame, market: pd.DataFrame, fit: dict) -> dict:
    """Monthly tracking difference (expense ratio added back) against the financing rate, annualized."""
    df = costs._frame(ticker, funds[ticker], market, costs.load_fees())
    g = df[["y", "rf", "n_days"]].groupby(costs._periods(df, "M")).sum()
    g = g[g.n_days >= 20]
    year = 365.0 / g.n_days
    k, s = fit["monthly"]["k"], fit["monthly"]["s_annual"]
    return {
        "ticker": ticker,
        "leverage": FUNDS[ticker].leverage,
        "month": _dates(g.index),
        "rate": (100 * g.rf * year).round(4).tolist(),
        "drag": (100 * g.y * year).round(4).tolist(),
        "fit_k": k,
        "fit_s": 100 * s,
    }


def actual_vs_rebuilt(ticker: str, funds: pd.DataFrame, market: pd.DataFrame, fit: dict) -> dict:
    """Growth of 1 in the real fund and in the model, using the fund's own costs, month ends."""
    df = costs._frame(ticker, funds[ticker], market, costs.load_fees())
    m = fit["monthly"]
    model = costs._predict(
        df,
        FUNDS[ticker].leverage,
        costs.Fit(m["k"], m["s_daily"], m["k_se"], m["s_se"], m["r2"], m["n_periods"]),
        df.er,
    )
    actual = _monthly_last((1 + df.r_fund).cumprod())
    rebuilt = _monthly_last((1 + model).cumprod())
    index = _monthly_last((1 + df.sp_tr).cumprod())
    return {
        "ticker": ticker,
        "month": _dates(actual.index),
        "actual": actual.round(5).tolist(),
        "rebuilt": rebuilt.round(5).tolist(),
        "index": index.round(5).tolist(),
        "oos_tracking_diff": fit["oos_tracking_diff"],
    }


def history(market: pd.DataFrame, letf: pd.DataFrame) -> dict:
    """Real growth of 1 since 1957 for the index and the rebuilt 2x and 3x funds, plus the rate."""
    deflate = 1 + market.infl
    out = {}
    for name, r in (("sp500", market.sp_tr), ("letf2", letf.letf2), ("letf3", letf.letf3)):
        out[name] = _monthly_last(((1 + r) / deflate).cumprod())
    rate = market.rf / market.n_days * 360 * 100
    out["fed_funds"] = rate.groupby(rate.index.to_period("M")).mean()
    months = out["sp500"].index
    return {"month": _dates(months)} | {k: v.reindex(months).round(5).tolist() for k, v in out.items()}


def borrowing_costs(fits: dict, params: dict, fed_funds: float, as_of: str) -> dict:
    """Cost of borrowing per borrowed dollar, in percent a year, at the given federal funds rate."""
    rows = []
    for lev, p in sorted(params.items()):
        borrowed = lev - 1
        mult = p["k"] / borrowed  # financing paid per borrowed dollar, as a multiple of the rate
        extra = 100 * (p["er"] + p["s_annual"]) / borrowed  # fee and spread per borrowed dollar
        rate = mult * fed_funds + extra
        rows.append(
            {
                "name": f"{lev}x LETF ({p['source']})",
                "low": rate,
                "high": rate,
                "spread": rate - fed_funds,
                "note": f"{mult:.2f} × fed funds + {extra:.2f} points per borrowed dollar (fitted)",
                "letf": True,
            }
        )
    for alt in BORROWING_ALTERNATIVES:
        rows.append(
            {
                "name": alt["name"],
                "low": fed_funds + alt["low"],
                "high": fed_funds + alt["high"],
                "spread": None,
                "note": alt["note"],
                "letf": False,
            }
        )
    rows.append(
        {
            "name": BIG_BROKER_TOTAL["name"],
            "low": BIG_BROKER_TOTAL["low"],
            "high": BIG_BROKER_TOTAL["high"],
            "spread": None,
            "note": "quoted total rate for smaller balances (Schwab and Fidelity, September 2026)",
            "letf": False,
        }
    )
    return {"fed_funds": fed_funds, "as_of": as_of, "rows": rows}


def method_figures(market, funds, letf, fits, params, dff: pd.Series) -> dict:
    fed_funds = float(dff.iloc[-1])
    return {
        "tracking": [tracking_points(t, funds, market, fits[t]) for t in FIGURE_FUNDS],
        "actual_vs_rebuilt": [actual_vs_rebuilt(t, funds, market, fits[t]) for t in FIGURE_FUNDS],
        "history": history(market, letf),
        "borrowing": borrowing_costs(fits, params, fed_funds, str(dff.index[-1].date())),
    }


def letf_borrowing_numbers(params: dict, fed_funds: float) -> dict:
    """Flat numbers for the article text."""
    out = {"fed_funds_now": fed_funds / 100}
    for lev, p in params.items():
        borrowed = lev - 1
        out[f"borrow_mult_{lev}x"] = p["k"] / borrowed
        out[f"borrow_extra_{lev}x"] = (p["er"] + p["s_annual"]) / borrowed
        out[f"borrow_rate_{lev}x"] = (
            p["k"] / borrowed * fed_funds + 100 * (p["er"] + p["s_annual"]) / borrowed
        ) / 100
    return {k: float(np.round(v, 6)) for k, v in out.items()}


def _real_cagr(r: pd.Series, infl: pd.Series) -> float:
    real = np.log1p(r) - np.log1p(infl)
    years = (r.index[-1] - r.index[0]).days / 365.25
    return float(np.exp(real.sum() / years) - 1)


def _max_drawdown(r: pd.Series, infl: pd.Series) -> float:
    wealth = ((1 + r) / (1 + infl)).cumprod()
    return float((1 - wealth / wealth.cummax()).max())


def history_numbers(market: pd.DataFrame, letf: pd.DataFrame, figures: dict) -> dict:
    """Flat numbers about the rebuilt history and the model check, for the article text."""
    out = {}
    for name, r in (("sp500", market.sp_tr), ("letf2", letf.letf2), ("letf3", letf.letf3)):
        out[f"hist_cagr_{name}"] = _real_cagr(r, market.infl)
        out[f"hist_mdd_{name}"] = _max_drawdown(r, market.infl)
        out[f"hist_growth_{name}"] = float(((1 + r) / (1 + market.infl)).prod())
    y2008 = market.index.year == 2008
    out["hist_2008_letf3"] = float(((1 + letf.letf3[y2008]) / (1 + market.infl[y2008])).prod() - 1)
    out["hist_2008_sp500"] = float(((1 + market.sp_tr[y2008]) / (1 + market.infl[y2008])).prod() - 1)
    for fig in figures["actual_vs_rebuilt"]:
        t = fig["ticker"].lower()
        years = (pd.Timestamp(fig["month"][-1]) - pd.Timestamp(fig["month"][0])).days / 365.25
        out[f"check_years_{t}"] = years
        out[f"check_cagr_actual_{t}"] = fig["actual"][-1] ** (1 / years) - 1
        out[f"check_cagr_rebuilt_{t}"] = fig["rebuilt"][-1] ** (1 / years) - 1
        out[f"check_start_{t}"] = fig["month"][0][:4]
    return out
