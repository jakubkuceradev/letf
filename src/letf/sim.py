"""Circular block bootstrap of lump-sum portfolios in real terms.

The simulation never touches daily returns inside its loop. It reduces each
daily series to circular rolling growth over one *step* of ``STEP`` trading
days starting at every day of the sample. A path is a sequence of block starts;
a block of ``b`` steps starting at day ``s`` contributes the steps starting at
``s, s + STEP, ..., s + (b - 1) STEP`` (mod sample length). Every block length
and rebalancing period is a whole number of steps, so this is exact.
"""

from dataclasses import dataclass

import numpy as np

STEP = 21  # trading days per month
YEAR_STEPS = 12  # a year is 252 trading days
INDEX_FEE = 0.0003  # index fund expense ratio per year


@dataclass(frozen=True)
class SimConfig:
    block_steps: int = 12
    rebalance_steps: int | None = 12  # None = never rebalance
    years: int = 50
    n_paths: int = 10_000
    seed: int = 20261118
    chunk: int = 2_000
    weights: tuple[float, ...] = tuple(np.round(np.arange(0, 1.0001, 0.05), 2))


def step_growth(daily: np.ndarray, step: int = STEP) -> np.ndarray:
    """Growth over ``step`` days starting at each day, wrapping at the end of the sample."""
    n = len(daily)
    logs = np.log1p(np.concatenate([daily, daily[: step - 1]]))
    c = np.concatenate([[0.0], np.cumsum(logs)])
    return np.exp(c[step : step + n] - c[:n])


def draw_step_starts(n_days: int, cfg: SimConfig, rng: np.random.Generator, n_paths: int) -> np.ndarray:
    """Day index at which each step of each path starts, shape (n_paths, total_steps)."""
    total = cfg.years * YEAR_STEPS
    n_blocks = -(-total // cfg.block_steps)
    starts = rng.integers(0, n_days, size=(n_paths, n_blocks))
    offsets = STEP * np.arange(cfg.block_steps)
    idx = (starts[:, :, None] + offsets) % n_days
    return idx.reshape(n_paths, -1)[:, :total]


@dataclass
class PathStats:
    """Per-path results sampled at the end of each year (axis -1 is horizon 1..years)."""

    wealth: np.ndarray  # (paths, n_w, years) real terminal wealth
    max_drawdown: np.ndarray  # (paths, n_w, years) worst peak-to-trough fall so far, as a fraction
    underwater_years: np.ndarray  # (paths, n_w, years) longest time below a previous peak, years
    letf_ruin: np.ndarray  # (paths, years) pure LETF holding fell to 10% of start at any month


def simulate(
    sp_daily: np.ndarray,
    letf_daily: np.ndarray,
    infl_daily: np.ndarray,
    n_days_cal: np.ndarray,
    cfg: SimConfig,
) -> PathStats:
    """Simulate all allocations of one LETF against the index fund on common paths."""
    n = len(sp_daily)
    index_net = sp_daily - n_days_cal * INDEX_FEE / 365.0
    g_cpi = step_growth(infl_daily)
    g_idx = step_growth(index_net) / g_cpi
    g_let = step_growth(letf_daily) / g_cpi

    w = np.asarray(cfg.weights)[None, :]
    total = cfg.years * YEAR_STEPS
    rng = np.random.default_rng(cfg.seed)
    out = {k: [] for k in ("wealth", "mdd", "uw", "ruin")}

    for start in range(0, cfg.n_paths, cfg.chunk):
        m = min(cfg.chunk, cfg.n_paths - start)
        idx = draw_step_starts(n, cfg, rng, m)
        gi, gl = g_idx[idx], g_let[idx]  # (m, total)

        let_val = np.repeat(w, m, axis=0).astype(float)
        idx_val = 1.0 - let_val
        peak = np.ones_like(let_val)
        mdd = np.zeros_like(let_val)
        uw = np.zeros_like(let_val)
        uw_max = np.zeros_like(let_val)
        pure = np.ones(m)
        ruined = np.zeros(m, dtype=bool)
        snaps = {k: [] for k in out}

        for t in range(total):
            let_val *= gl[:, t : t + 1]
            idx_val *= gi[:, t : t + 1]
            wealth = let_val + idx_val
            np.maximum(peak, wealth, out=peak)
            np.maximum(mdd, 1.0 - wealth / peak, out=mdd)
            below = wealth < peak
            uw = np.where(below, uw + 1, 0)
            np.maximum(uw_max, uw, out=uw_max)
            pure *= gl[:, t]
            ruined |= pure <= 0.1
            if cfg.rebalance_steps and (t + 1) % cfg.rebalance_steps == 0:
                let_val = w * wealth
                idx_val = wealth - let_val
            if (t + 1) % YEAR_STEPS == 0:
                snaps["wealth"].append(wealth.copy())
                snaps["mdd"].append(mdd.copy())
                snaps["uw"].append(uw_max / YEAR_STEPS)
                snaps["ruin"].append(ruined.copy())

        for k, chunks in out.items():
            chunks.append(np.stack(snaps[k], axis=-1))

    return PathStats(
        wealth=np.concatenate(out["wealth"]),
        max_drawdown=np.concatenate(out["mdd"]),
        underwater_years=np.concatenate(out["uw"]),
        letf_ruin=np.concatenate(out["ruin"]),
    )


def simulate_daily_reference(
    sp_daily: np.ndarray,
    letf_daily: np.ndarray,
    infl_daily: np.ndarray,
    n_days_cal: np.ndarray,
    step_starts: np.ndarray,
    weights: np.ndarray,
    rebalance_steps: int | None,
) -> np.ndarray:
    """Day-by-day terminal real wealth for given step starts (test oracle, slow)."""
    n = len(sp_daily)
    index_net = sp_daily - n_days_cal * INDEX_FEE / 365.0
    paths, steps = step_starts.shape
    out = np.empty((paths, len(weights)))
    for p in range(paths):
        for j, wt in enumerate(weights):
            let_val, idx_val = wt, 1.0 - wt
            for t in range(steps):
                for d in range(STEP):
                    day = (step_starts[p, t] + d) % n
                    cpi = 1.0 + infl_daily[day]
                    let_val *= (1.0 + letf_daily[day]) / cpi
                    idx_val *= (1.0 + index_net[day]) / cpi
                if rebalance_steps and (t + 1) % rebalance_steps == 0:
                    total = let_val + idx_val
                    let_val, idx_val = wt * total, (1 - wt) * total
            out[p, j] = let_val + idx_val
    return out
