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
    assert prices.category({"type": "change", "field": "overall_end", "severity": "medium", "old": "2027-03", "new": "2027-09"}) == "Delay"
    assert prices.category({"type": "change", "field": "completion", "severity": "medium", "old": "2027-09", "new": "2027-03"}) == "Brought forward"
    assert prices.EXPECTED["Delay"] == -1 and prices.EXPECTED["Brought forward"] == 1


def test_summary():
    rows = [{"excess_1d": 1, "excess_5d": 2, "excess_20d": None}, {"excess_1d": -3, "excess_5d": 4, "excess_20d": None}]  # no expected direction
    s = prices.summarise(rows)
    assert s["5d"] == {"n": 2, "mean_excess": 3.0, "median_excess": 3.0, "beat_market_pct": 100.0}
    assert "20d" not in s


def test_bad_news_flipped():
    # a trial stopped and the price fell 5% vs the market: the signal was right
    rows = [{"excess_5d": -5.0, "aligned_5d": 5.0, "excess_1d": None, "aligned_1d": None, "excess_20d": None, "aligned_20d": None},
            {"excess_5d": 2.0, "aligned_5d": 2.0, "excess_1d": None, "aligned_1d": None, "excess_20d": None, "aligned_20d": None}]
    d = prices.summarise_directional(rows)
    assert d["5d"] == {"n": 2, "expected_pct": 100.0, "mean_aligned": 3.5}
    assert prices.EXPECTED["Trial stopped"] == -1 and prices.EXPECTED["Contract award"] == 1


def test_drift_shows_slow_reaction():
    # two good-news signals: price keeps rising for days after the information became public
    slow = [0.5 * k for k in range(1, 21)]          # +0.5% a day, ends +10%
    rows = [{"aligned_path": slow, "days_to_signal": 2}, {"aligned_path": slow, "days_to_signal": 2}]
    d = prices.drift(rows)
    assert d["curve"][0] == {"day": 1, "mean": 0.5, "n": 2} and d["day20_mean"] == 10.0
    assert d["late_share_pct"] == 95.0                 # only 5% of the move happened on day 1
    assert d["after_signal"]["mean"] == 9.0            # still +9% to come after the signal on day 2
    assert d["median_days_to_signal"] == 2


def test_path_from_public_date():
    s = series([100, 100, 110, 121, 121])  # Thu 20 .. Wed 26 Nov
    p = prices.path(s, pd.Timestamp("2026-11-24"))
    assert p == [10.0, 21.0, 21.0]
    assert prices.trading_days_between(s, pd.Timestamp("2026-11-24"), pd.Timestamp("2026-11-26")) == 2
