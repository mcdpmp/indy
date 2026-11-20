"""The scope-risk review: gaps in the SOW that Project Initiation should start from.

Two sources, one rule. Code finds what code can find (vague phrases, deliverables without
acceptance criteria, totals that do not add up, changes from Scoper's draft, thin sections).
The model proposes the rest (hidden complexity, contradictions, risky assumptions). Every finding
must quote the document, and the quote is checked against the document text. A model proposal
whose quote is not found is not trusted: it goes to "unsupported" and is passed on to nobody.

basis "stated": the quoted text is itself the problem, or code measured a gap in the document
(an absence is anchored on the nearest heading and flagged evidence_kind "absence").
basis "inferred": the model is reading between the lines. Inferred findings never move the verdict.
"""

import hashlib
import re

from . import finding_rules as fr
from .diff import compare_draft
from .documents import SCOPER_DRAFT_PREFIX, Doc, Loaded
from .extract import _norm, verify_quote
from .llm_client import DATA_RULE, LLM, LLMError, untrusted
from .readiness import SUBJECTIVE
from .textutil import find_amounts, find_dates, find_sections, parse_tables

SEVERITY_ORDER = {"high": 0, "medium": 1, "low": 2}
QUOTE_MAX = 300
# Sections that list what is NOT promised or define terms: a phrase there is not a commitment.
_SKIP_SECTIONS = re.compile(
    r"signature|exception|out of scope|exclusion|not included|definition|glossary|traceability",
    re.IGNORECASE,
)
# A sentence that refuses or excludes the phrase ("We do not provide 24x7 support") is the
# opposite of a risk. "not limited to" is the opposite case and must not count as a negation.
_NEGATION = re.compile(
    r"(?<!\w)(?:not|never|cannot|excluded?|excludes?|without|rejected|declined?|exceptions?)(?!\w)(?!\s+limited)",
    re.IGNORECASE,
)
_IDIOM = re.compile(r"\s+by\s+law(?!\w)", re.IGNORECASE)  # "as required by law" is boilerplate


def finding_id(category: str, quote: str) -> str:
    """Stable across re-runs: the same problem in the same words keeps the same id, so the
    next agent can tell a repeat from something new."""
    return "F-" + hashlib.sha1(f"{category}|{_norm(quote)}".encode()).hexdigest()[:6]


def _make(
    category: str,
    severity: str,
    basis: str,
    title: str,
    quote: str,
    doc: Doc,
    where: str,
    why: str,
    question: str,
    asked_of: str,
    destination: str,
    origin: str,
    kind: str = "text",
    rule: str = "",
) -> dict:
    quote = " ".join(quote.split())[:QUOTE_MAX]
    return {
        "id": finding_id(category, quote),
        "category": category,
        "severity": severity,
        "basis": basis,
        "title": title[:200],
        "quote": quote,
        "doc": doc.filename,
        "where": where or "start",
        "why": why[:400],
        "question": question[:300],
        "asked_of": asked_of,
        "destination": destination,
        "origin": origin,
        "evidence_kind": kind,
        "rule": rule,
    }


# ---- code: phrase rules ------------------------------------------------------------------


def _sentence(body: str, start: int, end: int) -> str:
    """The sentence or table row around a match, as a literal slice of the document so the quote
    verifies. Long ones are cut to a window around the match."""
    a = body.rfind("\n", 0, start)
    b = body.rfind(". ", 0, start)
    cut = max(a, b + 1 if b != -1 else -1)
    left = cut + 1 if cut != -1 else 0
    c = body.find("\n", end)
    d = body.find(". ", end)
    stops = [c] + ([d + 1] if d != -1 else [])
    right = min((s for s in stops if s != -1), default=len(body))
    text = body[left:right]
    if len(text) > QUOTE_MAX:
        text = body[max(left, start - 120) : min(right, end + 120)]
    return text.strip()


def phrase_findings(doc: Doc, rules: list[dict], per_rule: int) -> list[dict]:
    out: list[dict] = []
    for rule in rules:
        if not rule.get("enabled", True):
            continue
        patterns = [fr.phrase_regex(p) for p in rule["phrases"]]
        seen: set[str] = set()
        for sec in doc.sections:
            if _SKIP_SECTIONS.search(sec.title):
                continue
            for rx in patterns:
                for m in rx.finditer(sec.body):
                    quote = _sentence(sec.body, m.start(), m.end())
                    key = _norm(quote)
                    if len(quote) < 8 or key in seen or len(seen) >= per_rule:
                        continue
                    if _NEGATION.search(quote) or _IDIOM.match(sec.body, m.end()):
                        continue
                    seen.add(key)
                    out.append(
                        _make(
                            rule["category"], rule["severity"], "stated",
                            f"{rule['label']}: \"{m.group(0)}\"", quote, doc, sec.title,
                            rule["why"], rule["question"], rule["asked_of"], rule["destination"],
                            "code", rule=rule["id"],
                        )
                    )  # fmt: skip
    return out


