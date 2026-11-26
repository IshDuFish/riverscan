"""Pull trials from the ClinicalTrials.gov v2 API (free, no key needed)."""
import re
import time
import requests

from net import SESSION

API = "https://clinicaltrials.gov/api/v2/studies"


def _get(d, *path, default=None):
    for key in path:
        if not isinstance(d, dict):
            return default
        d = d.get(key)
    return default if d is None else d


def simplify(study):
    """Turn one raw API study into the flat record we store and compare."""
    p = study.get("protocolSection", {})
    sponsors = [_get(p, "sponsorCollaboratorsModule", "leadSponsor", "name", default="")]
    sponsors += [c.get("name", "") for c in _get(p, "sponsorCollaboratorsModule", "collaborators", default=[])]
    nct = _get(p, "identificationModule", "nctId")
    return {
        "nct_id": nct,
        "title": _get(p, "identificationModule", "briefTitle", default=""),
        "sponsors": [s for s in sponsors if s],
        "status": _get(p, "statusModule", "overallStatus"),
        "why_stopped": _get(p, "statusModule", "whyStopped"),
        "phase": "/".join(_get(p, "designModule", "phases", default=[])) or None,
        "enrollment": _get(p, "designModule", "enrollmentInfo", "count"),
        "primary_completion": _get(p, "statusModule", "primaryCompletionDateStruct", "date"),
        "completion": _get(p, "statusModule", "completionDateStruct", "date"),
        "last_update": _get(p, "statusModule", "lastUpdatePostDateStruct", "date"),
        "has_results": bool(study.get("hasResults", False)),
        "url": f"https://clinicaltrials.gov/study/{nct}",
        # Other registry IDs for the same trial (ISRCTN, EU CT / EudraCT), used to spot mismatches.
        "xrefs": sorted({i.get("id", "").strip() for i in _get(p, "identificationModule", "secondaryIdInfos", default=[])
                         if i.get("id") and re.search(r"ISRCTN\d{8}|\d{4}-\d{6}-\d{2}", i.get("id", ""))}),
    }


def fetch_company(company, session=None):
    """All trials where this company is lead sponsor or collaborator."""
    s = session or SESSION
    terms = [t.lower() for t in company["sponsor_terms"]]
    trials = {}
    for term in company["sponsor_terms"]:
        params = {"query.spons": term, "pageSize": 200}
        while True:
            for attempt in range(3):
                try:
                    r = s.get(API, params=params, timeout=30)
                    r.raise_for_status()
                    break
                except requests.RequestException:
                    if attempt == 2:
                        raise
                    time.sleep(5 * (attempt + 1))
            data = r.json()
            for study in data.get("studies", []):
                rec = simplify(study)
                # The API search is fuzzy, so keep only real sponsor matches.
                if rec["nct_id"] and any(t in s_.lower() for s_ in rec["sponsors"] for t in terms):
                    trials[rec["nct_id"]] = rec
            token = data.get("nextPageToken")
            if not token:
                break
            params["pageToken"] = token
        time.sleep(1)  # be polite to the API
    return trials


def fetch_all(companies):
    """{ticker: {nct_id: record}}"""
    return {c["ticker"]: fetch_company(c) for c in companies}
