"""Plain-text helpers the checks are built on: sections, tables, dates, amounts, names.

Everything here is deterministic. The model is never asked to count, compare dates or decide
whether a section exists.
"""

import re
from dataclasses import dataclass, field
from datetime import date

_HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
# PDFs and plain text carry no markdown marks, so a short numbered title line counts as a heading
_NUMBERED_TITLE = re.compile(r"^\s*(\d+(?:\.\d+)*)[.)]?\s+([A-Z][A-Za-z0-9 ,&/'-]{2,70})$")


def _title_case(title: str) -> bool:
    """Headings are short and capitalised. A numbered sentence in a list is not a heading."""
    ws = title.split()
    return len(ws) <= 8 and all(w[0].isupper() or w[0] in "&/(" or len(w) <= 3 for w in ws)


@dataclass
class Section:
    title: str
    level: int
    body: str
    children: list["Section"] = field(default_factory=list)

    def full_text(self) -> str:
        return "\n".join([self.body] + [c.full_text() for c in self.children]).strip()


def split_sections(text: str) -> list[Section]:
    """Flat list of sections in document order. Text before the first heading is level 0."""
    lines = text.splitlines()
    has_marks = any(_HEADING.match(ln) for ln in lines)
    out: list[Section] = [Section("", 0, "")]
    buf: list[str] = []
    for ln in lines:
        m = _HEADING.match(ln)
        level, title = (len(m.group(1)), m.group(2).strip()) if m else (0, "")
        if not m and not has_marks:
            n = _NUMBERED_TITLE.match(ln)
            if n and _title_case(n.group(2)) and not ln.rstrip().endswith((".", ":", ",")):
                level, title = n.group(1).count(".") + 2, ln.strip()
        if level:
            out[-1].body = "\n".join(buf).strip()
            buf = []
            out.append(Section(title, level, ""))
        else:
            buf.append(ln)
    out[-1].body = "\n".join(buf).strip()
    # nest: a section owns the deeper sections that follow it
    stack: list[Section] = []
    for s in out[1:]:
        while stack and stack[-1].level >= s.level:
            stack.pop()
        if stack:
            stack[-1].children.append(s)
        stack.append(s)
    return out


def find_sections(sections: list[Section], pattern: str) -> list[Section]:
    """Sections whose title matches. A child of a match is not returned again."""
    rx = re.compile(pattern, re.IGNORECASE)
    hits: list[Section] = []
    covered: set[int] = set()
    for s in sections:
        if s.level and rx.search(s.title) and id(s) not in covered:
            hits.append(s)
            stack = list(s.children)
            while stack:
                c = stack.pop()
                covered.add(id(c))
                stack.extend(c.children)
    return hits


@dataclass
class Table:
    header: list[str]
    rows: list[list[str]]

    def column(self, pattern: str) -> int | None:
        rx = re.compile(pattern, re.IGNORECASE)
        for i, h in enumerate(self.header):
            if rx.search(h):
                return i
        return None


def _cells(line: str) -> list[str]:
    return [c.strip() for c in line.strip().strip("|").split("|")]


def parse_tables(text: str) -> list[Table]:
    """Markdown pipe tables. A table is a run of lines starting with a pipe."""
    tables: list[Table] = []
    run: list[str] = []
    for ln in [*text.splitlines(), ""]:
        if ln.strip().startswith("|"):
            run.append(ln)
            continue
        if len(run) >= 2:
            rows = [_cells(r) for r in run]
            body = [r for r in rows[1:] if not all(re.fullmatch(r":?-{2,}:?|", c) for c in r)]
            tables.append(Table(rows[0], body))
        run = []
    return tables


_MONTHS = {
    m: i
    for i, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ],
        start=1,
    )
    for m in names
}
_MONTH_RX = "|".join(sorted(_MONTHS, key=len, reverse=True))
_DATE_RX = re.compile(
    rf"\b(?:(?P<mon>{_MONTH_RX})\.?\s+(?P<d1>\d{{1,2}})(?:st|nd|rd|th)?,?\s+(?P<y1>\d{{4}})"
    r"|(?P<y2>\d{4})-(?P<m2>\d{2})-(?P<d2>\d{2})"
    r"|(?P<m3>\d{1,2})/(?P<d3>\d{1,2})/(?P<y3>\d{4}))\b",
    re.IGNORECASE,
)


