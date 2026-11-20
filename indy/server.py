"""Indy HTTP server (port 5112).

Open routes: GET /health (Vera polls it), the page shell, /static, and the sign-in routes.
Everything else, the UI API and the machine API under /v1, needs a Vera session.

  GET  /health          worker-contract health, busy while a job runs
  GET  /v1/jobs         recent jobs
  GET  /v1/jobs/{id}    poll a job; result holds the output references when done
"""

from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import ui_auth
from .jobs import JobStore
from .vera_client import VeraClient
from .version import AGENT, VERSION

STATIC_DIR = Path(__file__).parent / "static"


class PinIn(BaseModel):
    pin: str


def create_app(cfg: dict, *, vera_factory: Callable[[], VeraClient] = VeraClient) -> FastAPI:
    app = FastAPI(title=AGENT, version=VERSION)
    store = JobStore(cfg["paths"]["state_dir"])
    auth = ui_auth.UiAuth(vera_factory)
    needs_pin = [Depends(auth.require_pin)]

    @app.middleware("http")
    async def no_cache_shell(request, call_next):  # an old cached page would hide a fix
        response = await call_next(request)
        if request.url.path.startswith("/static/") or request.url.path == "/":
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        return response

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok", "agent": AGENT, "version": VERSION, "busy": store.busy()}

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
