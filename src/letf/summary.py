"""Every number the article text quotes, as one flat dict.

Keys are stable names used by ``data-num`` placeholders in ``site/index.html``.
Values are raw numbers (fractions, multiples, years); the page formats them.

Percentiles here always rank outcomes from worst to best. For drawdown and time under
water, where lower is better, the p-th percentile of outcomes is the (100 - p)-th
percentile of the data.
"""

import numpy as np
import pandas as pd

CUTOFF = 10  # headline percentile of outcomes
HORIZONS = (10, 20, 30, 40, 50)
# (letf, share, horizon) combinations the text discusses.
MIXES = ((3, 0.1, 50), (3, 0.2, 50), (2, 0.2, 50), (3, 0.1, 40), (3, 0.1, 30), (3, 0.3, 50))


def _row(grid: pd.DataFrame, setting: str, letf: int, w: float, horizon: int) -> pd.Series:
    sel = grid[
        (grid.setting == setting) & (grid.letf == letf) & np.isclose(grid.w, w) & (grid.horizon == horizon)
    ]
    if len(sel) != 1:
        raise KeyError(f"no unique grid row for {setting}, {letf}x, w={w}, h={horizon}")
    return sel.iloc[0]


def _bad(row: pd.Series, metric: str, cutoff: int = CUTOFF) -> float:
    """Value at the ``cutoff`` percentile of outcomes for a lower-is-better metric."""
    return row[f"{metric}_p{100 - cutoff:02d}"]


def _positive_from(ws: pd.DataFrame) -> int | None:
    """Lowest percentile from which w* stays above zero for every higher percentile."""
    w = ws.sort_values("percentile")
    zero = w[w.w_star == 0].percentile
    if zero.empty:
        return int(w.percentile.min())
    above = w[w.percentile > zero.max()]
    return int(above.percentile.min()) if len(above) else None


def _last_crossover(crossovers: pd.DataFrame, setting: str, letf: int, w: float, horizon: int):
    sel = crossovers[
        (crossovers.setting == setting)
        & (crossovers.letf == letf)
        & np.isclose(crossovers.w, w)
        & (crossovers.horizon == horizon)
    ].crossover_percentiles
    return float(sel.iloc[0][-1]) if len(sel) and len(sel.iloc[0]) else None


def _outcomes(row: pd.Series) -> dict:
    return {
        "p10": row.tw_p10,
        "p50": row.tw_p50,
        "mdd50": row.mdd_p50,
        "mdd_bad": _bad(row, "mdd"),
        "uw50": row.uw_p50,
        "uw_bad": _bad(row, "uw"),
    }


def article_numbers(
    grid: pd.DataFrame,
    w_star: pd.DataFrame,
    crossovers: pd.DataFrame,
    costs: dict,
    checks: dict,
    n_paths: int,
) -> dict:
    out: dict = {
        "cutoff": CUTOFF,
        "sample_start": checks["sample_start"],
        "sample_end": checks["sample_end"],
        "sample_years": (pd.Timestamp(checks["sample_end"]) - pd.Timestamp(checks["sample_start"])).days
        / 365.25,
        "trading_days": checks["trading_days"],
        "tr_check_diff_pp": checks["tr_check_diff_pp"],
        "paths": n_paths,
        "funds_count": len(costs),
        "oos_pass_count": sum(bool(f["oos_pass"]) for f in costs.values()),
    }
    for ticker in ("SSO", "UPRO"):
        f = costs[ticker]
        key = ticker.lower()
        out[f"{key}_k"] = f["monthly"]["k"]
        out[f"{key}_s"] = f["monthly"]["s_annual"]
        out[f"{key}_er"] = f["latest_er"]

    for h in (30, 40, 50):
        for k, v in _outcomes(_row(grid, "main", 3, 0.0, h)).items():
            out[f"base_h{h}_{k}"] = v

    main = w_star[w_star.setting == "main"]
    settings = sorted(w_star.setting.unique())
    out["sens_count"] = len(settings)
    out["variant_count"] = len([x for x in settings if x != "rebalance_none"])
    out["horizon_count"] = int(main.horizon.nunique())
    for letf in (2, 3):
        tag = f"{letf}x"
        m = main[main.letf == letf]
        for h in HORIZONS:
            ws = m[m.horizon == h]
            out[f"wstar_p{CUTOFF}_h{h}_{tag}"] = ws[ws.percentile == CUTOFF].w_star.iloc[0]
            out[f"wstar_p50_h{h}_{tag}"] = ws[ws.percentile == 50].w_star.iloc[0]
            out[f"positive_from_h{h}_{tag}"] = _positive_from(ws)
        for p in (5, CUTOFF):
            at = m[m.percentile == p]
            out[f"p{p}_zero_horizons_{tag}"] = int((at.w_star == 0).sum())
        cut50 = w_star[(w_star.letf == letf) & (w_star.horizon == 50) & (w_star.percentile == CUTOFF)]
        out[f"sens_p{CUTOFF}_h50_max_{tag}"] = cut50.w_star.max()
        for name, setting in (
            ("annual", "main"),
            ("quarterly", "rebalance_quarterly"),
            ("none", "rebalance_none"),
        ):
            for h in (30, 50):
                out[f"ruin_{name}_h{h}_{tag}"] = _row(grid, setting, letf, 0.1, h).p_letf_ruin

    for letf, w, h in MIXES:
        mk = f"mix_{letf}x_{round(w * 100)}_h{h}"
        row = _row(grid, "main", letf, w, h)
        out[f"{mk}_exposure"] = 1 + w * (letf - 1)
        out[f"{mk}_beat"] = 1.0 - row.p_below_base
        out[f"{mk}_cross"] = _last_crossover(crossovers, "main", letf, w, h)
        for k, v in _outcomes(row).items():
            out[f"{mk}_{k}"] = v
        base = _row(grid, "main", letf, 0.0, h)
        out[f"{mk}_p10_change"] = row.tw_p10 / base.tw_p10 - 1
        out[f"{mk}_p50_change"] = row.tw_p50 / base.tw_p50 - 1
        # Robustness range over variants of the same rebalanced strategy; no rebalancing is a
        # different strategy and is reported on its own.
        variants = [x for x in settings if x != "rebalance_none"]
        crosses = [c for c in (_last_crossover(crossovers, x, letf, w, h) for x in variants) if c is not None]
        out[f"{mk}_cross_min"] = min(crosses)
        out[f"{mk}_cross_max"] = max(crosses)
        out[f"{mk}_cross_norebal"] = _last_crossover(crossovers, "rebalance_none", letf, w, h)
    return {k: (v.item() if isinstance(v, np.generic) else v) for k, v in out.items()}
