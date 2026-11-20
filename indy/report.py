"""Render the readiness report as Markdown. The executive summary comes first.

Every statement is labelled: "stated" (quoted from a document), "computed" (counted or checked in
code) or "inferred" (the model's reading). No dashes of the long kind appear in user-facing text.
"""

from .version import VERSION

VERDICT_TEXT = {
    "ready": "Ready",
    "ready_with_conditions": "Ready with conditions",
    "not_ready": "Not ready",
}
VERDICT_LINE = {
    "ready": "Nothing blocks this deal from becoming a project.",
    "ready_with_conditions": "It can become a project, but the conditions below should be settled.",
    "not_ready": "It should not become a project until the blockers below are resolved.",
}
STATUS_TEXT = {
    "present": "Present",
    "partial": "Partial",
    "missing": "Missing",
    "unclear": "Unclear",
    "skipped": "Skipped",
}
FACT_LABELS = [
    ("customer", "Customer and delivering company"),
    ("scope", "Scope in plain language"),
    ("deliverables", "Deliverables"),
    ("key_dates", "Key dates"),
    ("commercial_terms", "Commercial terms"),
    ("assumptions", "Assumptions"),
    ("dependencies", "Dependencies"),
    ("people", "Named people and roles"),
]


def _cell(text: str) -> str:
    return " ".join(str(text).split()).replace("|", "/")


def _fact_line(f: dict) -> str:
    tag = f"stated, {f['doc']}" if f["basis"] == "stated" else "inferred, no matching quote"
    return f"- {f['text']} [{tag}]"


def findings_section(findings: dict | None) -> list[str]:
    """Stated and inferred findings are listed apart so nobody reads a guess as a clause."""
    if not findings:
        return []
    out = ["", "## Risks and gaps for project initiation", ""]
    out.append(
        "Findings from reading the SOW. Each quotes the document and the quote was checked against it. "
        "These become the starting risks, issues and open questions for Project Initiation."
    )
    for basis, title in (
        ("stated", "Stated in the documents"),
        ("inferred", "Inferred by Indy (reading between the lines, no effect on the verdict)"),
    ):
        rows = [f for f in findings["items"] if f["basis"] == basis]
        out += ["", f"### {title}", ""]
        if not rows:
            out.append("None.")
            continue
        out += [
            "| Id | Severity | Category | Finding | Ask | Goes to |",
            "|---|---|---|---|---|---|",
        ]
        for f in rows:
            out.append(
                f"| {f['id']} | {f['severity']} | {_cell(f['category'])} | {_cell(f['title'])} | "
                f"{f['asked_of']} | {_cell(f['destination'])} |"
            )
        for f in rows:
            out += [
                "",
                f"**{f['id']}** ({f['severity']}, {_cell(f['category'])}): {_cell(f['why'])}",
                f'- Quote ({f["doc"]}, {_cell(f["where"])}): "{_cell(f["quote"])}"',
                f"- Question for the {f['asked_of']}: {_cell(f['question'])}",
            ]
    return out


