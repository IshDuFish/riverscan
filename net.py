"""Shared HTTP helper: one session, polite retries, honours rate limits."""
import time
import requests

SESSION = requests.Session()
SESSION.headers["User-Agent"] = "RiverScan/1.0 (data analytics; https://riverscan.com)"


def request(method, url, tries=4, **kw):
    kw.setdefault("timeout", 60)
    for attempt in range(tries):
        try:
            r = SESSION.request(method, url, **kw)
            if r.status_code == 429 or r.status_code >= 500:
                wait = int(r.headers.get("Retry-After", 0) or 0) or 5 * (attempt + 1)
                if attempt < tries - 1:
                    time.sleep(min(wait, 60))
                    continue
            r.raise_for_status()
            return r
        except requests.RequestException:
            if attempt == tries - 1:
                raise
            time.sleep(5 * (attempt + 1))
