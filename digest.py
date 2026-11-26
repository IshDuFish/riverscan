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


def poss(name):
    return name + ("'" if name.endswith("s") else "'s")


def short_title(t, n=90):
    import re
    t = (t or "").strip()
    t = re.sub(r"\s*[-–]\s*contract (award )?notice\s*$", "", t, flags=re.I)       # "... - Contract Award Notice"
    t = re.sub(r"^(lot\s*\d+[a-z]?|[A-Z0-9][A-Z0-9/._-]*\d[A-Z0-9/._-]*)\s*[-–:]\s*", "", t, flags=re.I)  # "Lot 1 - ", "TSSP/114 - "
    for sep in (" - ", " – ", ": "):
        if sep in t and 12 < len(t.split(sep)[0]) <= n:
            return t.split(sep)[0]
    return t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + "…"


def tidy_buyer(b):
    b = b or "A public body"
    if b.isupper():
        small = {"OF", "AND", "FOR", "THE"}
        acronyms = {"NHS", "HM", "UK", "MOD", "DWP", "HMRC", "YPO", "ESPO", "CCS", "TFL", "TFW", "BBC", "DSIT", "UKRI", "PLC"}
        b = " ".join(w.lower() if w in small and i else w if w in acronyms or len(w) <= 2 else w.capitalize()
                     for i, w in enumerate(b.split()))
    return b


def paragraph(s, funds):
    """A short written paragraph, the way a newsletter would put it."""
    co, t = s["company"], s["type"]
    rev = (funds.get(s["ticker"]) or {}).get("revenue")
    title = short_title(s.get("title") or s.get("trial"))
    if t == "contract_award":
        buyer = tidy_buyer(s.get("buyer"))
        years = s.get("years") if (s.get("years") or 0) > 1.5 else None
        if s.get("framework"):
            out = f"{buyer} named {co} as a supplier on {('a ' + money(s['new'])) if s.get('new') else 'a'} framework for {title.lower() if title.isupper() else title}."
            out += f" Frameworks are shared and often only partly used, so {poss(co)} slice isn't known."
            if rev:
                out += f" For scale, its annual revenue is {money(rev)}."
            return out
        if not s.get("new"):
            return f"{buyer} awarded {co} a contract for {title}. The notice doesn't give a value."
        out = f"{buyer} awarded {co} a {money(s['new'])} contract for {title}"
        out += f", running {years:g} years." if years else "."
        share = share_of_revenue(s, funds)
        if share is not None and rev:
            per_year = s["new"] / (years or 1)
            out += (f" That works out at {money(per_year)} a year, {pct(share).replace('about ', 'roughly ')} of its {money(rev)} annual revenue."
                    if years else f" That's {pct(share).replace('about ', 'roughly ')} of its {money(rev)} annual revenue.")
        return out
    if t == "mismatch":
        a, b = str(s["old"]).split(": ", 1), str(s["new"]).split(": ", 1)
        sa = nice(a[-1]).lower().replace('active not', 'active, not')
        sb = nice(b[-1]).lower().replace('active not', 'active, not')
        return (f"The same {co} trial (“{title}”) is registered in two places, and they no longer agree: "
                f"{a[0]} still lists it as {sa}, while {b[0]} shows it as {sb}. Usually one record just hasn't been "
                f"updated yet, but a gap like this can be the first public sign that a trial has wound down.")
    if t == "new_trial":
        return f"{co} has registered a new trial: “{title}”."
    if t == "removed":
        return f"A trial no longer appears under {co} in the registry: “{title}”."
    f = s.get("field")
    if f in DATE_FIELDS and s.get("old") and s.get("new"):
        word = "pushed back" if str(s["new"]) > str(s["old"]) else "brought forward"
        what = (s.get("note") or "A date").replace(" changed", "").lower()
        return f"{co} has {word} the {what} on “{title}”, from {s['old']} to {s['new']}."
    if f in ("status", "status_override"):
        why = (s.get("note") or "").split("reason given: ")
        extra = f" The reason given: {why[1].rstrip(')')}." if len(why) > 1 else ""
        return f"{poss(co)} trial “{title}” changed status from {nice(s['old']).lower()} to {nice(s['new']).lower()}.{extra}"
    if f in ("enrollment", "target_enrolment", "final_enrolment"):
        return f"{co} changed enrolment on “{title}” from {s['old']} to {s['new']} participants."
    if f == "has_results":
        return f"{co} has posted results for “{title}”."
    if f in ("halts", "safety_measures", "serious_breaches"):
        kind = {"halts": "a temporary halt", "safety_measures": "an urgent safety measure", "serious_breaches": "a serious breach"}[f]
        return f"The EU register now records {kind} on {poss(co)} trial “{title}”."
    return f"{co}: {s.get('note')} on “{title}” ({nice(s.get('old'))} to {nice(s.get('new'))})."


def lead_phrase(s):
    co = s["company"]
    if s["type"] == "contract_award":
        buyer = tidy_buyer(s.get("buyer"))
        if s.get("framework"):
            return f"{co} was named on a {money(s['new']) + ' ' if s.get('new') else ''}{buyer} framework"
        return f"{co} won a {money(s['new']) + ' ' if s.get('new') else ''}contract from {buyer}"
    if s["type"] == "mismatch":
        return f"two registries disagree about one of {poss(co)} trials"
    if s["type"] == "new_trial":
        return f"{co} registered a new trial"
    if s.get("field") in DATE_FIELDS and s.get("old") and s.get("new"):
        return f"{co} {'pushed back' if str(s['new']) > str(s['old']) else 'brought forward'} a trial date"
    if s.get("field") in ("status", "status_override"):
        return f"one of {poss(co)} trials changed status to {nice(s.get('new')).lower()}"
    return f"{co} updated a trial record"


