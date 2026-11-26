"""Pull trials from the ISRCTN registry (the UK's clinical study registry).

Public XML API, no key needed: https://www.isrctn.com/api/query/format/default
Query syntax is field-scoped, e.g.  sponsor:"Scancell" OR funder:"Scancell"
"""
import re
import xml.etree.ElementTree as ET

from net import request

API = "https://www.isrctn.com/api/query/format/default"
NS = {"i": "http://www.67bricks.com/isrctn"}


def _t(el, path):
    found = el.find(path, NS) if el is not None else None
    return (found.text or "").strip() or None if found is not None else None


def _date(v):
    return v[:10] if v else None


def _int(v):
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return None


def simplify(full):
    """One <fullTrial> element -> the flat record we store and compare."""
    trial = full.find("i:trial", NS)
    num = _t(trial, "i:isrctn")
    isrctn = f"ISRCTN{num}" if num else None
    orgs = [o.text.strip() for o in full.findall(".//i:sponsor/i:organisation", NS) if o.text]
    orgs += [o.text.strip() for o in full.findall(".//i:funder/i:name", NS) if o.text]
    phases = sorted({p.text.strip() for p in trial.findall(".//i:intervention/i:phase", NS) if p.text})
    res = trial.find("i:results", NS)
    has_results = res is not None and any(
        (res.find(f"i:{tag}", NS) is not None and (res.find(f"i:{tag}", NS).text or "").strip())
        for tag in ("publicationDetails", "basicReport", "plainEnglishReport", "publicationStage"))
    ext = trial.find("i:externalRefs", NS)
    xrefs = [v for v in (_t(ext, "i:clinicalTrialsGovNumber"), _t(ext, "i:eudraCTNumber"), _t(ext, "i:ctisNumber")) if v]
    return {
        "id": isrctn,
        "title": _t(trial, ".//i:trialDescription/i:title") or "",
        "sponsors": orgs,
        "status_override": _t(trial, ".//i:participants/i:recruitmentStatusOverride"),
        "phase": "/".join(phases) or None,
        "target_enrolment": _int(_t(trial, ".//i:participants/i:targetEnrolment")),
        "final_enrolment": _int(_t(trial, ".//i:participants/i:totalFinalEnrolment")),
        "recruitment_start": _date(_t(trial, ".//i:participants/i:recruitmentStart")),
        "recruitment_end": _date(_t(trial, ".//i:participants/i:recruitmentEnd")),
        "overall_end": _date(_t(trial, ".//i:trialDesign/i:overallEndDate")),
        "has_results": has_results,
        "last_update": _date(trial.get("lastUpdated")),
        "xrefs": sorted(set(xrefs)),
        "url": f"https://www.isrctn.com/{isrctn}",
    }


def fetch_company(company):
    terms = [t.lower() for t in company["sponsor_terms"]]
    q = " OR ".join(f'sponsor:"{t}" OR funder:"{t}"' for t in company["sponsor_terms"])
    r = request("GET", API, params={"q": q, "limit": 100})
    root = ET.fromstring(r.content)
    trials = {}
    for full in root.findall("i:fullTrial", NS):
        rec = simplify(full)
        if rec["id"] and any(t in s.lower() for s in rec["sponsors"] for t in terms):
            trials[rec["id"]] = rec
    return trials


def status_bucket(rec, today):
    """Rough status for cross-registry comparison: active / ended / stopped / None."""
    o = (rec.get("status_override") or "").lower()
    if any(w in o for w in ("stopped", "suspended", "withdrawn", "terminated")):
        return "stopped"
    end = rec.get("overall_end")
    if end and end < today:
        return "ended"
    if rec.get("recruitment_start"):
        return "active"
    return None


ISRCTN_RE = re.compile(r"ISRCTN\s?(\d{8})", re.I)