def find_dates(text: str) -> list[tuple[str, date | None]]:
    """Every full date in the text as (as written, date). A date that is not on the calendar,
    such as February 30, comes back with None so the caller can flag it. Numeric dates with a
    slash are read month first (US), which is stated in the report when it matters."""
    found: list[tuple[str, date | None]] = []
    for m in _DATE_RX.finditer(text):
        try:
            if m.group("mon"):
                d = date(int(m.group("y1")), _MONTHS[m.group("mon").lower()], int(m.group("d1")))
            elif m.group("y2"):
                d = date(int(m.group("y2")), int(m.group("m2")), int(m.group("d2")))
            else:
                d = date(int(m.group("y3")), int(m.group("m3")), int(m.group("d3")))
        except ValueError:
            d = None
        found.append((m.group(0), d))
    return found


_AMOUNT = re.compile(
    r"(?:(?:USD|US\$|\$)\s?(?P<a>\d[\d,]*(?:\.\d+)?)(?:\s?(?P<u>million|thousand|k|m)\b)?"
    r"|(?P<b>\d[\d,]*(?:\.\d+)?)\s?(?:USD|dollars))",
    re.IGNORECASE,
)


def find_amounts(text: str) -> list[float]:
    """Money amounts in the text as numbers, so two documents can be compared by value."""
    out: list[float] = []
    for m in _AMOUNT.finditer(text):
        raw = (m.group("a") or m.group("b")).replace(",", "")
        try:
            val = float(raw)
        except ValueError:
            continue
        unit = (m.group("u") or "").lower()
        val *= {"million": 1e6, "m": 1e6, "thousand": 1e3, "k": 1e3}.get(unit, 1)
        out.append(val)
    return out


def table_amounts(text: str) -> list[float]:
    """Bare numbers of 1,000 or more under an Amount, Price, Fee, Total or Cost column. Price
    tables often omit the currency sign, so find_amounts alone would miss them."""
    out: list[float] = []
    money = re.compile(r"amount|price|fee|total|cost", re.IGNORECASE)
    not_money = re.compile(r"hours?|\bh\b|days?|qty|quantity|percent|%", re.IGNORECASE)
    for t in parse_tables(text):
        for col, head in enumerate(t.header):
            if not money.search(head) or not_money.search(head):
                continue  # "Total h" is hours, not money
            for row in t.rows:
                cell = row[col].replace(",", "").strip() if col < len(row) else ""
                if re.fullmatch(r"\d{4,}(?:\.\d+)?", cell):
                    out.append(float(cell))
    return out


# words that make a capitalised phrase a title or an organisation, not a person
_NOT_NAME = {
    "manager", "architect", "engineer", "director", "officer", "president", "partner", "lead",
    "analyst", "developer", "sponsor", "owner", "writer", "consultant", "administrator",
    "coordinator", "specialist", "team", "group", "company", "university", "services",
    "solutions", "inc", "llc", "corporation", "agency", "department", "office", "client",
    "representative", "chief", "head", "vice", "senior", "principal", "product", "project",
    "technical", "executive", "engagement", "operations", "security", "data", "business",
    "steering", "committee", "board", "council", "county", "state", "federal", "national",
    "master", "agreement", "statement", "work", "kestrel", "ridge",
}  # fmt: skip
_HONORIFIC = re.compile(r"^(?:dr|mr|mrs|ms|mx|prof)\.?\s+", re.IGNORECASE)
_NAME = re.compile(r"^[A-Z][a-z'’-]+(?: [A-Z]\.?)?(?: (?:Mc|O'|Mac)?[A-Z][a-z'’-]+){1,2}$")


def person_name(cell: str) -> str | None:
    """The person's name if the cell is one ("Dr. Jo Smith, Vice President" gives "Jo Smith"),
    otherwise None. Titles and organisation names are rejected by their words."""
    head = _HONORIFIC.sub("", cell.split(",")[0].strip())
    if not _NAME.match(head):
        return None
    if any(w.lower().strip(".") in _NOT_NAME for w in head.split()):
        return None
    return head


def words(text: str) -> int:
    return len(re.findall(r"\b\w+\b", text))


def list_items(text: str) -> list[str]:
    """Numbered or bulleted items, and the rows of a table, as plain strings."""
    items = [
        re.sub(r"^\s*(?:\d+[.)]|[-*•])\s+", "", ln).strip()
        for ln in text.splitlines()
        if re.match(r"^\s*(?:\d+[.)]|[-*•])\s+\S", ln)
    ]
    for t in parse_tables(text):
        items += [" | ".join(r) for r in t.rows if any(r)]
    return items


def snippet(text: str, limit: int = 160) -> str:
    one = " ".join(text.replace("**", "").split())  # bold marks only clutter a quoted line
    return one if len(one) <= limit else one[: limit - 3].rstrip() + "..."
