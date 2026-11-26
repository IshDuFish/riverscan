"""Track record: how slowly do small-company share prices react to public information?

For every medium or high signal we follow the share price day by day from the
moment the underlying record became PUBLIC (the date a contract notice was
published, or a trial registry record was updated), for 20 trading days, and
subtract the move in a benchmark index ("excess return").

If prices took information in instantly, all of the move would happen on day 1
and the line would then go flat. If the line keeps drifting for days afterwards,
including after RiverScan flagged the record, the information wasn't priced in.
Signals are direction-adjusted (bad news flipped) so "the expected way" is always up.

Writes
  data/track_record.json   summary by signal category, plus per-signal results
                           (per-signal and averages are only included when
                           TRACK_RECORD_PUBLIC is True in config.py)
  data/track_record_full.csv   full working table (returns only), for your own analysis

Only returns are stored, never raw prices.

    python prices.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf

from config import (TRIAL_COMPANIES, CONTRACT_COMPANIES, TRACK_RECORD_PUBLIC,
                    TRACK_RECORD_MIN_SIGNALS, TRACK_RECORD_MIN_GROUP)

DATA = Path(__file__).resolve().parent / "data"
HORIZONS = [1, 5, 20]
DAYS = 20
ALL_COS = TRIAL_COMPANIES + CONTRACT_COMPANIES
YAHOO = {c["ticker"]: c.get("yahoo") or c["ticker"].rstrip(".") + ".L" for c in ALL_COS}
DEFAULT_BENCH = {"trials": "^FTAI", "contracts": "^FTAS"}  # FTSE AIM All-Share / FTSE All-Share
BENCH = {c["ticker"]: c.get("benchmark") for c in ALL_COS if c.get("benchmark")}
BENCH_NAME = {"^FTAI": "FTSE AIM All-Share", "^FTAS": "FTSE All-Share", "^FTSE": "FTSE 100", "^FTMC": "FTSE 250"}


def category(s):
    """Group signals into categories that are worth averaging together."""
    t, f = s.get("type"), s.get("field")
    if t == "contract_award":
        return "Framework place" if s.get("framework") else "Contract award"
    if t == "mismatch":
        return "Registry mismatch"
    if t == "new_trial":
        return "New trial"
    if f in ("status", "status_override"):
        return "Trial stopped" if s["severity"] == "high" else "Trial status change"
    if f in ("halts", "safety_measures", "serious_breaches"):
        return "Safety event" if (s.get("new") or 0) > (s.get("old") or 0) else "Other"
    if f == "has_results":
        return "Results posted"
    if f in ("primary_completion", "completion", "recruitment_start", "recruitment_end", "overall_end", "end_date"):
        if s.get("old") and s.get("new"):
            return "Delay" if str(s["new"]) > str(s["old"]) else "Brought forward"
        return "Date change"
    if f in ("enrollment", "target_enrolment", "final_enrolment"):
        return "Enrolment change"
    if f == "phase":
        return "Phase change"
    return "Other"


# Which way would we expect the share price to move after each kind of signal?
#   +1 good news (expect it to beat the market), -1 bad news (expect it to lag the market),
#    0 could go either way, so it's measured but not scored as right or wrong.
EXPECTED = {
    "Contract award": 1,
    "Framework place": 1,
    "Trial stopped": -1,
    "Safety event": -1,
    "Delay": -1,               # a completion or end date pushed later
    "Brought forward": 1,      # a date moved earlier
    "Date change": 0,          # a date added or removed
    "Results posted": 0,       # good or bad depending on the results
    "Registry mismatch": 0,
    "Trial status change": 0,
    "Enrolment change": 0,
    "Phase change": 0,
    "New trial": 0,
    "Other": 0,
}
DIRECTION_LABEL = {1: "up", -1: "down", 0: "either"}


def signal_id(s):
    return "|".join(str(s.get(k) or "") for k in ("detected_at", "ticker", "ref", "nct_id", "field", "type"))


def closes(symbol, start):
    try:
        df = yf.download(symbol, start=start, progress=False, auto_adjust=True)
    except Exception:
        return pd.Series(dtype=float)
    if df.empty:
        return pd.Series(dtype=float)
    c = df["Close"]
    c = c.iloc[:, 0] if isinstance(c, pd.DataFrame) else c
    return c.dropna()


def path(series, day, n=DAYS):
    """Cumulative % move from the last close before `day` to each of the next n trading days."""
    before, after = series[series.index < day], series[series.index >= day]
    if before.empty or after.empty:
        return []
    base = float(before.iloc[-1])
    return [round((float(v) / base - 1) * 100, 3) for v in after.iloc[:n]]


def trading_days_between(series, start, end):
    """Number of trading days on/after `start` and before `end`."""
    return int(((series.index >= start) & (series.index < end)).sum())


def moves(series, day):
    """% moves from the last close before `day` to N trading days on (day itself = day 1)."""
    before, after = series[series.index < day], series[series.index >= day]
    if before.empty or after.empty:
        return {}
    base = float(before.iloc[-1])
    return {n: round((float(after.iloc[n - 1]) / base - 1) * 100, 2) for n in HORIZONS if len(after) >= n}


def summarise(rows):
    """Per horizon: average move vs the market, and (for signals with an expected
    direction) how often the price moved the way the signal suggested."""
    out = {}
    for n in HORIZONS:
        vals = [r[f"excess_{n}d"] for r in rows if r.get(f"excess_{n}d") is not None]
        if not vals:
            continue
        s = pd.Series(vals)
        h = {"n": len(vals), "mean_excess": round(float(s.mean()), 2),
             "median_excess": round(float(s.median()), 2),
             "beat_market_pct": round(float((s > 0).mean() * 100), 1)}
        aligned = [r[f"aligned_{n}d"] for r in rows if r.get(f"aligned_{n}d") is not None]
        if aligned:
            a = pd.Series(aligned)
            h["expected_pct"] = round(float((a > 0).mean() * 100), 1)
            h["mean_aligned"] = round(float(a.mean()), 2)
            h["n_directional"] = len(aligned)
        out[f"{n}d"] = h
    return out


def summarise_directional(rows):
    """Headline numbers across every signal with a clear expected direction, with bad-news
    signals flipped so that 'right' is always positive."""
    out = {}
    for n in HORIZONS:
        a = [r[f"aligned_{n}d"] for r in rows if r.get(f"aligned_{n}d") is not None]
        if a:
            s = pd.Series(a)
            out[f"{n}d"] = {"n": len(a), "expected_pct": round(float((s > 0).mean() * 100), 1),
                           "mean_aligned": round(float(s.mean()), 2)}
    return out


def drift(rows):
    """Average direction-adjusted path, day 1..20 after the information became public,
    plus how much of the move came late, and how much was still to come after RiverScan's signal."""
    paths = [r["aligned_path"] for r in rows if r.get("aligned_path")]
    if not paths:
        return None
    curve = []
    for k in range(DAYS):
        vals = [p[k] for p in paths if len(p) > k]
        if vals:
            curve.append({"day": k + 1, "mean": round(sum(vals) / len(vals), 2), "n": len(vals)})
    full = [p for p in paths if len(p) >= DAYS]
    out = {"curve": curve, "signals": len(paths), "full_20d": len(full)}
    if full:
        m1 = sum(p[0] for p in full) / len(full)
        m20 = sum(p[DAYS - 1] for p in full) / len(full)
        out["day1_mean"], out["day20_mean"] = round(m1, 2), round(m20, 2)
        if m20 > 0:
            out["late_share_pct"] = round(max(0.0, (m20 - m1) / m20) * 100, 1)  # share of the 20-day move after day 1
    after = []
    for r in rows:
        p, lag = r.get("aligned_path"), r.get("days_to_signal")
        if p and lag is not None and lag < DAYS and len(p) >= DAYS:
            at_signal = p[lag - 1] if lag > 0 else 0.0
            after.append(p[DAYS - 1] - at_signal)
    if after:
        out["after_signal"] = {"n": len(after), "mean": round(sum(after) / len(after), 2),
                               "expected_pct": round(100 * sum(1 for x in after if x > 0) / len(after), 1)}
    lags = sorted(r["days_to_signal"] for r in rows if r.get("days_to_signal") is not None)
    if lags:
        out["median_days_to_signal"] = lags[len(lags) // 2]
    return out


def main():
    sig_file = DATA / "signals.json"
    signals = json.loads(sig_file.read_text()) if sig_file.exists() else []
    tracked = [s for s in signals if s["severity"] in {"high", "medium"}]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows = []
    if tracked:
        start = (pd.Timestamp(min(s["detected_at"][:10] for s in tracked)) - pd.Timedelta(days=10)).date().isoformat()
        cache = {}

        def get(sym):
            if sym not in cache:
                cache[sym] = closes(sym, start)
            return cache[sym]

        for s in tracked:
            stream = s.get("stream", "trials")
            sym = YAHOO.get(s["ticker"], s["ticker"].rstrip(".") + ".L")
            bench = BENCH.get(s["ticker"], DEFAULT_BENCH[stream])
            caught = pd.Timestamp(s["detected_at"][:10])
            public = pd.Timestamp((s.get("published") or s["detected_at"])[:10])
            if public > caught:
                public = caught
            sp, ip = path(get(sym), public), path(get(bench), public)
            excess_path = [round(a - b, 3) for a, b in zip(sp, ip)]
            stock = {n: sp[n - 1] for n in HORIZONS if len(sp) >= n}
            idx = {n: ip[n - 1] for n in HORIZONS if len(ip) >= n}
            lag = trading_days_between(get(sym), public, caught) if sp else None
            cat = category(s)
            row = {"id": signal_id(s), "detected_at": s["detected_at"], "ticker": s["ticker"], "stream": stream,
                   "category": cat, "expected": DIRECTION_LABEL[EXPECTED.get(cat, 0)], "severity": s["severity"], "ref": s.get("ref") or s.get("nct_id"),
                   "note": s.get("note"), "benchmark": BENCH_NAME.get(bench, bench), "price_data": bool(stock),
                   "public_date": public.date().isoformat(), "days_to_signal": lag}
            d = EXPECTED.get(cat, 0)
            row["aligned_path"] = [round(x * d, 3) for x in excess_path] if d else None
            for n in HORIZONS:
                row[f"stock_{n}d"] = stock.get(n)
                row[f"index_{n}d"] = idx.get(n)
                row[f"excess_{n}d"] = round(stock[n] - idx[n], 2) if n in stock and n in idx else None
                d = EXPECTED.get(cat, 0)
                # "in the expected direction": positive means the price moved the way the signal suggested
                row[f"aligned_{n}d"] = round(row[f"excess_{n}d"] * d, 2) if d and row[f"excess_{n}d"] is not None else None
            rows.append(row)

    df = pd.DataFrame(rows)
    if not df.empty:
        df.drop(columns=["aligned_path"]).to_csv(DATA / "track_record_full.csv", index=False)

    with5 = [r for r in rows if r.get("excess_5d") is not None]
    ready = len(with5) >= TRACK_RECORD_MIN_SIGNALS
    report = {
        "updated": now,
        "public": bool(TRACK_RECORD_PUBLIC and ready),
        "signals_tracked": len(rows),
        "with_5d_result": len(with5),
        "with_20d_result": sum(1 for r in rows if r.get("excess_20d") is not None),
        "no_price_data": sorted({r["ticker"] for r in rows if not r["price_data"]}),
        "min_signals": TRACK_RECORD_MIN_SIGNALS,
        "min_group": TRACK_RECORD_MIN_GROUP,
        "horizons": HORIZONS,
    }
    report["drift"] = drift(rows) if report["public"] else None
    if report["public"]:
        groups = {}
        for r in rows:
            groups.setdefault(r["category"], []).append(r)
        report["overall"] = summarise_directional(rows)
        report["categories"] = [
            {"category": cat, "stream": rs[0]["stream"], "expected": rs[0]["expected"], "signals": len(rs), **summarise(rs)}
            for cat, rs in sorted(groups.items(), key=lambda kv: -len(kv[1]))
            if sum(1 for r in rs if r.get("excess_5d") is not None) >= TRACK_RECORD_MIN_GROUP
        ]
        report["signals"] = {r["id"]: {f"excess_{n}d": r[f"excess_{n}d"] for n in HORIZONS} | {"benchmark": r["benchmark"]}
                             for r in rows if r.get("excess_1d") is not None}
    (DATA / "track_record.json").write_text(json.dumps(report, indent=1))
    print(json.dumps({k: v for k, v in report.items() if k not in ("signals", "categories")}, indent=1))
    if report.get("categories"):
        for c in report["categories"]:
            print(c["category"], c.get("5d"))


if __name__ == "__main__":
    main()
