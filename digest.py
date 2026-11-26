"""Weekly signals email.

Builds data/digests/<date>.md and .html from the last 7 days of signals, in the
same style as the website: company names first, every contract compared with the
winner's annual revenue, grouped by data stream, most important first.
Only companies RiverScan currently covers (under £1bn) are included.

    python digest.py            # just build the files
    python digest.py --send     # build and email (see SETUP-EMAIL.md)
"""
import html
import json
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from config import MATERIALITY_HIGH, MATERIALITY_MEDIUM
from contracts import money

DATA = Path(__file__).resolve().parent / "data"
OUT = DATA / "digests"
SITE = "https://riverscan.com"
DISCLAIMER = ("RiverScan is a data analytics company. It reports changes in public records for "
              "information only. It is not investment advice.")
INK, TEAL, MUTED, LINE = "#0B1F2A", "#0F766E", "#5B6B70", "#E3E9E6"
SEV_COLOUR = {"high": "#B3261E", "medium": "#8A6A00", "low": "#5B6B70"}
DATE_FIELDS = {"primary_completion", "completion", "recruitment_start", "recruitment_end", "overall_end", "end_date"}


def load(name, default):
    p = DATA / name
    return json.loads(p.read_text()) if p.exists() else default


def esc(v):
    return html.escape(str(v if v is not None else ""))


def nice(v):
    v = str(v)
    return v.replace("_", " ").capitalize() if v.replace("_", "").replace(" ", "").isupper() else v


def pct(x):
    return "under 0.1%" if x < 0.001 else f"about {x * 100:.1f}%" if x < 0.1 else f"about {round(x * 100)}%"


def share_of_revenue(s, funds):
    if s.get("share_of_revenue") is not None:
        return s["share_of_revenue"]
    rev = (funds.get(s["ticker"]) or {}).get("revenue")
    if not s.get("new") or not rev or s.get("framework") or s.get("currency", "GBP") != "GBP":
        return None
    years = s.get("years") if (s.get("years") or 0) > 1 else 1
    return s["new"] / years / rev


def severity(s, funds):
    """Contracts are rated by size for the company that won them (same rule as the website)."""
    if s["type"] != "contract_award" or s.get("share_of_revenue") is not None or s.get("framework"):
        return s["severity"]
    share = share_of_revenue(s, funds)
    if share is None:
        return s["severity"]
    return "high" if share >= MATERIALITY_HIGH else "medium" if share >= MATERIALITY_MEDIUM else "low"


def news(s):
    if s["type"] == "contract_award":
        return "Good news"
    if s.get("field") in ("halts", "safety_measures", "serious_breaches") and (s.get("new") or 0) > (s.get("old") or 0):
        return "Bad news"
    if s.get("field") in ("status", "status_override") and s["severity"] == "high":
        return "Bad news"
    if s.get("type") == "change" and s.get("field") in DATE_FIELDS and s.get("old") and s.get("new"):
        return "Bad news" if str(s["new"]) > str(s["old"]) else "Good news"
    return "Mixed"


def headline(s):
    """One plain-English sentence saying what happened."""
    t = s["type"]
    if t == "contract_award":
        buyer = s.get("buyer") or "a public body"
        if buyer.isupper():  # many notices shout: NETWORK RAIL INFRASTRUCTURE LIMITED
            buyer = " ".join(w if w in ("NHS", "HM", "UK", "MOD", "DWP", "HMRC") else w.capitalize() for w in buyer.split())
        if not s.get("new"):
            return f"{'Named on a framework' if s.get('framework') else 'Won a contract'} from {buyer} (value not stated)."
        return (f"Named on a {money(s['new'])} framework by {buyer}." if s.get("framework")
                else f"Won a {money(s['new'])} contract from {buyer}.")
    if t == "mismatch":
        a, b = str(s["old"]).split(": ", 1), str(s["new"]).split(": ", 1)
        return f"Registries disagree: {a[0]} says {nice(a[-1])}, {b[0]} says {nice(b[-1])}."
    if t == "new_trial":
        return "New trial registered."
    if t == "removed":
        return "A trial is no longer listed under this company."
    label = (s.get("note") or "Changed").replace(" changed", "")
    if s.get("field") in DATE_FIELDS and s.get("old") and s.get("new"):
        label += " pushed back" if str(s["new"]) > str(s["old"]) else " brought forward"
        return f"{label}: {nice(s['old'])} → {nice(s['new'])}."
    return f"{label}: {nice(s['old'])} → {nice(s['new'])}."


