import numpy as np
import pandas as pd
import pytest

from letf import costs, results


def _fees():
    return pd.DataFrame(
        {
            "ticker": ["X", "X"],
            "fy_start": pd.to_datetime(["2020-01-01", "2021-01-01"]),
            "fy_end": pd.to_datetime(["2020-12-31", "2021-12-31"]),
            "net_expense_ratio": [1.0, 0.5],
        }
    )


def test_expense_ratio_by_fiscal_year_and_latest_after_end():
    dates = pd.to_datetime(["2020-06-01", "2020-12-31", "2021-01-01", "2023-05-05"])
    er = costs.daily_expense_ratio("X", pd.DatetimeIndex(dates), _fees())
    np.testing.assert_allclose(er.to_numpy(), [0.01, 0.01, 0.005, 0.005])


def test_expense_ratio_before_first_record_raises():
    with pytest.raises(ValueError):
        costs.daily_expense_ratio("X", pd.DatetimeIndex(pd.to_datetime(["2019-12-31"])), _fees())


def test_fit_recovers_known_costs():
    rng = np.random.default_rng(3)
    dates = pd.bdate_range("2000-01-03", periods=4000)
    n_days = np.diff(dates.to_numpy()).astype("timedelta64[D]").astype(float)
    n_days = np.concatenate([[1.0], n_days])
    rf = n_days * (0.03 + 0.02 * np.sin(np.arange(4000) / 400)) / 360
    market = pd.DataFrame({"sp_tr": rng.normal(0.0004, 0.01, 4000), "rf": rf, "n_days": n_days}, index=dates)
    er = 0.009
    s = 0.005
    df = market.assign(er=er, anchor=market.index)
    df["y"] = -1.0 * df.rf - df.n_days * s / 365 + rng.normal(0, 1e-5, 4000)
    fit = costs._fit(df, "M")
    assert fit.k == pytest.approx(1.0, abs=0.02)
    assert fit.s_annual == pytest.approx(s, abs=2e-4)


def test_crossovers_interpolate_and_report_all():
    base = np.ones(99)
    mix = np.ones(99)
    mix[:20] = 0.5  # below baseline at low percentiles
    mix[20:60] = 1.5  # above in the middle
    mix[60:] = 0.8  # below again at the top
    xs = results.crossovers(mix, base)
    assert len(xs) == 2
    assert 20 < xs[0] < 21 and 60 < xs[1] < 61


def test_stale_day_joins_the_period_of_its_catch_up_day():
    dates = pd.to_datetime(["2021-01-28", "2021-01-29", "2021-02-01", "2021-02-02"])
    market = pd.DataFrame(
        {"sp_tr": [0.001, -0.02, 0.01, 0.0], "rf": [0.0001] * 4, "n_days": [1.0, 1.0, 3.0, 1.0]}, index=dates
    )
    fund = pd.Series([0.002, 0.0, -0.02, 0.0], index=dates)  # 2021-01-29 stale, caught up on 02-01
    fees = _fees().assign(ticker="SSO")
    df = costs._frame("SSO", fund, market, fees)
    assert df.stale.tolist() == [False, True, False, False]
    assert list(costs._periods(df, "M").astype(str)) == ["2021-01", "2021-02", "2021-02", "2021-02"]


def test_crossovers_ignore_ties_without_sign_change():
    base = np.ones(99)
    assert results.crossovers(base.copy(), base) == []  # identical curves
    touch = np.full(99, 0.9)
    touch[40] = 1.0  # touches the baseline but never crosses
    assert results.crossovers(touch, base) == []
    tie_run = np.full(99, 0.9)
    tie_run[30:35] = 1.0
    tie_run[35:] = 1.1
    assert results.crossovers(tie_run, base) == [33.0]  # middle of percentiles 31-35
