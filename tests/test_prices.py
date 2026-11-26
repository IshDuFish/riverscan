import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import prices  # noqa: E402


def series(vals, start="2026-11-20"):
    return pd.Series(vals, index=pd.bdate_range(start, periods=len(vals)))


def test_moves_use_close_before_signal_day():
    s = series([100, 100, 110, 99, 120, 130, 140])  # Thu 20 .. Fri 28 Nov
    m = prices.moves(s, pd.Timestamp("2026-11-24"))  # signal caught Mon 24 before the open
    assert m[1] == 10.0     # base is Fri 21 close (100) -> Mon 24 close (110)
    assert m[5] == 40.0     # 5th trading day from Mon = Fri 28 (140)
    assert 20 not in m      # not enough days yet


def test_categories():
    assert prices.category({"type": "contract_award", "framework": True, "severity": "medium"}) == "Framework place"
    assert prices.category({"type": "change", "field": "status", "severity": "high"}) == "Trial stopped"
    assert prices.category({"type": "change", "field": "overall_end", "severity": "medium"}) == "Date change"


def test_summary():
    rows = [{"excess_1d": 1, "excess_5d": 2, "excess_20d": None}, {"excess_1d": -3, "excess_5d": 4, "excess_20d": None}]
    s = prices.summarise(rows)
    assert s["5d"] == {"n": 2, "mean_excess": 3.0, "median_excess": 3.0, "beat_market_pct": 100.0}
    assert "20d" not in s
