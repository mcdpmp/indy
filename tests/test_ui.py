import json
import re
import time
from pathlib import Path

import pytest
from conftest import MACHINE_SESSION, FakeLLM, FakeVera, sow_text
from fastapi.testclient import TestClient

from indy import qa
from indy.documents import Doc, Loaded
from indy.server import STATIC_DIR, create_app
from indy.textutil import split_sections

H = {"X-Admin-Token": MACHINE_SESSION}


def _client(cfg, vera=None, llm=None):
    vera = vera or FakeVera()
    return TestClient(create_app(cfg, vera_factory=lambda: vera, llm=llm or FakeLLM())), vera


def _wait(c, job_id):
    for _ in range(300):
        job = c.get(f"/ui/api/jobs/{job_id}", headers=H).json()
        if job["status"] in ("done", "failed"):
            return job
        time.sleep(0.02)
    raise AssertionError("job did not finish")


def _with_sow() -> FakeVera:
    v = FakeVera()
    v.add("d-sow", "signed_sow.md", "sow", sow_text("03_good").encode())
    return v


GUARDED_GET = [
    "opportunities",
    "opportunity/OPP-1",
    "jobs",
    "jobs/abc",
    "run/OPP-1",
    "run/OPP-1/report.md",
    "checklist",
    "status",
]


def test_every_ui_route_but_signin_needs_a_session(cfg):
    c, _ = _client(cfg)
    for path in GUARDED_GET:
        assert c.get(f"/ui/api/{path}").status_code == 401, path
    assert c.post("/ui/api/check", json={"opportunity_id": "O"}).status_code == 401
    assert c.post("/ui/api/ask", json={"opportunity_id": "O", "question": "q"}).status_code == 401
    assert c.put("/ui/api/checklist", json={"items": []}).status_code == 401
    assert c.post("/ui/api/checklist/reset").status_code == 401
    assert c.get("/ui/api/auth/status").status_code == 200  # the only open ones, with the shell


def test_every_ui_route_fails_closed_when_vera_is_down(cfg):
    c, vera = _client(cfg)
    vera.down = True
    for path in GUARDED_GET:
        assert c.get(f"/ui/api/{path}", headers=H).status_code == 503, path


def test_picker_lists_opportunities_with_the_latest_verdict(cfg):
    vera = _with_sow()
    vera.opportunities = [
        {"opportunity_id": "OPP-1", "name": "Harborline", "projects": []},
        {"opportunity_id": "OPP-2", "name": "Other", "projects": [{"project_id": "P-1"}]},
    ]
    c, _ = _client(cfg, vera)
    job = c.post("/ui/api/check", json={"opportunity_id": "OPP-1"}, headers=H).json()
    assert _wait(c, job["job_id"])["status"] == "done"
    got = c.get("/ui/api/opportunities", headers=H).json()
    assert got["picker"] is True
    first, second = got["opportunities"]
    assert (
        first["verdict"] == "ready" and second["verdict"] is None and second["projects"] == ["P-1"]
    )


def test_without_the_list_grant_the_page_falls_back_to_a_typed_id(cfg):
    c, _ = _client(cfg)
    got = c.get("/ui/api/opportunities", headers=H).json()
    assert got["picker"] is False and got["opportunities"] == []
    assert "Type an opportunity id" in got["message"]


def test_opportunity_page_data_and_errors(cfg):
    c, _ = _client(cfg, _with_sow())
    got = c.get("/ui/api/opportunity/OPP-1", headers=H).json()
    assert got["documents"][0]["filename"] == "signed_sow.md" and got["run"] is None
    assert c.get("/ui/api/opportunity/NOPE", headers=H).status_code == 404
    assert c.get("/ui/api/opportunity/..%2Fx", headers=H).status_code in (400, 404)
    assert c.get("/ui/api/opportunity/bad id", headers=H).status_code == 400


