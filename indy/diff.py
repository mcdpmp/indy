"""What changed between Scoper's draft SOW and the signed one, compared by value in code.

Only amounts, dates and deliverable ids are compared. They are the facts a project is built on,
and they can be compared exactly. Wording changes are not judged here.
"""

import re

from .textutil import find_amounts, find_dates, table_amounts

_DELIVERABLE_ID = re.compile(r"\bD-\d{1,3}\b")
MIN_AMOUNT = 100.0  # smaller numbers are usually rates or counts, not commitments


# a signed SOW always differs from its draft by the signing dates, which is not a change
_SIGNING_ROW = re.compile(
    r"^\|\s*(?:signature|date(?: signed)?)\s*\|.*$", re.IGNORECASE | re.MULTILINE
)


def _facts(text: str) -> dict[str, set]:
    text = _SIGNING_ROW.sub("", text)
    return {
        "amounts": {a for a in [*find_amounts(text), *table_amounts(text)] if a >= MIN_AMOUNT},
        "dates": {d for _, d in find_dates(text) if d is not None},
        "deliverables": set(_DELIVERABLE_ID.findall(text)),
    }


def compare_draft(draft: str, signed: str) -> dict:
    """Facts only in the draft, and facts only in the signed SOW, per kind."""
    a, b = _facts(draft), _facts(signed)
    changes: dict[str, dict[str, list[str]]] = {}
    for kind in a:
        gone, added = sorted(a[kind] - b[kind]), sorted(b[kind] - a[kind])
        if gone or added:
            changes[kind] = {
                "only_in_draft": [_show(kind, v) for v in gone],
                "only_in_signed": [_show(kind, v) for v in added],
            }
    return changes


def _show(kind: str, value: object) -> str:
    if kind == "amounts":
        return f"{value:,.2f}".removesuffix(".00")
    if kind == "dates":
        return value.isoformat()  # type: ignore[attr-defined]
    return str(value)
