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
    {"ticker": "EVG",  "name": "Evgen Pharma",          "sponsor_terms": ["evgen"]},
    {"ticker": "HVO",  "name": "hVIVO",                 "sponsor_terms": ["hvivo"]},
    {"ticker": "OXB",  "name": "Oxford Biomedica",      "sponsor_terms": ["oxford biomedica"]},
]
COMPANIES = TRIAL_COMPANIES  # older name, kept so nothing else breaks

CONTRACT_COMPANIES = [
    # Construction and infrastructure
    {"ticker": "BBY",  "name": "Balfour Beatty",  "sector": "Construction", "supplier_patterns": [r"\bbalfour beatty\b"]},
    {"ticker": "MGNS", "name": "Morgan Sindall",  "sector": "Construction", "supplier_patterns": [r"\bmorgan sindall\b", r"\blovell partnerships\b", r"\bbakerhicks\b", r"\boverbury\b"]},
    {"ticker": "KIE",  "name": "Kier Group",      "sector": "Construction", "supplier_patterns": [r"^kier\b", r"\bkier (construction|highways|integrated|services|infrastructure|group)\b"]},
    {"ticker": "COST", "name": "Costain",         "sector": "Construction", "supplier_patterns": [r"\bcostain\b"]},
    {"ticker": "GFRD", "name": "Galliford Try",   "sector": "Construction", "supplier_patterns": [r"\bgalliford try\b"]},
    {"ticker": "KLR",  "name": "Keller Group",    "sector": "Construction", "supplier_patterns": [r"^keller (ltd|limited|group|uk)\b"]},
    {"ticker": "RNWH", "name": "Renew Holdings",  "sector": "Construction", "supplier_patterns": [r"\brenew holdings\b", r"\bamalgamated construction\b"]},
    # Outsourcing and support services
    {"ticker": "SRP",  "name": "Serco",           "sector": "Services",     "supplier_patterns": [r"^serco\b"]},
    {"ticker": "MTO",  "name": "Mitie",           "sector": "Services",     "supplier_patterns": [r"^mitie\b"]},
    {"ticker": "CPI",  "name": "Capita",          "sector": "Services",     "supplier_patterns": [r"^capita\b(?! ?(one|investment|asset|partners))"]},
    # Defence
    {"ticker": "BA.",  "name": "BAE Systems",     "sector": "Defence",      "supplier_patterns": [r"\bbae systems\b"], "yahoo": "BA.L"},
    {"ticker": "BAB",  "name": "Babcock",         "sector": "Defence",      "supplier_patterns": [r"\bbabcock (international|marine|land|aerospace|nuclear|integrated|critical|mission|training|rail|power|networks|dsg|support|vehicle)\b", r"^babcock (ltd|limited)\b"]},
    {"ticker": "QQ.",  "name": "QinetiQ",         "sector": "Defence",      "supplier_patterns": [r"\bqinetiq\b"], "yahoo": "QQ.L"},
    {"ticker": "CHG",  "name": "Chemring",        "sector": "Defence",      "supplier_patterns": [r"\bchemring\b"]},
]

# Contract value thresholds (GBP) for severity.
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
