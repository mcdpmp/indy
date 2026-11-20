"""The readiness check. Every status and the verdict are computed here, in code.

Statuses per item:
  present  the documents state it
  partial  stated but thin (for example 5 of 10 deliverables have acceptance criteria)
  missing  not found
  unclear  the documents leave it open, so Indy cannot confirm it
  skipped  does not apply (for example no Scoper draft to compare against)

Verdict: any enabled blocker that is missing or unclear gives "not_ready". Otherwise any enabled
item that is not present gives "ready_with_conditions", else "ready". A partial blocker is a
condition, not a stop, because the deal is real and the gap is something to fix with the customer.

Each item carries evidence quoted from the documents ("stated") or a number counted in code
("computed"). Indy's own inferences come later, from the model, and are marked as such.
"""

import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date

from .diff import compare_draft
from .documents import SCOPER_DRAFT_PREFIX, Doc, Loaded
from .signature import SignatureResult, check_signature
from .textutil import (
    Section,
    Table,
    find_amounts,
    find_dates,
    find_sections,
    list_items,
    parse_tables,
    person_name,
    snippet,
    table_amounts,
    words,
)

OPEN_ENDED = re.compile(
    r"including but not limited to|as needed|as required|and so on|\betc\b\.?|any other|from time to time",
    re.IGNORECASE,
)
SUBJECTIVE = re.compile(
    r"to the (?:client|customer|university|county|state|company)['’]?s? satisfaction"
    r"|modern and intuitive|reasonable",
    re.IGNORECASE,
)


@dataclass
class Ctx:
    sow: Doc | None
    signature: SignatureResult | None
    loaded: Loaded
    cfg: dict
    today: date
    pool: list[Doc] = field(default_factory=list)  # SOW first, then supporting documents

    @property
    def r(self) -> dict:
        return self.cfg["readiness"]


def _res(
    status: str, detail: str, evidence: list[dict] | None = None, basis: str = "stated", notes=None
):
    return {
        "status": status,
        "detail": detail,
        "basis": basis,
        "evidence": evidence or [],
        "notes": notes or [],
    }


def _ev(doc: Doc, where: str, quote: str) -> dict:
    return {"doc": doc.filename, "where": where, "quote": snippet(quote)}


def _sections(doc: Doc, pattern: str) -> list[Section]:
    return find_sections(doc.sections, pattern)


def _first_line(text: str, rx: re.Pattern | str) -> str:
    rx = re.compile(rx, re.IGNORECASE) if isinstance(rx, str) else rx
    for ln in text.splitlines():
        if rx.search(ln):
            return ln.strip()
    return ""


# ---- choosing the SOW -------------------------------------------------------------------


def pick_sow(loaded: Loaded, today: date) -> tuple[Doc | None, SignatureResult | None, dict]:
    """The SOW the other checks run on, and the result for the signed_sow item."""
    unreadable = [s for s in loaded.skipped if s.get("category") == "sow"]
    if not loaded.sow:
        if unreadable:
            names = ", ".join(s["filename"] for s in unreadable)
            return (
                None,
                None,
                _res(
                    "unclear",
                    f"A SOW is filed but could not be read ({names}). A scanned copy has no text "
                    "to check, so Indy cannot confirm it is signed. Check it by eye.",
                ),
            )
        return None, None, _res("missing", "No document is filed as a SOW for this opportunity.")
    sigs = [(d, check_signature(d.text, today)) for d in loaded.sow]
    signed = [(d, s) for d, s in sigs if s.state == "signed"]
    newest = max(sigs, key=lambda p: (p[0].uploaded_at, p[0].filename))
    if len(signed) == 1:
        d, s = signed[0]
        dates = ", ".join(sorted({p.date for p in s.parties}))
        return (
            d,
            s,
            _res(
                "present",
                f"{d.filename}: {s.detail} Dated {dates}.",
                [_ev(d, "signature block", dates)],
                "computed",
            ),
        )
    if len(signed) > 1:
        d, s = max(signed, key=lambda p: (p[0].uploaded_at, p[0].filename))
        names = ", ".join(x.filename for x, _ in signed)
        return (
            d,
            s,
            _res(
                "unclear",
                f"More than one signed SOW is filed ({names}). Indy checked the newest. Confirm which one governs.",
            ),
        )
    d, s = newest
    others = (
        f" ({len(sigs)} SOW files are filed; Indy checked the newest.)" if len(sigs) > 1 else ""
    )
    if s.state == "unsigned":
        return (
            d,
            s,
            _res("missing", f"{d.filename} is not signed. {s.detail}{others}", basis="computed"),
        )
    return (
        d,
        s,
        _res(
            "unclear",
            f"{d.filename}: {s.detail}{others} Indy cannot confirm it is fully signed.",
            basis="computed",
        ),
    )


