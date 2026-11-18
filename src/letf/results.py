"""Run the settings grid, aggregate per-path results, derive w* and crossovers, export."""

import json
from dataclasses import dataclass, replace

import numpy as np
import pandas as pd

from letf import costs, sim

PERCENTILES = np.arange(1, 100)


@dataclass(frozen=True)
class Setting:
    name: str
    block_steps: int = 12
    rebalance_steps: int | None = 12
    spread: str = "fitted"  # fitted | min | max


SETTINGS = [
    Setting("main"),
    Setting("rebalance_quarterly", rebalance_steps=3),
    Setting("rebalance_none", rebalance_steps=None),
    Setting("block_1m", block_steps=1),
    Setting("block_6m", block_steps=6),
    Setting("block_2y", block_steps=24),
    Setting("block_5y", block_steps=60),
    Setting("block_10y", block_steps=120),
    Setting("spread_min", spread="min"),
    Setting("spread_max", spread="max"),
]


def _aggregate(setting: str, letf: int, weights, stats: sim.PathStats) -> pd.DataFrame:
    w = stats.wealth  # (paths, n_w, years)
    years = w.shape[-1]
    tw = np.percentile(w, PERCENTILES, axis=0)  # (99, n_w, years)
    mdd = np.percentile(stats.max_drawdown, PERCENTILES, axis=0)
    uw = np.percentile(stats.underwater_years, PERCENTILES, axis=0)
    base = w[:, :1, :]
    rows = {
        "setting": setting,
        "letf": letf,
        "w": np.repeat(weights, years),
        "horizon": np.tile(np.arange(1, years + 1), len(weights)),
        "mean": w.mean(axis=0).ravel(),
        "mean_log": np.log(w).mean(axis=0).ravel(),
        "p_below_start": (w < 1.0).mean(axis=0).ravel(),
        "p_below_base": (w < base).mean(axis=0).ravel(),
        "p_letf_ruin": np.tile(stats.letf_ruin.mean(axis=0), len(weights)),
    }
    df = pd.DataFrame(rows)
    for name, arr in (("tw", tw), ("mdd", mdd), ("uw", uw)):
        flat = arr.reshape(len(PERCENTILES), -1).T
        df = pd.concat([df, pd.DataFrame(flat, columns=[f"{name}_p{p:02d}" for p in PERCENTILES])], axis=1)
    return df


def run_grid(market: pd.DataFrame, fits: dict, cfg: sim.SimConfig, settings=SETTINGS) -> pd.DataFrame:
    frames = []
    arrays = {k: market[k].to_numpy() for k in ("sp_tr", "infl", "n_days")}
    for s in settings:
        params = costs.letf_params(fits, s.spread)
        letf = costs.rebuild(market, params)
        scfg = replace(cfg, block_steps=s.block_steps, rebalance_steps=s.rebalance_steps)
        for lev in (2, 3):
            stats = sim.simulate(
                arrays["sp_tr"], letf[f"letf{lev}"].to_numpy(), arrays["infl"], arrays["n_days"], scfg
            )
            frames.append(_aggregate(s.name, lev, np.asarray(cfg.weights), stats))
    return pd.concat(frames, ignore_index=True)


def tw_cube(grid: pd.DataFrame, setting: str, letf: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Terminal wealth percentiles as array [horizon, w, percentile]."""
    g = grid[(grid.setting == setting) & (grid.letf == letf)].sort_values(["horizon", "w"])
    weights = np.sort(g.w.unique())
    horizons = np.sort(g.horizon.unique())
    cols = [f"tw_p{p:02d}" for p in PERCENTILES]
    cube = g[cols].to_numpy().reshape(len(horizons), len(weights), len(PERCENTILES))
    return cube, weights, horizons


def crossovers(mix: np.ndarray, base: np.ndarray) -> list[float]:
    """Percentiles where mix - base changes sign.

    Exact ties are not crossovers by themselves. Between adjacent nonzero differences of
    opposite sign the crossing is interpolated linearly; across a run of exact ties it sits
    in the middle of the run. Identical curves have no crossovers.
    """
    d = mix - base
    out = []
    last = None  # index of the last nonzero difference
    for i in np.flatnonzero(d != 0):
        if last is not None and np.sign(d[i]) != np.sign(d[last]):
            if i == last + 1:
                out.append(float(PERCENTILES[last] + d[last] / (d[last] - d[i])))
            else:
                out.append(float((PERCENTILES[last + 1] + PERCENTILES[i - 1]) / 2))
        last = i
    return out


def derive(grid: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """w* per (setting, letf, horizon, percentile) and crossovers per (setting, letf, w, horizon)."""
    wstar_rows, cross_rows = [], []
    for (setting, letf), _ in grid.groupby(["setting", "letf"]):
        cube, weights, horizons = tw_cube(grid, setting, letf)
        best = np.argmax(cube, axis=1)  # first max -> smaller w on ties
        for hi, h in enumerate(horizons):
            for pi, p in enumerate(PERCENTILES):
                wstar_rows.append((setting, letf, h, p, weights[best[hi, pi]], cube[hi, best[hi, pi], pi]))
            for wi, wt in enumerate(weights[1:], start=1):
                cross_rows.append((setting, letf, wt, h, crossovers(cube[hi, wi], cube[hi, 0])))
    wstar = pd.DataFrame(wstar_rows, columns=["setting", "letf", "horizon", "percentile", "w_star", "tw"])
    cross = pd.DataFrame(cross_rows, columns=["setting", "letf", "w", "horizon", "crossover_percentiles"])
    return wstar, cross


def chart_json(grid: pd.DataFrame, setting: str) -> dict:
    """Compact export for the chart: log terminal wealth in thousandths, [horizon][w][percentile]."""
    out = {"setting": setting, "percentiles": PERCENTILES.tolist(), "letf": {}}
    for letf in (2, 3):
        cube, weights, horizons = tw_cube(grid, setting, letf)
        g = grid[(grid.setting == setting) & (grid.letf == letf)].sort_values(["horizon", "w"])
        shape = (len(horizons), len(weights))
        out["weights"] = weights.round(2).tolist()
        out["horizons"] = horizons.tolist()
        # w* and crossovers come from the exact percentiles; the rounded wealth is for drawing only.
        best = np.argmax(cube, axis=1)
        out["letf"][str(letf)] = {
            "log_tw_milli": np.round(1000 * np.log(cube)).astype(int).tolist(),
            "w_star": weights[best].round(2).tolist(),
            "crossovers": [
                [[round(x, 2) for x in crossovers(cube[hi, wi], cube[hi, 0])] for wi in range(len(weights))]
                for hi in range(len(horizons))
            ],
            "p_below_base": np.round(g.p_below_base.to_numpy().reshape(shape), 4).tolist(),
            "p_below_start": np.round(g.p_below_start.to_numpy().reshape(shape), 4).tolist(),
            "mean_log": np.round(g.mean_log.to_numpy().reshape(shape), 5).tolist(),
            "p_letf_ruin": np.round(g.p_letf_ruin.to_numpy().reshape(shape)[:, 0], 4).tolist(),
        }
    return out


def write_chart_json(grid: pd.DataFrame, directory) -> dict[str, int]:
    """Write ``chart.json`` for the main settings and ``chart_<setting>.json`` for each other one."""
    sizes = {}
    for setting in grid.setting.unique():
        name = "chart.json" if setting == "main" else f"chart_{setting}.json"
        text = json.dumps(chart_json(grid, setting), separators=(",", ":"))
        (directory / name).write_text(text)
        sizes[name] = len(text.encode())
    return sizes
