"""The page's own API, under /ui/api. Everything here needs a Vera session (see ui_auth.py);
the sign-in routes live in server.py. Long work (a check, a question) returns a job id.
"""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from . import qa, state, workflows
from .checklist import ChecklistError, ChecklistStore
from .documents import load_opportunity
from .jobs import JobStore
from .llm_client import LLM
from .ui_auth import UiAuth
from .vera_client import VeraClient, VeraError, VeraUnavailable

DOC_FIELDS = ("doc_id", "filename", "category", "size", "uploaded_at", "source")


class AskIn(BaseModel):
    opportunity_id: str
    question: str


class ChecklistIn(BaseModel):
    items: list[dict]


def _vera_call(fn: Callable, *args):
    """Run a Vera read for the page: Vera down is 503, a refusal is passed on in plain words."""
    try:
        return fn(*args)
    except VeraUnavailable as exc:
        raise HTTPException(503, str(exc)) from None
    except VeraError as exc:
        raise HTTPException(
            502 if exc.status >= 500 else exc.status, f"Vera said: {exc.message}"
        ) from None


def _oid(value: str) -> str:
    try:
        return state.safe_id(value)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None


def build_router(
    cfg: dict,
    store: JobStore,
    vera_factory: Callable[[], VeraClient],
    model: LLM,
    auth: UiAuth,
    start_check: Callable[[str, str], dict],
) -> APIRouter:
    router = APIRouter(prefix="/ui/api", dependencies=[Depends(auth.require_pin)])
    checklist = ChecklistStore(cfg["paths"]["state_dir"])

    @router.get("/opportunities")
    def opportunities() -> dict:
        """The picker needs Vera's list_projects grant. Without it the page falls back to a typed id."""
        try:
            raw = vera_factory().list_opportunities()
        except VeraUnavailable as exc:
            raise HTTPException(503, str(exc)) from None
        except VeraError as exc:
            return {
                "picker": False,
                "opportunities": [],
                "message": f"Vera would not list opportunities ({exc.message}). Type an opportunity id instead.",
            }
        out = []
        for o in raw:
            oid = o.get("opportunity_id") or o.get("id") or ""
            run = state.load_run(cfg, oid) if state.SAFE_ID.match(oid) else None
            out.append(
                {
                    "opportunity_id": oid,
                    "name": o.get("name") or o.get("title") or "",
                    "projects": [p.get("project_id") for p in o.get("projects", [])],
                    "verdict": run["verdict"] if run else None,
                    "checked_at": run["finished_at"] if run else None,
                }
            )
        return {"picker": True, "opportunities": out}

    @router.get("/opportunity/{opportunity_id}")
    def opportunity(opportunity_id: str) -> dict:
        oid = _oid(opportunity_id)
        vera = vera_factory()
        meta = _vera_call(vera.opportunity, oid)
        docs = _vera_call(lambda: vera.opportunity_documents(oid, include_outputs=True))
        run = state.load_run(cfg, oid)
        return {
            "opportunity": meta,
            "documents": [{k: d.get(k) for k in DOC_FIELDS} for d in docs],
            "run": run,
        }

    @router.post("/check", status_code=202)
    def check(body: dict) -> dict:
        return start_check(str(body.get("opportunity_id", "")), "ui")

    @router.post("/ask", status_code=202)
    def ask(body: AskIn) -> dict:
        oid = _oid(body.opportunity_id)
        question = body.question.strip()
        if not question or len(question) > qa.MAX_QUESTION:
            raise HTTPException(400, f"Ask a question of 1 to {qa.MAX_QUESTION} characters.")

        def task() -> dict:
            try:
                loaded = load_opportunity(vera_factory(), oid, cfg)
                out = qa.answer(model, loaded, question)
            except (VeraUnavailable, VeraError) as exc:
                raise workflows.explain(exc) from None
            state.audit(cfg, "ui", "ask", opportunity_id=oid, grounded=out["grounded"])
            return out

        return store.submit("ask", {"opportunity_id": oid, "question": question}, task)

    @router.get("/jobs")
    def jobs() -> list[dict]:
        return [
            {
                k: j.get(k)
                for k in (
                    "job_id",
                    "kind",
                    "status",
                    "created_at",
                    "finished_at",
                    "error",
                    "progress",
                    "params",
                )
            }
            for j in store.list()[:40]
        ]

    @router.get("/jobs/{job_id}")
    def job(job_id: str) -> dict:
        found = store.get(job_id)
        if not found:
            raise HTTPException(404, "no such job")
        return found

    @router.get("/run/{opportunity_id}")
    def run(opportunity_id: str) -> dict:
        found = state.load_run(cfg, _oid(opportunity_id))
        if found is None:
            raise HTTPException(404, "No check has been run for this opportunity yet.")
        return found

    @router.get("/run/{opportunity_id}/report.md")
    def report(opportunity_id: str) -> PlainTextResponse:
        found = state.load_run(cfg, _oid(opportunity_id))
        if found is None:
            raise HTTPException(404, "No check has been run for this opportunity yet.")
        return PlainTextResponse(
            found["report_markdown"],
            media_type="text/markdown",
            headers={
                "Content-Disposition": f'attachment; filename="readiness_report_{opportunity_id}.md"'
            },
        )

    @router.get("/checklist")
    def get_checklist() -> list[dict]:
        return checklist.load()

    @router.put("/checklist")
    def put_checklist(body: ChecklistIn) -> list[dict]:
        try:
            saved = checklist.save(body.items)
        except ChecklistError as exc:
            raise HTTPException(400, str(exc)) from None
        state.audit(cfg, "ui", "checklist.save")
        return saved

    @router.post("/checklist/reset")
    def reset_checklist() -> list[dict]:
        state.audit(cfg, "ui", "checklist.reset")
        return checklist.reset()

    @router.get("/status")
    def status() -> dict:
        return {"agent": "indy", "busy": store.busy()}

    return router
