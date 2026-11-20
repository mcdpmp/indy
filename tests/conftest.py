import copy

import pytest

from indy.config import DEFAULTS
from indy.vera_client import VeraError, VeraUnavailable

MACHINE_SESSION = "machine-session"


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
