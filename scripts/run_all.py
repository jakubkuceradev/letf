"""Run the full pipeline: data, cost model, rebuild, simulation grid, exports, reports.

usage: uv run python scripts/run_all.py [--refresh] [--paths N]
"""

import argparse
import json
import time

from letf import costs, results, sim
from letf.data import FUNDS, build_funds, build_market
from letf.paths import PROCESSED, REPORTS, RESULTS


def data_report(checks: dict, fund_info: dict) -> str:
    y = checks["tr_check_yearly"].copy()
    y["diff_pp"] = 100 * (y.reconstructed - y.official)
    lines = [
        "# Data checks",
        "",
        f"- Sample: {checks['sample_start']} to {checks['sample_end']} ({checks['trading_days']} trading days).",
        f"- Sample end is set by the last CPI month available: {checks['last_cpi_month']}.",
        (
            f"- Reconstructed total return vs official S&P 500 total return index, "
            f"{checks['tr_check_window']}: {100 * checks['tr_check_reconstructed_ann']:.2f}% vs "
            f"{100 * checks['tr_check_official_ann']:.2f}% a year, difference "
            f"{checks['tr_check_diff_pp']:+.3f} pp ({'pass' if checks['tr_check_pass'] else 'FAIL'}, "
            "limit 0.25 pp)."
        ),
        (
            "- Official total return days replaced as bad prints (price return plus the month's median "
            f"dividend gap): {', '.join(checks['tr_repaired_days']) or 'none'}."
        ),
        (
            "- CPI months missing on FRED, interpolated geometrically from neighbouring months: "
            f"{', '.join(checks['cpi_missing_months']) or 'none'}."
        ),
        (
            "- Federal funds rate calendar days missing (filled with the previous day's rate): "
            f"{', '.join(checks['dff_missing_days']) or 'none'}."
        ),
        "",
        "## Fund return sources",
        "",
    ]
    for t, info in fund_info.items():
        extra = ", ".join(
            f"{k} = {v:.4g}" if isinstance(v, float) else f"{k} = {v}"
            for k, v in info.items()
            if k != "source"
        )
        lines.append(
            f"- `{t}` ({FUNDS[t].leverage}x): {info['source']}. {FUNDS[t].note}."
            + (f" {extra}." if extra else "")
        )
    lines.append("- `SPXL` tracked the Russell 1000 until 2012-06-28; its calibration starts 2012-06-29.")
    lines += ["", "## Reconstruction vs official, by year", "", y.round(4).to_markdown()]
    return "\n".join(lines) + "\n"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true", help="re-download every source")
    ap.add_argument("--paths", type=int, default=10_000)
    args = ap.parse_args()
    t0 = time.perf_counter()
    for d in (PROCESSED, RESULTS, REPORTS):
        d.mkdir(parents=True, exist_ok=True)

    market, checks = build_market(args.refresh)
    funds, fund_info = build_funds(args.refresh)
    market.to_parquet(PROCESSED / "market.parquet")
    funds.to_parquet(PROCESSED / "funds.parquet")
    (REPORTS / "data.md").write_text(data_report(checks, fund_info))
    t_data = time.perf_counter()

    fits = costs.fit_all(funds, market)
    params = costs.letf_params(fits)
    (PROCESSED / "costs.json").write_text(json.dumps(fits, indent=2, default=str))
    costs.rebuild(market, params).to_parquet(PROCESSED / "letf.parquet")
    (REPORTS / "costs.md").write_text(costs.report(fits, params))
    t_costs = time.perf_counter()

    cfg = sim.SimConfig(n_paths=args.paths)
    grid = results.run_grid(market, fits, cfg)
    grid.to_parquet(RESULTS / "grid.parquet")
    wstar, cross = results.derive(grid)
    wstar.to_parquet(RESULTS / "w_star.parquet")
    cross.to_parquet(RESULTS / "crossovers.parquet")
    sizes = results.write_chart_json(grid, RESULTS)
    t_sim = time.perf_counter()

    print(
        f"data {t_data - t0:.1f}s, costs {t_costs - t_data:.1f}s, simulation {t_sim - t_costs:.1f}s, "
        f"total {t_sim - t0:.1f}s; chart.json {sizes['chart.json'] / 1e6:.2f} MB, "
        f"largest export {max(sizes.values()) / 1e6:.2f} MB"
    )
    print(
        wstar[
            (wstar.setting == "main") & (wstar.percentile == 5) & (wstar.horizon.isin([10, 20, 30, 40, 50]))
        ].to_string(index=False)
    )


if __name__ == "__main__":
    main()
