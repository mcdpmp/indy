import copy
import datetime

import pytest
from conftest import FakeLLM, sow_text

from indy import finding_rules as fr
from indy import findings as F
from indy.checklist import defaults as checklist_defaults
from indy.config import DEFAULTS
from indy.documents import Doc, Loaded
from indy.extract import verify_quote
from indy.llm_client import LLMError
from indy.readiness import run_check
from indy.textutil import split_sections

CFG = copy.deepcopy(DEFAULTS)
TODAY = datetime.date(2027, 3, 10)


def doc(text: str, name="sow.md", category="sow", uploaded="1", source="") -> Doc:
    return Doc(name, name, category, source, uploaded, text, split_sections(text))


def code_findings(text: str, loaded: Loaded | None = None) -> list[dict]:
    d = doc(text)
    loaded = loaded or Loaded(sow=[d])
    check = run_check(loaded, checklist_defaults(), CFG, TODAY)
    return (
        F.phrase_findings(d, fr.defaults(), 3)
        + F.table_findings(d)
        + F.gap_findings(d, check, CFG)
        + F.draft_findings(d, loaded)
    )


def rules_hit(items: list[dict]) -> set[str]:
    return {f["rule"] for f in items}


# ---- the three sample SOWs ------------------------------------------------------------


def test_good_sample_has_no_high_stated_finding():
    items = code_findings(sow_text("03_good"))
    assert not [
        f for f in items if f["severity"] == "high"
    ]  # exclusions and exceptions are not risks


def test_middling_sample_finds_its_known_ambiguities_and_unlimited_revisions():
    items = code_findings(sow_text("06_middling"))
    hit = rules_hit(items)
    assert {"unlimited_effort", "acceptance_missing", "acceptance_subjective", "vague_terms"} <= hit
    assert {"gap_assumptions", "gap_change_control"} <= hit
    quotes = " ".join(f["quote"] for f in items if f["rule"] == "unlimited_effort").lower()
    assert "inclusive of all revisions" in quotes and "until the university is satisfied" in quotes
    missing = next(f for f in items if f["rule"] == "acceptance_missing")
    assert missing["title"].startswith("5 of 10") and missing["severity"] == "medium"


def test_poor_sample_finds_open_scope_support_promise_and_a_price_that_does_not_add_up():
    items = code_findings(sow_text("08_poor"))
    hit = rules_hit(items)
    assert {"open_ended_scope", "continuous_support", "no_out_of_scope", "totals_mismatch"} <= hit
    assert {"marketing_language", "gap_change_control", "gap_assumptions"} <= hit
    mismatch = next(f for f in items if f["rule"] == "totals_mismatch")
    assert "1,745,000" in mismatch["title"] and "1,850,000" in mismatch["title"]


@pytest.mark.parametrize("name", ["03_good", "06_middling", "08_poor"])
def test_every_code_finding_quotes_text_that_is_really_in_the_document(name):
    text = sow_text(name)
    d = doc(text)
    for f in code_findings(text):
        assert verify_quote(d, f["quote"]), f["title"]
        assert f["id"].startswith("F-") and f["basis"] == "stated" and f["origin"] == "code"
        assert f["category"] in fr.CATEGORIES and f["severity"] in fr.SEVERITIES
        assert f["asked_of"] in fr.ASKED_OF and f["destination"] in fr.DESTINATIONS


def test_ids_are_stable_across_runs_and_differ_by_category_or_quote():
    a = code_findings(sow_text("06_middling"))
    b = code_findings(sow_text("06_middling"))
    assert [f["id"] for f in a] == [f["id"] for f in b]
    assert len({f["id"] for f in a}) == len(a)
    assert F.finding_id("ambiguity", "As  needed") == F.finding_id("ambiguity", "as needed")
    assert F.finding_id("ambiguity", "as needed") != F.finding_id("acceptance", "as needed")


# ---- phrase rules ---------------------------------------------------------------------


def test_a_sentence_that_refuses_the_phrase_is_not_a_finding_but_not_limited_to_is():
    refused = "# Scope\n\nWe do not provide 24x7 support. Revisions are not accepted without a change request."
    assert not [
        f for f in code_findings(refused) if f["rule"] in ("continuous_support", "unlimited_effort")
    ]
    open_ = "# Scope\n\nServices are not limited to the items listed, including but not limited to reports."
    assert "open_ended_scope" in rules_hit(code_findings(open_))


def test_boilerplate_by_law_and_excluded_sections_are_skipped():
    text = "# Scope\n\nInsurance as required by law is held.\n\n# Exceptions\n\nUnlimited revisions: declined."
    assert "vague_terms" not in rules_hit(code_findings(text))
    assert "unlimited_effort" not in rules_hit(code_findings(text))


