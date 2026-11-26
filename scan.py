"""Daily run: pull every source, compare with the last snapshot, log signals.

    python scan.py

Sources
  trials     ClinicalTrials.gov, ISRCTN (UK), EU CTIS  -> changes to each trial
             plus registry mismatches between them
  contracts  Find a Tender + Contracts Finder            -> new awards to covered companies
"""
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import contracts
import fundamentals
import ctis
import isrctn
import mismatch
from config import TRIAL_COMPANIES, CONTRACT_COMPANIES, TRACKED_FIELDS, ISRCTN_FIELDS, CTIS_FIELDS
from diff import diff_all, sort_signals
from fetch import fetch_company as ctgov_fetch

DATA = Path(__file__).resolve().parent / "data"
SNAPS = DATA / "snapshots"
LATEST = SNAPS / "latest.json"
SIGNALS_JSON = DATA / "signals.json"
SIGNALS_CSV = DATA / "signals.csv"
CSV_FIELDS = ["detected_at", "stream", "source", "ticker", "company", "ref", "title", "type", "field",
              "old", "new", "severity", "note", "url"]

REGISTRIES = {
    # key: (label, fetch function, fields compared)
    "ctgov": ("ClinicalTrials.gov", lambda c, prev: ctgov_fetch(c), TRACKED_FIELDS),
    "isrctn": ("ISRCTN", lambda c, prev: isrctn.fetch_company(c), ISRCTN_FIELDS),
    "ctis": ("EU CTIS", lambda c, prev: ctis.fetch_company(c, prev), CTIS_FIELDS),
}


def load_json(path, default):
    return json.loads(path.read_text()) if path.exists() else default


def load_snapshot():
    snap = load_json(LATEST, {})
    if snap and "version" not in snap:  # v1 files held ClinicalTrials.gov data only, keyed by ticker
        snap = {"version": 2, "ctgov": snap}
    return snap


def fetch_registry(key, old, companies):
    label, fn, _ = REGISTRIES[key]
    new, ok = {}, 0
    for c in companies:
        t = c["ticker"]
        try:
            trials = fn(c, old.get(t))
        except Exception as e:  # network/API problem: keep yesterday's data, no false signals
            print(f"[warn] {label} {t}: fetch failed ({e}); carrying forward", file=sys.stderr)
            if t in old:
                new[t] = old[t]
            continue
        if not trials and old.get(t):
            print(f"[warn] {label} {t}: 0 trials returned (had {len(old[t])}); carrying forward", file=sys.stderr)
            new[t] = old[t]
            continue
        new[t] = trials
        ok += 1
        print(f"{label:18} {t:5} {len(trials):4} trials")
    return new, ok


def main():
    now = datetime.now(timezone.utc)
    stamp = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    today = now.strftime("%Y-%m-%d")
    old = load_snapshot()
    new = {"version": 2}
    signals = []

    # 0. Company sizes: only cover companies valued under the limit
    funds = fundamentals.update()
    trial_cos, trial_out = fundamentals.split(TRIAL_COMPANIES, funds)
    contract_cos, contract_out = fundamentals.split(CONTRACT_COMPANIES, funds)
    for c, why in trial_out + contract_out:
        print(f"[skip] {c['ticker']} {c['name']}: {why}")

    # 1. Trial registries
    for key, (label, _, fields) in REGISTRIES.items():
        old_reg = old.get(key, {})
        new[key], ok = fetch_registry(key, old_reg, trial_cos)
        if not old_reg:
            print(f"{label}: first run, saving baseline (no signals)")
            continue
        signals += diff_all(trial_cos, old_reg, new[key], stamp, fields, label)

    # 2. Registry mismatches
    current = mismatch.find(trial_cos, new, today)
    signals += mismatch.signals(current, set(old.get("mismatches", [])), stamp)
    new["mismatches"] = sorted(current)

    # 3. Government contracts
    c_signals, new["contracts"], errors = contracts.scan(old.get("contracts", {}), stamp,
                                                         companies=contract_cos, funds=funds)
    for e in errors:
        print(f"[warn] contracts {e}", file=sys.stderr)
    print(f"Contracts: {len(c_signals)} new award(s) to covered companies")
    signals += c_signals
    signals = sort_signals(signals)

    # Save
    SNAPS.mkdir(parents=True, exist_ok=True)
    body = json.dumps(new, indent=1, sort_keys=True)
    (SNAPS / f"{today}.json").write_text(body)
    LATEST.write_text(body)
    (DATA / "mismatches.json").write_text(json.dumps(list(current.values()), indent=1))
    coverage = {
        "updated": stamp,
        "trials": {lab: sum(len(v) for v in new[k].values()) for k, (lab, _, _) in REGISTRIES.items()},
        "max_market_cap": fundamentals.MAX_MARKET_CAP,
        "trial_companies": [c["ticker"] for c in trial_cos],
        "trial_detail": [{"ticker": c["ticker"], "name": c["name"], "market_cap": (funds.get(c["ticker"]) or {}).get("market_cap")} for c in trial_cos],
        "contract_companies": [{"ticker": c["ticker"], "name": c["name"], "sector": c["sector"],
                                "market_cap": (funds.get(c["ticker"]) or {}).get("market_cap")} for c in contract_cos],
        "excluded": [{"ticker": c["ticker"], "name": c["name"], "reason": why} for c, why in trial_out + contract_out],
        "open_mismatches": len(current),
    }
    (DATA / "coverage.json").write_text(json.dumps(coverage, indent=1))

    log = load_json(SIGNALS_JSON, [])
    if signals:
        log.extend(signals)
        new_file = not SIGNALS_CSV.exists()
        with SIGNALS_CSV.open("a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
            if new_file:
                w.writeheader()
            w.writerows(signals)
    SIGNALS_JSON.write_text(json.dumps(log, indent=1))

    print(f"{len(signals)} new signal(s)")
    for s in signals[:60]:
        print(f"  [{s['severity']}] {s['source']} {s['ticker']} {s.get('ref')}: {s['note']} {s['old']} -> {s['new']}")


if __name__ == "__main__":
    main()