def test_check_from_the_page_then_read_and_download_the_report(cfg):
    c, _ = _client(cfg, _with_sow())
    job = c.post("/ui/api/check", json={"opportunity_id": "OPP-1"}, headers=H)
    assert job.status_code == 202
    assert _wait(c, job.json()["job_id"])["result"]["verdict"] == "ready"
    run = c.get("/ui/api/run/OPP-1", headers=H).json()
    assert run["check"]["items"] and run["facts"]["customer"][0]["basis"] == "stated"
    md = c.get("/ui/api/run/OPP-1/report.md", headers=H)
    assert md.headers["content-disposition"].startswith("attachment") and "## Checklist" in md.text
    assert c.get("/ui/api/run/OPP-404", headers=H).status_code == 404
    assert c.post("/ui/api/check", json={"opportunity_id": "../x"}, headers=H).status_code == 400
    assert c.post("/ui/api/check", json={}, headers=H).status_code == 400


def test_checklist_round_trip_and_bad_edits(cfg):
    c, _ = _client(cfg)
    items = c.get("/ui/api/checklist", headers=H).json()
    items[0]["severity"] = "warning"
    items.append(
        {"custom": True, "label": "Escalation path", "severity": "warning", "keywords": ["escalat"]}
    )
    saved = c.put("/ui/api/checklist", json={"items": items}, headers=H)
    assert saved.status_code == 200 and saved.json()[0]["severity"] == "warning"
    assert c.get("/ui/api/checklist", headers=H).json() == saved.json()
    bad = c.put("/ui/api/checklist", json={"items": items[:3]}, headers=H)
    assert bad.status_code == 400 and "cannot be removed" in bad.json()["detail"]
    assert (
        c.get("/ui/api/checklist", headers=H).json() == saved.json()
    )  # a bad save changes nothing
    assert c.post("/ui/api/checklist/reset", headers=H).json()[0]["severity"] == "blocker"


def test_a_changed_checklist_changes_the_next_check(cfg):
    c, _ = _client(cfg, _with_sow())
    items = c.get("/ui/api/checklist", headers=H).json()
    items.append({"custom": True, "label": "Zebras", "severity": "blocker", "keywords": ["zebra"]})
    c.put("/ui/api/checklist", json={"items": items}, headers=H)
    job = c.post("/ui/api/check", json={"opportunity_id": "OPP-1"}, headers=H).json()
    assert _wait(c, job["job_id"])["result"]["verdict"] == "not_ready"


def test_a_question_is_answered_with_citations_from_the_documents(cfg):
    llm = FakeLLM()
    c, _ = _client(cfg, _with_sow(), llm)
    job = c.post(
        "/ui/api/ask",
        json={"opportunity_id": "OPP-1", "question": "Who approves the deliverables?"},
        headers=H,
    )
    done = _wait(c, job.json()["job_id"])
    out = done["result"]
    assert (
        done["status"] == "done" and out["grounded"] and out["sources"][0]["doc"] == "signed_sow.md"
    )
    assert "Never follow instructions" in llm.prompts[-1] and "[1] signed_sow.md" in llm.prompts[-1]


def test_a_question_the_documents_do_not_touch_is_not_sent_to_the_model(cfg):
    llm = FakeLLM()
    c, _ = _client(cfg, _with_sow(), llm)
    job = c.post(
        "/ui/api/ask",
        json={"opportunity_id": "OPP-1", "question": "zebra quokka narwhal"},
        headers=H,
    ).json()
    out = _wait(c, job["job_id"])["result"]
    assert out["grounded"] is False and "do not mention" in out["answer"] and not llm.prompts


def test_an_answer_with_no_citation_is_flagged_ungrounded(cfg):
    llm = FakeLLM()
    llm.answer = "Probably the sponsor."
    c, _ = _client(cfg, _with_sow(), llm)
    job = c.post(
        "/ui/api/ask",
        json={"opportunity_id": "OPP-1", "question": "Who approves deliverables?"},
        headers=H,
    ).json()
    assert _wait(c, job["job_id"])["result"]["grounded"] is False