# ---- code: tables ------------------------------------------------------------------------


def _table_runs(body: str) -> list[list[str]]:
    """Raw lines of each pipe table, so a finding can quote the actual row."""
    runs: list[list[str]] = []
    run: list[str] = []
    for ln in [*body.splitlines(), ""]:
        if ln.strip().startswith("|"):
            run.append(ln)
        else:
            if len(run) >= 2:
                runs.append(run)
            run = []
    return runs


def _data_lines(run: list[str]) -> list[str]:
    return [ln for ln in run[1:] if not re.fullmatch(r"[|\s:\-]+", ln)]


def table_findings(doc: Doc) -> list[dict]:
    out: list[dict] = []
    for sec in doc.sections:
        for run in _table_runs(sec.body):
            table = parse_tables("\n".join(run))[0]
            lines = _data_lines(run)
            col = table.column(r"acceptance|criteria")
            if col is not None and len(lines) == len(table.rows):
                out += _acceptance(doc, sec.title, table, lines, col)
            out += _sums(doc, sec.title, table, lines)
    return out


def _acceptance(doc: Doc, where: str, table, lines: list[str], col: int) -> list[dict]:
    rows = [
        (r, ln) for r, ln in zip(table.rows, lines, strict=True)
        if any(r) and r[0].strip().lower() != "total"
    ]  # fmt: skip
    empty = [(r, ln) for r, ln in rows if col >= len(r) or not r[col].strip()]
    out: list[dict] = []
    if empty:
        share = len(empty) / len(rows)
        sev = "high" if share > 0.5 else "medium"
        out.append(
            _make(
                "acceptance", sev, "stated",
                f"{len(empty)} of {len(rows)} deliverables have no acceptance criteria",
                empty[0][1], doc, where,
                "Without criteria nobody can say when a deliverable is accepted, which delays "
                "sign-off and payment.",
                "What test or condition accepts each of these deliverables, and who decides?",
                "customer", "starting_risk", "code", rule="acceptance_missing",
            )
        )  # fmt: skip
    for r, ln in rows:
        if col < len(r) and SUBJECTIVE.search(r[col]):
            out.append(
                _make(
                    "acceptance", "medium", "stated",
                    f"Acceptance criterion is subjective: \"{' '.join(r[col].split())[:80]}\"",
                    ln, doc, where,
                    "A criterion based on someone's satisfaction cannot be tested.",
                    "What measurable result replaces this wording?",
                    "customer", "open_question", "code", rule="acceptance_subjective",
                )
            )  # fmt: skip
    return out


def _numbers(cells: list[str]) -> list[float]:
    out: list[float] = []
    for c in cells:
        c = c.replace(",", "").strip()
        if re.fullmatch(r"\d+(?:\.\d+)?", c):
            out.append(float(c))
    return out


def _sums(doc: Doc, where: str, table, lines: list[str]) -> list[dict]:
    """A Total row that is not the sum of the rows above it, in a money or percent column."""
    out: list[dict] = []
    total_i = next(
        (i for i, r in enumerate(table.rows) if r and r[0].strip().lower() == "total"), None
    )
    if total_i is None or len(lines) != len(table.rows):
        return out
    money = re.compile(r"amount|price|fee|cost", re.IGNORECASE)
    skip = re.compile(r"hours?|\bh\b|days?|qty|quantity|rate", re.IGNORECASE)
    for col, head in enumerate(table.header):
        is_pct = bool(re.search(r"percent|%", head, re.IGNORECASE))
        if not is_pct and (not money.search(head) or skip.search(head)):
            continue
        body = [
            _numbers([r[col]]) for i, r in enumerate(table.rows) if i != total_i and col < len(r)
        ]
        total = _numbers([table.rows[total_i][col]]) if col < len(table.rows[total_i]) else []
        vals = [v[0] for v in body if v]
        if not total or not vals:
            continue
        want, got = total[0], sum(vals)
        tol = 0.6 if is_pct else 1.0
        if abs(want - got) > tol:
            out.append(
                _make(
                    "commercial_timeline", "high", "stated",
                    f"The {head.strip()} column adds up to {got:,.2f}, not the stated total {want:,.2f}",
                    lines[total_i], doc, where,
                    "A price or payment schedule that does not add up will be disputed at invoicing.",
                    "Which figure is right, the total or the rows?",
                    "sales", "starting_issue", "code", rule="totals_mismatch",
                )
            )  # fmt: skip
    return out


