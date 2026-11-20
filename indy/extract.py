"""The model stages: read the SOW in pieces and pull out what a new project needs.

Rules that keep this honest:
- Each call sees only the sections it needs, so a long SOW is read in stages, not in one prompt.
- The model must copy the words it relied on. Code checks that the quote really is in the
  document: a verified quote makes the fact "stated", anything else is kept but marked
  "inferred" so nobody mistakes a guess for a clause.
- Whatever the model says about methodology, risks or questions is "inferred" by definition.
- Document text is fenced as data. A document that tells the model to do something changes
  nothing, because the answer is validated into fixed lists in code anyway.
"""

import re

from .documents import Doc
from .llm_client import DATA_RULE, LLM, LLMError, untrusted
from .textutil import find_sections

# call key -> (section title pattern, fields the call returns, per-field cap, what to extract)
STAGES: list[dict] = [
    {
        "key": "parties_scope",
        "sections": r"background|purpose|scope|objective|understanding|executive summary|our solution",
        "fields": {
            "customer": (1, "the customer's legal name and the delivering company's name"),
            "scope": (6, "what the work covers, in plain language, one short sentence each"),
        },
    },
    {
        "key": "deliverables_dates",
        "sections": r"deliverable|timeline|milestone|schedule|constraint",
        "fields": {
            "deliverables": (15, "each deliverable by name"),
            "key_dates": (12, "each date that matters: start, milestones, go live, end"),
        },
    },
    {
        "key": "commercial",
        "sections": r"fee|pric|payment|invoice|billing|investment|commercial|cost",
        "fields": {"commercial_terms": (8, "price, pricing model, payment and invoicing terms")},
    },
    {
        "key": "assumptions_dependencies",
        "sections": r"assumption|dependenc|client responsibilit|customer responsibilit",
        "fields": {
            "assumptions": (10, "each assumption the plan rests on"),
            "dependencies": (10, "each thing the customer or a third party must provide"),
        },
    },
    {
        "key": "people",
        "sections": r"role|contact|team|governance|personnel|stakeholder",
        "fields": {"people": (12, "each named person with their role and which side they are on")},
    },
]
LIMIT = 9000


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[|*_`]", " ", text)).strip().lower()


def verify_quote(doc: Doc, quote: str) -> bool:
    q = _norm(quote)
    return len(q) >= 8 and q in _norm(doc.text)


def _clean_list(raw: object, cap: int, doc: Doc) -> list[dict]:
    """Model output in, a fixed shape out. Anything that is not text is dropped."""
    out: list[dict] = []
    for item in raw if isinstance(raw, list) else []:
        if isinstance(item, str):
            item = {"text": item, "quote": ""}
        if not isinstance(item, dict):
            continue
        text, quote = item.get("text"), item.get("quote", "")
        if not isinstance(text, str) or not text.strip():
            continue
        quote = quote if isinstance(quote, str) else ""
        stated = bool(quote) and verify_quote(doc, quote)
        out.append(
            {
                "text": text.strip()[:300],
                "quote": quote.strip()[:300] if stated else "",
                "basis": "stated" if stated else "inferred",
                "doc": doc.filename,
            }
        )
        if len(out) >= cap:
            break
    return out


def _section_text(doc: Doc, pattern: str) -> tuple[str, bool]:
    """The sections' text and whether it had to be cut to fit the model."""
    parts = [f"## {s.title}\n{s.full_text()}" for s in find_sections(doc.sections, pattern)]
    text = "\n\n".join(parts)
    return text[:LIMIT], len(text) > LIMIT


def extract_facts(llm: LLM, doc: Doc, progress=lambda text: None) -> dict:
    """Run the extraction stages. A stage that fails is recorded, not hidden, and the next one
    still runs, so one bad call does not cost the whole report."""
    facts: dict[str, list[dict]] = {}
    problems: list[str] = []
    truncated: list[str] = []
    for stage in STAGES:
        progress(f"Reading the SOW: {stage['key'].replace('_', ' ')}")
        text, cut = _section_text(doc, stage["sections"])
        if not text.strip():
            for field in stage["fields"]:
                facts[field] = []
            continue
        if cut:
            truncated.append(stage["key"])
        wanted = "\n".join(
            f'- "{f}": {desc} (at most {cap})' for f, (cap, desc) in stage["fields"].items()
        )
        prompt = (
            f"{DATA_RULE}\n\nTASK: extract project facts\n"
            "Read the SOW sections below and fill these lists:\n"
            f"{wanted}\n\n"
            'Return JSON: {"<field>": [{"text": "...", "quote": "words copied exactly from the text"}]}.\n'
            "Only list what the text states. If it does not state something, leave that list empty. "
            "Never invent a name, date or amount.\n\n"
            f"{untrusted('SOW', text, LIMIT)}"
        )
        try:
            raw = llm.json(prompt)
        except LLMError as exc:
            problems.append(f"{stage['key']}: {exc}")
            for field in stage["fields"]:
                facts[field] = []
            continue
        for field, (cap, _) in stage["fields"].items():
            facts[field] = _clean_list(raw.get(field), cap, doc)
    return {"facts": facts, "problems": problems, "truncated": truncated}


# keywords counted in code so the methodology suggestion rests on something visible
_SCRUM = r"sprint|iteration|backlog|agile|scrum|product owner|user stor(?:y|ies)|\breleases?\b"
_WATERFALL = r"\bphase[sd]?\b|milestone|baseline|sign.?off|requirements specification|fixed price|acceptance of"


def methodology_signals(doc: Doc) -> dict[str, int]:
    return {
        "scrum_terms": len(re.findall(_SCRUM, doc.text, re.IGNORECASE)),
        "waterfall_terms": len(re.findall(_WATERFALL, doc.text, re.IGNORECASE)),
    }


def suggest_methodology(llm: LLM, doc: Doc, facts: dict, signals: dict[str, int]) -> dict:
    scope = "; ".join(f["text"] for f in facts.get("scope", [])[:6]) or "not extracted"
    pricing = "; ".join(f["text"] for f in facts.get("commercial_terms", [])[:3]) or "not extracted"
    prompt = (
        f"{DATA_RULE}\n\nTASK: suggest a delivery methodology\n"
        "Suggest waterfall or scrum for this project and explain why in two or three sentences, "
        "using only the facts given. This is advice for a human who decides.\n"
        f"Scope: {scope}\nPricing: {pricing}\n"
        f"Counts in the SOW: {signals['scrum_terms']} agile terms, "
        f"{signals['waterfall_terms']} phase, milestone or sign-off terms.\n"
        'Return JSON: {"suggestion": "waterfall" or "scrum", "reasoning": "..."}.'
    )
    raw = llm.json(prompt)
    pick = str(raw.get("suggestion", "")).strip().lower()
    reasoning = raw.get("reasoning")
    if (
        pick not in ("waterfall", "scrum")
        or not isinstance(reasoning, str)
        or not reasoning.strip()
    ):
        return {
            "suggestion": None,
            "reasoning": "The model gave no usable suggestion.",
            "signals": signals,
        }
    return {"suggestion": pick, "reasoning": reasoning.strip()[:600], "signals": signals}


def infer_questions(llm: LLM, items: list[dict], facts: dict) -> dict:
    """Open questions, risks and hand-offs, all inferred. Built only from what the checklist found."""
    gaps = [
        f"- {i['label']} ({i['severity']}, {i['status']}): {i['detail']}"
        for i in items
        if i["status"] not in ("present", "skipped")
    ]
    known = (
        "; ".join(f["text"] for k in ("customer", "scope") for f in facts.get(k, []))
        or "not extracted"
    )
    prompt = (
        f"{DATA_RULE}\n\nTASK: write intake follow-ups\n"
        f"A signed SOW was checked for readiness to become a project. Known: {known}\n"
        f"Gaps found:\n{chr(10).join(gaps) or '- none'}\n\n"
        "Return JSON with four lists of short sentences, at most 6 each: "
        '"customer_questions", "delivery_questions", "risks", "later_agents_need". '
        "Base them on the gaps and known facts only."
    )
    raw = llm.json(prompt)
    out: dict[str, list[str]] = {}
    for key in ("customer_questions", "delivery_questions", "risks", "later_agents_need"):
        vals = raw.get(key)
        out[key] = (
            [v.strip()[:240] for v in vals if isinstance(v, str) and v.strip()][:6]
            if isinstance(vals, list)
            else []
        )
    return out
