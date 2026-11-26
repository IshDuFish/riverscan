"""Compare two snapshots and turn the differences into signals."""
from config import TRACKED_FIELDS, BAD_STATUSES

DATE_FIELDS = {"primary_completion", "completion", "recruitment_start", "recruitment_end", "overall_end", "end_date"}
ENROL_FIELDS = {"enrollment", "target_enrolment", "final_enrolment"}
SAFETY_FIELDS = {"halts", "safety_measures", "serious_breaches"}
SOURCE_URL_KEY = {"ClinicalTrials.gov": "nct_id"}


def _severity(field, old, new):
    if field in ("status", "status_override"):
        n = str(new or "").upper()
        if n in BAD_STATUSES or any(b in n for b in ("HALT", "STOPPED", "SUSPEND", "TERMINAT", "WITHDRAW", "REVOKED")):
            return "high"
        if n in {"COMPLETED", "ACTIVE_NOT_RECRUITING"} or "ENDED" in n:
            return "medium"
        return "low"
    if field == "has_results" and new:
        return "high"
    if field in SAFETY_FIELDS:
        return "high" if (new or 0) > (old or 0) else "low"
    if field in DATE_FIELDS:
        return "medium"  # timelines slipping or being pulled forward
    if field in ENROL_FIELDS and isinstance(old, int) and isinstance(new, int) and old:
        change = abs(new - old) / old
        return "medium" if change >= 0.2 else "low"
    if field == "phase":
        return "high" if old and new else "low"
    if field == "member_states":
        return "medium" if (new or 0) > (old or 0) else "low"
    return "low"


def _signal(company, trial, kind, field, old, new, severity, detected_at, note, source):
    rid = trial.get("id") or trial.get("nct_id")
    s = {
        "detected_at": detected_at,
        "stream": "trials",
        "source": source,
        "ticker": company["ticker"],
        "company": company["name"],
        "ref": rid,
        "title": trial.get("title", ""),
        "type": kind,
        "field": field,
        "old": old,
        "new": new,
        "severity": severity,
        "note": note,
        "url": trial["url"],
        "published": trial.get("last_update"),  # when the registry says the record changed
    }
    if source == "ClinicalTrials.gov":  # keep the original keys for older readers
        s["nct_id"], s["trial"] = rid, s["title"]
    return s


def diff_company(company, old_trials, new_trials, detected_at, fields=None, source="ClinicalTrials.gov"):
    fields = fields or TRACKED_FIELDS
    signals = []
    for tid, new in new_trials.items():
        old = old_trials.get(tid)
        if old is None:
            signals.append(_signal(company, new, "new_trial", None, None, new.get("status") or new.get("status_override"),
                                   "medium", detected_at, f"New {new.get('phase') or ''} trial registered".replace("  ", " "), source))
            continue
        for field, label in fields.items():
            if field not in old:
                continue  # field added in a later version of the scanner: not a real change
            if old.get(field) != new.get(field):
                note = label + " changed"
                if field == "status" and new.get("why_stopped"):
                    note += f" (reason given: {new['why_stopped']})"
                signals.append(_signal(company, new, "change", field, old.get(field), new.get(field),
                                       _severity(field, old.get(field), new.get(field)), detected_at, note, source))
    for tid, old in old_trials.items():
        if tid not in new_trials:
            signals.append(_signal(company, old, "removed", None, old.get("status"), None,
                                   "low", detected_at, "Trial no longer returned by the registry search", source))
    return signals


def diff_all(companies, old_snapshot, new_snapshot, detected_at, fields=None, source="ClinicalTrials.gov"):
    signals = []
    for c in companies:
        t = c["ticker"]
        if t not in old_snapshot:
            continue  # first time we've seen this company: baseline only, no signals
        signals += diff_company(c, old_snapshot[t], new_snapshot.get(t, {}), detected_at, fields, source)
    return sort_signals(signals)


def sort_signals(signals):
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(signals, key=lambda s: (order[s["severity"]], s["ticker"]))
