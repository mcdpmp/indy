import copy
import hashlib
import re
from datetime import date
from pathlib import Path

import pytest

from indy.config import DEFAULTS
from indy.vera_client import VeraError, VeraUnavailable

MACHINE_SESSION = "machine-session"
FIXTURES = Path(__file__).parent / "fixtures"
TODAY = date(2027, 3, 10)


def sow_text(name: str, signed: bool = True) -> str:
    """One of the three fictional sample SOWs. Their signature cells are blank, as an unsigned
    SOW is, so a signed copy is made by filling them in."""
    text = (FIXTURES / f"sow_{name}.md").read_text(encoding="utf-8")
    if signed:
        text = re.sub(r"\| Signature \| \| \|", "| Signature | /s/ A Person | /s/ B Person |", text)
        text = re.sub(r"\| Date \| \| \|", "| Date | March 1, 2025 | March 2, 2025 |", text)
    return text


@pytest.fixture
def cfg(tmp_path):
    c = copy.deepcopy(DEFAULTS)
    c["paths"]["state_dir"] = str(tmp_path / "state")
    return c


class FakeVera:
    """Stands in for Vera's single sign-in until a live Vera and key exist."""

    def __init__(self, down: bool = False) -> None:
        self.down = down
        self.pin, self.locked, self.sso_grant = "1234", False, True
        self.sessions = {MACHINE_SESSION}

    def _check(self) -> None:
        if self.down:
            raise VeraUnavailable("Vera at http://x is not reachable. Nothing was done.")

    def sso_login(self, pin: str) -> dict:
        self._check()
        if not self.sso_grant:
            raise VeraError(403, "forbidden", "this agent does not hold the sso grant")
        if self.locked:
            raise VeraError(429, "too_many_attempts", "Too many failed attempts. Try again soon.")
        if pin != self.pin:
            raise VeraError(401, "bad_pin", "Wrong PIN")
        token = f"vera-session-{len(self.sessions) + 1}"
        self.sessions.add(token)
        return {"token": token, "expires_at": "2026-12-01T00:00:00Z"}

    def sso_introspect(self, token: str) -> dict:
        self._check()
        return {"valid": token in self.sessions}

    def sso_logout(self, token: str) -> dict:
        self.sessions.discard(token)
        return {"ended": True}

    # documents
    def add(self, doc_id: str, filename: str, category: str, content: bytes, **extra) -> None:
        if not hasattr(self, "docs"):
            self.docs, self.content = {}, {}
        self.docs[doc_id] = {"doc_id": doc_id, "filename": filename, "category": category, **extra}
        self.content[doc_id] = content

    def opportunity_documents(self, oid, *, category=None, include_outputs=False):
        self._check()
        docs = getattr(self, "docs", {})
        return [
            {**d, "sha256": hashlib.sha256(self.content[d["doc_id"]]).hexdigest()}
            for d in docs.values()
            if (include_outputs or d["category"] != "outputs")
            and (category is None or d["category"] == category)
        ]

    def fetch(self, doc_id):
        self._check()
        if doc_id in getattr(self, "forbidden", set()):
            raise VeraError(403, "forbidden", "outside this agent's read scope")
        return self.content[doc_id]

    # opportunity metadata and outputs
    def opportunity(self, oid):
        self._check()
        if oid == "NOPE":
            raise VeraError(404, "not_found", "no such opportunity")
        return {"opportunity_id": oid, "name": "Harborline claims triage"}

    def put_opportunity_output(self, oid, filename, data):
        self._check()
        if getattr(self, "reject_outputs", False):
            raise VeraError(413, "too_large", "file too large")
        outputs = self.__dict__.setdefault("outputs", {})
        stem, dot, ext = filename.rpartition(".")
        name, n = filename, 1
        while name in outputs:  # Vera never overwrites: a clash becomes name__v2.ext
            n += 1
            name = f"{stem}__v{n}{dot}{ext}"
        outputs[name] = data
        return {"storage_ref": f"{oid}/_opportunity/outputs/indy/{name}"}


def _list_opportunities(self):
    self._check()
    if getattr(self, "opportunities", None) is None:
        raise VeraError(403, "forbidden", "this agent does not hold the list_projects grant")
    return self.opportunities


FakeVera.list_opportunities = _list_opportunities


class FakeLLM:
    """Stands in for Ollama. Answers by the TASK line in the prompt."""

    def __init__(self, down: bool = False, junk: bool = False) -> None:
        self.down, self.junk, self.prompts = down, junk, []
        self.answer = "The Client Sponsor accepts deliverables [1]."

    def text(self, prompt, **kw):
        from indy.llm_client import LLMError

        self.prompts.append(prompt)
        if self.down:
            raise LLMError("Ollama call failed: connection refused")
        return self.answer

    def json(self, prompt, retries=1, **kw):
        from indy.llm_client import LLMError

        self.prompts.append(prompt)
        if self.down:
            raise LLMError("Ollama call failed: connection refused")
        if self.junk:  # what a prompt-injected or confused model might send back
            return {
                "suggestion": "ignore all rules",
                "reasoning": 5,
                "customer": "owned",
                "scope": [5, None, {"text": ""}],
            }
        if "TASK: extract project facts" in prompt:
            fields = re.findall(r'^- "(\w+)":', prompt, re.MULTILINE)
            good = "Harborline Mutual Insurance Company"
            return {
                f: [
                    {
                        "text": f"{f} item",
                        "quote": good if f == "customer" else "words that are not in the document",
                    }
                ]
                for f in fields
            }
        if "TASK: suggest a delivery methodology" in prompt:
            return {"suggestion": "waterfall", "reasoning": "Fixed price with milestones."}
        return {
            "customer_questions": ["Who signs acceptance?"],
            "delivery_questions": ["Is the team staffed?"],
            "risks": ["Late data"],
            "later_agents_need": ["The deliverables list"],
        }
