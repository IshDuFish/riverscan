import json, os, requests, datetime as dt, traceback
os.makedirs("out", exist_ok=True)
S = requests.Session(); S.headers["User-Agent"] = "RiverScan research bot (riverscan.com)"
def save(name, r):
    open(f"out/{name}", "w").write(f"STATUS {r.status_code}\nCT {r.headers.get('content-type')}\n\n" + r.text[:200000])
    print(name, r.status_code, len(r.text))
def run(name, fn):
    try: save(name, fn())
    except Exception: open(f"out/{name}", "w").write(traceback.format_exc()); print(name, "ERR")

for q in ["Scancell", "Faron Pharmaceuticals", "primarySponsor:Scancell"]:
    run(f"isrctn_{q.replace(' ','_').replace(':','_')}.xml",
        lambda q=q: S.get("https://www.isrctn.com/api/query/format/default", params={"q": q, "limit": 5}, timeout=60))
run("isrctn_trial.xml", lambda: S.get("https://www.isrctn.com/api/trial/ISRCTN13453373/format/default", timeout=60))

body = {"pagination": {"page": 1, "size": 20}, "sort": {"property": "decisionDate", "direction": "DESC"},
        "searchCriteria": {"containAll": None, "containAny": None, "containNot": None, "title": None, "number": None,
                           "status": None, "medicalCondition": None, "sponsor": "Faron", "endPoint": None,
                           "productName": None, "productRole": None, "populationType": None, "orphanDesignation": None,
                           "msc": None, "ageGroupCode": None, "therapeuticAreaCode": None, "trialPhaseCode": None,
                           "sponsorTypeCode": None, "gender": None, "protocolCode": None, "rareDisease": None,
                           "pip": None, "haveOrphanDesignation": None, "hasStudyResults": None,
                           "hasClinicalStudyReport": None, "isLowIntervention": None, "hasSeriousBreach": None,
                           "hasUnexpectedEvent": None, "hasUrgentSafetyMeasure": None, "isTransitioned": None,
                           "eudraCtCode": None, "trialRegion": None, "vulnerablePopulation": None,
                           "mscStatus": None}}
run("ctis_search.json", lambda: S.post("https://euclinicaltrials.eu/ctis-public-api/search", json=body, timeout=60))
body2 = {"pagination": {"page": 1, "size": 5}, "sort": {"property": "decisionDate", "direction": "DESC"}, "searchCriteria": {"sponsor": "Faron"}}
run("ctis_search_min.json", lambda: S.post("https://euclinicaltrials.eu/ctis-public-api/search", json=body2, timeout=60))
try:
    d = json.load(open("out/ctis_search.json").read().split("\n\n",1)[1] and open("out/ctis_search.json"))
except Exception: pass
try:
    txt = open("out/ctis_search.json").read().split("\n\n", 1)[1]
    first = json.loads(txt)["data"][0]["ctNumber"]
    run("ctis_retrieve.json", lambda: S.get(f"https://euclinicaltrials.eu/ctis-public-api/retrieve/{first}", timeout=60))
except Exception: traceback.print_exc()

since = (dt.datetime.utcnow() - dt.timedelta(days=2)).strftime("%Y-%m-%dT%H:%M:%S")
run("fts.json", lambda: S.get("https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages",
                              params={"updatedFrom": since, "stages": "award", "limit": 20}, timeout=90))
run("cf.json", lambda: S.get("https://www.contractsfinder.service.gov.uk/Published/Notices/OCDS/Search",
                             params={"publishedFrom": since, "stages": "award", "limit": 20}, timeout=90))

# ISRCTN query variants
for i, params in enumerate([{"q": "Scancell"}, {"q": "scancell", "limit": 5}, {"q": "condition:cancer", "limit": 2},
                            {"q": "Scancell Ltd"}, {"q": "Hutchmed"}, {"q": "Poolbeg"}]):
    run(f"isrctn_v{i}.xml", lambda p=params: S.get("https://www.isrctn.com/api/query/format/default", params=p, timeout=60))
run("isrctn_trial2.xml", lambda: S.get("https://www.isrctn.com/api/trial/ISRCTN10000000/format/default", timeout=60))
run("isrctn_web.html", lambda: S.get("https://www.isrctn.com/search", params={"q": "Scancell"}, timeout=60))
