"""What RiverScan watches.

TRIAL_COMPANIES  London-listed biotechs. A trial is kept if its sponsor (or a
                 collaborator/funder) contains one of `sponsor_terms`
                 (case-insensitive). The same terms are used on all three
                 registries: ClinicalTrials.gov, ISRCTN (UK) and EU CTIS.

CONTRACT_COMPANIES  London-listed contractors and service companies. A UK public
                 contract award is kept if one of the named suppliers matches a
                 pattern in `supplier_patterns` (regular expressions, matched
                 case-insensitively against the supplier's name).

`yahoo` is the Yahoo Finance symbol used by prices.py (defaults to TICKER.L).
"""

TRIAL_COMPANIES = [
    {"ticker": "HCM",  "name": "HUTCHMED",              "sponsor_terms": ["hutchmed", "hutchison medipharma"]},
    {"ticker": "SCLP", "name": "Scancell",              "sponsor_terms": ["scancell"]},
    {"ticker": "FARN", "name": "Faron Pharmaceuticals", "sponsor_terms": ["faron pharmaceuticals"]},
    {"ticker": "AVCT", "name": "Avacta",                "sponsor_terms": ["avacta"]},
    {"ticker": "POLB", "name": "Poolbeg Pharma",        "sponsor_terms": ["poolbeg"]},
    {"ticker": "FUM",  "name": "Futura Medical",        "sponsor_terms": ["futura medical"]},
    {"ticker": "AREC", "name": "Arecor Therapeutics",   "sponsor_terms": ["arecor"]},
    {"ticker": "IMM",  "name": "ImmuPharma",            "sponsor_terms": ["immupharma"]},
    {"ticker": "STX",  "name": "Shield Therapeutics",   "sponsor_terms": ["shield therapeutics"]},
    {"ticker": "EVG",  "name": "Evgen Pharma",          "sponsor_terms": ["evgen"]},  # no Yahoo price data as of Nov 2026: check it is still listed
    {"ticker": "HVO",  "name": "hVIVO",                 "sponsor_terms": ["hvivo"]},
    {"ticker": "OXB",  "name": "Oxford Biomedica",      "sponsor_terms": ["oxford biomedica"], "benchmark": "^FTAS"},
]
COMPANIES = TRIAL_COMPANIES  # older name, kept so nothing else breaks

CONTRACT_COMPANIES = [
    # Construction and infrastructure
    {"ticker": "COST", "name": "Costain",         "sector": "Construction", "supplier_patterns": [r"\bcostain\b"]},
    {"ticker": "GFRD", "name": "Galliford Try",   "sector": "Construction", "supplier_patterns": [r"\bgalliford try\b"]},
    {"ticker": "RNWH", "name": "Renew Holdings",  "sector": "Construction", "supplier_patterns": [r"\brenew holdings\b", r"\bamalgamated construction\b"]},
    {"ticker": "SFR",  "name": "Severfield",      "sector": "Construction", "supplier_patterns": [r"\bseverfield\b"]},
    {"ticker": "BOOT", "name": "Henry Boot",      "sector": "Construction", "supplier_patterns": [r"\bhenry boot\b"]},
    {"ticker": "NTBR", "name": "Northern Bear",   "sector": "Construction", "supplier_patterns": [r"\bnorthern bear\b"]},
    {"ticker": "KIE",  "name": "Kier Group",      "sector": "Construction", "supplier_patterns": [r"^kier\b", r"\bkier (construction|highways|integrated|services|infrastructure|group)\b"]},
    {"ticker": "MGNS", "name": "Morgan Sindall",  "sector": "Construction", "supplier_patterns": [r"\bmorgan sindall\b", r"\blovell partnerships\b", r"\bbakerhicks\b", r"\boverbury\b"]},
    {"ticker": "BBY",  "name": "Balfour Beatty",  "sector": "Construction", "supplier_patterns": [r"\bbalfour beatty\b"]},
    {"ticker": "KLR",  "name": "Keller Group",    "sector": "Construction", "supplier_patterns": [r"^keller (ltd|limited|group|uk)\b"]},
    # Public services and outsourcing
    {"ticker": "CPI",  "name": "Capita",          "sector": "Services",     "supplier_patterns": [r"^capita\b(?! ?(one|investment|asset|partners))"]},
    {"ticker": "MER",  "name": "Mears Group",     "sector": "Services",     "supplier_patterns": [r"^mears\b"]},
    {"ticker": "RST",  "name": "Restore",         "sector": "Services",     "supplier_patterns": [r"^restore (plc|records|datashred|digital|technology services|harrow green|information management)\b"]},
    {"ticker": "SRP",  "name": "Serco",           "sector": "Services",     "supplier_patterns": [r"^serco\b"]},
    {"ticker": "MTO",  "name": "Mitie",           "sector": "Services",     "supplier_patterns": [r"^mitie\b"]},
    # Government digital and cyber
    {"ticker": "MTEC", "name": "Made Tech",       "sector": "Digital",      "supplier_patterns": [r"^made tech\b"]},
    {"ticker": "TPX",  "name": "TPXimpact",       "sector": "Digital",      "supplier_patterns": [r"\btpximpact\b"]},
    {"ticker": "NCC",  "name": "NCC Group",       "sector": "Digital",      "supplier_patterns": [r"^ncc (group|services)\b"]},
    {"ticker": "KNOS", "name": "Kainos",          "sector": "Digital",      "supplier_patterns": [r"\bkainos\b"]},
    # Defence
    {"ticker": "CHRT", "name": "Cohort",          "sector": "Defence",      "supplier_patterns": [r"^cohort (plc|ltd|limited)\b", r"\bsystems engineering (&|and) assessment\b", r"\bmass consultants\b", r"\bchess dynamics\b", r"\bmarlborough communications\b"]},
    {"ticker": "AVON", "name": "Avon Technologies", "sector": "Defence",    "supplier_patterns": [r"\bavon (protection|technologies)\b"]},
    {"ticker": "PEG",  "name": "Petards Group",   "sector": "Defence",      "supplier_patterns": [r"\bpetards\b"]},
    {"ticker": "CHG",  "name": "Chemring",        "sector": "Defence",      "supplier_patterns": [r"\bchemring\b"]},
    {"ticker": "QQ.",  "name": "QinetiQ",         "sector": "Defence",      "supplier_patterns": [r"\bqinetiq\b"], "yahoo": "QQ.L"},
    {"ticker": "BAB",  "name": "Babcock",         "sector": "Defence",      "supplier_patterns": [r"\bbabcock (international|marine|land|aerospace|nuclear|integrated|critical|mission|training|rail|power|networks|dsg|support|vehicle)\b", r"^babcock (ltd|limited)\b"]},
    {"ticker": "BA.",  "name": "BAE Systems",     "sector": "Defence",      "supplier_patterns": [r"\bbae systems\b"], "yahoo": "BA.L"},
]

