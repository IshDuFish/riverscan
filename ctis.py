"""Pull trials from the EU Clinical Trials Information System (CTIS).

Public JSON API used by euclinicaltrials.eu, no key needed.
  search:   POST /ctis-public-api/search
  detail:   GET  /ctis-public-api/retrieve/<EU CT number>
"""
import json
import re
import time

from net import request

BASE = "https://euclinicaltrials.eu/ctis-public-api"


def _date(v):
    """CTIS mixes 'dd/mm/yyyy' and ISO dates; return ISO yyyy-mm-dd."""
    if not v:
        return None
    m = re.match(r"(\d{2})/(\d{2})/(\d{4})", v)
    return f"{m.group(3)}-{m.group(2)}-{m.group(1)}" if m else v[:10]


def search(term):
    out, page = [], 1
    while True:
        body = {"pagination": {"page": page, "size": 50},
                "sort": {"property": "decisionDate", "direction": "DESC"},
                "searchCriteria": {"sponsor": term}}
        d = request("POST", f"{BASE}/search", json=body).json()
        out += d.get("data", [])
        if not d.get("pagination", {}).get("nextPage"):
            return out
        page += 1


def simplify(summary, detail):
    ct = summary["ctNumber"]
    events = (detail or {}).get("events") or {}
    auth = (detail or {}).get("authorizedApplication") or {}
    part1 = auth.get("authorizedPartI") or {}
    ids_blob = json.dumps((part1.get("trialDetails") or {}).get("clinicalTrialIdentifiers") or {}) + \
        json.dumps((part1.get("trialDetails") or {}).get("associatedClinicalTrials") or [])
    xrefs = set(re.findall(r"NCT\d{8}", ids_blob)) | {f"ISRCTN{n}" for n in re.findall(r"ISRCTN\s?(\d{8})", ids_blob)}
    eudract = (auth.get("eudraCt") or {}).get("eudraCtCode")
    if eudract:
        xrefs.add(eudract)
    return {
        "id": ct,
        "title": summary.get("ctTitle") or summary.get("shortTitle") or "",
        "sponsors": [summary.get("sponsor") or ""],
        "status": (detail or {}).get("ctStatus") or str(summary.get("ctStatus")),
        "phase": summary.get("trialPhase"),
        "enrollment": summary.get("totalNumberEnrolled"),
        "end_date": _date(summary.get("endDateEU")),
        "member_states": len(auth.get("memberStatesConcerned") or []) or None,
        "halts": len(events.get("temporaryHaltList") or []),
        "safety_measures": len(events.get("urgentSafetyMeasures") or []),
        "serious_breaches": len(events.get("seriousBreaches") or []),
        "has_results": bool(summary.get("resultsFirstReceived")),
        "last_update": _date(summary.get("lastUpdated")),
        "xrefs": sorted(xrefs),
        "url": f"https://euclinicaltrials.eu/search-for-clinical-trials/?lang=en&EUCT={ct}",
    }


def fetch_company(company, previous=None):
    terms = [t.lower() for t in company["sponsor_terms"]]
    trials = {}
    for term in company["sponsor_terms"]:
        for s in search(term):
            if not any(t in (s.get("sponsor") or "").lower() for t in terms) or s["ctNumber"] in trials:
                continue
            try:
                detail = request("GET", f"{BASE}/retrieve/{s['ctNumber']}").json()
            except Exception:
                detail = None
            if detail is None and previous and s["ctNumber"] in previous:
                trials[s["ctNumber"]] = previous[s["ctNumber"]]  # detail unavailable today: no false changes
                continue
            trials[s["ctNumber"]] = simplify(s, detail)
            time.sleep(0.5)
    return trials


def status_bucket(rec, today=None):
    s = (rec.get("status") or "").lower()
    if any(w in s for w in ("halt", "revoked", "withdrawn", "not authorised", "cancel", "suspend")):
        return "stopped"
    if "ended" in s or "completed" in s:
        return "ended"
    if any(w in s for w in ("authorised", "ongoing", "recruit")):
        return "active"
    return None
