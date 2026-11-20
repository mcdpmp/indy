import io

import docx
import pytest
from conftest import FakeVera

from indy.config import DEFAULTS
from indy.documents import load_opportunity
from indy.parsers import ParseError, parse
from indy.vera_client import VeraUnavailable


def _vera() -> FakeVera:
    v = FakeVera()
    v.add("d1", "signed_sow.md", "sow", b"# SOW\n\nText")
    v.add("d2", "rfp.md", "rfp", b"# RFP\n\nText")
    v.add("d3", "msa.md", "other", b"# MSA\n\nText")
    v.add("d4", "ignored.md", "invoice", b"# Not read")
    v.add("o1", "sow_draft.md", "outputs", b"# Draft", source="agent:scoper")
    v.add("o2", "other_agent.md", "outputs", b"# Nope", source="agent:pinny")
    return v


def test_documents_are_sorted_into_buckets_and_other_agents_outputs_are_ignored():
    got = load_opportunity(_vera(), "OPP-1", DEFAULTS)
    assert [d.filename for d in got.sow] == ["signed_sow.md"]
    assert [d.filename for d in got.rfp] == ["rfp.md"]
    assert [d.filename for d in got.other] == ["msa.md"]
    assert [d.filename for d in got.scoper] == ["sow_draft.md"]
    assert got.skipped == []


def test_vera_down_raises_so_the_caller_stops():
    v = _vera()
    v.down = True
    with pytest.raises(VeraUnavailable):
        load_opportunity(v, "OPP-1", DEFAULTS)


def test_a_refused_document_is_skipped_with_the_reason_not_guessed_at():
    v = _vera()
    v.forbidden = {"d3"}
    got = load_opportunity(v, "OPP-1", DEFAULTS)
    assert got.other == [] and got.skipped[0]["filename"] == "msa.md"
    assert "scope" in got.skipped[0]["reason"]


def test_a_checksum_mismatch_is_skipped():
    v = _vera()
    real = v.opportunity_documents

    def lying(oid, **kw):
        docs = real(oid, **kw)
        docs[0]["sha256"] = "0" * 64
        return docs

    v.opportunity_documents = lying
    got = load_opportunity(v, "OPP-1", DEFAULTS)
    assert got.sow == [] and "checksum" in got.skipped[0]["reason"]


def test_unreadable_and_unsupported_files_are_skipped_with_category():
    v = FakeVera()
    v.add("p", "scan.pdf", "sow", b"not a pdf")
    v.add("x", "sheet.xlsx", "other", b"zip")
    got = load_opportunity(v, "OPP-1", DEFAULTS)
    reasons = {s["filename"]: s for s in got.skipped}
    assert (
        reasons["scan.pdf"]["category"] == "sow"
        and "could not be read" in reasons["scan.pdf"]["reason"]
    )
    assert "unsupported" in reasons["sheet.xlsx"]["reason"]


def test_empty_file_is_a_parse_error():
    with pytest.raises(ParseError, match="no text"):
        parse("a.md", b"   \n")


def test_docx_keeps_headings_order_and_first_table_column():
    d = docx.Document()
    d.add_heading("21. Signatures", level=2)
    t = d.add_table(rows=3, cols=3)
    for r, row in enumerate([["", "Client", "Vendor"], ["Signature", "", ""], ["Date", "", ""]]):
        for c, val in enumerate(row):
            t.cell(r, c).text = val
    buf = io.BytesIO()
    d.save(buf)
    text = parse("sow.docx", buf.getvalue())
    assert text.startswith("## 21. Signatures") and "| Signature |" in text


def test_csv_becomes_a_pipe_table():
    assert parse("a.csv", b"a,b\n1,2\n").splitlines()[0] == "| a | b |"
