"""The machine-readable handoff for Project Initiation (agent 3).

Written to Vera next to the human report as an opportunity output. Project Initiation finds it by
NAME, so FILE_NAME must never change; the content carries schema_version so the shape can.
Vera never overwrites: a re-run becomes indy_handoff__v2.json, and the newest version is the one
to read. The file is validated against handoff.schema.json before upload, so a bug in Indy
fails the job loudly instead of handing the next agent a malformed file.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

from jsonschema import Draft202012Validator

from .documents import Doc, Loaded
from .version import VERSION

FILE_NAME = "indy_handoff.json"
SCHEMA_VERSION = "1.0"
SCHEMA = json.loads((Path(__file__).parent / "handoff.schema.json").read_text(encoding="utf-8"))
_VALIDATOR = Draft202012Validator(SCHEMA)
HOW_TO_READ = (
    "Several versions can exist (indy_handoff.json, indy_handoff__v2.json, ...): read the newest. "
    "Findings and facts marked stated quote a document; those marked inferred are Indy's reading "
    "between the lines. The methodology is a suggestion only: the choice belongs to Michael."
)
METHOD_NOTE = "Suggestion only. Michael chooses the methodology and it is permanent."
FACT_KEYS = (
    "customer",
    "scope",
    "deliverables",
    "key_dates",
    "commercial_terms",
    "assumptions",
    "dependencies",
    "people",
)


class HandoffError(Exception):
    pass


def validate(doc: dict) -> None:
    """Raises HandoffError naming the first problem and where it is."""
    errors = sorted(_VALIDATOR.iter_errors(doc), key=lambda e: list(e.absolute_path))
    if errors:
        e = errors[0]
        where = "/".join(str(p) for p in e.absolute_path) or "top level"
        raise HandoffError(f"Handoff file is not valid at {where}: {e.message}")


def _role(doc: Doc, loaded: Loaded) -> str:
    if any(doc is d for d in loaded.sow):
        return "sow"
    if any(doc is d for d in loaded.rfp):
        return "rfp"
    if any(doc is d for d in loaded.scoper):
        return "scoper_output"
    return "supporting"


def _facts(rows: list[dict] | None) -> list[dict]:
    return [
        {"text": f["text"], "basis": f["basis"], "quote": f.get("quote", ""), "document": f["doc"]}
        for f in rows or []
    ]


def build(
    opportunity_id: str,
    opportunity: dict,
    check: dict,
    loaded: Loaded,
    facts: dict | None,
    methodology: dict | None,
    inferred: dict | None,
    findings: dict | None,
    problems: list[str],
    now: datetime | None = None,
) -> dict:
    ids = {d.filename: d.doc_id for d in loaded.everything()}
    sow = check["sow"]
    sig = check["signature"]
    out = {
        "schema": "indy_handoff",
        "schema_version": SCHEMA_VERSION,
        "generated_at": (now or datetime.now(UTC)).isoformat(timespec="seconds"),
        "indy_version": VERSION,
        "how_to_read": HOW_TO_READ,
        "opportunity": {
            "id": opportunity_id,
            "name": str(opportunity.get("name") or opportunity.get("title") or ""),
        },
        "verdict": check["verdict"],
        "checklist_verdict": check.get("checklist_verdict", check["verdict"]),
        "verdict_reasons": check.get("verdict_reasons", []),
        "checklist": [
            {
                "id": i["id"],
                "label": i["label"],
                "kind": i["severity"],
                "status": i["status"],
                "detail": i["detail"],
                "basis": i["basis"],
            }
            for i in check["items"]
        ],
        "documents": {
            "signed_sow": (
                {
                    "doc_id": sow["doc_id"],
                    "filename": sow["filename"],
                    "signature_state": sig["state"] if sig else "no_block",
                }
                if sow
                else None
            ),
            "considered": [
                {
                    "doc_id": d.doc_id,
                    "filename": d.filename,
                    "category": d.category,
                    "role": _role(d, loaded),
                }
                for d in loaded.everything()
            ],
            "not_read": [
                {"filename": s["filename"], "category": s["category"], "reason": s["reason"]}
                for s in check["documents"]["skipped"]
            ],
        },
        "findings": [
            {
                "id": f["id"],
                "category": f["category"],
                "severity": f["severity"],
                "basis": f["basis"],
                "title": f["title"],
                "quote": f["quote"],
                "source_document": {"doc_id": ids.get(f["doc"], ""), "filename": f["doc"]},
                "where": f["where"],
                "why": f["why"],
                "question": f["question"],
                "asked_of": f["asked_of"],
                "destination": f["destination"],
                "origin": f["origin"],
                "evidence_kind": f["evidence_kind"],
            }
            for f in (findings["items"] if findings else [])
        ],
        "project_summary": {k: _facts((facts or {}).get(k)) for k in FACT_KEYS} if facts else None,
        "methodology_suggestion": (
            {
                "suggestion": methodology["suggestion"],
                "reasoning": methodology["reasoning"],
                "signals": methodology["signals"],
                "note": METHOD_NOTE,
            }
            if methodology
            else None
        ),
        "inferred_followups": (
            {
                k: inferred.get(k, [])
                for k in ("customer_questions", "delivery_questions", "risks", "later_agents_need")
            }
            if inferred
            else None
        ),
        "model_problems": problems,
    }
    validate(out)
    return out


def to_bytes(doc: dict) -> bytes:
    return json.dumps(doc, indent=2, ensure_ascii=False).encode("utf-8")