def size_line(s, funds):
    if s["type"] != "contract_award":
        return ""
    rev = (funds.get(s["ticker"]) or {}).get("revenue")
    name = s["company"]
    if not rev:
        return ""
    if s.get("framework"):
        if s.get("share_of_revenue") is not None:
            return f"Shared framework. Split equally, {pct(s['share_of_revenue'])} of {name}'s {money(rev)} annual revenue."
        return f"Shared framework, so {name}'s slice is unknown. For scale, its annual revenue is {money(rev)}."
    share = share_of_revenue(s, funds)
    if share is None:
        return f"Value not stated. {name}'s annual revenue is {money(rev)}."
    years = s.get("years") if (s.get("years") or 0) > 1.5 else None
    return (f"Over {years:g} years, that's {pct(share)} of {name}'s {money(rev)} annual revenue each year." if years
            else f"That's {pct(share)} of {name}'s {money(rev)} annual revenue.")


def recent_signals(days=7):
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return [s for s in load("signals.json", []) if s["detected_at"] >= cutoff]


def build(sigs):
    funds, cov = load("fundamentals.json", {}), load("coverage.json", {})
    covered = set(cov.get("trial_companies", [])) | {c["ticker"] for c in cov.get("contract_companies", [])}
    if covered:
        sigs = [s for s in sigs if s["ticker"] in covered]
    for s in sigs:
        s["_sev"] = severity(s, funds)
    order = {"high": 0, "medium": 1, "low": 2}
    key = sorted([s for s in sigs if s["_sev"] != "low"], key=lambda s: (order[s["_sev"]], s["company"]))
    low = [s for s in sigs if s["_sev"] == "low"]
    today = datetime.now(timezone.utc).strftime("%-d %B %Y")
    subject = f"RiverScan weekly: {len(key)} signal{'s' if len(key) != 1 else ''} worth a look ({today})"

    streams = [("Clinical trials", [s for s in key if s.get("stream", "trials") == "trials"]),
               ("Government contracts", [s for s in key if s.get("stream") == "contracts"])]
    n_cos = len({s["ticker"] for s in key})
    intro = (f"This week we logged {len(sigs)} changes across the companies we cover. "
             f"{len(key)} are worth a look, from {n_cos} compan{'ies' if n_cos != 1 else 'y'}; "
             f"the other {len(low)} were minor and are in the full log.")
    if not key:
        intro = f"A quiet week: {len(sigs)} minor changes, nothing rated medium or high. Everything is in the full log."

    # ---- plain text ----
    md = [f"RiverScan weekly signals, {today}", "", intro, ""]
    for label, items in streams:
        if not items:
            continue
        md += [label.upper(), ""]
        for s in items:
            md += [f"{s['company']} ({s['ticker']}) · {s['_sev'].upper()} · {news(s)}", headline(s)]
            if size_line(s, funds):
                md.append(size_line(s, funds))
            md += [f"{s.get('title') or s.get('trial') or ''}", f"Source: {s.get('source', 'ClinicalTrials.gov')}, {s['url']}", ""]
    md += ["Full signal log: " + SITE + "/signals.html", "Track record: " + SITE + "/track-record.html", "", DISCLAIMER]

    # ---- HTML (inline styles so it looks right in every email app) ----
    def card(s):
        sev, nw = s["_sev"], news(s)
        nw_col = {"Good news": "#0B7A52", "Bad news": "#B3261E"}.get(nw, MUTED)
        size = size_line(s, funds)
        title = s.get("title") or s.get("trial") or ""
        if len(title) > 160:
            title = title[:157].rsplit(" ", 1)[0] + "…"
        link = "View notice" if s["type"] == "contract_award" else (s.get("ref") or s.get("nct_id") or "View record")
        return (
            f'<div style="border:1px solid {LINE};border-left:4px solid {SEV_COLOUR[sev]};border-radius:8px;padding:14px 16px;margin:0 0 12px">'
            f'<div style="font-size:17px;font-weight:bold;color:{INK}">{esc(s["company"])} '
            f'<span style="font-size:12px;font-weight:normal;color:{MUTED};font-family:monospace">{esc(s["ticker"])}</span></div>'
            f'<div style="font-size:12px;margin:4px 0 8px"><span style="color:{SEV_COLOUR[sev]};font-weight:bold;text-transform:uppercase">{sev}</span>'
            f' &nbsp;·&nbsp; <span style="color:{nw_col};font-weight:bold">{nw}</span>'
            f' &nbsp;·&nbsp; <span style="color:{MUTED}">{esc(s.get("source", "ClinicalTrials.gov"))}</span></div>'
            f'<div style="font-size:15px;color:{INK};margin-bottom:6px">{esc(headline(s))}</div>'
            + (f'<div style="font-size:14px;background:#EEF8F6;border-left:2px solid {TEAL};padding:6px 10px;margin:6px 0;color:{INK}">{esc(size)}</div>' if size else "")
            + f'<div style="font-size:13px;color:{MUTED};margin:6px 0">{esc(title)}</div>'
            f'<a href="{esc(s["url"])}" style="font-size:13px;color:{TEAL}">{esc(link)} →</a></div>')

    sections = "".join(
        f'<h3 style="font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:{MUTED};margin:24px 0 10px">{label}</h3>'
        + "".join(card(s) for s in items) for label, items in streams if items)
    page = (
        f'<div style="font-family:Arial,Helvetica,sans-serif;max-width:620px;margin:0 auto;color:{INK};line-height:1.5">'
        f'<div style="background:{INK};color:#EEF3F1;padding:20px 22px;border-radius:10px">'
        f'<div style="font-size:13px;color:#3CC9B5">RiverScan weekly · {today}</div>'
        f'<div style="font-size:22px;font-weight:bold;margin-top:4px">What changed upstream this week</div></div>'
        f'<p style="font-size:15px;margin:18px 0">{esc(intro)}</p>'
        + sections +
        f'<p style="margin:24px 0"><a href="{SITE}/signals.html" style="background:#3CC9B5;color:#06161E;padding:10px 16px;border-radius:6px;text-decoration:none;font-weight:bold">See the full signal log</a></p>'
        f'<p style="font-size:14px;color:{MUTED}">How did prices react to past signals? See the <a href="{SITE}/track-record.html" style="color:{TEAL}">track record</a>.</p>'
        f'<p style="font-size:12px;color:#888;margin-top:24px">{DISCLAIMER}</p></div>')
    for s in sigs:
        s.pop("_sev", None)
    return "\n".join(md), page, subject


