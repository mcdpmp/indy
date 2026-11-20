"""The readiness job, in stages.

1. Read the opportunity's documents from Vera (Vera down stops the job).
2. Run the checklist and compute the verdict in code.
3. Scope-risk review: code finds what it can, the model proposes more, code checks every quote.
   Stated high-severity findings can move the verdict (config findings.verdict_effect).
4. Model stages: project facts, a methodology suggestion, follow-up questions. If the model is
   unavailable the report is still written with a clear banner, because the verdict does not
   depend on it.
5. Render the report and store it through Vera (never anywhere else).
"""

from datetime import UTC, datetime

from . import extract, report, state
from . import findings as findings_mod
from .checklist import ChecklistStore
from .documents import load_opportunity
from .finding_rules import RuleStore
from .jobs import JobContext
from .llm_client import LLM, LLMError
from .readiness import run_check
from .vera_client import VeraClient, VeraError, VeraUnavailable
from .version import AGENT, VERSION


def explain(exc: Exception) -> Exception:
    if isinstance(exc, VeraUnavailable):
        return RuntimeError(str(exc))
    if isinstance(exc, VeraError):
        return RuntimeError(f"Vera refused the request ({exc.status} {exc.code}): {exc.message}")
    return exc


def run_readiness(vera: VeraClient, llm: LLM, cfg: dict, params: dict, ctx: JobContext) -> dict:
    oid = params["opportunity_id"]
    ctx.progress("Reading the documents from Vera")
    opportunity = vera.opportunity(oid)
    loaded = load_opportunity(vera, oid, cfg)
    ctx.progress("Checking the checklist")
    checklist = ChecklistStore(cfg["paths"]["state_dir"]).load()
    check = run_check(loaded, checklist, cfg)

    facts = methodology = inferred = None
    problems: list[str] = []
    found: dict | None = None
    sow = next((d for d in loaded.sow if check["sow"] and d.doc_id == check["sow"]["doc_id"]), None)
    if sow is not None:
        ctx.progress("Reviewing the SOW for scope risk")
        rules = RuleStore(cfg["paths"]["state_dir"]).load()
        found = findings_mod.review(llm, sow, loaded, check, rules, cfg, ctx.progress)
        problems += found["problems"]
        check["checklist_verdict"] = check["verdict"]
        check["verdict"] = found["verdict"]
        check["verdict_reasons"] = found["verdict_reasons"]
        got = extract.extract_facts(llm, sow, ctx.progress)
        facts = got["facts"]
        problems += got["problems"]  # keep the gap review's problems recorded just above
        if got["truncated"]:
            problems.append(
                "long sections were cut to fit the model: " + ", ".join(got["truncated"])
            )
        ctx.progress("Suggesting a methodology")
        try:
            methodology = extract.suggest_methodology(
                llm, sow, facts, extract.methodology_signals(sow)
            )
        except LLMError as exc:
            problems.append(f"methodology suggestion: {exc}")
    ctx.progress("Writing follow-up questions")
    try:
        inferred = extract.infer_questions(llm, check["items"], facts or {})
    except LLMError as exc:
        problems.append(f"follow-up questions: {exc}")

    ctx.progress("Writing the report")
    markdown = report.render(opportunity, check, facts, methodology, inferred, problems, found)
    # one report per run; Vera never overwrites, a repeat becomes readiness_report__v2.md and so on
    stored = vera.put_opportunity_output(oid, "readiness_report.md", markdown.encode())
    run = {
        "opportunity_id": oid,
        "agent": AGENT,
        "version": VERSION,
        "verdict": check["verdict"],
        "check": check,
        "facts": facts,
        "methodology": methodology,
        "inferred": inferred,
        "findings": found,
        "model_problems": problems,
        "report_markdown": markdown,
        "stored": stored,
        "finished_at": datetime.now(UTC).isoformat(timespec="seconds"),
    }
    state.save_run(cfg, oid, run)
    return {k: run[k] for k in ("verdict", "model_problems", "stored", "finished_at")}
