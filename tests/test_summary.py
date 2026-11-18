import json
import re

import numpy as np
import pandas as pd
import pytest

from letf import summary
from letf.paths import RESULTS, ROOT

SUMMARY = ROOT / "site" / "data" / "summary.json"
INDEX = ROOT / "site" / "index.html"

pytestmark = pytest.mark.skipif(
    not (SUMMARY.exists() and (RESULTS / "grid.parquet").exists()),
    reason="run scripts/run_all.py and scripts/build_site.py first",
)


def _summary() -> dict:
    return json.loads(SUMMARY.read_text())


def test_every_placeholder_has_a_number():
    keys = set(re.findall(r'data-num="([^"]+)"', INDEX.read_text()))
    assert keys, "no placeholders found"
    missing = keys - set(_summary())
    assert not missing, f"summary.json lacks {sorted(missing)}"


def test_numbers_match_results():
    s = _summary()
    grid = pd.read_parquet(RESULTS / "grid.parquet")
    w_star = pd.read_parquet(RESULTS / "w_star.parquet")
    row = grid[(grid.setting == "main") & (grid.letf == 3) & np.isclose(grid.w, 0.25) & (grid.horizon == 30)]
    assert s["mix_3x_25_p50"] == pytest.approx(row.tw_p50.iloc[0])
    assert s["mix_3x_25_beat"] == pytest.approx(1 - row.p_below_base.iloc[0])
    ws = w_star[(w_star.setting == "main") & (w_star.letf == 2) & (w_star.horizon == 30)]
    assert s["wstar_p5_h30_2x"] == ws[ws.percentile == 5].w_star.iloc[0]
    assert s["positive_from_h30_2x"] == summary._positive_from(ws)
