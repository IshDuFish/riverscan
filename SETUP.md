# Riverscan scanner: setup

RiverScan now scans five public sources every morning:

- **Clinical trials:** ClinicalTrials.gov, ISRCTN (UK) and EU CTIS, plus *registry mismatches* between them
- **Government contracts:** Find a Tender and Contracts Finder, matched to the London-listed companies in `config.py` (`CONTRACT_COMPANIES`)

To add or remove a company, edit `TRIAL_COMPANIES` or `CONTRACT_COMPANIES` in `config.py`. Only companies worth less than `MAX_MARKET_CAP` (£1bn) are scanned: company values and revenues are refreshed daily from market data (`fundamentals.py`), so big companies can stay in the lists and are picked up automatically if they ever fall below the line. Contracts are rated by their value per year as a share of the winner's annual revenue (10% or more is high, 2% or more is medium). The first run after adding a source or company only saves a baseline, so its signals start the next day (new contract awards are logged straight away).


## What's here
| File | Job |
|---|---|
| `scanner/config.py` | The companies you watch (edit this first) |
| `scanner/scan.py` | Daily: pull trials, compare with yesterday, log signals |
| `scanner/prices.py` | Weekly: did the share price move after each signal? |
| `scanner/digest.py` | Weekly: build (and optionally email) the signals digest |
| `signals.html` | Public signal log page, reads `data/signals.json` |
| `.github/workflows/` | Runs it all automatically |

## 1. Add to your repo
Copy everything into the root of `IshDuFish/riverscan`, then commit and push.

## 2. Check the company list
Open `scanner/config.py`. For each company, search its name under "Sponsor" at
clinicaltrials.gov and make sure `sponsor_terms` matches how it's spelled there.
Remove any company that's delisted, and add ones you're interested in.

## 3. Turn on Actions
Repo → **Settings → Actions → General → Workflow permissions → Read and write**. Save.
Then **Actions → Daily trial scan → Run workflow**. The first run only saves a
baseline, so signals start from the second day.

## 4. Test locally (optional)
```
pip install -r requirements.txt
python -m pytest tests
python -m scanner.scan
```

## 5. Emailing the digest (optional)
Without this, the digest is still saved weekly in `data/digests/` for you to paste
into an email. To send it automatically from Gmail:
1. Turn on 2-step verification, then create an **App password** (Google Account → Security).
2. Repo → Settings → Secrets and variables → Actions → add:
   - `SMTP_HOST` = `smtp.gmail.com`
   - `SMTP_PORT` = `465`
   - `SMTP_USER` = your Gmail address
   - `SMTP_PASS` = the app password
   - `DIGEST_TO` = subscriber emails, comma-separated (copy them from Formspree)

Subscribers are BCC'd so they can't see each other's addresses.

## 6. Link it from the homepage
Add a link to `signals.html` and this section to `index.html`:

```html
<section>
  <h2>Signals, not headlines.</h2>
  <p>Most tools react to news. Riverscan tracks the sources that create it.
     Every morning we scan clinical trial registries for the London-listed
     biotechs we follow and flag changes to status, timelines and enrolment,
     often before they reach the share price.</p>
  <a href="signals.html">See every signal we've logged →</a>
</section>
```

## Severity guide
- **High**: trial terminated, withdrawn or suspended; results posted; phase change
- **Medium**: completed; completion date moved; enrolment changed by 20% or more; new trial
- **Low**: everything else

Keep the "not investment advice" line on the site and emails.
