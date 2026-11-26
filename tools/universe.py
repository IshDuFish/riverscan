"""Build the universe: every London-listed equity under the size limit, via Yahoo's screener."""
import json, sys
import yfinance as yf
from yfinance import EquityQuery as Q

out = {}
for exch in ("LSE", "IOB"):  # LSE main market and AIM both appear as LSE on Yahoo; IOB = international order book
    for sector in (None,):
        q = Q("and", [Q("eq", ["exchange", exch]), Q("lt", ["intradaymarketcap", 1_400_000_000]), Q("gt", ["intradaymarketcap", 1_000_000])])
        offset = 0
        while True:
            try:
                r = yf.screen(q, size=250, offset=offset, sortField="intradaymarketcap", sortAsc=False)
            except Exception as e:
                print("ERR", exch, offset, str(e)[:200]); break
            quotes = r.get("quotes", [])
            for x in quotes:
                out[x["symbol"]] = {"name": x.get("longName") or x.get("shortName"), "mcap": x.get("marketCap"),
                                    "currency": x.get("currency"), "quoteType": x.get("quoteType"),
                                    "exchange": x.get("exchange"), "sector": x.get("sector"), "industry": x.get("industry")}
            print(exch, offset, len(quotes), r.get("total"))
            offset += len(quotes)
            if not quotes or offset >= (r.get("total") or 0):
                break
print("total", len(out))
import collections
print(collections.Counter(v.get("sector") for v in out.values()).most_common())
print([ (k, v["name"], v["mcap"]) for k, v in list(out.items())[:8]])
json.dump(out, open("data/universe_raw.json", "w"), indent=1)