# ---- code: checklist gaps, scope edge, draft changes -------------------------------------


def _anchor(doc: Doc, pattern: str) -> tuple[str, str]:
    """A real line to quote for something that is absent: the matching heading, else the scope
    heading, else the document's first line. Returns (quote, where)."""
    rx = re.compile(pattern, re.IGNORECASE)
    for s in doc.sections:
        if s.level and rx.search(s.title):
            return s.title, s.title
    for s in doc.sections:
        if s.level and re.search(
            r"scope|background|purpose|summary|solution", s.title, re.IGNORECASE
        ):
            return s.title, s.title
    first = next((ln.strip() for ln in doc.text.splitlines() if len(ln.strip()) >= 8), doc.filename)
    return first.lstrip("# "), "start"


_GAP = {
    "change_control": (
        "scope_boundary", r"change", "Change control is missing or only mentioned",
        "Without a way to request and approve changes, scope grows unpriced.",
        "How are changes to scope, schedule and price requested and approved?", "sales",
    ),
    "assumptions": (
        "assumptions_dependencies", r"assumption", "Assumptions are missing or thin",
        "Unstated assumptions become disputes when they turn out false.",
        "What does the plan assume, and what happens if each assumption is wrong?", "delivery",
    ),
    "dependencies": (
        "assumptions_dependencies", r"dependenc|responsibilit", "Dependencies are missing or thin",
        "Work that waits on the customer or a third party slips with no one accountable.",
        "What must the customer or others provide, by when, and who owns it?", "customer",
    ),
    "security_compliance": (
        "complexity", r"security|compliance|privacy", "Security or compliance terms are missing or thin",
        "Compliance needs found late are expensive and can block go-live.",
        "Which security, privacy or regulatory requirements apply?", "customer",
    ),
}  # fmt: skip


def gap_findings(doc: Doc, check: dict, cfg: dict) -> list[dict]:
    out: list[dict] = []
    sev_map = cfg["findings"]["gap_severity"]
    for item in check["items"]:
        spec = _GAP.get(item["id"])
        if not spec or item["status"] not in ("partial", "missing"):
            continue
        category, pattern, title, why, question, asked = spec
        quote, where = _anchor(doc, pattern)
        sev = sev_map.get(item["id"], {}).get(item["status"], "medium")
        out.append(
            _make(
                category, sev, "stated", f"{title}: {item['detail']}", quote, doc, where,
                why, question, asked, "starting_risk", "code", kind="absence", rule=f"gap_{item['id']}",
            )
        )  # fmt: skip
    has_out = any(
        re.search(r"out of scope|exclusion|not included|excluded", s.title, re.IGNORECASE)
        for s in doc.sections
    ) or re.search(r"out of scope|not included|excluded from", doc.text, re.IGNORECASE)
    if not has_out:
        quote, where = _anchor(doc, r"scope")
        out.append(
            _make(
                "scope_boundary", "high", "stated", "There is no out-of-scope list", quote, doc, where,
                "Without stated exclusions, anything implied by the scope can be claimed as included.",
                "What is explicitly not included in this engagement?",
                "sales", "starting_risk", "code", kind="absence", rule="no_out_of_scope",
            )
        )  # fmt: skip
    return out


def _line_with(doc: Doc, test) -> str:
    return next((ln.strip() for ln in doc.text.splitlines() if ln.strip() and test(ln)), "")