def render(
    opportunity: dict,
    check: dict,
    facts: dict | None,
    methodology: dict | None,
    inferred: dict | None,
    model_problems: list[str],
    findings: dict | None = None,
) -> str:
    name = (
        opportunity.get("name") or opportunity.get("title") or opportunity.get("opportunity_id", "")
    )
    items = check["items"]
    verdict = check["verdict"]
    blockers = [
        i for i in items if i["severity"] == "blocker" and i["status"] in ("missing", "unclear")
    ]
    conditions = [
        i for i in items if i not in blockers and i["status"] not in ("present", "skipped")
    ]
    lines = [f"# Project intake readiness: {name}", ""]
    lines.append(f"**Verdict: {VERDICT_TEXT[verdict]}.** {VERDICT_LINE[verdict]}")
    lines.append("")
    lines.append(
        f"Checked on {check['checked_on']} by Indy {VERSION}. The verdict and every status below are computed in code from the documents. Indy does not create projects or choose a methodology."
    )
    if check.get("verdict_reasons"):
        lines += [
            "",
            "Stated findings moved the verdict from "
            + f"{VERDICT_TEXT[check['checklist_verdict']]} to {VERDICT_TEXT[verdict]}: "
            + ", ".join(check["verdict_reasons"])
            + ".",
        ]
    if model_problems:
        lines += [
            "",
            "> **The model stages did not fully run.** The checklist and verdict are complete. Missing below: "
            + "; ".join(_cell(p) for p in model_problems),
        ]
    lines += ["", "## Executive summary", ""]
    sow = check["sow"]["filename"] if check["sow"] else "none found"
    sig = check["signature"]["detail"] if check["signature"] else "No SOW to check."
    lines.append(f"- SOW checked: {sow}. {sig}")
    if blockers:
        lines.append(
            f"- Blockers ({len(blockers)}): "
            + "; ".join(f"{b['label']} ({STATUS_TEXT[b['status']].lower()})" for b in blockers)
        )
    if conditions:
        lines.append(
            f"- Conditions ({len(conditions)}): "
            + "; ".join(f"{c['label']} ({STATUS_TEXT[c['status']].lower()})" for c in conditions)
        )
    if not blockers and not conditions:
        lines.append("- Every enabled checklist item is present.")
    if facts:
        customer = (facts.get("customer") or [{}])[0].get("text")
        if customer:
            lines.append(f"- Customer: {customer}")
    lines += [
        "",
        "## Checklist",
        "",
        "| Item | Kind | Status | What the documents show |",
        "|---|---|---|---|",
    ]
    for i in items:
        lines.append(
            f"| {_cell(i['label'])} | {i['severity']} | {STATUS_TEXT[i['status']]} | {_cell(i['detail'])} ({i['basis']}) |"
        )
    for i in items:
        if i["status"] in ("present", "skipped") and not i["notes"]:
            continue
        extra = [f"- {_cell(n)}" for n in i["notes"]]
        extra += [f'- {e["doc"]}, {e["where"]}: "{_cell(e["quote"])}"' for e in i["evidence"][:3]]
        if extra:
            lines += ["", f"### {i['label']}", *extra]
    lines += findings_section(findings)
    docs = check["documents"]
    lines += ["", "## Documents", "", "Read:"]
    lines += [f"- {d['filename']} ({d['category']})" for d in docs["read"]] or ["- none"]
    if docs["skipped"]:
        lines += ["", "Not read, so nothing below relies on them:"]
        lines += [f"- {s['filename']}: {_cell(s['reason'])}" for s in docs["skipped"]]
    if facts:
        lines += [
            "",
            "## Suggested project summary",
            "",
            "For Michael to confirm when he promotes the opportunity to a project in Vera. Each line says whether a document states it.",
            "",
        ]
        for key, label in FACT_LABELS:
            rows = facts.get(key) or []
            lines.append(f"**{label}**")
            lines += [_fact_line(f) for f in rows] or ["- not found in the SOW"]
            lines.append("")
    if methodology:
        lines += ["## Suggested methodology (suggestion only)", ""]
        pick = methodology["suggestion"]
        lines.append(
            f"Indy's reading (inferred): {pick or 'no suggestion'}. {methodology['reasoning']}"
        )
        s = methodology["signals"]
        lines.append(
            f"Counted in the SOW (computed): {s['scrum_terms']} agile terms, {s['waterfall_terms']} phase, milestone or sign-off terms."
        )
        lines += [
            "",
            "The choice belongs to Michael and is permanent once the project is created.",
            "",
        ]
    if inferred:
        lines += ["## What Indy inferred (not stated in the documents)", ""]
        for key, label in (
            ("customer_questions", "Questions for the customer"),
            ("delivery_questions", "Questions for the delivery team"),
            ("risks", "Risks"),
            ("later_agents_need", "What later agents will need"),
        ):
            lines.append(f"**{label}**")
            lines += [f"- {v}" for v in inferred.get(key, [])] or ["- none"]
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"
