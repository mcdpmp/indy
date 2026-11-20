"""Small on-disk state: an audit trail and the latest run per opportunity.

Vera holds the report. The run cache only lets the page show the latest result at once and lets
questions be answered without re-reading everything; losing it costs nothing.
"""

import json
import re
import threading
from datetime import UTC, datetime
from pathlib import Path

_LOCK = threading.Lock()
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


def safe_id(value: str) -> str:
    """Opportunity ids become file names, so anything but a plain id is refused."""
    if not SAFE_ID.match(value or ""):
        raise ValueError("Opportunity id may only use letters, digits, dot, dash and underscore.")
    return value


def _dir(cfg: dict, name: str) -> Path:
    d = Path(cfg["paths"]["state_dir"]) / name
    d.mkdir(parents=True, exist_ok=True)
    return d


def audit(cfg: dict, actor: str, event: str, **fields: object) -> None:
    line = {"at": datetime.now(UTC).isoformat(timespec="seconds"), "actor": actor, "event": event}
    line.update(fields)
    log = Path(cfg["paths"]["state_dir"]) / "audit.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK, log.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")


def save_run(cfg: dict, opportunity_id: str, run: dict) -> None:
    path = _dir(cfg, "runs") / f"{safe_id(opportunity_id)}.json"
    with _LOCK:
        path.write_text(json.dumps(run, indent=2), encoding="utf-8")


def load_run(cfg: dict, opportunity_id: str) -> dict | None:
    path = _dir(cfg, "runs") / f"{safe_id(opportunity_id)}.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
