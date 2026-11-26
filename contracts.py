"""UK public contract awards, matched to London-listed suppliers.

Sources (both free, no key, OCDS format):
  Find a Tender   https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages
                  higher-value contracts, including central government and defence
  Contracts Finder https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search
                  English public sector contracts over £12k (£30k for some bodies)
"""
import re
from datetime import datetime, timedelta, timezone

from net import request
from config import CONTRACT_COMPANIES, CONTRACT_HIGH, CONTRACT_MEDIUM

SOURCES = {
    "Find a Tender": ("https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages", "updatedFrom", "updatedTo"),
    "Contracts Finder": ("https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search", "publishedFrom", "publishedTo"),
}
MAX_PAGES = 400
COMPILED = [(c, [re.compile(p, re.I) for p in c["supplier_patterns"]]) for c in CONTRACT_COMPANIES]


def _ts(d):
    return d.strftime("%Y-%m-%dT%H:%M:%S")


def releases(source, since, until):
    url, f_from, f_to = SOURCES[source]
    params = {f_from: _ts(since), f_to: _ts(until), "stages": "award", "limit": 100}
    pages = 0
    while url and pages < MAX_PAGES:
        d = request("GET", url, params=params, timeout=120).json()
        yield from d.get("releases", [])
        url = (d.get("links") or {}).get("next")
        params = None  # the next link already carries the query
        pages += 1


def match_company(name):
    n = " ".join((name or "").split())
    for c, pats in COMPILED:
        if any(p.search(n) for p in pats):
            return c
    return None


def _value(release, award):
    v = award.get("value") or {}
    if not v.get("amount"):
        for k in release.get("contracts") or []:
            if k.get("awardID") == award.get("id") and (k.get("value") or {}).get("amount"):
                v = k["value"]
                break
    if not v.get("amount"):
        v = (release.get("tender") or {}).get("value") or {}
    return v.get("amount"), v.get("currency") or "GBP"


def _url(source, release):
    if source == "Find a Tender":
        for link in release.get("links") or []:
            if "find-tender" in (link.get("href") or ""):
                return link["href"]
        return f"https://www.find-tender.service.gov.uk/Notice/{release['id']}"
    guid = release.get("ocid", "").replace("ocds-b5fd17-", "")
    return f"https://www.contractsfinder.service.gov.uk/Notice/{guid}"


def severity(amount):
    if amount and amount >= CONTRACT_HIGH:
        return "high"
    if amount and amount >= CONTRACT_MEDIUM:
        return "medium"
    return "low"


def money(amount, currency="GBP"):
    if not amount:
        return "value not stated"
    sym = "£" if currency == "GBP" else (currency + " ")
    for div, unit in ((1e9, "bn"), (1e6, "m"), (1e3, "k")):
        if amount >= div:
            return f"{sym}{amount / div:.1f}{unit}".replace(".0", "")
    return f"{sym}{amount:,.0f}"


def scan(state, detected_at, now=None, backfill_days=14):
    """Return (signals, new_state). `state` holds the last run time and award keys already logged."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    last = state.get("last_run")
    since = (datetime.fromisoformat(last) - timedelta(days=1)) if last else now - timedelta(days=backfill_days)
    seen = state.get("seen", {})
    if isinstance(seen, list):
        seen = {k: now.date().isoformat() for k in seen}
    signals, errors = [], []
    for source in SOURCES:
        scanned = 0
        try:
            for rel in releases(source, since, now):
                scanned += 1
                buyer = (rel.get("buyer") or {}).get("name") or "a public body"
                tender = rel.get("tender") or {}
                for award in rel.get("awards") or []:
                    for sup in award.get("suppliers") or []:
                        c = match_company(sup.get("name"))
                        if not c:
                            continue
                        key = f"{rel.get('ocid')}|{award.get('id')}|{c['ticker']}"
                        if key in seen:
                            continue
                        seen[key] = now.date().isoformat()
                        amount, cur = _value(rel, award)
                        title = award.get("title") or tender.get("title") or "Untitled contract"
                        signals.append({
                            "detected_at": detected_at, "stream": "contracts", "source": source,
                            "ticker": c["ticker"], "company": c["name"], "sector": c["sector"],
                            "ref": rel.get("id"), "title": title, "type": "contract_award",
                            "field": None, "old": None, "new": amount, "currency": cur,
                            "buyer": buyer, "supplier": sup.get("name"),
                            "published": (rel.get("date") or "")[:10],
                            "severity": severity(amount),
                            "note": f"Awarded {money(amount, cur)} contract by {buyer}",
                            "url": _url(source, rel),
                        })
        except Exception as e:  # one source down shouldn't stop the other
            errors.append(f"{source}: {e}")
        print(f"{source:18} scanned {scanned} award notices since {since:%Y-%m-%d %H:%M}")
    new_state = {"last_run": now.isoformat(timespec="seconds") if not errors else (last or since.isoformat(timespec="seconds")),
                 "seen": {k: d for k, d in seen.items() if d >= (now - timedelta(days=45)).date().isoformat()}}
    return signals, new_state, errors
