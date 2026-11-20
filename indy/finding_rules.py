"""The phrase rules behind the scope-risk review, editable like the readiness checklist.

Each rule is a list of phrases Indy looks for in the SOW, with the category, severity and the
follow-up question a hit produces. Built-in rules can be switched off, retuned or given more
phrases; Michael can add rules of his own. A "*" in a phrase stands for any one word, so
"until the * is satisfied" catches "until the University is satisfied". Phrases are plain text,
never regular expressions, so an edit cannot hang the check.
Edits are saved in state/finding_rules.json.
"""

import json
import re
import threading
from pathlib import Path

SEVERITIES = ("high", "medium", "low")
CATEGORIES = (
    "ambiguity",
    "acceptance",
    "complexity",
    "scope_boundary",
    "assumptions_dependencies",
    "commercial_timeline",
)
ASKED_OF = ("customer", "sales", "delivery")
DESTINATIONS = ("starting_risk", "starting_issue", "open_question")
MAX_CUSTOM = 30


class RuleError(ValueError):
    pass


def _rule(rid, label, category, severity, phrases, why, question, asked_of, destination):
    return {
        "id": rid,
        "label": label,
        "category": category,
        "severity": severity,
        "phrases": phrases,
        "why": why,
        "question": question,
        "asked_of": asked_of,
        "destination": destination,
    }


BUILTIN: list[dict] = [
    _rule(
        "vague_terms",
        "Vague or unmeasurable wording",
        "ambiguity",
        "medium",
        [
            "as needed",
            "as required",
            "etc.",
            "and so on",
            "from time to time",
            "where possible",
            "if possible",
            "best efforts",
            "reasonable",
            "timely",
            "promptly",
            "appropriate",
            "adequate",
            "sufficient",
            "user friendly",
            "intuitive",
        ],
        "Nobody can tell when this is met, so it invites a dispute about whether it was delivered.",
        "What measurable threshold, number or date does this wording stand for?",
        "customer",
        "open_question",
    ),
    _rule(
        "marketing_language",
        "Marketing language in a contract",
        "ambiguity",
        "low",
        [
            "world class",
            "cutting edge",
            "state of the art",
            "best in class",
            "second to none",
            "seamless",
            "delightful",
            "stress free",
            "hand in hand",
            "with ease",
        ],
        "A claim that cannot be measured is not a commitment, but it can be read as one.",
        "Can this claim be replaced with something measurable, or removed?",
        "sales",
        "open_question",
    ),
    _rule(
        "open_ended_scope",
        "Open-ended scope",
        "scope_boundary",
        "high",
        [
            "including but not limited to",
            "all future enhancements",
            "any and all",
            "any other third party",
            "any other system",
        ],
        "Scope with no edge cannot be priced, planned or accepted, and grows without a change request.",
        "What exactly is included? List the items, quantities and environments.",
        "sales",
        "starting_risk",
    ),
    _rule(
        "unlimited_effort",
        "Unlimited or open-ended effort",
        "scope_boundary",
        "high",
        [
            "unlimited",
            "until the * is satisfied",
            "until satisfied",
            "inclusive of all revisions",
        ],
        "A fixed price with no limit on revisions or rework turns every disagreement into free work.",
        "How many review and revision cycles are included, and what happens after that?",
        "sales",
        "starting_risk",
    ),
    _rule(
        "continuous_support",
        "Round-the-clock commitments",
        "complexity",
        "high",
        ["24x7", "24/7", "24 x 7", "around the clock", "24 hours a day"],
        "Continuous cover needs a rota, tooling and cost that a normal project team does not have.",
        "Is round-the-clock cover really in scope, for how long, and who staffs it?",
        "delivery",
        "starting_risk",
    ),
]
BUILTIN_IDS = {r["id"] for r in BUILTIN}


def _check_choice(value: object, allowed: tuple[str, ...], name: str, rid: str) -> str:
    if value not in allowed:
        raise RuleError(f"Rule '{rid}': {name} must be one of {', '.join(allowed)}.")
    return str(value)


