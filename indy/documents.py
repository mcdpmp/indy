"""Read an opportunity's documents from Vera, and only from Vera.

Every document is untrusted text. Nothing here follows instructions found in a document; the
text is only parsed and handed to code. If Vera cannot be reached the whole read fails (the
caller must say so), but one document Vera refuses or that cannot be parsed is listed as
skipped with the reason, so the report never pretends it was read.
"""

import hashlib
from dataclasses import dataclass, field

from .parsers import ParseError, parse
from .textutil import Section, split_sections
from .vera_client import VeraClient, VeraError

# Scoper writes sow_draft.md and rfp_gap_report.md into the opportunity's outputs
SCOPER_DRAFT_PREFIX = "sow_draft"


@dataclass
class Doc:
    doc_id: str
    filename: str
    category: str
    source: str
    uploaded_at: str
    text: str
    sections: list[Section] = field(default_factory=list)

    def ref(self) -> dict:
        return {"doc_id": self.doc_id, "filename": self.filename, "category": self.category}


@dataclass
class Loaded:
    sow: list[Doc] = field(default_factory=list)
    rfp: list[Doc] = field(default_factory=list)
    other: list[Doc] = field(default_factory=list)
    scoper: list[Doc] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)

    def everything(self) -> list[Doc]:
        return [*self.sow, *self.other, *self.rfp, *self.scoper]

    def summary(self) -> dict:
        return {
            "read": [d.ref() for d in self.everything()],
            "skipped": self.skipped,
        }


def _read(vera: VeraClient, meta: dict, skipped: list[dict]) -> Doc | None:
    name = meta.get("filename", meta.get("doc_id", "?"))
    try:
        data = vera.fetch(meta["doc_id"])
    except VeraError as exc:  # out of scope or gone: say so, do not guess at the content
        skipped.append(
            {"filename": name, "category": meta.get("category", ""), "reason": exc.message}
        )
        return None
    want = meta.get("sha256")
    if want and hashlib.sha256(data).hexdigest() != want:
        skipped.append(
            {
                "filename": name,
                "category": meta.get("category", ""),
                "reason": "content does not match the checksum Vera lists",
            }
        )
        return None
    try:
        text = parse(name, data)
    except ParseError as exc:
        skipped.append({"filename": name, "category": meta.get("category", ""), "reason": str(exc)})
        return None
    return Doc(
        meta["doc_id"],
        name,
        meta.get("category", ""),
        meta.get("source", ""),
        meta.get("uploaded_at", ""),
        text,
        split_sections(text),
    )


def load_opportunity(vera: VeraClient, opportunity_id: str, cfg: dict) -> Loaded:
    """Raises VeraUnavailable when Vera cannot be reached, VeraError when the listing itself is
    refused. The caller turns both into a plain message and stops."""
    v = cfg["vera"]
    out = Loaded()
    scoper_source = f"agent:{v['scoper_agent']}"
    for meta in vera.opportunity_documents(opportunity_id, include_outputs=True):
        category = meta.get("category", "")
        is_output = category == "outputs" or str(meta.get("source", "")).startswith("agent:")
        if is_output:
            # only Scoper's outputs are read; another agent's outputs are not Indy's input
            if meta.get("source") != scoper_source:
                continue
            bucket = out.scoper
        elif category == v["sow_category"]:
            bucket = out.sow
        elif category == v["rfp_category"]:
            bucket = out.rfp
        elif category == v["other_category"]:
            bucket = out.other
        else:
            continue
        doc = _read(vera, meta, out.skipped)
        if doc:
            bucket.append(doc)
    return out
