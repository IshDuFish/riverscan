from scanner.diff import diff_all
from scanner.fetch import simplify

CO = [{"ticker": "SCLP", "name": "Scancell", "sponsor_terms": ["scancell"]}]


def trial(**kw):
    base = {"nct_id": "NCT1", "title": "Test", "sponsors": ["Scancell Ltd"], "status": "RECRUITING",
            "why_stopped": None, "phase": "PHASE2", "enrollment": 100, "primary_completion": "2027-06",
            "completion": "2027-12", "last_update": "2026-11-01", "has_results": False,
            "url": "https://clinicaltrials.gov/study/NCT1"}
    base.update(kw)
    return base


def test_first_run_is_baseline_only():
    assert diff_all(CO, {}, {"SCLP": {"NCT1": trial()}}, "t") == []


def test_no_change_no_signal():
    snap = {"SCLP": {"NCT1": trial()}}
    assert diff_all(CO, snap, snap, "t") == []


def test_termination_is_high_with_reason():
    old = {"SCLP": {"NCT1": trial()}}
    new = {"SCLP": {"NCT1": trial(status="TERMINATED", why_stopped="Sponsor decision")}}
    [s] = diff_all(CO, old, new, "t")
    assert s["severity"] == "high" and "Sponsor decision" in s["note"]


def test_multiple_changes_and_new_trial():
    old = {"SCLP": {"NCT1": trial()}}
    new = {"SCLP": {"NCT1": trial(enrollment=60, primary_completion="2028-01"),
                    "NCT2": trial(nct_id="NCT2")}}
    sigs = diff_all(CO, old, new, "t")
    kinds = {(s["type"], s["field"]) for s in sigs}
    assert kinds == {("change", "enrollment"), ("change", "primary_completion"), ("new_trial", None)}
    assert all(s["severity"] == "medium" for s in sigs)


def test_simplify_parses_api_shape():
    raw = {"hasResults": True, "protocolSection": {
        "identificationModule": {"nctId": "NCT9", "briefTitle": "X"},
        "statusModule": {"overallStatus": "COMPLETED",
                         "primaryCompletionDateStruct": {"date": "2025-01"},
                         "completionDateStruct": {"date": "2025-03"},
                         "lastUpdatePostDateStruct": {"date": "2025-04-01"}},
        "designModule": {"phases": ["PHASE1", "PHASE2"], "enrollmentInfo": {"count": 40}},
        "sponsorCollaboratorsModule": {"leadSponsor": {"name": "Scancell Ltd"},
                                       "collaborators": [{"name": "Uni"}]}}}
    r = simplify(raw)
    assert r["phase"] == "PHASE1/PHASE2" and r["enrollment"] == 40 and r["has_results"]
    assert r["sponsors"] == ["Scancell Ltd", "Uni"]
