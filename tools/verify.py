"""Verify candidate companies: real London listing, market value, revenue, and actual
trial-registry matches under the company's name. Output: data/verify.json for review."""
import json, re, sys, time, collections
sys.path.insert(0, ".")
import yfinance as yf
import xml.etree.ElementTree as ET
import isrctn
from net import request
from fetch import simplify as ct_simplify

HEALTH = """SNG HEMO SAR ETX BVXP AGY AGL RENX POLX TRX AMS CREO IHC BELL LLAI COG ABDX N4P OCTP DXRX GDR IXI KMK ODX NCYT PRTC NIOX BYOT
PYC VAL OPTI VRCI OBD CRTX NFX CIZ GENF FAB APTA SBTX RUA PRM GENI TCF SVNS CLBX THAT SUN IDHC IBAI FDBK CNSL MXCT TILS EAH ANCR
ONC SMIF PHC CAR TSTL OXB SCLP FARN AVCT POLB FUM AREC IMM STX HVO""".split()
RESEARCH = "IKA CWR EDEN ITX OMG IQE SEE FIPP IPO TEK OXIG SAG ZOO PCT CLIG AMTE".split()
CONTRACT = """TRB IDOX NET MAI RCN IOM GATC SDY HSP TRCS TLY SAG CNC PRES CSC THRU KMK GTC EAAS EBQ
COST GFRD RNWH SFR BOOT NTBR CPI MER RST MTEC TPX NCC CHRT AVON PEG""".split()

SUFFIX = {"plc", "limited", "ltd", "group", "holdings", "holding", "the", "company", "co", "inc", "ord", "corporation"}
def stem(name):
    n = re.sub(r"\(.*?\)", " ", name.lower().replace("&", " and "))
    n = re.sub(r"[^a-z0-9 ]", " ", n)
    return " ".join(w for w in n.split() if w not in SUFFIX)

out = {}
for t in dict.fromkeys(HEALTH + RESEARCH + CONTRACT):
    try:
        i = yf.Ticker(t + ".L").info or {}
    except Exception as e:
        out[t] = {"error": str(e)[:80]}; continue
    name = i.get("longName") or i.get("shortName")
    rec = {"name": name, "mcap": i.get("marketCap"), "revenue": i.get("totalRevenue"), "fin": i.get("financialCurrency"),
           "sector": i.get("sector"), "industry": i.get("industry"), "summary": (i.get("longBusinessSummary") or "")[:220],
           "group": "health" if t in HEALTH else "research" if t in RESEARCH else "contract"}
    if name and t in HEALTH + RESEARCH:
        st = stem(name)
        # try the full stem, then the first word if it's distinctive (e.g. "synairgen")
        terms = [st] + ([st.split()[0]] if len(st.split()) > 1 and len(st.split()[0]) >= 6 else [])
        sponsors, counts = collections.Counter(), collections.Counter()
        for term in terms:
            rx = re.compile(r"\b" + re.escape(term) + r"\b")
            try:
                d = request("GET", "https://clinicaltrials.gov/api/v2/studies", params={"query.spons": term, "pageSize": 200}).json()
                for s in d.get("studies", []):
                    r = ct_simplify(s); hit = [x for x in r["sponsors"] if rx.search(x.lower())]
                    if hit: counts["ctgov:" + r["nct_id"]] = 1; sponsors.update(hit)
            except Exception as e: rec["ct_err"] = str(e)[:60]
            try:
                for full in ET.fromstring(request("GET", isrctn.API, params={"q": term, "limit": 100}).content).findall("i:fullTrial", isrctn.NS):
                    r = isrctn.simplify(full); hit = [x for x in r["sponsors"] if rx.search(x.lower())]
                    if hit: counts["isrctn:" + r["id"]] = 1; sponsors.update(hit)
            except Exception as e: rec["isrctn_err"] = str(e)[:60]
            try:
                body = {"pagination": {"page": 1, "size": 50}, "sort": {"property": "decisionDate", "direction": "DESC"}, "searchCriteria": {"sponsor": term}}
                for s in request("POST", "https://euclinicaltrials.eu/ctis-public-api/search", json=body).json().get("data", []):
                    if rx.search((s.get("sponsor") or "").lower()): counts["ctis:" + s["ctNumber"]] = 1; sponsors[s["sponsor"]] += 1
            except Exception as e: rec["ctis_err"] = str(e)[:60]
            time.sleep(0.3)
        rec["terms"] = terms
        rec["trials"] = {k: sum(1 for x in counts if x.startswith(k + ":")) for k in ("ctgov", "isrctn", "ctis")}
        rec["sponsors"] = sponsors.most_common(5)
    out[t] = rec
    print(t, rec.get("name"), rec.get("mcap"), rec.get("trials"), [s[0][:30] for s in rec.get("sponsors", [])[:2]], flush=True)
json.dump(out, open("data/verify.json", "w"), indent=1)
