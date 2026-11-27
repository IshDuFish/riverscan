import re, sys, json
sys.path.insert(0, ".")
from net import request
t = request("GET", "https://www.londonstockexchange.com/reports?tab=issuers", tries=1).text
print("hosts:", sorted(set(re.findall(r'https?://[a-z0-9.-]*londonstockexchange\.com', t)))[:20])
print("files:", sorted(set(re.findall(r'[A-Za-z0-9%_ /.-]*\.(?:xlsx|xls|csv)', t)))[:20])
m = re.search(r'<script id="ng-state"[^>]*>(.*?)</script>', t, re.S)
if m:
    s = m.group(1); print("ng-state len", len(s)); print(sorted(set(re.findall(r'[^"]*\.xlsx?', s)))[:20])
for u, body in [("https://api.londonstockexchange.com/api/v1/pages?path=reports&parameters=tab%3Dissuers", None)]:
    try:
        r = request("GET", u, tries=1); print(u, r.status_code, len(r.text)); print(sorted(set(re.findall(r'[^"]*\.xlsx?', r.text)))[:20])
    except Exception as e: print(u, "ERR", str(e)[:150])
