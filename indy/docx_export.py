"""The readiness report as a Word document, built from the saved run (the same data the page and
the Markdown report use), so the three can never disagree. Download only: Vera keeps the
Markdown report as the stored output.
"""

import io

import docx
from docx.shared import Pt, RGBColor

from .report import FACT_LABELS, STATUS_TEXT, VERDICT_LINE, VERDICT_TEXT
from .version import VERSION

_COLORS = {
    "ready": RGBColor(0x16, 0xA3, 0x4A),
    "ready_with_conditions": RGBColor(0xB4, 0x53, 0x09),
    "not_ready": RGBColor(0xB9, 0x1C, 0x1C),
}
_INFERRED = (
    ("customer_questions", "Questions for the customer"),
    ("delivery_questions", "Questions for the delivery team"),
    ("risks", "Risks"),
    ("later_agents_need", "What later agents will need"),
)


def _table(d: docx.document.Document, header: list[str], rows: list[list[str]]) -> None:
    t = d.add_table(rows=1, cols=len(header))
    t.style = "Light Grid Accent 1"
    for i, h in enumerate(header):
        t.rows[0].cells[i].text = h
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = v


def _findings(d: docx.document.Document, findings: dict | None) -> None:
    """Stated and inferred findings in separate tables, with the quote under each table."""
    if not findings:
        return
    d.add_heading("Risks and gaps for project initiation", level=1)
    d.add_paragraph(
        "Each finding quotes the document and the quote was checked against it. These become the "
        "starting risks, issues and open questions for Project Initiation."
    )
    for basis, title in (
        ("stated", "Stated in the documents"),
        ("inferred", "Inferred by Indy (reading between the lines, no effect on the verdict)"),
    ):
        d.add_heading(title, level=2)
        rows = [f for f in findings["items"] if f["basis"] == basis]
        if not rows:
            d.add_paragraph("None.")
            continue
        _table(
            d,
            ["Id", "Severity", "Category", "Finding", "Ask", "Goes to"],
            [
                [f["id"], f["severity"], f["category"], f["title"], f["asked_of"], f["destination"]]
                for f in rows
            ],
        )
        for f in rows:
            p = d.add_paragraph()
            p.add_run(f"{f['id']} ").bold = True
            p.add_run(f'{f["why"]} Quote ({f["doc"]}, {f["where"]}): "{f["quote"]}" ')
            p.add_run(f"Question for the {f['asked_of']}: {f['question']}")


def render_docx(run: dict, opportunity_name: str = "") -> bytes:
    check = run["check"]
    d = docx.Document()
    d.styles["Normal"].font.name = "Calibri"
    d.styles["Normal"].font.size = Pt(10.5)
    d.add_heading(f"Project intake readiness: {opportunity_name or run['opportunity_id']}", level=0)
    p = d.add_paragraph()
    r = p.add_run(f"Verdict: {VERDICT_TEXT[run['verdict']]}. ")
    r.bold = True
    r.font.color.rgb = _COLORS[run["verdict"]]
    p.add_run(VERDICT_LINE[run["verdict"]])
    d.add_paragraph(
        f"Checked on {check['checked_on']} by Indy {VERSION}. The verdict and every status are "
        "computed in code from the documents. Indy does not create projects or choose a methodology."
    )
    if check.get("verdict_reasons"):
        d.add_paragraph(
            f"Stated findings moved the verdict from {VERDICT_TEXT[check['checklist_verdict']]} "
            f"to {VERDICT_TEXT[run['verdict']]}: " + ", ".join(check["verdict_reasons"]) + "."
        )
    if run["model_problems"]:
        d.add_paragraph("The model stages did not fully run: " + "; ".join(run["model_problems"]))

    items = check["items"]
    blockers = [
        i for i in items if i["severity"] == "blocker" and i["status"] in ("missing", "unclear")
    ]
    conditions = [
        i for i in items if i not in blockers and i["status"] not in ("present", "skipped")
    ]
    d.add_heading("Executive summary", level=1)
    sow = check["sow"]["filename"] if check["sow"] else "none found"
    d.add_paragraph(
        f"SOW checked: {sow}. {check['signature']['detail'] if check['signature'] else ''}"
    )
    for label, group in (("Blockers", blockers), ("Conditions", conditions)):
        if group:
            d.add_paragraph(
                f"{label} ({len(group)}): "
                + "; ".join(f"{i['label']} ({STATUS_TEXT[i['status']].lower()})" for i in group)
            )

    d.add_heading("Checklist", level=1)
    _table(
        d,
        ["Item", "Kind", "Status", "What the documents show"],
        [
            [i["label"], i["severity"], STATUS_TEXT[i["status"]], f"{i['detail']} ({i['basis']})"]
            for i in items
        ],
    )
    _findings(d, run.get("findings"))
    docs = check["documents"]
    d.add_heading("Documents", level=1)
    d.add_paragraph("Read: " + (", ".join(x["filename"] for x in docs["read"]) or "none"))
    if docs["skipped"]:
        d.add_paragraph(
            "Not read, so nothing relies on them: "
            + "; ".join(f"{s['filename']} ({s['reason']})" for s in docs["skipped"])
        )
    facts = run.get("facts")
    if facts:
        d.add_heading("Suggested project summary", level=1)
        d.add_paragraph(
            "For Michael to confirm when promoting the opportunity to a project in Vera."
        )
        for key, label in FACT_LABELS:
            d.add_heading(label, level=2)
            rows = facts.get(key) or []
            for f in rows:
                tag = (
                    f"stated, {f['doc']}"
                    if f["basis"] == "stated"
                    else "inferred, no matching quote"
                )
                d.add_paragraph(f"{f['text']} [{tag}]", style="List Bullet")
            if not rows:
                d.add_paragraph("Not found in the SOW.")
    m = run.get("methodology")
    if m:
        d.add_heading("Suggested methodology (suggestion only)", level=1)
        d.add_paragraph(
            f"Indy's reading (inferred): {m['suggestion'] or 'no suggestion'}. {m['reasoning']}"
        )
        d.add_paragraph(
            "The choice belongs to Michael and is permanent once the project is created."
        )
    inferred = run.get("inferred")
    if inferred:
        d.add_heading("What Indy inferred (not stated in the documents)", level=1)
        for key, label in _INFERRED:
            d.add_heading(label, level=2)
            for v in inferred.get(key, []):
                d.add_paragraph(v, style="List Bullet")
            if not inferred.get(key):
                d.add_paragraph("None.")
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()