# ---- the detectors, one per built-in item -----------------------------------------------


def _need_sow(ctx: Ctx) -> dict | None:
    return None if ctx.sow else _res("missing", "There is no SOW to check.")


def check_parties_dates(ctx: Ctx) -> dict:
    if (gap := _need_sow(ctx)) is not None:
        return gap
    t = ctx.sow.text
    party_line = _first_line(
        t, r"\bbetween\b.*\(|legal name|\"(?:client|customer)\"|by and between"
    )
    eff_line = _first_line(
        t, r"effective date|start date|commenc|project (?:starts|begins)|starts? on"
    )
    dates = find_dates(t)
    bad = [raw for raw, d in dates if d is None]
    ev = []
    if party_line:
        ev.append(_ev(ctx.sow, "parties", party_line))
    if eff_line:
        ev.append(_ev(ctx.sow, "effective date", eff_line))
    if bad:
        return _res(
            "unclear", f"These dates are not on the calendar: {', '.join(bad)}.", ev, "computed"
        )
    if party_line and eff_line and dates:
        return _res(
            "present",
            f"Parties and an effective or start date are stated ({len(dates)} dates found).",
            ev,
        )
    if party_line or (eff_line and dates):
        what = "the parties" if party_line else "an effective date"
        miss = "an effective or start date" if party_line else "the parties"
        return _res("partial", f"The SOW states {what} but not {miss}.", ev)
    return _res("missing", "Neither the parties nor an effective date could be found.", ev)


def _deliverable_tables(ctx: Ctx) -> list[tuple[Section | None, Table]]:
    out: list[tuple[Section | None, Table]] = []
    for sec in _sections(ctx.sow, r"deliverable"):
        out += [(sec, t) for t in parse_tables(sec.full_text())]
    return out


def check_scope_deliverables(ctx: Ctx) -> dict:
    if (gap := _need_sow(ctx)) is not None:
        return gap
    minw = ctx.r["min_section_words"]
    scope = _sections(ctx.sow, r"scope|our solution|statement of work")
    scope_words = sum(words(s.full_text()) for s in scope)
    deliv_secs = _sections(ctx.sow, r"deliverable")
    rows = sum(len(t.rows) for _, t in _deliverable_tables(ctx))
    ids = len(set(re.findall(r"\bD-\d{1,3}\b", ctx.sow.text)))
    count = max(
        rows,
        ids,
        len(list_items("\n".join(s.full_text() for s in deliv_secs))) if deliv_secs else 0,
    )
    open_ended = len(OPEN_ENDED.findall("\n".join(s.full_text() for s in scope)))
    notes = (
        [f"{open_ended} open-ended phrases in scope (for example 'as needed', 'etc.')."]
        if open_ended
        else []
    )
    ev = [_ev(ctx.sow, s.title, s.body or s.full_text()) for s in (scope[:1] + deliv_secs[:1])]
    has_scope, has_deliv = scope_words >= minw, count >= 1
    detail = f"Scope section: {scope_words} words. Deliverables listed: {count}."
    if has_scope and has_deliv:
        return _res("present", detail, ev, "computed", notes)
    if has_scope or has_deliv:
        return _res(
            "partial",
            detail + (" No deliverables found." if not has_deliv else " Scope is missing or thin."),
            ev,
            "computed",
            notes,
        )
    return _res("missing", "No scope section or deliverables found.", [], "computed")