def kind_label(s):
    if s["type"] == "contract_award":
        return "Framework place" if s.get("framework") else "Contract award"
    return {"mismatch": "Registry mismatch", "new_trial": "New trial", "removed": "Trial removed"}.get(s["type"], "Trial update")


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
    now = datetime.now(timezone.utc)
    today = now.strftime("%-d %B %Y")
    names = list(dict.fromkeys(s["company"] for s in key))
    who = ", ".join(names[:-1]) + (" and " + names[-1] if len(names) > 1 else (names[0] if names else ""))
    subject = f"RiverScan Weekly, {now.strftime('%-d %b')}: {who}" if names else f"RiverScan Weekly, {now.strftime('%-d %b')}: a quiet week"

    words = ["No", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten"]
    n = len(key)
    num = words[n] if n < len(words) else str(n)
    nc = len(names)
    cos = (words[nc].lower() if nc < len(words) else str(nc)) + (" companies" if nc != 1 else " company")
    phrases = [lead_phrase(x) for x in key[:4]]
    summary = ""
    if phrases:
        body = "; ".join(phrases[:-1]) + ("; and " if len(phrases) > 1 else "") + phrases[-1]
        summary = " " + body[0].upper() + body[1:] + "."
    intro = (f"{num} signal{'s' if n != 1 else ''} this week, across {cos}.{summary} "
             f"Another {len(low)} smaller change{'s are' if len(low) != 1 else ' is'} in the full log." if n else
             f"A quiet week. Nothing we track moved enough to flag; {len(low)} smaller change{'s are' if len(low) != 1 else ' is'} in the full log.")

    sections = [("Contracts", [s for s in key if s.get("stream") == "contracts"]),
                ("Clinical trials", [s for s in key if s.get("stream", "trials") == "trials"])]

    # ---- plain text ----
    md = [f"RIVERSCAN WEEKLY | {today}", "", intro, ""]
    for label, items in sections:
        if items:
            md += [label.upper(), "-" * len(label), ""]
            for s in items:
                md += [f"{s['company']} ({s['ticker']})", paragraph(s, funds),
                       f"{kind_label(s)}, {s['_sev']} importance. Source: {s.get('source', 'ClinicalTrials.gov')}, {s['url']}", ""]
    md += [f"Full log: {SITE}/signals.html", f"Track record: {SITE}/track-record.html", "", DISCLAIMER]

    # ---- HTML: one typeface throughout, logo masthead, table layout for email apps ----
    font = "'Inter','Helvetica Neue',Helvetica,Arial,sans-serif"
    ink, grey, rule, green = "#0B1F2A", "#6B7A80", "#E2E7E5", "#0F766E"

    def item(s):
        link = "Read the notice" if s["type"] == "contract_award" else "Read the record"
        return (f'<tr><td style="padding:16px 0;border-top:1px solid {rule};font-family:{font}">'
                f'<p style="margin:0;font-size:16px;line-height:1.65;color:{ink}">'
                f'<strong>{esc(s["company"])}</strong> <span style="color:{grey}">({esc(s["ticker"])})</span>. {esc(paragraph(s, funds))}</p>'
                f'<p style="margin:6px 0 0;font-size:13px;line-height:1.5;color:{grey}">{esc(kind_label(s))} · {esc(s["_sev"].capitalize())} importance · '
                f'{esc(s.get("source", "ClinicalTrials.gov"))} · <a href="{esc(s["url"])}" style="color:{green}">{link}</a></p></td></tr>')

    body = "".join(
        f'<tr><td style="padding:24px 0 8px;font-family:{font};font-size:14px;font-weight:600;color:{green}">{label}</td></tr>'
        + "".join(item(s) for s in items) for label, items in sections if items)
    page = (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:600px;margin:0 auto;background:#fff">'
        f'<tr><td style="padding:20px 0 16px;border-bottom:2px solid {ink}">'
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>'
        f'<td><a href="{SITE}"><img src="{SITE}/assets/email-logo.png" width="170" height="36" alt="RiverScan" style="display:block;border:0"></a></td>'
        f'<td align="right" style="font-family:{font};font-size:13px;color:{grey};vertical-align:bottom">Weekly · {today}</td>'
        f'</tr></table></td></tr>'
        f'<tr><td style="padding:20px 0 4px;font-family:{font};font-size:17px;line-height:1.65;color:{ink}">{esc(intro)}</td></tr>'
        + body +
        f'<tr><td style="padding:20px 0;border-top:1px solid {rule};font-family:{font};font-size:15px;line-height:1.6;color:{ink}">'
        f'Every signal, with a link to its source, is in the <a href="{SITE}/signals.html" style="color:{green}">full log</a>. '
        f'To see how prices moved after past signals, read the <a href="{SITE}/track-record.html" style="color:{green}">track record</a>.</td></tr>'
        f'<tr><td style="padding:4px 0 0;font-family:{font};font-size:12px;line-height:1.5;color:#98A3A7">{DISCLAIMER}</td></tr></table>')
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