def draft_findings(sow: Doc, loaded: Loaded) -> list[dict]:
    drafts = [d for d in loaded.scoper if d.filename.lower().startswith(SCOPER_DRAFT_PREFIX)]
    if not drafts:
        return []
    draft = max(drafts, key=lambda d: (d.uploaded_at, d.filename))
    out: list[dict] = []
    for kind, change in compare_draft(draft.text, sow.text).items():
        new, gone = change["only_in_signed"], change["only_in_draft"]
        source, shown = (sow, new) if new else (draft, gone)

        def has(ln: str, kind=kind, shown=shown) -> bool:
            if kind == "amounts":
                # a lone table row has no header, so read every number on the line instead
                nums = [float(n.replace(",", "")) for n in re.findall(r"\d[\d,]*(?:\.\d+)?", ln)]
                vals = {*find_amounts(ln), *nums}
                return any(f"{v:,.2f}".removesuffix(".00") in shown for v in vals)
            if kind == "dates":
                return any(d is not None and d.isoformat() in shown for _, d in find_dates(ln))
            return any(i in ln for i in shown)

        quote = _line_with(source, has)
        if len(quote) < 8:
            continue
        side = "added or changed in the signed SOW" if new else "dropped from the draft"
        out.append(
            _make(
                "scope_boundary" if kind == "deliverables" else "commercial_timeline",
                "medium", "stated",
                f"Unexplained change from Scoper's draft: {kind} {side} ({', '.join(shown[:4])})",
                quote, source, "start",
                "A signed SOW that differs from the reviewed draft may carry terms nobody costed.",
                "Why did this change between the draft and the signed SOW, and who agreed it?",
                "sales", "open_question", "code", rule="draft_change",
            )
        )  # fmt: skip
    return out


# ---- model proposals, checked by code ----------------------------------------------------

GROUPS = [
    ("scope and deliverables", r"scope|deliverable|objective|our solution|background|purpose"),
    (
        "assumptions, dependencies, timeline and commercial terms",
        r"assumption|dependenc|client responsibilit|timeline|milestone|schedule|fee|pric|payment|constraint|risk",
    ),
]
LIMIT = 6000
RFP_NOTE = (
    "Also add an optional field rfp_quote with words copied exactly from the RFP "
    "when the SOW contradicts or silently drops an RFP requirement."
)


def _field(item: dict, key: str, default: str) -> str:
    return str(item.get(key) or default).strip()


def _clean_proposals(raw: object, doc: Doc, rfps: list[Doc]) -> tuple[list[dict], list[dict]]:
    ok: list[dict] = []
    bad: list[dict] = []
    items = raw.get("findings") if isinstance(raw, dict) else None
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        quote = item.get("quote")
        if not isinstance(title, str) or not title.strip():
            continue
        quote = quote if isinstance(quote, str) else ""
        reason = None
        if not verify_quote(doc, quote):
            reason = "the quoted text was not found in the SOW"
        rq = item.get("rfp_quote")
        if (
            reason is None
            and isinstance(rq, str)
            and rq.strip()
            and not any(verify_quote(r, rq) for r in rfps)
        ):
            reason = "the quoted RFP text was not found in the RFP"
        if reason:
            bad.append(
                {"title": title.strip()[:200], "quote": quote.strip()[:300], "reason": reason}
            )
            continue
        cat = item.get("category") if item.get("category") in fr.CATEGORIES else "scope_boundary"
        sev = item.get("severity") if item.get("severity") in fr.SEVERITIES else "low"
        asked = item.get("asked_of") if item.get("asked_of") in fr.ASKED_OF else "customer"
        dest = (
            item.get("destination")
            if item.get("destination") in fr.DESTINATIONS
            else "open_question"
        )
        basis = "stated" if item.get("basis") == "stated" else "inferred"
        ok.append(
            _make(
                cat, sev, basis, title.strip(), quote, doc,
                _field(item, "where", "start"),
                _field(item, "why", "The model flagged this as a risk."),
                _field(item, "question", "Can this be clarified?"),
                asked, dest, "model",
            )
        )  # fmt: skip
    return ok, bad


def find_sections_of(doc: Doc, pattern: str) -> list:
    return find_sections(doc.sections, pattern)