def check_acceptance(ctx: Ctx) -> dict:
    if (gap := _need_sow(ctx)) is not None:
        return gap
    total = filled = 0
    subjective: list[str] = []
    for _, t in [(None, t) for t in parse_tables(ctx.sow.text)]:
        col = t.column(r"acceptance|criteria")
        if col is None:
            continue
        for row in t.rows:
            if not any(row) or (row and row[0].strip().lower() in ("total", "")):
                continue
            total += 1
            cell = row[col].strip() if col < len(row) else ""
            if cell:
                filled += 1
                if SUBJECTIVE.search(cell):
                    subjective.append(snippet(cell, 80))
    notes = [f"Subjective criterion, not testable: '{s}'" for s in subjective]
    if total:
        share = filled / total
        detail = f"{filled} of {total} deliverables have acceptance criteria."
        ev = [_ev(ctx.sow, "deliverables table", detail)]
        if filled == total:
            return _res("present", detail, ev, "computed", notes)
        if share >= ctx.r["partial_min_share"]:
            return _res("partial", detail, ev, "computed", notes)
        return _res("missing", detail + " Too few to rely on.", ev, "computed", notes)
    process = _sections(ctx.sow, r"acceptance")
    if process and sum(words(s.full_text()) for s in process) >= ctx.r["min_section_words"]:
        return _res(
            "partial",
            "An acceptance process is described but no per-deliverable criteria were found.",
            [_ev(ctx.sow, process[0].title, process[0].full_text())],
        )
    return _res("missing", "No acceptance criteria were found.")


_BILLING = re.compile(
    r"invoice|net\s*\d+|payment schedule|milestone payment|billed|billing|payable|percent of (?:the )?(?:price|fee)",
    re.IGNORECASE,
)


def check_commercial(ctx: Ctx) -> dict:
    if (gap := _need_sow(ctx)) is not None:
        return gap
    secs = _sections(ctx.sow, r"fee|pric|payment|invoice|billing|investment|commercial|cost")
    text = "\n".join(s.full_text() for s in secs)
    amounts = [*find_amounts(text), *table_amounts(text)]
    billing = _BILLING.search(text)
    ev = [_ev(ctx.sow, secs[0].title, secs[0].body or text)] if secs else []
    biggest = f"{max(amounts):,.0f}" if amounts else None
    if amounts and billing:
        return _res(
            "present",
            f"Price stated (largest amount {biggest}) with billing terms.",
            ev,
            "computed",
        )
    if amounts:
        return _res(
            "partial",
            f"Price stated (largest amount {biggest}) but no billing or invoicing terms.",
            ev,
            "computed",
        )
    if billing:
        return _res("partial", "Billing terms found but no price or rates.", ev, "computed")
    return _res("missing", "No price, rates or billing terms were found.", ev)


def _named_people(ctx: Ctx) -> tuple[list[dict], bool]:
    """People named in roles, contacts, team and dependency tables, with their party if the
    table has a party column. Signature blocks are left out: signing is not being a contact."""
    people: list[dict] = []
    has_party_col = False
    for sec in _sections(
        ctx.sow, r"role|contact|team|governance|responsib|personnel|stakeholder|dependenc"
    ):
        if re.search(r"signature", sec.title, re.IGNORECASE):
            continue
        for t in parse_tables(sec.full_text()):
            name_cols = [
                i
                for i, h in enumerate(t.header)
                if re.search(r"name|contact|owner", h, re.IGNORECASE)
            ]
            party_col = t.column(r"organi[sz]ation|party|company|side")
            has_party_col = has_party_col or party_col is not None
            for row in t.rows:
                for c in name_cols:
                    n = person_name(row[c]) if c < len(row) else None
                    if n:
                        party = (
                            row[party_col].strip()
                            if party_col is not None and party_col < len(row)
                            else ""
                        )
                        people.append({"name": n, "party": party, "section": sec.title})
    return people, has_party_col


def check_contacts(ctx: Ctx) -> dict:
    if (gap := _need_sow(ctx)) is not None:
        return gap
    people, party_col = _named_people(ctx)
    uniq = {p["name"]: p for p in people}
    ev = [
        _ev(ctx.sow, p["section"], f"{p['name']} ({p['party'] or 'party not given'})")
        for p in list(uniq.values())[:4]
    ]
    if not uniq:
        return _res(
            "missing",
            "No named people were found in the roles, contacts or dependency tables.",
            [],
            "computed",
        )
    parties = {p["party"].lower() for p in uniq.values() if p["party"]}
    if party_col and len(parties) >= 2:
        return _res(
            "present", f"{len(uniq)} named people across {len(parties)} parties.", ev, "computed"
        )
    if party_col:
        return _res(
            "partial",
            f"{len(uniq)} named people, all on one side ({', '.join(sorted(parties)) or 'party not given'}). Both customer and delivery contacts are needed.",
            ev,
            "computed",
        )
    return _res(
        "partial",
        f"{len(uniq)} named people, but the tables do not say which side each is on.",
        ev,
        "computed",
    )


