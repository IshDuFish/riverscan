"""Company size data: market value and annual revenue, in GBP.

Used to decide which companies count as small enough to cover (config.MAX_MARKET_CAP)
and to judge how big a contract is for the company that won it.
Refreshed once a day; if the lookup fails, the last known values are kept.

    python fundamentals.py
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from config import TRIAL_COMPANIES, CONTRACT_COMPANIES, MAX_MARKET_CAP

DATA = Path(__file__).resolve().parent / "data"
PATH = DATA / "fundamentals.json"


def yahoo_symbol(c):
    return c.get("yahoo") or c["ticker"].rstrip(".") + ".L"


def load():
    return json.loads(PATH.read_text()) if PATH.exists() else {}


def _fx(yf):
    """GBP value of one unit of each currency."""
    rates = {"GBP": 1.0, "GBp": 0.01}
    for cur, pair, invert in (("USD", "GBPUSD=X", True), ("EUR", "EURGBP=X", False)):
        try:
            r = float(yf.Ticker(pair).fast_info["last_price"])
            rates[cur] = 1 / r if invert else r
        except Exception:
            pass
    return rates


def update():
    """Refresh every company's size; returns {ticker: {...}}. Never raises."""
    old = load()
    try:
        import yfinance as yf
    except ImportError:
        return old
    fx = _fx(yf)
    out, today = {}, datetime.now(timezone.utc).strftime("%Y-%m-%d")
    for c in TRIAL_COMPANIES + CONTRACT_COMPANIES:
        t = c["ticker"]
        if t in out:
            continue
        try:
            info = yf.Ticker(yahoo_symbol(c)).info or {}
            mcap = info.get("marketCap")  # Yahoo gives this in GBP for London listings
            rev, cur = info.get("totalRevenue"), info.get("financialCurrency") or "GBP"
            rev_gbp = rev * fx[cur] if rev and cur in fx else None
            out[t] = {"name": info.get("shortName"), "market_cap": mcap, "revenue": round(rev_gbp) if rev_gbp else None,
                      "as_of": today}
        except Exception:
            if t in old:
                out[t] = old[t]  # keep yesterday's numbers rather than guessing
    if out:
        DATA.mkdir(parents=True, exist_ok=True)
        PATH.write_text(json.dumps(out, indent=1, sort_keys=True))
    return out or old


def split(companies, funds):
    """(covered, excluded) — excluded is a list of (company, reason)."""
    covered, excluded = [], []
    for c in companies:
        f = funds.get(c["ticker"])
        if f is None:
            covered.append(c)  # no data yet: don't drop it
        elif not f.get("market_cap"):
            excluded.append((c, "no market data (may no longer be listed)"))
        elif f["market_cap"] > MAX_MARKET_CAP:
            excluded.append((c, f"market value £{f['market_cap'] / 1e9:.1f}bn, above the £{MAX_MARKET_CAP / 1e9:g}bn limit"))
        else:
            covered.append(c)
    return covered, excluded


if __name__ == "__main__":
    for t, f in sorted(update().items()):
        print(t, f)
