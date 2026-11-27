import re, sys
sys.path.insert(0, ".")
from net import request
for u in ["https://www.londonstockexchange.com/reports?tab=issuers", "https://www.londonstockexchange.com/reports?tab=instruments",
          "https://www.lseg.com/en/investor-relations/trading-statistics"]:
    try:
        t = request("GET", u, tries=1).text
        links = sorted(set(re.findall(r'https?://[^"\' ]+?\.xlsx?', t)))
        print(u, len(t), links[:20])
    except Exception as e:
        print(u, "ERR", str(e)[:120])