def check_assumptions(ctx: Ctx) -> dict:
    if (gap := _need_sow(ctx)) is not None:
        return gap
    secs = _sections(ctx.sow, r"assumption")
    items = list_items("\n".join(s.full_text() for s in secs))
    n, need = len(items), ctx.r["min_assumptions"]
    ev = [_ev(ctx.sow, secs[0].title, items[0])] if items else []
    if n >= need:
        return _res("present", f"{n} assumptions listed.", ev, "computed")
    if n:
        return _res(
            "partial",
            f"Only {n} assumptions listed; at least {need} are expected on a project.",
            ev,
            "computed",
        )
    return _res("missing", "No assumptions were found.", [], "computed")


def check_dependencies(ctx: Ctx) -> dict:
    if (gap := _need_sow(ctx)) is not None:
        return gap
    secs = _sections(ctx.sow, r"dependenc|client responsibilit|customer responsibilit")
    n = len(list_items("\n".join(s.full_text() for s in secs)))
    if n:
        return _res(
            "present",
            f"{n} dependencies listed.",
            [_ev(ctx.sow, secs[0].title, secs[0].full_text())],
            "computed",
        )
    if re.search(r"depend(?:s|ent|encies) on", ctx.sow.text, re.IGNORECASE):
        return _res(
            "partial",
            "Dependencies are mentioned in passing but not listed.",
            [_ev(ctx.sow, "text", _first_line(ctx.sow.text, r"depend(?:s|ent|encies) on"))],
        )
    return _res("missing", "No dependencies were found.")


_COMPLIANCE_WORDS = re.compile(
    r"\b(?:HIPAA|FERPA|GDPR|SOC ?2|FedRAMP|CMMC|PCI|encrypt\w*|data protection|security requirements?|privacy)\b",
    re.IGNORECASE,
)


def _in_pool(ctx: Ctx, pattern: str) -> tuple[Doc, Section] | None:
    for d in ctx.pool:
        hit = _sections(d, pattern)
        if hit:
            return d, hit[0]
    return None


def check_security(ctx: Ctx) -> dict:
    if (gap := _need_sow(ctx)) is not None:
        return gap
    hit = _in_pool(ctx, r"security|compliance|privacy|data (?:handling|protection)|confidential")
    if hit and words(hit[1].full_text()) >= ctx.r["min_section_words"]:
        d, s = hit
        return _res(
            "present",
            f"A security or compliance section is found in {d.filename}.",
            [_ev(d, s.title, s.full_text())],
            "computed",
        )
    for d in ctx.pool:
        m = _COMPLIANCE_WORDS.search(d.text)
        if m:
            return _res(
                "partial",
                f"Security or compliance terms appear ('{m.group(0)}') but there is no section for them.",
                [_ev(d, "text", _first_line(d.text, re.escape(m.group(0))))],
            )
    return _res("missing", "No security or compliance requirements were found.")


_START = re.compile(
    r"start date|(?:project|work) (?:starts|begins)|commenc|kick.?off|begins? on|starts? (?:on|by)",
    re.IGNORECASE,
)


def check_staffing(ctx: Ctx) -> dict:
    if (gap := _need_sow(ctx)) is not None:
        return gap
    team = _sections(ctx.sow, r"role|team|staff|personnel|resourc")
    # the first start-like line may carry no date ("kickoff day in Dunmore"), so look for one that does
    start = next(
        (ln.strip() for ln in ctx.sow.text.splitlines() if _START.search(ln) and find_dates(ln)),
        "",
    )
    start_ok = bool(start)
    ev = [_ev(ctx.sow, "start", start)] if start else []
    if team and start_ok:
        return _res(
            "present",
            "A team or roles section and a dated start are stated.",
            ev + [_ev(ctx.sow, team[0].title, team[0].full_text())],
        )
    if team or start_ok:
        return _res(
            "partial",
            "A team is described but no dated start."
            if team
            else "A start date is given but no team or roles.",
            ev,
        )
    return _res("missing", "Neither staffing nor a start date was found.")


