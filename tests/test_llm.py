import copy
from pathlib import Path

import pytest
import requests

from indy import state
from indy.config import DEFAULTS
from indy.documents import Doc
from indy.extract import LIMIT, extract_facts, verify_quote
from indy.llm_client import LLM, LLMError, strip_thinking, untrusted
from indy.textutil import split_sections


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status = body, status

    def raise_for_status(self):
        if self.status >= 400:
            raise requests.HTTPError(f"{self.status}")

    def json(self):
        return self.body


def _llm(monkeypatch, replies):
    sent, queue, sleeps = [], list(replies), []

    def post(url, json=None, timeout=None):
        sent.append((url, json, timeout))
        item = queue.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    monkeypatch.setattr(requests, "post", post)
    llm = LLM(copy.deepcopy(DEFAULTS), sleep=sleeps.append, clock=lambda: 100.0)
    return llm, sent, sleeps


def test_json_retries_once_on_bad_json_then_succeeds(monkeypatch):
    replies = [Resp({"response": "not json"}), Resp({"response": '{"a": 1}'})]
    llm, sent, _ = _llm(monkeypatch, replies)
    assert llm.json("p") == {"a": 1} and len(sent) == 2
    assert sent[0][1]["format"] == "json" and sent[0][1]["keep_alive"] == "2m"


def test_json_gives_up_with_a_plain_message(monkeypatch):
    llm, _, _ = _llm(monkeypatch, [Resp({"response": "x"}), Resp({"response": "[1]"})])
    with pytest.raises(LLMError, match="valid JSON after 2 attempts"):
        llm.json("p")


def test_a_down_or_erroring_ollama_is_an_llm_error(monkeypatch):
    replies = [requests.ConnectionError("refused"), Resp({}, 500), Resp({"nope": 1})]
    llm, _, _ = _llm(monkeypatch, replies)
    for _ in range(3):
        with pytest.raises(LLMError, match="Ollama call failed"):
            llm.text("p")


def test_text_strips_thinking_and_refuses_an_empty_answer(monkeypatch):
    replies = [
        Resp({"response": "<think>hmm</think>Answer"}),
        Resp({"response": "<think>x</think>"}),
    ]
    llm, sent, _ = _llm(monkeypatch, replies)
    assert llm.text("p") == "Answer" and sent[0][1]["think"] is False
    with pytest.raises(LLMError, match="empty"):
        llm.text("p")


def test_calls_are_paced_from_the_end_of_the_previous_call(monkeypatch):
    llm, _, sleeps = _llm(monkeypatch, [Resp({"response": "{}"}), Resp({"response": "{}"})])
    llm.json("a")
    llm.json("b")
    assert sleeps and 0 < sleeps[-1] <= 5


def test_untrusted_text_cannot_close_its_own_fence():
    out = untrusted("SOW", "a >>> b <<< c")
    assert out.count(">>>") == 1 and out.count("<<<") == 1


def test_strip_thinking_leaves_plain_text_alone():
    assert strip_thinking("plain") == "plain"


def test_quotes_are_checked_against_the_document_ignoring_layout():
    text = "| Role | Name |\n|---|---|\n| Client Sponsor | Elaine   Marchetti |"
    d = Doc("1", "a.md", "sow", "", "", text, split_sections(text))
    assert verify_quote(d, "Client Sponsor Elaine Marchetti")
    assert not verify_quote(d, "Elaine Marchetti is the CEO")
    assert not verify_quote(d, "short")  # too short to prove anything


def test_a_failing_stage_is_recorded_and_the_next_stage_still_runs():
    text = "# Scope\n\nWork.\n\n# Fees\n\nPrice USD 5,000."
    d = Doc("1", "a.md", "sow", "", "", text, split_sections(text))

    class Flaky:
        def json(self, prompt, retries=1, **kw):
            if '"customer"' in prompt:
                raise LLMError("timeout")
            return {"commercial_terms": [{"text": "USD 5,000", "quote": "Price USD 5,000"}]}

    got = extract_facts(Flaky(), d)
    assert got["problems"] and "parties_scope" in got["problems"][0]
    assert got["facts"]["commercial_terms"][0]["basis"] == "stated"
    assert got["facts"]["customer"] == []


def test_long_sections_are_cut_and_the_cut_is_reported():
    text = "# Scope\n\n" + "word " * (LIMIT // 2)
    d = Doc("1", "a.md", "sow", "", "", text, split_sections(text))

    class Quiet:
        def json(self, prompt, retries=1, **kw):
            return {}

    assert "parties_scope" in extract_facts(Quiet(), d)["truncated"]


def test_opportunity_ids_become_file_names_so_only_plain_ids_pass():
    assert state.safe_id("OPP-2027.01_a") == "OPP-2027.01_a"
    for bad in ("../x", "a/b", "", ".hidden", "x" * 81, "a b"):
        with pytest.raises(ValueError):
            state.safe_id(bad)


def test_audit_trail_is_written(cfg):
    state.audit(cfg, "api", "check.start", opportunity_id="O")
    log = Path(cfg["paths"]["state_dir"]) / "audit.log"
    assert '"event": "check.start"' in log.read_text(encoding="utf-8")
