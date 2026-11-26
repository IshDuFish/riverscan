import collections, datetime as dt
from net import request
since=(dt.datetime.utcnow()-dt.timedelta(days=3)).strftime("%Y-%m-%dT%H:%M:%S")
for stages in ["award", None]:
    url="https://www.find-tender.service.gov.uk/api/1.0/ocdsReleasePackages"; p={"updatedFrom":since,"limit":100}
    if stages: p["stages"]=stages
    n=0; tags=collections.Counter(); sup=collections.Counter(); pages=0
    while url and pages<40:
        d=request("GET",url,params=p).json(); p=None; pages+=1
        for r in d.get("releases",[]):
            n+=1; tags[",".join(r.get("tag",[]))]+=1
            for a in r.get("awards") or []:
                for s in a.get("suppliers") or []: sup[s.get("name","")]+=1
        url=(d.get("links") or {}).get("next")
    print("stages",stages,"releases",n,"pages",pages, tags.most_common(8))
    big=[k for k in sup if any(w in k.lower() for w in ["serco","capita","mitie","babcock","bae","qinetiq","balfour","kier","costain","galliford","morgan sindall","keller","chemring"])]
    print("  covered-looking suppliers:", big[:20])