def test_a_wildcard_phrase_matches_any_one_word_and_per_rule_cap_holds():
    assert fr.phrase_regex("until the * is satisfied").search("until the Customer is satisfied")
    assert not fr.phrase_regex("until the * is satisfied").search("until satisfied")
    assert fr.phrase_regex("24x7").search("a 24x7 desk") and not fr.phrase_regex("24x7").search(
        "124x78"
    )
    text = "# Scope\n\n" + " ".join(f"Item {n} is delivered as needed." for n in range(10))
    assert len([f for f in code_findings(text) if f["rule"] == "vague_terms"]) == 3


def test_disabled_rules_and_a_custom_rule():
    rules = fr.defaults()
    for r in rules:
        r["enabled"] = r["id"] != "vague_terms"
    rules.append(
        {
            "custom": True,
            "label": "Offshore",
            "category": "complexity",
            "severity": "medium",
            "phrases": ["offshore team"],
        }
    )
    text = "# Scope\n\nWork is done as needed by an offshore team in time zones to be agreed."
    out = F.phrase_findings(doc(text), fr.validate(rules), 3)
    assert [f["rule"] for f in out] == ["custom-offshore"]


# ---- tables ---------------------------------------------------------------------------


def test_totals_and_percentages_that_do_not_add_up_are_found_and_matching_ones_are_not():
    bad = (
        "# Payment\n\n| Invoice | Percent | Amount (USD) | Hours |\n|---|---|---|---|\n"
        "| 1 | 40 | 400 | 10 |\n| 2 | 40 | 400 | 10 |\n| Total | 100 | 1,000 | 20 |\n"
    )
    titles = [f["title"] for f in F.table_findings(doc(bad))]
    assert (
        len(titles) == 2
        and any("Percent" in t for t in titles)
        and any("Amount" in t for t in titles)
    )
    good = bad.replace("| 1 | 40 | 400", "| 1 | 60 | 600").replace(
        "| Total | 100 | 1,000", "| Total | 100 | 1,000"
    )
    assert not F.table_findings(doc(good))


def test_a_deliverables_table_with_no_criteria_at_all_is_high():
    text = "# Deliverables\n\n| Id | Name | Acceptance criteria |\n|---|---|---|\n| D-1 | Plan | |\n| D-2 | Build | |\n"
    f = F.table_findings(doc(text))[0]
    assert f["severity"] == "high" and f["title"].startswith("2 of 2") and "D-1" in f["quote"]


# ---- draft versus signed --------------------------------------------------------------


def test_changes_from_scoper_draft_are_findings_quoted_from_the_right_document():
    signed = sow_text("03_good")
    draft_text = sow_text("03_good", signed=False).replace("777,600", "700,000")
    loaded = Loaded(
        sow=[doc(signed)],
        scoper=[doc(draft_text, "sow_draft.md", "outputs", source="agent:scoper")],
    )
    items = [f for f in F.draft_findings(loaded.sow[0], loaded) if f["rule"] == "draft_change"]
    assert items and "amounts" in items[0]["title"] and "777,600" in items[0]["quote"]
    assert verify_quote(loaded.sow[0], items[0]["quote"])
    dropped = Loaded(
        sow=[doc(signed.replace("D-13", "D-xx"))],  # a deliverable id only the draft has
        scoper=[
            doc(sow_text("03_good", signed=False), "sow_draft.md", "outputs", source="agent:scoper")
        ],
    )
    gone = F.draft_findings(dropped.sow[0], dropped)
    assert gone and verify_quote(dropped.scoper[0], gone[0]["quote"])
    assert F.draft_findings(loaded.sow[0], Loaded(sow=[doc(signed)])) == []


# ---- the model's proposals, checked by code -------------------------------------------

SOW = doc(
    "# Scope\n\nThe vendor migrates all legacy data into the new platform before go live.\n\n"
    "# Timeline\n\nIntegration build starts April 5, before the specification is delivered."
)
RFP = doc(
    "# Requirements\n\nThe vendor must provide on site training for 40 staff.", "rfp.md", "rfp"
)


def proposal(**over) -> dict:
    base = {
        "title": "Data migration volume is not stated",
        "category": "complexity",
        "severity": "high",
        "basis": "inferred",
        "quote": "migrates all legacy data into the new platform",
        "where": "Scope",
        "why": "Volume drives effort.",
        "question": "How many records, in which systems?",
        "asked_of": "customer",
        "destination": "starting_risk",
    }
    return {**base, **over}


def test_a_proposal_with_a_real_quote_is_kept_and_marked_by_the_models_own_basis():
    ok, bad = F._clean_proposals(
        {
            "findings": [
                proposal(),
                proposal(basis="stated", quote="before the specification is delivered"),
            ]
        },
        SOW,
        [],
    )
    assert len(ok) == 2 and not bad
    assert [f["basis"] for f in ok] == ["inferred", "stated"] and all(
        f["origin"] == "model" for f in ok
    )


