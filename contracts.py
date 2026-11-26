"""UK public contract awards, matched to London-listed suppliers.

Sources (both free, no key, OCDS format):
  Find a Tender   https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages
                  higher-value contracts, including central government and defence
  Contracts Finder https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search
                  English public sector contracts over £12k (£30k for some bodies)
"""
import json
import re
from datetime import datetime, timedelta, timezone

from net import request
from config import CONTRACT_COMPANIES, CONTRACT_HIGH, CONTRACT_MEDIUM, MATERIALITY_HIGH, MATERIALITY_MEDIUM

SOURCES = {
    "Find a Tender": ("https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages", "updatedFrom", "updatedTo"),
    "Contracts Finder": ("https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search", "publishedFrom", "publishedTo"),
}
MAX_PAGES = 400
CF_URL = re.compile(r"https://www\.contractsfinder\.service\.gov\.uk/Notice/[0-9a-fA-F-]{36}")
def compile_patterns(companies):
    return [(c, [re.compile(p, re.I) for p in c["supplier_patterns"]]) for c in companies]


COMPILED = compile_patterns(CONTRACT_COMPANIES)


def _ts(d):
    return d.strftime("%Y-%m-%dT%H:%M:%S")


def releases(source, since, until):
    url, f_from, f_to = SOURCES[source]
    # No "stages" filter: on Find a Tender it drops most award notices, so filter by tag here instead.
    params = {f_from: _ts(since), f_to: _ts(until), "limit": 100}
    pages = 0
    while url and pages < MAX_PAGES:
        d = request("GET", url, params=params, timeout=120).json()
        for rel in d.get("releases", []):
            if any(t.startswith(("award", "contract")) and "Termination" not in t for t in rel.get("tag") or []):
                yield rel
        url = (d.get("links") or {}).get("next")
        params = None  # the next link already carries the query
        pages += 1


def match_company(name, compiled=None):
    n = " ".join((name or "").split())
    for c, pats in (COMPILED if compiled is None else compiled):
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
    m = CF_URL.search(json.dumps(release))
    return m.group(0) if m else f"https://www.contractsfinder.service.gov.uk/Notice/{release.get('id', '')[:36]}"


def _years(release, award):
    """Contract length in years (at least 1), from whichever period the notice gives."""
    periods = [award.get("contractPeriod")] + [k.get("period") for k in release.get("contracts") or []
                                               if k.get("awardID") == award.get("id")] + [(release.get("tender") or {}).get("contractPeriod")]
    for p in periods:
        if p and p.get("startDate") and p.get("endDate"):
            try:
                a = datetime.fromisoformat(p["startDate"][:10])
                b = datetime.fromisoformat(p["endDate"][:10])
                return max(1.0, (b - a).days / 365.25)
            except ValueError:
                continue
        if p and p.get("durationInDays"):
            return max(1.0, p["durationInDays"] / 365.25)
    return None


def materiality(annual_value, revenue):
    """Contract value per year as a share of the winner's annual revenue."""
    if not annual_value or not revenue:
        return None
    return annual_value / revenue


def severity_by_share(share):
    if share is None:
        return None
    return "high" if share >= MATERIALITY_HIGH else "medium" if share >= MATERIALITY_MEDIUM else "low"


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


