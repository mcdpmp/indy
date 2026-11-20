"""Turn an uploaded document (bytes plus filename) into plain text.

Tables are rendered as markdown pipe tables, first column kept, so the checks work the same on
a markdown SOW and a Word one. A document that cannot be parsed raises ParseError; the caller
decides whether that is fatal (the signed SOW) or reportable (one supporting file). A scanned
PDF with no text layer is a ParseError on purpose: Indy cannot tell whether it is signed.
"""

import csv
import io
from pathlib import PurePath

import docx
from pypdf import PdfReader


class ParseError(Exception):
    pass


def _text(data: bytes) -> str:
    return data.decode("utf-8-sig", errors="replace")


def _pipe_table(rows: list[list[str]]) -> str:
    width = max(len(r) for r in rows)
    padded = [
        [c.replace("|", "/").replace("\n", " ").strip() for c in r] + [""] * (width - len(r))
        for r in rows
    ]
    lines = ["| " + " | ".join(padded[0]) + " |", "|" + "---|" * width]
    lines += ["| " + " | ".join(r) + " |" for r in padded[1:]]
    return "\n".join(lines)


def _csv(data: bytes) -> str:
    rows = [r for r in csv.reader(io.StringIO(_text(data))) if any(c.strip() for c in r)]
    return _pipe_table(rows) if rows else ""


def _docx(data: bytes) -> str:
    d = docx.Document(io.BytesIO(data))
    blocks: list[str] = []
    # python-docx lists paragraphs and tables separately; walk the body to keep document order,
    # because a signature table's meaning depends on the heading above it.
    body = d.element.body
    tables = {t._tbl: t for t in d.tables}
    paragraphs = {p._p: p for p in d.paragraphs}
    for child in body.iterchildren():
        if child in paragraphs:
            p = paragraphs[child]
            if not p.text.strip():
                continue
            style = (p.style.name or "") if p.style is not None else ""
            level = style.removeprefix("Heading ").strip()
            if style.startswith("Heading") and level.isdigit():
                blocks.append(f"{'#' * min(int(level), 6)} {p.text.strip()}")
            elif style == "Title":
                blocks.append(f"# {p.text.strip()}")
            else:
                blocks.append(p.text.strip())
        elif child in tables:
            rows = [[c.text.strip() for c in r.cells] for r in tables[child].rows]
            rows = [r for r in rows if any(r)]
            if rows:
                blocks.append(_pipe_table(rows))
    return "\n\n".join(blocks)


def _pdf(data: bytes) -> str:
    reader = PdfReader(io.BytesIO(data))
    return "\n\n".join((page.extract_text() or "").strip() for page in reader.pages).strip()


_PARSERS = {
    ".txt": _text,
    ".md": _text,
    ".eml": _text,
    ".csv": _csv,
    ".docx": _docx,
    ".pdf": _pdf,
}


def parse(filename: str, data: bytes) -> str:
    ext = PurePath(filename).suffix.lower()
    fn = _PARSERS.get(ext)
    if fn is None:
        raise ParseError(f"{filename}: unsupported file type {ext or '(none)'}")
    try:
        text = fn(data)
    except Exception as exc:  # noqa: BLE001 - any library failure becomes one ParseError
        raise ParseError(f"{filename}: could not be read ({exc})") from None
    if not text.strip():
        raise ParseError(f"{filename}: no text found (scanned PDF or empty file)")
    return text
