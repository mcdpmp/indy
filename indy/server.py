"""Indy HTTP server (port 5112).

Open routes: GET /health (Vera polls it), the page shell, /static, and the sign-in routes.
Everything else, the UI API and the machine API under /v1, needs a Vera session.

  GET  /health          worker-contract health, busy while a job runs
  GET  /v1/jobs         recent jobs
  GET  /v1/jobs/{id}    poll a job; result holds the output references when done
"""

import threading
from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import state, ui_auth, workflows
from .jobs import JobStore
from .llm_client import LLM
from .vera_client import VeraClient
from .version import AGENT, VERSION

STATIC_DIR = Path(__file__).parent / "static"


class PinIn(BaseModel):
    pin: str


class CheckIn(BaseModel):
    opportunity_id: str


def create_app(
    cfg: dict,
    *,
    vera_factory: Callable[[], VeraClient] = VeraClient,
    llm: LLM | None = None,
) -> FastAPI:
    app = FastAPI(title=AGENT, version=VERSION)
    store = JobStore(cfg["paths"]["state_dir"])
    model = llm or LLM(cfg)
    auth = ui_auth.UiAuth(vera_factory)
    needs_pin = [Depends(auth.require_pin)]
    submit_lock = threading.Lock()

    def start_check(opportunity_id: str, actor: str) -> dict:
        try:
            oid = state.safe_id(opportunity_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None

        def task(ctx):
            try:
                out = workflows.run_readiness(
                    vera_factory(), model, cfg, {"opportunity_id": oid}, ctx
                )
            except Exception as exc:  # noqa: BLE001 - audited, then re-raised for the job
                state.audit(cfg, actor, "check.failed", opportunity_id=oid, error=str(exc)[:200])
                raise workflows.explain(exc) from None
            state.audit(cfg, actor, "check.done", opportunity_id=oid, verdict=out["verdict"])
            return out

        with submit_lock:  # check and queue together so two requests cannot both pass
            active = store.find_active("check", oid)
            if active:
                raise HTTPException(
                    409,
                    f"A check for {oid} is already {active['status']} (job {active['job_id']}).",
                )
            state.audit(cfg, actor, "check.start", opportunity_id=oid)
            return store.submit("check", {"opportunity_id": oid}, task)

    @app.middleware("http")
    async def no_cache_shell(request, call_next):  # an old cached page would hide a fix
        response = await call_next(request)
        if request.url.path.startswith("/static/") or request.url.path == "/":
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "agent": AGENT, "version": VERSION, "busy": store.busy()}

    @app.post("/v1/check", status_code=202, dependencies=needs_pin)
    def check(body: CheckIn) -> dict:
        return start_check(body.opportunity_id, "api")

    @app.get("/v1/runs/{opportunity_id}", dependencies=needs_pin)
    def latest_run(opportunity_id: str) -> dict:
        try:
            run = state.load_run(cfg, opportunity_id)
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from None
        if run is None:
            raise HTTPException(404, "No check has been run for this opportunity yet.")
        return run

    @app.get("/v1/jobs", dependencies=needs_pin)
    def jobs() -> list[dict]:
        return store.list()

    @app.get("/v1/jobs/{job_id}", dependencies=needs_pin)
    def job(job_id: str) -> dict:
        found = store.get(job_id)
        if not found:
            raise HTTPException(404, "no such job")
        return found

    ui = APIRouter(prefix="/ui/api")

    @ui.get("/auth/status")
    def auth_status() -> dict:
        return {"pin_set": True, "managed_by": "vera"}

    @ui.post("/auth/setup")
    def auth_setup() -> dict:
        # no PIN screens here on purpose: the one PIN lives in Vera's Access tab
        raise HTTPException(409, "The PIN is managed in Vera (Access tab)")

    @ui.post("/auth/verify")
    def auth_verify(body: PinIn) -> dict:
        return {"token": auth.login(body.pin)}

    @ui.post("/auth/logout")
    def auth_logout(x_admin_token: str | None = Header(default=None)) -> dict:
        auth.logout(x_admin_token)
        return {"ok": True}

    @ui.get("/status", dependencies=needs_pin)
    def status() -> dict:
        return {"agent": AGENT, "version": VERSION, "busy": store.busy()}

    app.include_router(ui)
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app
