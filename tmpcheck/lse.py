import re, sys, json
sys.path.insert(0, ".")
from net import request
for u in ["https://apidata.londonstockexchange.com/api/v1/pages?path=reports&parameters=tab%3Dissuers",
          "https://apidata.londonstockexchange.com/api/v1/pages?path=reports&parameters=tab%3Dinstruments"]:
    try:
        r = request("GET", u, tries=1); print(u, r.status_code, len(r.text))
        print(sorted(set(re.findall(r'https?://[^"]*?\.xlsx?', r.text)))[:30])
        print(sorted(set(re.findall(r'"[^"]*\.xlsx?"', r.text)))[:30])
    except Exception as e: print(u, "ERR", str(e)[:150])