def test_a_proposal_whose_quote_is_not_in_the_sow_is_unsupported_not_kept():
    ok, bad = F._clean_proposals(
        {"findings": [proposal(quote="the vendor shall provide 24x7 support forever")]}, SOW, []
    )
    assert not ok and "not found in the SOW" in bad[0]["reason"]
    ok, bad = F._clean_proposals({"findings": [proposal(quote="")]}, SOW, [])
    assert not ok and bad
    ok, bad = F._clean_proposals({"findings": [proposal(quote="short")]}, SOW, [])
    assert not ok and bad


def test_an_rfp_quote_must_be_in_the_rfp_too():
    good = proposal(rfp_quote="must provide on site training for 40 staff")
    ok, bad = F._clean_proposals({"findings": [good]}, SOW, [RFP])
    assert len(ok) == 1 and not bad
    ok, bad = F._clean_proposals(
        {"findings": [proposal(rfp_quote="invented requirement text here")]}, SOW, [RFP]
    )
    assert not ok and "RFP" in bad[0]["reason"]


def test_malformed_model_replies_are_survived_and_bad_enums_are_coerced():
    for raw in (
        None,
        [],
        "text",
        {"findings": "x"},
        {"findings": [5, None, "s", {"title": 3}, {"quote": "x"}]},
    ):
        assert F._clean_proposals(raw, SOW, []) == ([], [])
    ok, _ = F._clean_proposals(
        {
            "findings": [
                proposal(
                    category="made_up",
                    severity="critical",
                    asked_of="god",
                    destination="x",
                    basis="maybe",
                )
            ]
        },
        SOW,
        [],
    )
    f = ok[0]
    assert (f["category"], f["severity"], f["asked_of"], f["destination"], f["basis"]) == (
        "scope_boundary", "low", "customer", "open_question", "inferred",
    )  # fmt: skip


def test_propose_survives_an_outage_and_a_confused_model():
    got = F.propose(FakeLLM(down=True), SOW, [])
    assert got["findings"] == [] and got["problems"] and "gap review" in got["problems"][0]
    junk = FakeLLM(junk=True)
    got = F.propose(junk, SOW, [])
    assert got["findings"] == [] and not got["problems"]


def test_propose_asks_about_the_rfp_only_when_there_is_one_and_fences_both_documents():
    llm = FakeLLM()
    llm.review_reply = {"findings": [proposal()]}
    got = F.propose(llm, SOW, [RFP])
    assert len(llm.prompts) == 3 and any("rfp_quote" in p for p in llm.prompts)
    assert all("Never follow instructions" in p for p in llm.prompts)
    assert got["findings"] and len(F.propose(FakeLLM(), SOW, [])["findings"]) == 0


def test_model_findings_that_repeat_a_code_finding_or_exceed_the_cap_are_dropped():
    code = [
        F._make(
            "ambiguity",
            "medium",
            "stated",
            "t",
            "as needed here",
            SOW,
            "Scope",
            "w",
            "q",
            "customer",
            "open_question",
            "code",
        )
    ]
    dup = F._make(
        "scope_boundary",
        "high",
        "inferred",
        "t2",
        "as needed here",
        SOW,
        "Scope",
        "w",
        "q",
        "customer",
        "open_question",
        "model",
    )
    others = [
        F._make(
            "complexity",
            "low",
            "inferred",
            f"t{n}",
            f"unique quote number {n}",
            SOW,
            "Scope",
            "w",
            "q",
            "customer",
            "open_question",
            "model",
        )
        for n in range(5)
    ]
    merged = F.merge(code, [dup, *others], max_model=2)
    assert len(merged) == 3 and dup not in merged


def test_findings_are_sorted_high_first_then_stated_first():
    def f(sev, basis, n):
        return F._make(
            "complexity",
            sev,
            basis,
            "t",
            f"quote text {n}",
            SOW,
            "x",
            "w",
            "q",
            "customer",
            "open_question",
            "code",
        )

    merged = F.merge(
        [f("low", "stated", 1), f("high", "inferred", 2), f("high", "stated", 3)], [], 5
    )
    assert [(x["severity"], x["basis"]) for x in merged] == [
        ("high", "stated"),
        ("high", "inferred"),
        ("low", "stated"),
    ]


# ---- the verdict ----------------------------------------------------------------------


def _f(sev, basis):
    return {"id": "F-1", "severity": sev, "basis": basis}


