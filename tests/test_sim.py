import numpy as np
import pytest

from letf import sim


def _series(n=3000, seed=0):
    rng = np.random.default_rng(seed)
    sp = rng.normal(0.0004, 0.01, n)
    letf = 3 * sp - 0.0002 + rng.normal(0, 0.0005, n)
    infl = rng.normal(0.0001, 0.0002, n)
    n_days = rng.choice([1.0, 1.0, 1.0, 1.0, 3.0], n)
    return sp, letf, infl, n_days


def test_step_growth_wraps_circularly():
    daily = np.array([0.1, -0.05, 0.2, 0.0])
    g = sim.step_growth(daily, step=3)
    assert g[0] == pytest.approx(1.1 * 0.95 * 1.2)
    assert g[3] == pytest.approx(1.0 * 1.1 * 0.95)  # wraps to the start


def test_block_starts_uniform_and_contiguous():
    n_days = 500
    cfg = sim.SimConfig(block_steps=6, years=2, n_paths=1)
    rng = np.random.default_rng(1)
    idx = sim.draw_step_starts(n_days, cfg, rng, 20_000)
    blocks = idx.reshape(20_000, -1, cfg.block_steps)
    # contiguous modulo the sample length: each step starts STEP days after the previous one
    assert np.all(np.diff(blocks, axis=2) % n_days == sim.STEP)
    # block starts uniform over all days (chi-square well within tolerance)
    counts = np.bincount(blocks[:, :, 0].ravel(), minlength=n_days)
    expected = counts.sum() / n_days
    chi2 = ((counts - expected) ** 2 / expected).sum()
    assert chi2 < n_days + 5 * np.sqrt(2 * n_days)


@pytest.mark.parametrize("block_steps", [1, 6, 12, 24, 60, 120])
@pytest.mark.parametrize("rebalance", [3, 12, None])
def test_fast_matches_daily_reference(block_steps, rebalance):
    sp, letf, infl, n_days = _series()
    cfg = sim.SimConfig(
        block_steps=block_steps,
        rebalance_steps=rebalance,
        years=10,
        n_paths=50,
        chunk=50,
        weights=(0.0, 0.3, 1.0),
    )
    fast = sim.simulate(sp, letf, infl, n_days, cfg).wealth[:, :, -1]
    idx = sim.draw_step_starts(len(sp), cfg, np.random.default_rng(cfg.seed), cfg.n_paths)
    ref = sim.simulate_daily_reference(sp, letf, infl, n_days, idx, np.array(cfg.weights), rebalance)
    np.testing.assert_allclose(fast, ref, rtol=1e-9)


def test_boundary_allocations():
    sp, letf, infl, n_days = _series()
    cfg = sim.SimConfig(years=5, n_paths=40, chunk=40, weights=(0.0, 1.0), rebalance_steps=None)
    stats = sim.simulate(sp, letf, infl, n_days, cfg)
    idx = sim.draw_step_starts(len(sp), cfg, np.random.default_rng(cfg.seed), cfg.n_paths)
    g_cpi = sim.step_growth(infl)
    index_only = np.prod(sim.step_growth(sp - n_days * sim.INDEX_FEE / 365)[idx] / g_cpi[idx], axis=1)
    letf_only = np.prod(sim.step_growth(letf)[idx] / g_cpi[idx], axis=1)
    np.testing.assert_allclose(stats.wealth[:, 0, -1], index_only, rtol=1e-12)
    np.testing.assert_allclose(stats.wealth[:, 1, -1], letf_only, rtol=1e-12)


def test_reproducible():
    sp, letf, infl, n_days = _series()
    cfg = sim.SimConfig(years=3, n_paths=100, chunk=30)
    a = sim.simulate(sp, letf, infl, n_days, cfg)
    b = sim.simulate(sp, letf, infl, n_days, cfg)
    np.testing.assert_array_equal(a.wealth, b.wealth)
    np.testing.assert_array_equal(a.max_drawdown, b.max_drawdown)
