"""Daily run: fetch trials, compare with last snapshot, log signals.

    python scan.py
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from config import COMPANIES
from fetch import fetch_company
from diff import diff_all

DATA = Path(__file__).resolve().parent / "data"
SNAPS = DATA / "snapshots"
LATEST = SNAPS / "latest.json"
SIGNALS_JSON = DATA / "signals.json"
SIGNALS_CSV = DATA / "signals.csv"
CSV_FIELDS = ["detected_at", "ticker", "company", "nct_id", "trial", "type", "field",
              "old", "new", "severity", "note", "url"]


def load_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def main():
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    old = load_json(LATEST, {})

    new = {}
    for c in COMPANIES:
        t = c["ticker"]
        try:
            trials = fetch_company(c)
        except Exception as e:  # network/API problem: keep yesterday's data, no false signals
            print(f"[warn] {t}: fetch failed ({e}); carrying forward previous data", file=sys.stderr)
            if t in old:
                new[t] = old[t]
            continue
        if not trials and old.get(t):
            print(f"[warn] {t}: 0 trials returned (had {len(old[t])}); carrying forward", file=sys.stderr)
            new[t] = old[t]
            continue
        new[t] = trials
        print(f"{t}: {len(trials)} trials")

    signals = diff_all(COMPANIES, old, new, stamp)

    SNAPS.mkdir(parents=True, exist_ok=True)
    (SNAPS / f"{now:%Y-%m-%d}.json").write_text(json.dumps(new, indent=1, sort_keys=True))
    LATEST.write_text(json.dumps(new, indent=1, sort_keys=True))

    if signals:
        log = load_json(SIGNALS_JSON, [])
        log.extend(signals)
        SIGNALS_JSON.write_text(json.dumps(log, indent=1))
        new_file = not SIGNALS_CSV.exists()
        with SIGNALS_CSV.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
            if new_file:
                w.writeheader()
            w.writerows(signals)
    elif not SIGNALS_JSON.exists():
        SIGNALS_JSON.write_text("[]")

    print(f"{len(signals)} new signal(s)")
    for s in signals:
        print(f"  [{s['severity']}] {s['ticker']} {s['nct_id']}: {s['note']} {s['old']} -> {s['new']}")


if __name__ == "__main__":
    main()