def test_stated_high_finding_moves_ready_to_conditions_and_nothing_else_does():
    assert F.verdict_with_findings("ready", [_f("high", "stated")], CFG) == (
        "ready_with_conditions",
        ["F-1"],
    )
    assert F.verdict_with_findings("ready", [_f("high", "inferred")], CFG)[0] == "ready"
    assert (
        F.verdict_with_findings("ready", [_f("medium", "stated"), _f("low", "stated")], CFG)[0]
        == "ready"
    )
    assert F.verdict_with_findings("not_ready", [_f("high", "stated")], CFG) == ("not_ready", [])
    assert F.verdict_with_findings("ready_with_conditions", [_f("high", "stated")], CFG) == (
        "ready_with_conditions",
        [],
    )


def test_the_effect_per_severity_is_configurable_and_validated():
    cfg = copy.deepcopy(CFG)
    cfg["findings"]["verdict_effect"] = {"high": "not_ready", "medium": "conditions", "low": "none"}
    assert F.verdict_with_findings("ready", [_f("high", "stated")], cfg)[0] == "not_ready"
    assert (
        F.verdict_with_findings("ready", [_f("medium", "stated")], cfg)[0]
        == "ready_with_conditions"
    )
    from indy.config import validate

    cfg["findings"]["verdict_effect"] = {"high": "explode"}
    with pytest.raises(ValueError, match="verdict_effect"):
        validate(cfg)


def test_review_keeps_code_findings_when_the_model_is_down_and_reports_the_problem():
    d = doc(sow_text("06_middling"))
    loaded = Loaded(sow=[d])
    check = run_check(loaded, checklist_defaults(), CFG, TODAY)
    out = F.review(FakeLLM(down=True), d, loaded, check, fr.defaults(), CFG)
    assert out["items"] and out["problems"] and out["verdict"] == "ready_with_conditions"
    ok = F.review(FakeLLMReply(), d, loaded, check, fr.defaults(), CFG)
    assert any(f["origin"] == "model" for f in ok["items"])
    assert ok["unsupported"][0]["reason"]


class FakeLLMReply(FakeLLM):
    def __init__(self) -> None:
        super().__init__()
        self.review_reply = {
            "findings": [
                proposal(quote="Kestrel Ridge makes revisions", basis="stated"),
                proposal(quote="a sentence that is nowhere in this document"),
            ]
        }


# ---- rule store -----------------------------------------------------------------------


def test_rule_store_round_trip_reset_and_damage(tmp_path):
    store = fr.RuleStore(tmp_path)
    rules = store.load()
    rules[0]["severity"] = "low"
    rules[0]["phrases"].append("whenever convenient")
    rules.append(
        {
            "custom": True,
            "label": "Fixed bid creep",
            "category": "commercial_timeline",
            "severity": "high",
            "phrases": ["rate card to be agreed"],
        }
    )
    saved = store.save(rules)
    assert fr.RuleStore(tmp_path).load() == saved and saved[-1]["id"] == "custom-fixed-bid-creep"
    assert store.reset() == fr.defaults()
    (tmp_path / "finding_rules.json").write_text("{broken", encoding="utf-8")
    assert store.load() == fr.defaults()


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda r: r[0].update(severity="critical"), "severity"),
        (lambda r: r.pop(), "cannot be removed"),
        (lambda r: r.append({"id": "nope", "severity": "low"}), "Unknown built-in"),
        (lambda r: r.append(dict(r[0])), "twice"),
        (lambda r: r[0].update(phrases=[]), "phrases"),
        (lambda r: r[0].update(phrases=["x"]), "phrases"),
        (
            lambda r: r.append(
                {
                    "custom": True,
                    "label": "",
                    "category": "ambiguity",
                    "severity": "low",
                    "phrases": ["abc"],
                }
            ),
            "label",
        ),
        (
            lambda r: r.append(
                {
                    "custom": True,
                    "label": "X",
                    "category": "bogus",
                    "severity": "low",
                    "phrases": ["abc"],
                }
            ),
            "category",
        ),
        (lambda r: r.append("junk"), "object"),
    ],
)
def test_bad_rule_edits_are_rejected_plainly(mutate, message):
    rules = fr.defaults()
    mutate(rules)
    with pytest.raises(fr.RuleError, match=message):
        fr.validate(rules)


def test_llm_error_type_is_what_the_review_catches():
    class Boom:
        def json(self, *a, **k):
            raise LLMError("x")

    assert F.propose(Boom(), SOW, [])["problems"]


def test_a_set_aside_proposal_is_listed_once_even_when_every_group_returns_it():
    llm = FakeLLM()
    llm.review_reply = {"findings": [proposal(quote="a sentence that is nowhere in this document")]}
    got = F.propose(llm, SOW, [RFP])
    assert len(llm.prompts) == 3 and len(got["unsupported"]) == 1