def propose(llm: LLM, doc: Doc, rfps: list[Doc], progress=lambda t: None) -> dict:
    """Ask the model for candidate findings, group by group. A group that fails is reported and
    the others still run."""
    found: list[dict] = []
    unsupported: list[dict] = []
    problems: list[str] = []
    cats = ", ".join(fr.CATEGORIES)
    rules = (
        f'Return JSON: {{"findings": [{{"title": "...", "category": one of [{cats}], '
        '"severity": "high" or "medium" or "low", "basis": "stated" if the quoted text itself is the '
        'problem or "inferred" if you are reading between the lines, "quote": "words copied exactly '
        'from the SOW", "where": "section heading", "why": "why it matters", "question": "a clarifying '
        'question", "asked_of": "customer" or "sales" or "delivery", "destination": "starting_risk" or '
        '"starting_issue" or "open_question"}]}. At most 6. Every finding must quote the SOW. '
        "If you find nothing, return an empty list. Do not build a schedule."
    )
    jobs: list[tuple[str, str]] = []
    for label, pattern in GROUPS:
        text = "\n\n".join(
            f"## {s.title}\n{s.full_text()}" for s in find_sections_of(doc, pattern)
        )[:LIMIT]
        if text.strip():
            jobs.append((label, f"{untrusted('SOW', text, LIMIT)}"))
    if rfps:
        rfp_text = "\n\n".join(
            f"## {s.title}\n{s.full_text()}"
            for r in rfps
            for s in find_sections_of(r, r"requirement|scope|deliverable|schedule|term")
        )[:LIMIT]
        sow_scope = "\n\n".join(
            f"## {s.title}\n{s.full_text()}" for s in find_sections_of(doc, GROUPS[0][1])
        )[:LIMIT]
        if rfp_text.strip() and sow_scope.strip():
            jobs.append(
                (
                    "contradictions with the RFP",
                    f"{untrusted('SOW', sow_scope, LIMIT)}\n\n{untrusted('RFP', rfp_text, LIMIT)}\n"
                    + RFP_NOTE,
                )
            )
    for label, body in jobs:
        progress(f"Reviewing for gaps: {label}")
        prompt = (
            f"{DATA_RULE}\n\nTASK: review a signed SOW for scope risk\n"
            f"Focus: {label}. Find ambiguity, missing or hidden complexity, scope boundary problems, "
            "risky assumptions and dependencies, and inconsistent commercial or timeline statements.\n"
            f"{rules}\n\n{body}"
        )
        try:
            raw = llm.json(prompt)
        except LLMError as exc:
            problems.append(f"gap review ({label}): {exc}")
            continue
        ok, bad = _clean_proposals(raw, doc, rfps)
        found += ok
        unsupported += bad
    return {"findings": found, "unsupported": unsupported, "problems": problems}


# ---- put it together ---------------------------------------------------------------------


def merge(code: list[dict], model: list[dict], max_model: int) -> list[dict]:
    """Code findings first. A model finding that repeats one by quote is dropped."""
    seen = {(f["category"], _norm(f["quote"])) for f in code}
    seen_quotes = {_norm(f["quote"]) for f in code}
    out = list(code)
    kept = 0
    for f in model:
        key = (f["category"], _norm(f["quote"]))
        if key in seen or _norm(f["quote"]) in seen_quotes or kept >= max_model:
            continue
        seen.add(key)
        out.append(f)
        kept += 1
    return sorted(
        out,
        key=lambda f: (
            SEVERITY_ORDER[f["severity"]],
            f["basis"] != "stated",
            f["category"],
            f["id"],
        ),
    )


def verdict_with_findings(
    checklist_verdict: str, findings: list[dict], cfg: dict
) -> tuple[str, list[str]]:
    """Fold findings into the verdict by the configured effect. Only stated findings count."""
    effects = cfg["findings"]["verdict_effect"]
    verdict, reasons = checklist_verdict, []
    for f in findings:
        effect = effects.get(f["severity"], "none")
        if f["basis"] != "stated" or effect == "none":
            continue
        if effect == "not_ready" and verdict != "not_ready":
            verdict = "not_ready"
        elif effect == "conditions" and verdict == "ready":
            verdict = "ready_with_conditions"
        else:
            continue
        reasons.append(f["id"])
    return verdict, reasons


def review(
    llm: LLM,
    sow: Doc,
    loaded: Loaded,
    check: dict,
    rules: list[dict],
    cfg: dict,
    progress=lambda t: None,
) -> dict:
    """Run the whole review for the chosen SOW. A model outage leaves the code findings and a
    problem line, never an empty report."""
    f = cfg["findings"]
    code = (
        phrase_findings(sow, rules, f["max_per_rule"])
        + table_findings(sow)
        + gap_findings(sow, check, cfg)
        + draft_findings(sow, loaded)
    )
    proposed = propose(llm, sow, loaded.rfp, progress)
    items = merge(code, proposed["findings"], f["max_model_findings"])
    verdict, reasons = verdict_with_findings(check["verdict"], items, cfg)
    return {
        "items": items,
        "unsupported": proposed["unsupported"],
        "problems": proposed["problems"],
        "verdict": verdict,
        "verdict_reasons": reasons,
    }