# Only companies worth less than this are scanned (in GBP). Company values are
# refreshed from market data every day, so a company drops out if it grows past
# the line and comes back if it falls under it. Companies above the line stay in
# the lists above so they're picked up automatically if they qualify.
MAX_MARKET_CAP = 1_000_000_000

# Contract severity is based on how big the contract is for the company that won it:
# the contract's value per year as a share of the company's annual revenue.
MATERIALITY_HIGH = 0.10    # 10% of annual revenue or more
MATERIALITY_MEDIUM = 0.02  # 2% or more
# Used only when a company's revenue isn't available.
CONTRACT_HIGH = 100_000_000
CONTRACT_MEDIUM = 5_000_000

# ClinicalTrials.gov fields compared between snapshots, with a label for each.
TRACKED_FIELDS = {
    "status": "Status",
    "phase": "Phase",
    "enrollment": "Enrolment",
    "primary_completion": "Primary completion date",
    "completion": "Completion date",
    "has_results": "Results posted",
}

ISRCTN_FIELDS = {
    "status_override": "Status",
    "phase": "Phase",
    "target_enrolment": "Target enrolment",
    "final_enrolment": "Final enrolment",
    "recruitment_start": "Recruitment start date",
    "recruitment_end": "Recruitment end date",
    "overall_end": "Overall end date",
    "has_results": "Results published",
}

CTIS_FIELDS = {
    "status": "Status",
    "phase": "Phase",
    "enrollment": "Enrolment",
    "end_date": "End date (EU)",
    "member_states": "Countries authorised",
    "halts": "Temporary halts",
    "safety_measures": "Urgent safety measures",
    "serious_breaches": "Serious breaches",
    "has_results": "Results posted",
}

# Statuses that usually move a small-cap share price.
BAD_STATUSES = {"TERMINATED", "WITHDRAWN", "SUSPENDED", "STOPPED", "HALTED", "TEMPORARILY HALTED",
                "REVOKED", "NOT AUTHORISED", "CANCELLED"}

# ---------------------------------------------------------------------------
# Track record (prices.py)
# Price moves after each signal are measured every Friday. They stay off the
# website until you switch TRACK_RECORD_PUBLIC to True AND at least
# TRACK_RECORD_MIN_SIGNALS signals have a 5-day result. Before switching it on,
# check you're allowed to publish the price data you use (Yahoo Finance's terms
# are for personal use), and that the wording meets UK financial promotion rules.
TRACK_RECORD_PUBLIC = False
TRACK_RECORD_MIN_SIGNALS = 20
TRACK_RECORD_MIN_GROUP = 5   # a category needs this many results before its average is shown

# Benchmarks: trial companies are compared with the FTSE AIM All-Share and contract
# companies with the FTSE All-Share, unless a company sets its own "benchmark".


# ---------------------------------------------------------------------------
# Extra companies found automatically (tools/discover.py, then reviewed) live in
# data/companies.json, so this file stays readable. Hand-written entries above win
# if a ticker appears in both.
def _load_extra():
    import json
    from pathlib import Path
    path = Path(__file__).resolve().parent / "data" / "companies.json"
    if not path.exists():
        return
    extra = json.loads(path.read_text())
    have = {c["ticker"] for c in TRIAL_COMPANIES}
    TRIAL_COMPANIES.extend(c for c in extra.get("trials", []) if c["ticker"] not in have)
    have = {c["ticker"] for c in CONTRACT_COMPANIES}
    CONTRACT_COMPANIES.extend(c for c in extra.get("contracts", []) if c["ticker"] not in have)


_load_extra()
