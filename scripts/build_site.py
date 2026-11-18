"""Copy chart data into site/data and write summary.json for the article text.

usage: uv run python scripts/build_site.py   (after scripts/run_all.py)
"""

import json
import shutil

import pandas as pd

from letf import summary
from letf.data import build_market
from letf.paths import PROCESSED, RESULTS, ROOT
from letf.sim import SimConfig

SITE_DATA = ROOT / "site" / "data"


def main() -> None:
    SITE_DATA.mkdir(parents=True, exist_ok=True)
    charts = sorted(RESULTS.glob("chart*.json"))
    if not charts:
        raise SystemExit("no results/chart*.json; run scripts/run_all.py first")
    for path in charts:
        shutil.copyfile(path, SITE_DATA / path.name)

    _, checks = build_market()
    numbers = summary.article_numbers(
        grid=pd.read_parquet(RESULTS / "grid.parquet"),
        w_star=pd.read_parquet(RESULTS / "w_star.parquet"),
        crossovers=pd.read_parquet(RESULTS / "crossovers.parquet"),
        costs=json.loads((PROCESSED / "costs.json").read_text()),
        checks=checks,
        n_paths=SimConfig().n_paths,
    )
    (SITE_DATA / "summary.json").write_text(json.dumps(numbers, indent=1))
    print(f"copied {len(charts)} chart files, wrote {len(numbers)} summary numbers to {SITE_DATA}")


if __name__ == "__main__":
    main()