def check_change_control(ctx: Ctx) -> dict:
    if (gap := _need_sow(ctx)) is not None:
        return gap
    hit = _in_pool(ctx, r"change (?:control|management|request)")
    if hit:
        d, s = hit
        text = s.full_text()
        covered = sum(
            bool(re.search(w, text, re.IGNORECASE)) for w in (r"written", r"approv", r"impact")
        )
        if words(text) >= ctx.r["min_section_words"] or covered >= 2:
            return _res(
                "present",
                f"Change control is described in {d.filename}.",
                [_ev(d, s.title, text)],
                "computed",
            )
        return _res(
            "partial",
            f"Change control is only mentioned ({words(text)} words, no approval or impact steps).",
            [_ev(d, s.title, text)],
            "computed",
        )
    for d in ctx.pool:
        line = _first_line(d.text, r"change control|change request")
        if line:
            return _res(
                "partial", "Change control is mentioned but has no section.", [_ev(d, "text", line)]
            )
    return _res("missing", "No change control terms were found.")


def _scoper_draft(loaded: Loaded) -> Doc | None:
    drafts = [d for d in loaded.scoper if d.filename.lower().startswith(SCOPER_DRAFT_PREFIX)]
    return max(drafts, key=lambda d: (d.uploaded_at, d.filename)) if drafts else None


def check_draft_vs_signed(ctx: Ctx) -> dict:
    draft = _scoper_draft(ctx.loaded)
    if draft is None:
        return _res(
            "skipped",
            "No Scoper draft is readable for this opportunity, so there is nothing to compare.",
        )
    if ctx.sow is None:
        return _res("skipped", "There is no SOW to compare the draft against.")
    changes = compare_draft(draft.text, ctx.sow.text)
    if not changes:
        return _res(
            "present", f"Amounts, dates and deliverable ids match {draft.filename}.", [], "computed"
        )
    parts = [
        f"{k}: {len(v['only_in_draft'])} only in the draft, {len(v['only_in_signed'])} only in the signed SOW"
        for k, v in changes.items()
    ]
    return _res(
        "partial",
        f"Changed since {draft.filename}: " + "; ".join(parts) + ".",
        [],
        "computed",
        [
            f"{k} {side}: {', '.join(vals)}"
            for k, v in changes.items()
            for side, vals in v.items()
            if vals
        ],
    )


def check_custom(ctx: Ctx, item: dict) -> dict:
    hits: list[tuple[Doc, str]] = []
    for d in ctx.pool:
        for kw in item["keywords"]:
            line = _first_line(d.text, re.escape(kw))
            if line:
                hits.append((d, line))
                break
    if hits:
        return _res(
            "present",
            f"Found in {len(hits)} document(s).",
            [_ev(d, "text", ln) for d, ln in hits[:3]],
            "computed",
        )
    return _res(
        "missing",
        f"None of the keywords were found: {', '.join(item['keywords'])}.",
        basis="computed",
    )


DETECTORS = {
    "parties_dates": check_parties_dates,
    "scope_deliverables": check_scope_deliverables,
    "acceptance_criteria": check_acceptance,
    "commercial_terms": check_commercial,
    "contacts": check_contacts,
    "assumptions": check_assumptions,
    "dependencies": check_dependencies,
    "security_compliance": check_security,
    "staffing_start": check_staffing,
    "change_control": check_change_control,
    "draft_vs_signed": check_draft_vs_signed,
}


def verdict(results: list[dict]) -> str:
    live = [r for r in results if r["status"] != "skipped"]
    if any(r["severity"] == "blocker" and r["status"] in ("missing", "unclear") for r in live):
        return "not_ready"
    if any(r["status"] != "present" for r in live):
        return "ready_with_conditions"
    return "ready"


def run_check(loaded: Loaded, checklist: list[dict], cfg: dict, today: date | None = None) -> dict:
    today = today or date.today()
    sow, sig, signed_res = pick_sow(loaded, today)
    support = [*loaded.other]
    ctx = Ctx(sow, sig, loaded, cfg, today, [d for d in [sow, *support] if d])
    results: list[dict] = []
    for item in checklist:
        if not item.get("enabled", True):
            continue
        if item["id"] == "signed_sow":
            out = signed_res
        elif item.get("custom"):
            out = check_custom(ctx, item)
        else:
            out = DETECTORS[item["id"]](ctx)
        results.append(
            {"id": item["id"], "label": item["label"], "severity": item["severity"], **out}
        )
    counts = Counter(r["status"] for r in results)
    return {
        "verdict": verdict(results),
        "items": results,
        "counts": dict(counts),
        "sow": sow.ref() if sow else None,
        "signature": sig.as_dict() if sig else None,
        "documents": loaded.summary(),
        "checked_on": today.isoformat(),
    }