def _phrases(raw: object, rid: str) -> list[str]:
    phrases = [str(p).strip() for p in raw] if isinstance(raw, list) else []
    phrases = [p for p in phrases if p]
    if not phrases or len(phrases) > 40 or any(not 2 <= len(p) <= 80 for p in phrases):
        raise RuleError(f"Rule '{rid}' needs 1 to 40 phrases of 2 to 80 characters each.")
    return phrases


def validate(rules: list[dict]) -> list[dict]:
    base = {r["id"]: r for r in BUILTIN}
    out: list[dict] = []
    seen: set[str] = set()
    for raw in rules:
        if not isinstance(raw, dict):
            raise RuleError("Each rule must be an object.")
        if raw.get("custom"):
            label = str(raw.get("label", "")).strip()
            if not label or len(label) > 120:
                raise RuleError("A custom rule needs a label of 1 to 120 characters.")
            slug = re.sub(r"[^a-z0-9]+", "-", str(raw.get("id") or label).lower()).strip("-")[:40]
            rid = slug if slug.startswith("custom-") else f"custom-{slug}"
            rule = {
                "id": rid,
                "label": label,
                "category": _check_choice(raw.get("category"), CATEGORIES, "category", rid),
                "severity": _check_choice(raw.get("severity"), SEVERITIES, "severity", rid),
                "phrases": _phrases(raw.get("phrases"), rid),
                "why": str(raw.get("why", "")).strip()[:300] or "Flagged by a rule Michael added.",
                "question": str(raw.get("question", "")).strip()[:300] or "Can this be clarified?",
                "asked_of": _check_choice(
                    raw.get("asked_of", "customer"), ASKED_OF, "asked_of", rid
                ),
                "destination": _check_choice(
                    raw.get("destination", "open_question"), DESTINATIONS, "destination", rid
                ),
                "enabled": bool(raw.get("enabled", True)),
                "custom": True,
            }
        else:
            rid = raw.get("id")
            if rid not in base:
                raise RuleError(f"Unknown built-in rule '{rid}'.")
            rule = {
                **base[rid],
                "severity": _check_choice(raw.get("severity"), SEVERITIES, "severity", rid),
                "phrases": _phrases(raw.get("phrases", base[rid]["phrases"]), rid),
                "enabled": bool(raw.get("enabled", True)),
            }
        if rule["id"] in seen:
            raise RuleError(f"Rule '{rule['id']}' appears twice.")
        seen.add(rule["id"])
        out.append(rule)
    if len([r for r in out if r.get("custom")]) > MAX_CUSTOM:
        raise RuleError(f"At most {MAX_CUSTOM} custom rules.")
    missing = BUILTIN_IDS - seen
    if missing:
        raise RuleError(f"Built-in rules cannot be removed: {', '.join(sorted(missing))}.")
    return out


def defaults() -> list[dict]:
    return [{**r, "enabled": True} for r in BUILTIN]


def phrase_regex(phrase: str) -> re.Pattern:
    """A phrase as a case-insensitive whole-word pattern. Only "*" is special."""
    parts = [r"\w+(?:['’]s)?" if w == "*" else re.escape(w) for w in phrase.split()]
    return re.compile(r"(?<!\w)" + r"\s+".join(parts) + r"(?!\w)", re.IGNORECASE)


class RuleStore:
    def __init__(self, state_dir: str | Path) -> None:
        self.path = Path(state_dir) / "finding_rules.json"
        self._lock = threading.Lock()

    def load(self) -> list[dict]:
        with self._lock:
            try:
                return validate(json.loads(self.path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                return defaults()  # a missing or damaged file never leaves half a rule set

    def save(self, rules: list[dict]) -> list[dict]:
        clean = validate(rules)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(clean, indent=2), encoding="utf-8")
        return clean

    def reset(self) -> list[dict]:
        with self._lock:
            self.path.unlink(missing_ok=True)
        return defaults()
