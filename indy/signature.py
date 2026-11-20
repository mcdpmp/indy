"""Is this SOW actually signed? Decided in code from the text, never by the model.

Signed means every party in the signature block has a signature and a valid date that is not in
the future. A blank signature table, which is what an unsigned SOW looks like, is "unsigned".
A scanned PDF has no text, so the parser refuses it and the caller reports "cannot verify".
"""

import re
from dataclasses import dataclass, field
from datetime import date

from .textutil import find_dates, parse_tables

_PLACEHOLDER = re.compile(
    r"^[\s_.\-x]*$|^\[.*\]$|^<.*>$|^\(.*\)$|(?:sign|signature|date)\s+here|^(?:pending|tbd|n/?a)$",
    re.IGNORECASE,
)
_SIG_ROW = re.compile(r"^(?:e-?)?signatures?(?:\s+of.*)?$", re.IGNORECASE)
_DATE_ROW = re.compile(r"^date(?:\s+signed)?$", re.IGNORECASE)
_TEXT_EVIDENCE = re.compile(
    r"/s/\s*\w|digitally signed by|electronically signed|docusign envelope id|signed by:\s*\w",
    re.IGNORECASE,
)
_SIG_LINE = re.compile(r"^\s*(?:signature|by)\s*:\s*(.*)$", re.IGNORECASE | re.MULTILINE)


@dataclass
class Party:
    name: str
    signed: bool
    dated: bool
    date: str = ""


@dataclass
class SignatureResult:
    state: str  # signed | partly | unsigned | no_block
    detail: str
    parties: list[Party] = field(default_factory=list)

    def as_dict(self) -> dict:
        return {
            "state": self.state,
            "detail": self.detail,
            "parties": [vars(p) for p in self.parties],
        }


def _filled(cell: str) -> bool:
    return bool(cell.strip()) and not _PLACEHOLDER.search(cell.strip())


def check_signature(text: str, today: date | None = None) -> SignatureResult:
    today = today or date.today()
    for table in parse_tables(text):
        sig_row = next((r for r in table.rows if r and _SIG_ROW.match(r[0].strip())), None)
        if sig_row is None:
            continue
        date_row = next((r for r in table.rows if r and _DATE_ROW.match(r[0].strip())), None)
        names = table.header[1:]
        parties: list[Party] = []
        problems: list[str] = []
        for i, cell in enumerate(sig_row[1:], start=1):
            name = (names[i - 1] if i - 1 < len(names) else "") or f"Party {i}"
            raw = date_row[i] if date_row and i < len(date_row) else ""
            parsed = find_dates(raw)
            valid = bool(parsed) and parsed[0][1] is not None
            if valid and parsed[0][1] > today:
                valid = False
                problems.append(f"{name} dated {raw.strip()}, which is in the future")
            parties.append(Party(name, _filled(cell), valid, raw.strip() if valid else ""))
        return _verdict(parties, problems)
    # no table: plain text, as a PDF or a pasted SOW usually arrives
    lines = [m.group(1).strip() for m in _SIG_LINE.finditer(text)]
    if lines:
        parties = [Party(f"Signature line {i}", _filled(v), False) for i, v in enumerate(lines, 1)]
        result = _verdict(parties, [])
        if result.state == "signed":  # dates are not tied to a party in running text
            result.detail = "Signature lines are filled. Dates could not be tied to each party."
            result.state = "partly"
        return result
    if _TEXT_EVIDENCE.search(text):
        return SignatureResult(
            "partly",
            "The text carries a signing mark but no signature block to confirm every party signed.",
        )
    return SignatureResult("no_block", "No signature block was found in the document.")


def _verdict(parties: list[Party], problems: list[str]) -> SignatureResult:
    if len(parties) < 2:
        return SignatureResult(
            "partly", "The signature block lists fewer than two parties.", parties
        )
    signed = [p for p in parties if p.signed]
    if not signed:
        return SignatureResult("unsigned", "The signature block is blank for every party.", parties)
    gaps = [f"{p.name} has not signed" for p in parties if not p.signed]
    gaps += [f"{p.name} has no valid signature date" for p in parties if p.signed and not p.dated]
    gaps += problems
    if gaps:
        return SignatureResult("partly", "; ".join(gaps) + ".", parties)
    return SignatureResult("signed", "Every party has signed and dated.", parties)
