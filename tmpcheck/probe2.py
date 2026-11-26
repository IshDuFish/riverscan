import io, sys, json
sys.path.insert(0, ".")
from net import request
def show(name, fn):
    try:
        r = fn(); print(name, r.status_code, r.headers.get("content-type"), len(r.content)); return r
    except Exception as e:
        print(name, "ERR", str(e)[:150])
# FCA short positions (daily update spreadsheet)
for u in ["https://www.fca.org.uk/publication/data/short-positions-daily-update.xlsx"]:
    r = show("fca", lambda: request("GET", u, tries=2))
    if r is not None and r.ok:
        import pandas as pd
        x = pd.read_excel(io.BytesIO(r.content), sheet_name=None)
        for k, v in x.items(): print("  sheet", k, v.shape, list(v.columns)[:6])
# RNS sources
for name, u in [("investegate_co", "https://www.investegate.co.uk/company/SCLP"),
                ("investegate_rss", "https://www.investegate.co.uk/Rss.aspx?company=SCLP"),
                ("lse_news_api", "https://api.londonstockexchange.com/api/gw/lse/instruments/alldata/SCLP"),
                ("lse_page", "https://www.londonstockexchange.com/stock/SCLP/scancell-holdings-plc/analysis")]:
    r = show(name, lambda u=u: request("GET", u, tries=1))
    if r is not None and r.ok: print("   sample:", r.text[:300].replace("\n", " "))
# Yahoo news for an LSE stock
try:
    import yfinance as yf
    n = yf.Ticker("SCLP.L").news or []
    print("yahoo news", len(n), [ (x.get("content") or x).get("title", "")[:60] for x in n[:3]])
    h = yf.Ticker("SCLP.L").history(period="5d"); print("yahoo hist", h.shape, list(h.columns))
except Exception as e: print("yahoo ERR", e)
# UKRI Gateway to Research
r = show("gtr_org", lambda: request("GET", "https://gtr.ukri.org/api/search/organisation", params={"term": "ilika", "page": 1, "fetchSize": 5}, headers={"Accept": "application/json"}, tries=1))
if r is not None and r.ok: print("   ", r.text[:400])
r = show("gtr_proj", lambda: request("GET", "https://gtr.ukri.org/api/search/project", params={"term": "ilika", "page": 1, "fetchSize": 3}, headers={"Accept": "application/json"}, tries=1))
if r is not None and r.ok: print("   ", r.text[:600])
r = show("gtr_v2", lambda: request("GET", "https://gtr.ukri.org/gtr/api/organisations", params={"q": "ilika", "s": 5}, headers={"Accept": "application/vnd.rcuk.gtr.json-v7"}, tries=1))
if r is not None and r.ok: print("   ", r.text[:600])
# Companies House (needs key) - just check reachability
show("companies_house", lambda: request("GET", "https://api.company-information.service.gov.uk/search/companies", params={"q": "scancell"}, tries=1))
# Contract tender stage availability
from datetime import datetime, timedelta
since = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
r = show("fts_tender", lambda: request("GET", "https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages", params={"updatedFrom": since, "limit": 50}, tries=1))
if r is not None and r.ok:
    import collections
    d = r.json(); print("   tags", collections.Counter(",".join(x.get("tag", [])) for x in d["releases"]).most_common(6))
    rel = next((x for x in d["releases"] if "tender" in x.get("tag", [])), None)
    if rel: print("   tender keys", sorted((rel.get("tender") or {}).keys())[:25], "cpv", ((rel.get("tender") or {}).get("classification")))
    a = next((x for x in d["releases"] if x.get("awards")), None)
    if a: print("   award keys", sorted(a["awards"][0].keys()), "contract keys", sorted((a.get("contracts") or [{}])[0].keys()))
