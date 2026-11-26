"""Tests for the ISRCTN, EU CTIS, contracts and mismatch code, using real API responses
saved in tests/fixtures. Run from the repo root:  python -m pytest"""
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FIX = Path(__file__).resolve().parent / "fixtures"

import contracts  # noqa: E402
import ctis  # noqa: E402
import isrctn  # noqa: E402
import mismatch  # noqa: E402
import scan  # noqa: E402
from diff import diff_company  # noqa: E402
from config import ISRCTN_FIELDS, CTIS_FIELDS  # noqa: E402


def test_isrctn_parse():
    root = ET.fromstring((FIX / "isrctn_v5.xml").read_bytes())
    rec = isrctn.simplify(root.find("i:fullTrial", isrctn.NS))
    assert rec["id"] == "ISRCTN50499387"
    assert rec["target_enrolment"] == 30 and rec["phase"] == "Phase II"
    assert rec["overall_end"] == "2027-06-30" and rec["recruitment_start"] == "2026-03-29"
    assert any("poolbeg" in s.lower() for s in rec["sponsors"]) or rec["sponsors"]
    assert isrctn.status_bucket(rec, "2026-11-26") == "active"
    assert isrctn.status_bucket(rec, "2027-07-01") == "ended"


def test_ctis_parse_and_diff():
    summary = json.loads((FIX / "ctis_search.json").read_text())["data"][0]
    detail = json.loads((FIX / "ctis_retrieve.json").read_text())
    rec = ctis.simplify(summary, detail)
    assert rec["id"] == "2026-526706-33-00" and rec["status"] == "Authorised"
    assert rec["member_states"] == 5 and rec["halts"] == 0
    assert ctis.status_bucket(rec) == "active"
    halted = dict(rec, status="Temporarily halted", halts=1)
    co = {"ticker": "FARN", "name": "Faron"}
    sigs = diff_company(co, {rec["id"]: rec}, {rec["id"]: halted}, "t", CTIS_FIELDS, "EU CTIS")
    assert {s["field"] for s in sigs} == {"status", "halts"}
    assert all(s["severity"] == "high" and s["source"] == "EU CTIS" for s in sigs)


def test_new_field_is_not_a_change():
    co = {"ticker": "X", "name": "X"}
    old = {"T1": {"id": "T1", "title": "t", "url": "u", "phase": "Phase II"}}
    new = {"T1": {"id": "T1", "title": "t", "url": "u", "phase": "Phase II", "final_enrolment": 10}}
    assert diff_company(co, old, new, "t", ISRCTN_FIELDS, "ISRCTN") == []


def test_contracts_match_and_value(monkeypatch):
    pages = {"Find a Tender": json.loads((FIX / "fts.json").read_text()),
             "Contracts Finder": json.loads((FIX / "cf.json").read_text())}
    monkeypatch.setattr(contracts, "releases", lambda source, since, until: iter(pages[source]["releases"]))
    sigs, state, errors = contracts.scan({}, "2026-11-26T06:17:00Z")
    assert not errors
    assert {s["ticker"] for s in sigs} == {"BBY", "SRP"}
    fts = next(s for s in sigs if s["source"] == "Find a Tender")
    assert fts["new"] == 722820.34  # value taken from the contract when the award has none
    assert fts["url"].startswith("https://")
    cf = next(s for s in sigs if s["source"] == "Contracts Finder")
    assert cf["url"] == "https://www.contractsfinder.service.gov.uk/Notice/819a2b22-31a7-41d8-bf97-15e2febf5192"
    assert fts["url"] == "https://www.find-tender.service.gov.uk/Notice/112310-2026"
    assert fts["framework"] and fts["note"].startswith("Named on")  # shared dynamic purchasing system, not a solo win
    # second run with the same notices: nothing new
    again, _, _ = contracts.scan(state, "2026-11-27T06:17:00Z")
    assert again == []


def test_mismatch_detected_once():
    co = [{"ticker": "SNG", "name": "Synairgen", "sponsor_terms": ["synairgen"]}]
    snaps = {
        "ctgov": {"SNG": {"NCT00000001": {"nct_id": "NCT00000001", "title": "T", "status": "RECRUITING",
                                          "url": "u1", "xrefs": ["ISRCTN12345678"]}}},
        "isrctn": {"SNG": {"ISRCTN12345678": {"id": "ISRCTN12345678", "title": "T", "status_override": "Stopped",
                                             "recruitment_start": "2025-01-01", "overall_end": "2027-01-01",
                                             "url": "u2", "xrefs": ["NCT00000001"]}}},
    }
    found = mismatch.find(co, snaps, "2026-11-26")
    assert len(found) == 1
    [s] = mismatch.signals(found, set(), "t")
    assert s["severity"] == "high" and s["type"] == "mismatch"
    assert mismatch.signals(found, set(found), "t") == []


def test_v1_snapshot_migrates(tmp_path, monkeypatch):
    latest = tmp_path / "latest.json"
    latest.write_text(json.dumps({"SCLP": {"NCT1": {"nct_id": "NCT1"}}}))
    monkeypatch.setattr(scan, "LATEST", latest)
    snap = scan.load_snapshot()
    assert snap["version"] == 2 and "SCLP" in snap["ctgov"]
