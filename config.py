"""Companies Riverscan watches.

Each entry:
  ticker         – London ticker (Yahoo Finance adds ".L")
  name           – display name
  sponsor_terms  – how the company appears as a trial sponsor on ClinicalTrials.gov.
                   A trial is kept if its lead sponsor OR a collaborator contains
                   any of these strings (case-insensitive).

Before relying on this list: check each company is still listed, and search
ClinicalTrials.gov by sponsor to confirm the spelling it uses there.
"""

COMPANIES = [
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

# Fields compared between snapshots, with a label for each.
TRACKED_FIELDS = {
    "status": "Status",
    "phase": "Phase",
    "enrollment": "Enrolment",
    "primary_completion": "Primary completion date",
    "completion": "Completion date",
    "has_results": "Results posted",
}

# Statuses that usually move a small-cap share price.
BAD_STATUSES = {"TERMINATED", "WITHDRAWN", "SUSPENDED"}