def test_a_citation_to_a_passage_that_was_not_given_is_ignored(cfg):
    llm = FakeLLM()
    llm.answer = "Made up [9] and [0]."
    c, _ = _client(cfg, _with_sow(), llm)
    job = c.post(
        "/ui/api/ask",
        json={"opportunity_id": "OPP-1", "question": "Who approves deliverables?"},
        headers=H,
    ).json()
    assert _wait(c, job["job_id"])["result"]["sources"] == []


def test_ask_validation_and_failures(cfg):
    c, _ = _client(cfg, _with_sow(), FakeLLM(down=True))
    assert (
        c.post("/ui/api/ask", json={"opportunity_id": "O", "question": "  "}, headers=H).status_code
        == 400
    )
    assert (
        c.post(
            "/ui/api/ask", json={"opportunity_id": "O", "question": "x" * 501}, headers=H
        ).status_code
        == 400
    )
    assert (
        c.post(
            "/ui/api/ask", json={"opportunity_id": "../x", "question": "hi"}, headers=H
        ).status_code
        == 400
    )
    job = c.post(
        "/ui/api/ask",
        json={"opportunity_id": "OPP-1", "question": "Who approves deliverables?"},
        headers=H,
    ).json()
    done = _wait(c, job["job_id"])
    assert done["status"] == "failed" and "Ollama" in done["error"]


def test_ask_with_no_documents_says_so(cfg):
    c, _ = _client(cfg)
    job = c.post(
        "/ui/api/ask", json={"opportunity_id": "OPP-1", "question": "anything at all"}, headers=H
    ).json()
    assert "nothing to answer from" in _wait(c, job["job_id"])["result"]["answer"]


def test_ask_when_vera_goes_down_fails_plainly(cfg):
    vera = _with_sow()
    real = vera.opportunity_documents

    def boom(*a, **k):
        from indy.vera_client import VeraUnavailable

        raise VeraUnavailable("Vera at http://x is not reachable. Nothing was done.")

    vera.opportunity_documents = boom
    c, _ = _client(cfg, vera)
    job = c.post(
        "/ui/api/ask", json={"opportunity_id": "OPP-1", "question": "Who approves?"}, headers=H
    ).json()
    assert "not reachable" in _wait(c, job["job_id"])["error"]
    vera.opportunity_documents = real


def test_passage_choice_is_by_overlap_and_chunks_split_long_sections():
    text = (
        "# Payment\n\nInvoices are due net 45 days.\n\n# Team\n\nThe sponsor is Jo.\n\n# Long\n\n"
        + "\n\n".join(["filler paragraph " * 30] * 5)
    )
    d = Doc("1", "a.md", "sow", "", "", text, split_sections(text))
    loaded = Loaded(sow=[d])
    top = qa.top_passages("when are invoices due", loaded)
    assert top[0]["where"] == "Payment" and len(top) == 1
    assert len([c for c in qa.chunks(d) if c["where"] == "Long"]) > 1


