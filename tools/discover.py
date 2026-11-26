"""Discovery: which small London-listed companies appear in trial registries or contract awards?

Writes data/discovery.json for review. Matching is by the company's distinctive name stem;
results are candidates to be checked, not final."""
import json, re, sys, time, collections
from datetime import datetime, timedelta
sys.path.insert(0, ".")
import yfinance as yf
from yfinance import EquityQuery as Q
import contracts, isrctn
from net import request
from fetch import simplify as ct_simplify

GENERIC = set("""plc limited ltd group holdings holding company co the and of international global uk british
capital investments investment trust fund income growth opportunities energy resources resource mining minerals metals
gold oil gas property properties real estate reit systems system services service solutions technology technologies tech
digital data health healthcare care medical medicine pharma pharmaceuticals therapeutics bio biotech sciences science life
partners partnership industries industrial enterprises ventures brands brand media network networks power green renewable
renewables infrastructure finance financial bank asset assets management consulting new first one best smart world""".split())

def stem(name):
    n = name.lower().replace("&", " and ")
    n = re.sub(r"\(.*?\)", " ", n)
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    words = [w for w in n.split() if w not in {"plc", "limited", "ltd", "group", "holdings", "holding", "the", "company", "co", "inc", "corporation", "corp", "sa", "nv", "se", "ag", "oy", "oyj"}]
    return " ".join(words)

def distinctive(s):
    w = s.split()
    return bool(w) and len(s) >= 5 and not all(x in GENERIC for x in w) and not (len(w) == 1 and w[0] in GENERIC)

# 1. universe with sectors
uni = {}
for sector in ("Healthcare", None):
    parts = [Q("eq", ["exchange", "LSE"]), Q("lt", ["intradaymarketcap", 1_400_000_000]), Q("gt", ["intradaymarketcap", 1_000_000])]
    if sector: parts.append(Q("eq", ["sector", sector]))
    off = 0
    while True:
        r = yf.screen(Q("and", parts), size=250, offset=off, sortField="intradaymarketcap", sortAsc=False)
        qs = r.get("quotes", [])
        for x in qs:
            d = uni.setdefault(x["symbol"], {"name": x.get("longName") or x.get("shortName"), "mcap": x.get("marketCap"), "sector": None})
            if sector: d["sector"] = sector
        off += len(qs)
        if not qs or off >= (r.get("total") or 0): break
for sym, d in uni.items():
    d["stem"] = stem(d["name"] or "")
    d["ok"] = distinctive(d["stem"])
print("universe", len(uni), "healthcare", sum(1 for d in uni.values() if d["sector"] == "Healthcare"), flush=True)

# 2. trials for healthcare companies
trials = {}
for sym, d in uni.items():
    if d["sector"] != "Healthcare" or not d["ok"]: continue
    st = d["stem"]; res = {"ctgov": [], "isrctn": [], "ctis": [], "sponsors": collections.Counter()}
    try:
        data = request("GET", "https://clinicaltrials.gov/api/v2/studies", params={"query.spons": st, "pageSize": 200}).json()
        for s in data.get("studies", []):
            rec = ct_simplify(s)
            hit = [x for x in rec["sponsors"] if re.search(r"\b" + re.escape(st) + r"\b", x.lower())]
            if hit: res["ctgov"].append(rec["nct_id"]); res["sponsors"].update(hit)
    except Exception as e: print("ct err", sym, e)
    try:
        import xml.etree.ElementTree as ET
        r = request("GET", isrctn.API, params={"q": st, "limit": 100})
        for full in ET.fromstring(r.content).findall("i:fullTrial", isrctn.NS):
            rec = isrctn.simplify(full)
            hit = [x for x in rec["sponsors"] if re.search(r"\b" + re.escape(st) + r"\b", x.lower())]
            if hit: res["isrctn"].append(rec["id"]); res["sponsors"].update(hit)
    except Exception as e: print("isrctn err", sym, e)
    try:
        body = {"pagination": {"page": 1, "size": 50}, "sort": {"property": "decisionDate", "direction": "DESC"}, "searchCriteria": {"sponsor": st}}
        for s in request("POST", "https://euclinicaltrials.eu/ctis-public-api/search", json=body).json().get("data", []):
            if re.search(r"\b" + re.escape(st) + r"\b", (s.get("sponsor") or "").lower()):
                res["ctis"].append(s["ctNumber"]); res["sponsors"][s["sponsor"]] += 1
    except Exception as e: print("ctis err", sym, e)
    n = len(res["ctgov"]) + len(res["isrctn"]) + len(res["ctis"])
    if n:
        trials[sym] = {"name": d["name"], "stem": st, "mcap": d["mcap"], "ctgov": len(res["ctgov"]), "isrctn": len(res["isrctn"]),
                       "ctis": len(res["ctis"]), "sponsors": res["sponsors"].most_common(6)}
        print("TRIALS", sym, d["name"], n, res["sponsors"].most_common(3), flush=True)
    time.sleep(0.5)

# 3. contracts over the last N days
DAYS = int(sys.argv[1]) if len(sys.argv) > 1 else 120
cands = [(sym, d, re.compile(r"^(the )?" + re.escape(d["stem"]) + r"\b")) for sym, d in uni.items() if d["ok"]]
hits = collections.defaultdict(lambda: {"awards": 0, "value": 0.0, "buyers": collections.Counter(), "suppliers": collections.Counter()})
now = datetime.utcnow(); since = now - timedelta(days=DAYS)
scanned = collections.Counter()
for source in contracts.SOURCES:
    try:
        for rel in contracts.releases(source, since, now):
            scanned[source] += 1
            for a in rel.get("awards") or []:
                for sup in a.get("suppliers") or []:
                    nm = stem(sup.get("name") or "")
                    for sym, d, rx in cands:
                        if rx.search(nm):
                            h = hits[sym]; h["awards"] += 1
                            v, _ = contracts._value(rel, a); h["value"] += v or 0
                            h["buyers"][(rel.get("buyer") or {}).get("name")] += 1; h["suppliers"][sup.get("name")] += 1
    except Exception as e:
        print("contracts err", source, e)
print("scanned", dict(scanned))
con = {sym: {"name": uni[sym]["name"], "stem": uni[sym]["stem"], "mcap": uni[sym]["mcap"], "sector": uni[sym]["sector"],
             "awards": h["awards"], "value": round(h["value"]), "buyers": h["buyers"].most_common(5), "suppliers": h["suppliers"].most_common(6)}
       for sym, h in hits.items()}
json.dump({"universe": len(uni), "days": DAYS, "scanned": dict(scanned), "trials": trials, "contracts": con}, open("data/discovery.json", "w"), indent=1)
print("trial companies", len(trials), "contract companies", len(con))
