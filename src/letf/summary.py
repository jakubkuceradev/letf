"""Every number the article text quotes, as one flat dict.

Keys are stable names used by ``data-num`` placeholders in ``site/index.html``.
Values are raw numbers (fractions, multiples, years); the page formats them.
"""

import numpy as np
import pandas as pd

HEADLINE_HORIZON = 30
MIX_SHARES = (0.25, 0.5, 1.0)


def _row(grid: pd.DataFrame, setting: str, letf: int, w: float, horizon: int) -> pd.Series:
    sel = grid[
        (grid.setting == setting) & (grid.letf == letf) & np.isclose(grid.w, w) & (grid.horizon == horizon)
    ]
    if len(sel) != 1:
        raise KeyError(f"no unique grid row for {setting}, {letf}x, w={w}, h={horizon}")
    return sel.iloc[0]


def _wstar(w_star: pd.DataFrame, setting: str, letf: int, horizon: int) -> pd.DataFrame:
    return w_star[(w_star.setting == setting) & (w_star.letf == letf) & (w_star.horizon == horizon)]


def article_numbers(
    grid: pd.DataFrame,
    w_star: pd.DataFrame,
    crossovers: pd.DataFrame,
    costs: dict,
    checks: dict,
    n_paths: int,
) -> dict:
    out: dict = {
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
        out[f"{key}_s_min"] = f["rolling_s_min"]
        out[f"{key}_s_max"] = f["rolling_s_max"]

    h = HEADLINE_HORIZON
    base = _row(grid, "main", 3, 0.0, h)
    out |= {
        "base_p5": base.tw_p05,
        "base_p50": base.tw_p50,
        "base_p95": base.tw_p95,
        "base_mdd50": base.mdd_p50,
        "base_uw50": base.uw_p50,
    }

    settings = sorted(w_star.setting.unique())
    for letf in (2, 3):
        tag = f"{letf}x"
        for horizon in (10, 20, 30, 40):
            ws = _wstar(w_star, "main", letf, horizon).sort_values("percentile")
            out[f"wstar_p5_h{horizon}_{tag}"] = ws[ws.percentile == 5].w_star.iloc[0]
            out[f"first_pct_positive_h{horizon}_{tag}"] = int(ws[ws.w_star > 0].percentile.min())
        ws = _wstar(w_star, "main", letf, h)
        out[f"wstar_p25_{tag}"] = ws[ws.percentile == 25].w_star.iloc[0]
        out[f"wstar_p50_{tag}"] = ws[ws.percentile == 50].w_star.iloc[0]

        for w in MIX_SHARES:
            r = _row(grid, "main", letf, w, h)
            mk = f"mix_{tag}_{round(w * 100)}"
            cross = crossovers[
                (crossovers.setting == "main")
                & (crossovers.letf == letf)
                & np.isclose(crossovers.w, w)
                & (crossovers.horizon == h)
            ].crossover_percentiles.iloc[0]
            out |= {
                f"{mk}_p5": r.tw_p05,
                f"{mk}_p50": r.tw_p50,
                f"{mk}_p95": r.tw_p95,
                f"{mk}_beat": 1.0 - r.p_below_base,
                f"{mk}_mdd50": r.mdd_p50,
                f"{mk}_uw50": r.uw_p50,
                f"{mk}_cross": float(cross[0]) if len(cross) else None,
                f"{mk}_cross_count": len(cross),
            }

        for setting, name in (
            ("main", "annual"),
            ("rebalance_quarterly", "quarterly"),
            ("rebalance_none", "none"),
        ):
            out[f"ruin_{name}_{tag}"] = _row(grid, setting, letf, 0.25, h).p_letf_ruin

        p5 = w_star[(w_star.letf == letf) & (w_star.horizon == h) & (w_star.percentile == 5)]
        p50 = w_star[(w_star.letf == letf) & (w_star.horizon == h) & (w_star.percentile == 50)]
        out[f"sens_p5_zero_count_{tag}"] = int((p5.w_star == 0).sum())
        out[f"sens_p50_min_{tag}"] = p50.w_star.min()
        out[f"sens_p50_max_{tag}"] = p50.w_star.max()
    out["sens_count"] = len(settings)
    return {k: (v.item() if isinstance(v, np.generic) else v) for k, v in out.items()}
