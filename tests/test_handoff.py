import copy
import json
import time

import pytest
from conftest import MACHINE_SESSION, FakeLLM, FakeVera, sow_text
from fastapi.testclient import TestClient

from indy import handoff
from indy.server import create_app

H = {"X-Admin-Token": MACHINE_SESSION}


def _run(cfg, vera, llm=None, oid="OPP-1"):
    c = TestClient(create_app(cfg, vera_factory=lambda: vera, llm=llm or FakeLLM()))
    job_id = c.post("/v1/check", json={"opportunity_id": oid}, headers=H).json()["job_id"]
    for _ in range(300):
        job = c.get(f"/v1/jobs/{job_id}", headers=H).json()
        if job["status"] in ("done", "failed"):
            return c, job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def _vera(name="06_middling", signed=True, extra=()):
    v = FakeVera()
    v.add("d-sow", "signed_sow.md", "sow", sow_text(name, signed).encode())
    for doc_id, filename, category, body in extra:
        v.add(doc_id, filename, category, body)
    return v


def _file(vera, name="indy_handoff.json") -> dict:
    return json.loads(vera.outputs[name])


@pytest.mark.parametrize("name", ["03_good", "06_middling", "08_poor"])
def test_the_handoff_for_every_sample_is_written_under_the_stable_name_and_validates(cfg, name):
    vera = _vera(name)
    _, job = _run(cfg, vera)
    assert job["status"] == "done"
    doc = _file(vera)
    handoff.validate(doc)
    assert handoff.FILE_NAME == "indy_handoff.json" and doc["schema"] == "indy_handoff"
    assert doc["schema_version"] == handoff.SCHEMA_VERSION == "1.0"
    ref = job["result"]["stored_handoff"]["storage_ref"]
    assert ref.endswith("/outputs/indy/indy_handoff.json")


def test_the_handoff_names_the_exact_documents_and_what_was_not_read(cfg):
    vera = _vera(
        extra=[
            ("d-rfp", "rfp.md", "rfp", b"# RFP\n\nThe university needs seven apps."),
            ("d-msa", "msa.md", "other", b"# MSA\n\nTerms."),
            ("d-scan", "scan.pdf", "other", b"not a pdf"),
            ("o-draft", "sow_draft.md", "outputs", b"# Draft\n\nText here."),
        ]
    )
    vera.docs["o-draft"]["source"] = "agent:scoper"
    _run(cfg, vera)
    docs = _file(vera)["documents"]
    got = {d["doc_id"]: (d["filename"], d["role"]) for d in docs["considered"]}
    assert got == {
        "d-sow": ("signed_sow.md", "sow"),
        "d-msa": ("msa.md", "supporting"),
        "d-rfp": ("rfp.md", "rfp"),
        "o-draft": ("sow_draft.md", "scoper_output"),
    }
    assert docs["signed_sow"] == {
        "doc_id": "d-sow",
        "filename": "signed_sow.md",
        "signature_state": "signed",
    }
    assert docs["not_read"][0]["filename"] == "scan.pdf"


def test_findings_in_the_file_match_the_run_and_carry_quotes_ids_and_destinations(cfg):
    vera = _vera()
    c, _ = _run(cfg, vera)
    doc = _file(vera)
    run = c.get("/v1/runs/OPP-1", headers=H).json()
    assert [f["id"] for f in doc["findings"]] == [f["id"] for f in run["findings"]["items"]]
    for f in doc["findings"]:
        assert f["source_document"] == {"doc_id": "d-sow", "filename": "signed_sow.md"}
        assert len(f["quote"]) >= 8
        assert f["destination"] in ("starting_risk", "starting_issue", "open_question")
    assert doc["verdict"] == run["verdict"]
    assert doc["checklist_verdict"] == run["check"]["checklist_verdict"]


def test_unsupported_findings_never_reach_the_file(cfg):
    llm = FakeLLM()
    llm.review_reply = {
        "findings": [
            {
                "title": "Made up",
                "quote": "text that is nowhere in the document",
                "category": "complexity",
                "severity": "high",
            }
        ]
    }
    vera = _vera()
    c, _ = _run(cfg, vera, llm)
    assert c.get("/v1/runs/OPP-1", headers=H).json()["findings"]["unsupported"]
    assert "Made up" not in vera.outputs["indy_handoff.json"].decode()


