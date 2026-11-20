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
        text = re.sub(r"\| Date \| \| \|", "| Date | March 1, 2027 | March 2, 2027 |", text)
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
