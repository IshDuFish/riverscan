"""Registry mismatches: the same trial saying different things in different registries.

Trials are linked through the cross-references each registry records
(NCT numbers, ISRCTN numbers, EudraCT / EU CT numbers). Each linked record is
put into a rough bucket (active / ended / stopped) and pairs where one registry
says the trial is still running and another says it is over are reported. A signal is raised the first time a mismatch appears.
"""
import re

import ctis
import isrctn

NCT = re.compile(r"NCT\d{8}")
ISR = re.compile(r"ISRCTN\s?(\d{8})", re.I)
EU = re.compile(r"\d{4}-\d{6}-\d{2}(?:-\d{2})?")


def ctgov_bucket(rec, today=None):
    s = (rec.get("status") or "").upper()
    if s in {"TERMINATED", "WITHDRAWN", "SUSPENDED"}:
        return "stopped"
    if s == "COMPLETED":
        return "ended"
    if s in {"NOT_YET_RECRUITING", "RECRUITING", "ENROLLING_BY_INVITATION", "ACTIVE_NOT_RECRUITING"}:
        return "active"
    return None


def _ids(text):
    out = set(NCT.findall(text)) | {f"ISRCTN{n}" for n in ISR.findall(text)}
    out |= {m[:14] for m in EU.findall(text)}  # compare on the yyyy-nnnnnn-nn stem
    return out


def find(companies, snaps, today):
    """snaps: {"ctgov": {...}, "isrctn": {...}, "ctis": {...}} -> {key: mismatch dict}"""
    label = {"ctgov": "ClinicalTrials.gov", "isrctn": "ISRCTN", "ctis": "EU CTIS"}
    bucket = {"ctgov": ctgov_bucket, "isrctn": isrctn.status_bucket, "ctis": ctis.status_bucket}
    shown = {"ctgov": lambda r: r.get("status"),
             "isrctn": lambda r: r.get("status_override") or bucket["isrctn"](r, today),
             "ctis": lambda r: r.get("status")}
    out = {}
    for c in companies:
        t = c["ticker"]
        recs = []  # (registry, record, identifiers)
        for reg in ("ctgov", "isrctn", "ctis"):
            for rid, rec in (snaps.get(reg, {}).get(t) or {}).items():
                ids = {rid} | _ids(" ".join(rec.get("xrefs") or []))
                if reg == "ctis":
                    ids.add(rid[:14])
                recs.append((reg, rec, ids))
        for i in range(len(recs)):
            for j in range(i + 1, len(recs)):
                (ra, a, ia), (rb, b, ib) = recs[i], recs[j]
                if ra == rb or not (ia & ib):
                    continue
                ba, bb = bucket[ra](a, today), bucket[rb](b, today)
                # Only flag open-vs-closed disagreements. "Ended" in one registry and "Terminated"
                # in another both mean the trial is over, so that is not a mismatch.
                if not ba or not bb or (ba == "active") == (bb == "active"):
                    continue
                ida, idb = a.get("id") or a.get("nct_id"), b.get("id") or b.get("nct_id")
                key = "|".join(sorted([f"{ra}:{ida}", f"{rb}:{idb}"]))
                out[key] = {
                    "ticker": t, "company": c["name"], "title": a.get("title") or b.get("title"),
                    "a": {"registry": label[ra], "id": ida, "status": shown[ra](a), "bucket": ba, "url": a["url"]},
                    "b": {"registry": label[rb], "id": idb, "status": shown[rb](b), "bucket": bb, "url": b["url"]},
                }
    return out


def signals(current, previous_keys, detected_at):
    sigs = []
    for key, m in current.items():
        if key in previous_keys:
            continue
        a, b = m["a"], m["b"]
        sev = "high" if "stopped" in (a["bucket"], b["bucket"]) else "medium"
        sigs.append({
            "detected_at": detected_at, "stream": "trials", "source": f"{a['registry']} vs {b['registry']}",
            "ticker": m["ticker"], "company": m["company"], "ref": f"{a['id']} / {b['id']}",
            "title": m["title"], "type": "mismatch", "field": "status",
            "old": f"{a['registry']}: {a['status']}", "new": f"{b['registry']}: {b['status']}",
            "severity": sev, "note": "Registries disagree on this trial's status",
            "url": a["url"], "url2": b["url"],
        })
    return sigs