def scan(state, detected_at, now=None, backfill_days=14, companies=None, funds=None):
    """Return (signals, new_state, errors). `state` holds the last run time and award keys already logged.
    `companies` limits matching to the companies currently covered; `funds` gives their revenue."""
    compiled = compile_patterns(companies) if companies is not None else COMPILED
    funds = funds or {}
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)
    last = state.get("last_run")
    since = (datetime.fromisoformat(last) - timedelta(days=1)) if last else now - timedelta(days=backfill_days)
    tickers = sorted(c["ticker"] for c in (companies if companies is not None else CONTRACT_COMPANIES))
    if last and ("covered" not in state or set(tickers) - set(state["covered"])):
        since = min(since, now - timedelta(days=backfill_days))  # newly covered companies: look back two weeks
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
                tech = tender.get("techniques") or {}
                # Group this notice's awards (lots) by covered company: one signal per company per notice.
                hits = {}
                for award in rel.get("awards") or []:
                    sups = award.get("suppliers") or []
                    for sup in sups:
                        c = match_company(sup.get("name"), compiled)
                        if c:
                            h = hits.setdefault(c["ticker"], {"c": c, "awards": [], "shared": False, "suppliers": 1, "supplier": sup.get("name")})
                            h["awards"].append(award)
                            h["shared"] = h["shared"] or len(sups) > 1
                            h["suppliers"] = max(h["suppliers"], len(sups))
                for ticker, h in hits.items():
                    key = f"{rel.get('ocid')}|{ticker}"
                    if key in seen:
                        continue
                    seen[key] = now.date().isoformat()
                    c, awards = h["c"], h["awards"]
                    vals = [_value(rel, a) for a in awards]
                    amount = max((v[0] for v in vals if v[0]), default=None)
                    cur = next((v[1] for v in vals if v[0] == amount), "GBP")
                    names = " ".join([tender.get("title") or ""] + [a.get("title") or "" for a in awards]).lower()
                    framework = (h["shared"] or bool(tech.get("hasFrameworkAgreement") or tech.get("hasDynamicPurchasingSystem"))
                                 or "framework" in names or "dynamic purchasing" in names)
                    lots = f" ({len(awards)} lots)" if len(awards) > 1 else ""
                    # How big is this for the company? Value per year, as a share of annual revenue.
                    # On a shared framework, assume an equal split between the named suppliers.
                    best = max(awards, key=lambda a: _value(rel, a)[0] or 0)
                    years = _years(rel, best)
                    per_year = amount / (years or 1) if amount else None
                    if framework and per_year:
                        per_year /= h["suppliers"]
                    revenue = (funds.get(c["ticker"]) or {}).get("revenue")
                    share = materiality(per_year if cur == "GBP" else None, revenue)
                    pct = "under 0.1%" if share is not None and share < 0.001 else f"about {share * 100:.1f}%" if share is not None else ""
                    size = f" ({pct} of annual revenue{' per year' if years and years > 1.5 else ''})" if share is not None else ""
                    if framework:
                        note = f"Named on {money(amount, cur)} framework by {buyer}{lots}{size}"
                        sev = severity_by_share(share)
                        sev = "low" if sev is None else ("medium" if sev == "high" else sev)  # framework places are never 'high'
                        if share is None:
                            sev = "medium" if amount and amount >= CONTRACT_HIGH else "low"
                    else:
                        note = f"Awarded {money(amount, cur)} contract by {buyer}{lots}{size}"
                        sev = severity_by_share(share) or severity(amount)
                    title = awards[0].get("title") or tender.get("title") or "Untitled contract"
                    signals.append({
                        "detected_at": detected_at, "stream": "contracts", "source": source,
                        "ticker": c["ticker"], "company": c["name"], "sector": c["sector"],
                        "ref": rel.get("id"), "title": title, "type": "contract_award",
                        "field": None, "old": None, "new": amount, "currency": cur,
                        "framework": framework, "buyer": buyer, "supplier": h["supplier"],
                        "years": round(years, 1) if years else None,
                        "share_of_revenue": round(share, 4) if share is not None else None,
                        "published": (rel.get("date") or "")[:10],
                        "severity": sev, "note": note, "url": _url(source, rel),
                    })
        except Exception as e:  # one source down shouldn't stop the other
            errors.append(f"{source}: {e}")
        print(f"{source:18} scanned {scanned} award notices since {since:%Y-%m-%d %H:%M}")
    new_state = {"last_run": now.isoformat(timespec="seconds") if not errors else (last or since.isoformat(timespec="seconds")),
                 "seen": {k: d for k, d in seen.items() if d >= (now - timedelta(days=45)).date().isoformat()},
                 "covered": tickers}
    return signals, new_state, errors