def send_via_script(subject, html_body, text_body):
    """Send through the Google Apps Script email service (SETUP-EMAIL.md): every active
    subscriber gets it, and the owner always gets a copy."""
    import requests
    r = requests.post(os.environ["SIGNUP_SCRIPT_URL"], timeout=120,
                      json={"action": "digest", "token": os.environ["SIGNUP_TOKEN"],
                            "subject": subject, "html": html_body, "text": text_body})
    r.raise_for_status()
    print("Email service:", r.text[:200])


def send(subject, html_body, text_body):
    host, user, pw = os.environ["SMTP_HOST"], os.environ["SMTP_USER"], os.environ["SMTP_PASS"]
    to = [a.strip() for a in os.environ.get("DIGEST_TO", "").split(",") if a.strip()]
    owner = os.environ.get("OWNER_EMAIL", "").strip()
    if owner and owner not in to:
        to.append(owner)  # always send the owner a copy
    msg = MIMEMultipart("alternative")
    msg["Subject"], msg["From"], msg["To"] = subject, user, user
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))
    with smtplib.SMTP_SSL(host, int(os.environ.get("SMTP_PORT", 465))) as s:
        s.login(user, pw)
        s.sendmail(user, [user] + to, msg.as_string())  # subscribers go in BCC
    print(f"Sent to {len(to)} subscriber(s)")


def main():
    text, page, subject = build(recent_signals())
    OUT.mkdir(parents=True, exist_ok=True)
    day = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    (OUT / f"{day}.md").write_text(text)
    (OUT / f"{day}.html").write_text(page)
    print(text)
    if "--send" in sys.argv:
        if os.environ.get("SIGNUP_SCRIPT_URL") and os.environ.get("SIGNUP_TOKEN"):
            send_via_script(subject, page, text)
        elif os.environ.get("SMTP_HOST") and (os.environ.get("DIGEST_TO") or os.environ.get("OWNER_EMAIL")):
            send(subject, page, text)
        else:
            print("No email settings yet (see SETUP-EMAIL.md); digest built but not sent.")


if __name__ == "__main__":
    main()
