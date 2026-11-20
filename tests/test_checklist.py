import pytest

from indy.checklist import BUILTIN_IDS, ChecklistError, ChecklistStore, defaults, validate


def test_defaults_have_six_blockers_and_the_rest_warnings():
    items = defaults()
    assert {i["id"] for i in items} == BUILTIN_IDS
    assert sum(i["severity"] == "blocker" for i in items) == 6


def test_edits_persist_and_reset(tmp_path):
    store = ChecklistStore(tmp_path)
    items = store.load()
    items[6]["severity"] = "blocker"
    items[7]["enabled"] = False
    items.append(
        {"custom": True, "label": "Escalation path", "severity": "warning", "keywords": ["escalat"]}
    )
    saved = store.save(items)
    again = ChecklistStore(tmp_path).load()
    assert again == saved and again[-1]["id"] == "custom-escalation-path"
    assert again[6]["severity"] == "blocker" and again[7]["enabled"] is False
    assert store.reset() == defaults() and store.load() == defaults()


def test_a_damaged_file_falls_back_to_the_defaults(tmp_path):
    (tmp_path / "checklist.json").write_text("{not json", encoding="utf-8")
    assert ChecklistStore(tmp_path).load() == defaults()


@pytest.mark.parametrize(
    "mutate, message",
    [
        (lambda i: i[0].update(severity="fatal"), "severity"),
        (lambda i: i.pop(), "cannot be removed"),
        (lambda i: i.append({"id": "nope", "severity": "warning"}), "Unknown built-in"),
        (lambda i: i.append(dict(i[0])), "twice"),
        (
            lambda i: i.append(
                {"custom": True, "label": "", "severity": "warning", "keywords": ["a"]}
            ),
            "label",
        ),
        (
            lambda i: i.append(
                {"custom": True, "label": "X", "severity": "warning", "keywords": []}
            ),
            "keywords",
        ),
        (
            lambda i: i.append(
                {"custom": True, "label": "X", "severity": "bad", "keywords": ["a"]}
            ),
            "severity",
        ),
        (lambda i: i.append("junk"), "object"),
    ],
)
def test_bad_edits_are_rejected_with_a_plain_message(mutate, message):
    items = defaults()
    mutate(items)
    with pytest.raises(ChecklistError, match=message):
        validate(items)


def test_too_many_custom_items_are_rejected():
    items = defaults() + [
        {"custom": True, "label": f"Item {n}", "severity": "warning", "keywords": ["k"]}
        for n in range(31)
    ]
    with pytest.raises(ChecklistError, match="At most"):
        validate(items)


def test_a_failed_save_leaves_the_old_list(tmp_path):
    store = ChecklistStore(tmp_path)
    good = store.save(defaults())
    with pytest.raises(ChecklistError):
        store.save([{"id": "signed_sow", "severity": "nope"}])
    assert store.load() == good
