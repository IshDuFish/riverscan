"""Compare two snapshots and turn the differences into signals."""
from .config import TRACKED_FIELDS, BAD_STATUSES


def _severity(field, old, new):
    if field == "status":
        if new in BAD_STATUSES:
            return "high"
        if new in {"COMPLETED", "ACTIVE_NOT_RECRUITING"}:
            return "medium"
        return "low"
    if field == "has_results" and new:
        return "high"
    if field in {"primary_completion", "completion"}:
        return "medium"  # timelines slipping or being pulled forward
    if field == "enrollment" and isinstance(old, int) and isinstance(new, int) and old:
        change = abs(new - old) / old
        return "medium" if change >= 0.2 else "low"
    if field == "phase":
        return "high"
    return "low"


def _signal(company, trial, kind, field, old, new, severity, detected_at, note=None):
    return {
        "detected_at": detected_at,
        "ticker": company["ticker"],
        "company": company["name"],
        "nct_id": trial["nct_id"],
        "trial": trial["title"],
        "type": kind,
        "field": field,
        "old": old,
        "new": new,
        "severity": severity,
        "note": note,
        "url": trial["url"],
    }


def diff_company(company, old_trials, new_trials, detected_at):
    signals = []
    for nct, new in new_trials.items():
        old = old_trials.get(nct)
        if old is None:
            signals.append(_signal(company, new, "new_trial", None, None, new.get("status"),
                                   "medium", detected_at, f"New {new.get('phase') or ''} trial registered".replace("  ", " ")))
            continue
        for field, label in TRACKED_FIELDS.items():
            if old.get(field) != new.get(field):
                note = label + " changed"
                if field == "status" and new.get("why_stopped"):
                    note += f" (reason given: {new['why_stopped']})"
                signals.append(_signal(company, new, "change", field, old.get(field), new.get(field),
                                       _severity(field, old.get(field), new.get(field)), detected_at, note))
    for nct, old in old_trials.items():
        if nct not in new_trials:
            signals.append(_signal(company, old, "removed", None, old.get("status"), None,
                                   "low", detected_at, "Trial no longer returned by the registry search"))
    return signals


def diff_all(companies, old_snapshot, new_snapshot, detected_at):
    signals = []
    for c in companies:
        t = c["ticker"]
        if t not in old_snapshot:
            continue  # first time we've seen this company: baseline only, no signals
        signals += diff_company(c, old_snapshot[t], new_snapshot.get(t, {}), detected_at)
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(signals, key=lambda s: (order[s["severity"]], s["ticker"]))
