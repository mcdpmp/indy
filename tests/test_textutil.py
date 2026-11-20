from datetime import date

from indy.signature import check_signature
from indy.textutil import (
    find_amounts,
    find_dates,
    find_sections,
    list_items,
    parse_tables,
    person_name,
    split_sections,
)


def test_dates_in_three_formats_and_an_impossible_one():
    got = find_dates(
        "Start April 12, 2027, end 2027-09-30, signed 3/4/2027, due February 30, 2027."
    )
    assert [d for _, d in got] == [date(2027, 4, 12), date(2027, 9, 30), date(2027, 3, 4), None]


def test_amounts_are_compared_by_value():
    assert find_amounts("USD 1,850,000 and $2.5 million, 135 USD per hour, 40 dollars") == [
        1850000.0,
        2500000.0,
        135.0,
        40.0,
    ]
    assert find_amounts("nothing here, 2027 widgets") == []


def test_person_names_reject_titles_and_organisations():
    assert person_name("Elaine Marchetti") == "Elaine Marchetti"
    assert person_name("Dr. Alan Whitcombe, Vice President for Student Affairs") == "Alan Whitcombe"
    assert person_name("Solution Architect") is None
    assert person_name("Kestrel Ridge Solutions") is None
    assert person_name("") is None and person_name("TBD") is None


def test_sections_nest_and_unmarked_text_gets_numbered_headings():
    secs = split_sections("# A\n\ntext\n\n## A1\n\nchild\n\n# B\n\nother")
    hit = find_sections(secs, "^A")
    assert len(hit) == 1 and "child" in hit[0].full_text() and "other" not in hit[0].full_text()
    plain = split_sections(
        "Intro\n\n5. Assumptions\n\n1. The client provides data\n2. Approvals within five days\n\n6. Risks\n\nStuff"
    )
    assert [s.title for s in plain if s.level] == ["5. Assumptions", "6. Risks"]


def test_tables_and_list_items():
    text = "| A | B |\n|---|---|\n| 1 | 2 |\n| 3 | |\n\n- bullet\n1. numbered"
    t = parse_tables(text)[0]
    assert t.header == ["A", "B"] and t.rows == [["1", "2"], ["3", ""]] and t.column("^b") == 1
    assert list_items(text) == ["bullet", "numbered", "1 | 2", "3 | "]


def test_signature_variants():
    blank = "| | A | B |\n|---|---|---|\n| Signature | | |\n| Date | | |"
    assert check_signature(blank).state == "unsigned"
    placeholder = blank.replace("| Signature | | |", "| Signature | ______ | [sign here] |")
    assert check_signature(placeholder).state == "unsigned"
    one_party = "| | A |\n|---|---|\n| Signature | /s/ X |"
    assert check_signature(one_party, date(2027, 1, 1)).state == "partly"
    assert check_signature("Signature: Jo Smith\nSignature: Al Jones").state == "partly"
    assert check_signature("Signature: ____\nBy: ").state == "unsigned"
    assert check_signature("Executed. DocuSign Envelope ID: 123").state == "partly"
    assert check_signature("Just a contract with no block.").state == "no_block"
