"""Sign-in for Indy's page and APIs is Vera's single sign-in; Indy keeps no PIN of its own.

The page forwards the PIN a person types to Vera and gets back a session token. Every guarded
route then asks Vera whether that token is still good (cached for a few seconds), so calling
the API directly without a session fails the same as going through the page. If Vera cannot
be reached the answer is 503, never "let it through": signed SOWs are commercially sensitive.

Only /health, the page shell, static files and the sign-in routes are open.
"""

from collections.abc import Callable

from fastapi import Header, HTTPException

from .vera_client import SsoGate, VeraClient, VeraError, VeraUnavailable


class UiAuth:
    def __init__(self, vera_factory: Callable[[], VeraClient]) -> None:
        self._factory = vera_factory
        self._gate: SsoGate | None = None

    def _get_gate(self) -> SsoGate:
        # built on first use so Indy still starts (and says why) when Vera is unconfigured
        if self._gate is None:
            self._gate = SsoGate(self._factory())
        return self._gate

    def login(self, pin: str) -> str:
        try:
            return self._get_gate().login(pin)["token"]
        except (VeraUnavailable, RuntimeError) as exc:
            raise HTTPException(503, str(exc)) from None
        except VeraError as exc:
            if exc.status == 401:
                raise HTTPException(401, "Wrong PIN") from None
            if exc.status == 429:
                raise HTTPException(429, exc.message) from None
            raise HTTPException(503, f"Vera would not check the PIN: {exc.message}") from None

    def logout(self, token: str | None) -> None:
        try:
            self._get_gate().logout(token)
        except (VeraUnavailable, VeraError, RuntimeError):
            pass  # the session expires on its own; signing out locally must still work

    def require_pin(
        self,
        x_admin_token: str | None = Header(default=None),
        authorization: str | None = Header(default=None),
    ) -> None:
        # scripts calling /v1 send the session as a Bearer token; the page sends X-Admin-Token
        token = x_admin_token
        if not token and authorization and authorization.lower().startswith("bearer "):
            token = authorization[7:].strip()
        try:
            ok = self._get_gate().valid(token)
        except (VeraUnavailable, VeraError, RuntimeError) as exc:
            raise HTTPException(503, f"Sign-in check unavailable, refusing: {exc}") from None
        if not ok:
            raise HTTPException(401, "PIN required")