def test_summary_and_methodology_are_marked_stated_or_inferred_and_suggestion_only(cfg):
    vera = _vera("03_good")
    _run(cfg, vera)
    doc = _file(vera)
    cust = doc["project_summary"]["customer"][0]
    assert cust["basis"] == "stated" and cust["quote"] and cust["document"] == "signed_sow.md"
    assert doc["project_summary"]["scope"][0]["basis"] == "inferred"
    assert doc["methodology_suggestion"]["suggestion"] == "waterfall"
    assert "Suggestion only" in doc["methodology_suggestion"]["note"]
    assert doc["inferred_followups"]["risks"] == ["Late data"]


def test_a_rerun_becomes_v2_and_the_file_says_to_read_the_newest(cfg):
    vera = _vera()
    _run(cfg, vera)
    _run(cfg, vera)
    assert {"indy_handoff.json", "indy_handoff__v2.json"} <= set(vera.outputs)
    assert "read the newest" in _file(vera)["how_to_read"]


def test_no_sow_gives_a_valid_file_with_no_summary_and_no_findings(cfg):
    vera = FakeVera()
    _, job = _run(cfg, vera)
    doc = _file(vera)
    handoff.validate(doc)
    assert job["result"]["verdict"] == "not_ready" and doc["documents"]["signed_sow"] is None
    assert doc["findings"] == [] and doc["project_summary"] is None
    assert doc["methodology_suggestion"] is None


def test_unsigned_sow_is_reported_as_such_in_the_file(cfg):
    vera = _vera(signed=False)
    _run(cfg, vera)
    assert _file(vera)["documents"]["signed_sow"]["signature_state"] == "unsigned"


def test_model_outage_still_writes_a_valid_file_with_the_problem_listed(cfg):
    vera = _vera()
    _, job = _run(cfg, vera, FakeLLM(down=True))
    doc = _file(vera)
    handoff.validate(doc)
    assert job["status"] == "done" and doc["model_problems"] and doc["inferred_followups"] is None
    assert doc["findings"]  # code findings survive


def test_an_invalid_file_fails_the_job_and_stores_nothing(cfg, monkeypatch):
    def boom(_doc):
        raise handoff.HandoffError("Handoff file is not valid at findings/0/id: bad")

    monkeypatch.setattr(handoff, "validate", boom)
    vera = _vera()
    _, job = _run(cfg, vera)
    assert job["status"] == "failed" and "not valid" in job["error"]
    assert not getattr(vera, "outputs", {})


@pytest.fixture
def sample(cfg) -> dict:
    vera = _vera()
    _run(cfg, vera)
    return copy.deepcopy(_file(vera))


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (lambda d: d.update(schema_version="v1"), "schema_version"),
        (lambda d: d.update(verdict="maybe"), "verdict"),
        (lambda d: d.update(extra="x"), "extra"),
        (lambda d: d.pop("findings"), "findings"),
        (lambda d: d["findings"][0].update(severity="critical"), "severity"),
        (lambda d: d["findings"][0].update(id="F-xyz"), "id"),
        (lambda d: d["findings"][0].update(quote="short"), "quote"),
        (lambda d: d["findings"][0].update(destination="somewhere"), "destination"),
        (lambda d: d["findings"][0].pop("source_document"), "source_document"),
        (lambda d: d["findings"][0].update(basis="computed"), "basis"),
        (lambda d: d["checklist"][0].update(status="great"), "status"),
        (lambda d: d["documents"]["considered"][0].pop("doc_id"), "doc_id"),
        (lambda d: d["methodology_suggestion"].update(suggestion="kanban"), "suggestion"),
        (lambda d: d["project_summary"]["people"].append({"text": "x"}), "people"),
    ],
)
def test_the_validator_rejects_malformed_files(sample, mutate, fragment):
    mutate(sample)
    with pytest.raises(handoff.HandoffError) as err:
        handoff.validate(sample)
    assert fragment in str(err.value)


def test_the_schema_file_is_valid_json_schema_with_no_long_dashes():
    from jsonschema import Draft202012Validator

    Draft202012Validator.check_schema(handoff.SCHEMA)
    assert chr(0x2014) not in json.dumps(handoff.SCHEMA)
    assert chr(0x2014) not in handoff.HOW_TO_READ