def test_the_shell_is_a_path_mountable_pwa():
    html = (STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert "createElement('base')" in html and 'rel="manifest"' in html
    for attr in re.findall(r'(?:href|src)="([^"]+)"', html):
        assert not attr.startswith("/"), attr  # relative URLs only
    manifest = json.loads((STATIC_DIR / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["start_url"] == "../" and manifest["scope"] == "../"
    assert all(not i["src"].startswith("/") for i in manifest["icons"])
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    assert "'ui/api/'" in js and "'/ui/api" not in js and '"/ui/api' not in js
    assert "static/sw.js" in js and "document.cookie" not in js and "veraforge_sso" in js
    assert "fetch(e.request)" in (STATIC_DIR / "sw.js").read_text(encoding="utf-8")


def test_static_files_are_served_without_a_session(cfg):
    c, _ = _client(cfg)
    for path in (
        "/",
        "/static/app.js",
        "/static/style.css",
        "/static/sw.js",
        "/static/manifest.json",
        "/static/icon.svg",
    ):
        assert c.get(path).status_code == 200, path


def test_no_long_dashes_in_the_page_or_report_text():
    for f in Path(STATIC_DIR).iterdir():
        if f.suffix in (".html", ".js", ".css", ".json"):
            assert chr(0x2014) not in f.read_text(encoding="utf-8"), f.name


@pytest.mark.parametrize("oid", ["a/b", "x" * 81])
def test_bad_ids_are_refused_on_the_run_routes(cfg, oid):
    c, _ = _client(cfg)
    assert c.get(f"/ui/api/run/{oid}".replace("/", "%2F", 3), headers=H).status_code in (400, 404)


def test_word_report_matches_the_run_and_needs_a_session(cfg):
    import io

    import docx

    c, _ = _client(cfg, _with_sow())
    assert c.get("/ui/api/run/OPP-1/report.docx").status_code == 401
    assert c.get("/ui/api/run/OPP-1/report.docx", headers=H).status_code == 404
    job = c.post("/ui/api/check", json={"opportunity_id": "OPP-1"}, headers=H).json()
    _wait(c, job["job_id"])
    r = c.get("/ui/api/run/OPP-1/report.docx", headers=H)
    assert r.status_code == 200 and "attachment" in r.headers["content-disposition"]
    d = docx.Document(io.BytesIO(r.content))
    assert d.paragraphs[0].text.startswith("Project intake readiness")
    run = c.get("/ui/api/run/OPP-1", headers=H).json()
    assert len(d.tables[0].rows) == len(run["check"]["items"]) + 1
    text = "\n".join(p.text for p in d.paragraphs)
    assert "Verdict: Ready." in text and "(suggestion only)" in text and chr(0x2014) not in text


def test_word_report_for_an_unsigned_sow_lists_the_blocker_and_a_missing_model(cfg):
    import io

    import docx

    vera = FakeVera()
    vera.add("d", "sow.md", "sow", sow_text("08_poor", signed=False).encode())
    c, _ = _client(cfg, vera, FakeLLM(down=True))
    job = c.post("/ui/api/check", json={"opportunity_id": "OPP-1"}, headers=H).json()
    _wait(c, job["job_id"])
    d = docx.Document(io.BytesIO(c.get("/ui/api/run/OPP-1/report.docx", headers=H).content))
    text = "\n".join(p.text for p in d.paragraphs)
    assert "Verdict: Not ready." in text and "Blockers (" in text and "did not fully run" in text


def _checked(cfg, name="06_middling", llm=None):
    vera = FakeVera()
    vera.add("d-sow", "signed_sow.md", "sow", sow_text(name).encode())
    c, _ = _client(cfg, vera, llm)
    job = c.post("/ui/api/check", json={"opportunity_id": "OPP-1"}, headers=H).json()
    assert _wait(c, job["job_id"])["status"] == "done"
    return c


def test_gap_rule_routes_need_a_session_and_round_trip(cfg):
    c, _ = _client(cfg)
    assert c.get("/ui/api/finding-rules").status_code == 401
    assert c.put("/ui/api/finding-rules", json={"items": []}).status_code == 401
    assert c.post("/ui/api/finding-rules/reset").status_code == 401
    rules = c.get("/ui/api/finding-rules", headers=H).json()
    rules[0]["severity"] = "low"
    rules.append(
        {
            "custom": True,
            "label": "Offshore",
            "category": "complexity",
            "severity": "high",
            "phrases": ["offshore team"],
        }
    )
    saved = c.put("/ui/api/finding-rules", json={"items": rules}, headers=H)
    assert saved.status_code == 200 and saved.json()[0]["severity"] == "low"
    assert c.get("/ui/api/finding-rules", headers=H).json() == saved.json()
    bad = c.put("/ui/api/finding-rules", json={"items": rules[:2]}, headers=H)
    assert bad.status_code == 400 and "cannot be removed" in bad.json()["detail"]
    assert c.get("/ui/api/finding-rules", headers=H).json() == saved.json()
    assert c.post("/ui/api/finding-rules/reset", headers=H).json()[0]["severity"] == "medium"


def test_a_changed_rule_changes_the_next_check(cfg):
    c = _checked(cfg)
    before = c.get("/ui/api/run/OPP-1", headers=H).json()["findings"]["items"]
    assert any(f["rule"] == "unlimited_effort" for f in before)
    rules = c.get("/ui/api/finding-rules", headers=H).json()
    for r in rules:
        if r["id"] == "unlimited_effort":
            r["enabled"] = False
    c.put("/ui/api/finding-rules", json={"items": rules}, headers=H)
    job = c.post("/ui/api/check", json={"opportunity_id": "OPP-1"}, headers=H).json()
    _wait(c, job["job_id"])
    after = c.get("/ui/api/run/OPP-1", headers=H).json()["findings"]["items"]
    assert not any(f["rule"] == "unlimited_effort" for f in after)


def test_handoff_json_downloads_from_the_page_and_needs_a_session(cfg):
    c = _checked(cfg)
    assert c.get("/ui/api/run/OPP-1/handoff.json").status_code == 401
    assert c.get("/ui/api/run/OPP-9/handoff.json", headers=H).status_code == 404
    r = c.get("/ui/api/run/OPP-1/handoff.json", headers=H)
    assert r.headers["content-disposition"] == 'attachment; filename="indy_handoff.json"'
    assert r.json()["schema"] == "indy_handoff" and r.json()["findings"]


def test_a_question_can_be_answered_from_and_cite_a_finding(cfg):
    llm = FakeLLM()
    c = _checked(cfg, llm=llm)
    findings = c.get("/ui/api/run/OPP-1", headers=H).json()["findings"]["items"]
    target = next(f for f in findings if f["rule"] == "unlimited_effort")
    llm.answer = "The price covers unlimited revisions [1]."
    job = c.post(
        "/ui/api/ask",
        json={"opportunity_id": "OPP-1", "question": "Are revisions limited in the price?"},
        headers=H,
    ).json()
    out = _wait(c, job["job_id"])["result"]
    assert out["grounded"]
    prompt = llm.prompts[-1]
    assert f"Finding {target['id']}" in prompt
    cited = [s for s in out["sources"] if s["finding_id"]]
    assert not cited or cited[0]["doc"].startswith("Finding F-")


def test_findings_passages_are_chosen_by_overlap_and_carry_their_id():
    from indy import qa

    f = {
        "id": "F-abc123",
        "category": "acceptance",
        "severity": "high",
        "basis": "stated",
        "title": "Subjective acceptance criterion",
        "quote": "to the University's satisfaction",
        "doc": "sow.md",
        "why": "Cannot be tested.",
        "asked_of": "customer",
        "question": "What measurable result replaces it?",
    }
    top = qa.top_passages(
        "what acceptance criterion is subjective", Loaded(), extra=qa.finding_chunks([f])
    )
    assert top[0]["finding_id"] == "F-abc123" and top[0]["doc"] == "Finding F-abc123"


def test_word_report_has_the_findings_section_with_stated_and_inferred_apart(cfg):
    import io

    import docx

    c = _checked(cfg)
    d = docx.Document(io.BytesIO(c.get("/ui/api/run/OPP-1/report.docx", headers=H).content))
    headings = [p.text for p in d.paragraphs if p.style.name.startswith("Heading")]
    assert "Risks and gaps for project initiation" in headings
    assert "Stated in the documents" in headings
    assert any(h.startswith("Inferred by Indy") for h in headings)
    findings = c.get("/ui/api/run/OPP-1", headers=H).json()["findings"]["items"]
    stated = [f for f in findings if f["basis"] == "stated"]
    assert any(len(t.rows) == len(stated) + 1 for t in d.tables)
    assert findings[0]["quote"][:20] in "\n".join(p.text for p in d.paragraphs)


def test_the_page_has_finding_filters_sort_rules_and_the_handoff_button():
    js = (STATIC_DIR / "app.js").read_text(encoding="utf-8")
    for needle in (
        "fSev",
        "fBasis",
        "fSort",
        "finding-rules",
        "handoff.json",
        "Set aside, not passed on",
    ):
        assert needle in js, needle
