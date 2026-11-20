"""Tiny client every VeraForge worker uses to talk to Vera.

Contract (docs/worker_contract.md):
  VERA_URL        e.g. http://host.docker.internal:5100
  VERA_AGENT_KEY  issued with `python -m vera.cli issue-key <agent>`

If Vera is unreachable the client retries with backoff and then raises VeraUnavailable with a
clear message. Workers must surface it. Never guess, never continue with missing data.
Stdlib plus httpx only, so it can be copied into any worker image unchanged.
"""

import os
import time

import httpx


class VeraError(Exception):
    """Vera answered with an error (4xx or 5xx)."""

    def __init__(self, status: int, code: str, message: str):
        super().__init__(f"Vera said {status} {code}: {message}")
        self.status, self.code, self.message = status, code, message


class VeraUnavailable(Exception):
    """Vera could not be reached after retries."""


class VeraClient:
    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
        *,
        retries: int = 4,
        backoff: float = 0.5,
        timeout: float = 30.0,
        transport: httpx.BaseTransport | None = None,
    ):
        self.url = (url or os.environ.get("VERA_URL", "")).rstrip("/")
        key = key or os.environ.get("VERA_AGENT_KEY", "")
        if not self.url or not key:
            raise RuntimeError("VERA_URL and VERA_AGENT_KEY must be set")
        self.retries, self.backoff = retries, backoff
        self._http = httpx.Client(
            base_url=self.url, headers={"Authorization": f"Bearer {key}"}, timeout=timeout,
            transport=transport,
        )  # fmt: skip

    def _request(self, method: str, path: str, **kw) -> httpx.Response:
        last: Exception | None = None
        for attempt in range(self.retries):
            try:
                resp = self._http.request(method, path, **kw)
            except httpx.TransportError as exc:  # refused, timeout, DNS: Vera is down
                last = exc
                time.sleep(self.backoff * (2**attempt))
                continue
            if resp.status_code >= 500 and resp.status_code != 501:
                last = VeraError(resp.status_code, "server_error", resp.text[:200])
                time.sleep(self.backoff * (2**attempt))
                continue
            if resp.status_code >= 400:
                try:
                    err = resp.json()["error"]
                    raise VeraError(resp.status_code, err["code"], err["message"])
                except (ValueError, KeyError):
                    raise VeraError(resp.status_code, "error", resp.text[:200]) from None
            return resp
        raise VeraUnavailable(
            f"Vera at {self.url} is not reachable after {self.retries} attempts ({last}). "
            "Nothing was done. Check that Vera is running and try again."
        )

    def project(self, project_id: str) -> dict:
        return self._request("GET", f"/v1/projects/{project_id}").json()

    def opportunity(self, opportunity_id: str) -> dict:
        """Indy addition (not in the shared client): GET /v1/opportunities/{oid}."""
        return self._request("GET", f"/v1/opportunities/{opportunity_id}").json()

    def list_opportunities(self) -> list[dict]:
        """Needs the list_projects grant. Each opportunity carries its projects."""
        return self._request("GET", "/v1/opportunities").json()

    def list_projects(self) -> list[dict]:
        return self._request("GET", "/v1/projects").json()

    def documents(self, project_id: str, *, category: str | None = None,
                  include_outputs: bool = False) -> list[dict]:  # fmt: skip
        params = {"include_outputs": str(include_outputs).lower()}
        if category:
            params["category"] = category
        return self._request("GET", f"/v1/projects/{project_id}/documents", params=params).json()

    def fetch(self, doc_id: str) -> bytes:
        return self._request("GET", f"/v1/documents/{doc_id}/content").content

    def put_output(self, project_id: str, filename: str, data: bytes) -> dict:
        return self._request(
            "POST", f"/v1/projects/{project_id}/outputs", files={"file": (filename, data)}
        ).json()

    def opportunity_documents(
        self, opportunity_id: str, *, category: str | None = None, include_outputs: bool = False
    ) -> list[dict]:
        params = {"include_outputs": str(include_outputs).lower()}
        if category:
            params["category"] = category
        return self._request(
            "GET", f"/v1/opportunities/{opportunity_id}/documents", params=params
        ).json()

    def put_opportunity_output(self, opportunity_id: str, filename: str, data: bytes) -> dict:
        """For work done before a project exists (SOW drafting, intake)."""
        return self._request(
            "POST",
            f"/v1/opportunities/{opportunity_id}/outputs",
            files={"file": (filename, data)},
        ).json()

    def put_library(self, filename: str, data: bytes) -> dict:
        return self._request("POST", "/v1/library/outputs", files={"file": (filename, data)}).json()

    def list_library(self) -> list[dict]:
        return self._request("GET", "/v1/library/documents").json()

    def retire_library(self, doc_id: str) -> dict:
        return self._request("DELETE", f"/v1/library/documents/{doc_id}").json()

    # Single sign-in (needs the sso grant). The page's backend forwards the PIN a person typed
    # and later asks whether their session is still good, so no agent keeps a PIN of its own.
    def sso_login(self, pin: str) -> dict:
        """Returns {token, expires_at}. Raises VeraError 401 (wrong PIN) or 429 (locked out)."""
        return self._request("POST", "/v1/sso/login", json={"pin": pin}).json()

    def sso_introspect(self, token: str) -> dict:
        return self._request("POST", "/v1/sso/introspect", json={"token": token}).json()

    def sso_logout(self, token: str) -> dict:
        return self._request("POST", "/v1/sso/logout", json={"token": token}).json()

    def notify(self, severity: str, title: str, message: str, **extra) -> dict:
        body = {"severity": severity, "title": title, "message": message, **extra}
        return self._request("POST", "/v1/notify", json=body).json()


class SsoGate:
    """What a page's backend uses to gate its own API on Vera's single sign-in.

    Positive answers are cached for a few seconds so a busy page does not call Vera on every
    request; a sign-out or PIN change therefore takes effect within `ttl` seconds. If Vera
    cannot be reached the check raises VeraUnavailable and the caller must refuse the request
    (fail closed), never let it through.
    """

    def __init__(self, client: "VeraClient", *, ttl: float = 30.0, clock=time.monotonic):
        self.client, self.ttl, self._clock = client, ttl, clock
        self._seen: dict[str, tuple[float, bool]] = {}

    def login(self, pin: str) -> dict:
        return self.client.sso_login(pin)

    def valid(self, token: str | None) -> bool:
        if not token:
            return False
        now = self._clock()
        hit = self._seen.get(token)
        if hit and now - hit[0] < (self.ttl if hit[1] else 5.0):
            return hit[1]
        ok = bool(self.client.sso_introspect(token).get("valid"))
        if len(self._seen) > 500:
            self._seen.clear()
        self._seen[token] = (now, ok)
        return ok

    def logout(self, token: str | None) -> None:
        if token:
            self._seen.pop(token, None)
            self.client.sso_logout(token)
