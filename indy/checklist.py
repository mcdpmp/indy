"""The readiness checklist: what "ready" means, editable on the page.

Built-in items cannot be deleted or renamed, but each can be switched off or moved between
blocker and warning. Michael can add his own items, each with keywords Indy looks for in the
documents. Changes are saved in state/checklist.json, so a new image keeps them.
"""

import json
import re
import threading
from pathlib import Path

SEVERITIES = ("blocker", "warning")
MAX_CUSTOM = 30

BUILTIN: list[dict] = [
    {
        "id": "signed_sow",
        "label": "Signed SOW present and actually signed",
        "severity": "blocker",
        "description": "A document filed as sow with a signature and a valid date for every party.",
    },
    {
        "id": "parties_dates",
        "label": "Parties and dates",
        "severity": "blocker",
        "description": "Who the parties are and when the SOW takes effect.",
    },
    {
        "id": "scope_deliverables",
        "label": "Scope and deliverables",
        "severity": "blocker",
        "description": "A scope section and a list of deliverables.",
    },
    {
        "id": "acceptance_criteria",
        "label": "Acceptance criteria",
        "severity": "blocker",
        "description": "Criteria for accepting each deliverable.",
    },
    {
        "id": "commercial_terms",
        "label": "Commercial terms and billing",
        "severity": "blocker",
        "description": "Price or rates, and how and when the customer is invoiced.",
    },
    {
        "id": "contacts",
        "label": "Named customer and delivery contacts",
        "severity": "blocker",
        "description": "Named people on both the customer side and the delivery side.",
    },
    {
        "id": "assumptions",
        "label": "Assumptions",
        "severity": "warning",
        "description": "A list of assumptions the plan rests on.",
    },
    {
        "id": "dependencies",
        "label": "Dependencies",
        "severity": "warning",
        "description": "What the customer or third parties must provide, and by when.",
    },
    {
        "id": "security_compliance",
        "label": "Security or compliance requirements",
        "severity": "warning",
        "description": "Security, privacy or regulatory obligations.",
    },
    {
        "id": "staffing_start",
        "label": "Staffing and start date",
        "severity": "warning",
        "description": "The team or roles, and a start date.",
    },
    {
        "id": "change_control",
        "label": "Change control terms",
        "severity": "warning",
        "description": "How changes to scope, schedule or price are requested and approved.",
    },
    {
        "id": "draft_vs_signed",
        "label": "Differences between Scoper's draft and the signed SOW",
        "severity": "warning",
        "description": "Amounts, dates and deliverables that changed. Skipped when no Scoper draft is readable.",
    },
]
BUILTIN_IDS = {i["id"] for i in BUILTIN}


class ChecklistError(ValueError):
    pass


def _clean_custom(item: dict) -> dict:
    label = str(item.get("label", "")).strip()
    if not label or len(label) > 120:
        raise ChecklistError("A custom item needs a label of 1 to 120 characters.")
    keywords = [str(k).strip() for k in item.get("keywords", []) if str(k).strip()]
    if not keywords or len(keywords) > 20 or any(len(k) > 80 for k in keywords):
        raise ChecklistError(f"'{label}' needs 1 to 20 keywords of at most 80 characters each.")
    slug = re.sub(r"[^a-z0-9]+", "-", str(item.get("id") or label).lower()).strip("-")[:40]
    return {
        "id": slug if slug.startswith("custom-") else f"custom-{slug}",
        "label": label,
        "severity": _severity(item, label),
        "description": str(item.get("description", "")).strip()[:300],
        "keywords": keywords,
        "enabled": bool(item.get("enabled", True)),
        "custom": True,
    }


def _severity(item: dict, name: str) -> str:
    sev = item.get("severity")
    if sev not in SEVERITIES:
        raise ChecklistError(f"'{name}': severity must be blocker or warning.")
    return sev


def validate(items: list[dict]) -> list[dict]:
    """Full list in, cleaned list out. Raises ChecklistError with a plain message."""
    out: list[dict] = []
    seen: set[str] = set()
    base = {i["id"]: i for i in BUILTIN}
    for raw in items:
        if not isinstance(raw, dict):
            raise ChecklistError("Each checklist item must be an object.")
        if raw.get("custom"):
            item = _clean_custom(raw)
        else:
            iid = raw.get("id")
            if iid not in base:
                raise ChecklistError(f"Unknown built-in item '{iid}'.")
            item = {
                **base[iid],
                "severity": _severity(raw, iid),
                "enabled": bool(raw.get("enabled", True)),
            }
        if item["id"] in seen:
            raise ChecklistError(f"Item '{item['id']}' appears twice.")
        seen.add(item["id"])
        out.append(item)
    if len([i for i in out if i.get("custom")]) > MAX_CUSTOM:
        raise ChecklistError(f"At most {MAX_CUSTOM} custom items.")
    missing = BUILTIN_IDS - seen
    if missing:
        raise ChecklistError(f"Built-in items cannot be removed: {', '.join(sorted(missing))}.")
    return out


def defaults() -> list[dict]:
    return [{**i, "enabled": True} for i in BUILTIN]


class ChecklistStore:
    def __init__(self, state_dir: str | Path) -> None:
        self.path = Path(state_dir) / "checklist.json"
        self._lock = threading.Lock()

    def load(self) -> list[dict]:
        with self._lock:
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                return validate(saved)
            except (OSError, ValueError):
                # a missing or damaged file falls back to the defaults, never to a half list
                return defaults()

    def save(self, items: list[dict]) -> list[dict]:
        clean = validate(items)
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text(json.dumps(clean, indent=2), encoding="utf-8")
        return clean

    def reset(self) -> list[dict]:
        with self._lock:
            self.path.unlink(missing_ok=True)
        return defaults()
