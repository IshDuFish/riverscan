"""Step 6: weekly signals email.

Builds data/digests/<date>.md and .html from the last 7 days of signals.
Paste the HTML into your email tool (e.g. Buttondown or Mailchimp, both free
for small lists), or send it automatically by setting the SMTP_* secrets
described in SETUP.md.

    python digest.py            # just build the files
    python digest.py --send     # build and email
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

DATA = Path(__file__).resolve().parent / "data"
OUT = DATA / "digests"
SITE = "https://riverscan.com"
DISCLAIMER = ("Riverscan reports public registry changes for information only. "
              "It is not investment advice.")


def recent_signals(days=7):
    path = DATA / "signals.json"
    if not path.exists():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    sigs = [s for s in json.loads(path.read_text()) if s["detected_at"] >= cutoff]
    order = {"high": 0, "medium": 1, "low": 2}
    return sorted(sigs, key=lambda s: (order[s["severity"]], s["detected_at"]))


def build(sigs):
    today = datetime.now(timezone.utc).strftime("%d %b %Y")
    key = [s for s in sigs if s["severity"] != "low"]
    md = [f"# Riverscan weekly signals – {today}", ""]
    if not key:
        md.append("No significant trial changes this week across the companies we track.")
    for s in key:
        change = f"{s['old']} → {s['new']}" if s["type"] == "change" else (s["new"] or "")
        md += [f"**{s['company']} ({s['ticker']})** · {s['severity'].upper()}",
               f"{s['note']}: {change}",
               f"_{s['trial']}_ – [{s['nct_id']}]({s['url']})", ""]
    md += ["---", DISCLAIMER, f"{SITE}/signals.html"]

    rows = "".join(
        f"<tr><td><b>{html.escape(s['company'])}</b><br><small>{s['ticker']}</small></td>"
        f"<td>{html.escape(s['note'] or '')}<br><small>"
        f"{html.escape(str(s['old']))} → {html.escape(str(s['new']))}</small></td>"
        f"<td><a href='{s['url']}'>{s['nct_id']}</a></td>"
        f"<td>{s['severity'].upper()}</td></tr>"
        for s in key)
    body = (f"<table cellpadding='8' style='border-collapse:collapse'>{rows}</table>" if key
            else "<p>No significant trial changes this week across the companies we track.</p>")
    page = (f"<div style='font-family:Arial,sans-serif;max-width:640px'>"
            f"<h2>Riverscan weekly signals – {today}</h2>{body}"
            f"<p><a href='{SITE}/signals.html'>See the full signal log</a></p>"
            f"<p style='color:#777;font-size:12px'>{DISCLAIMER}</p></div>")
    return "\n".join(md), page, f"Riverscan weekly signals – {today}"


def send(subject, html_body, text_body):
    host, user, pw = os.environ["SMTP_HOST"], os.environ["SMTP_USER"], os.environ["SMTP_PASS"]
    to = [a.strip() for a in os.environ["DIGEST_TO"].split(",") if a.strip()]
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
        if os.environ.get("SMTP_HOST") and os.environ.get("DIGEST_TO"):
            send(subject, page, text)
        else:
            print("SMTP secrets not set; digest built but not sent.")


if __name__ == "__main__":
    main()
