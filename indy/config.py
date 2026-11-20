"""Configuration: built-in defaults, overlaid by config.yaml, overlaid by a few env vars.

No credentials here. The Vera key is read from VERA_AGENT_KEY by the Vera client.
"""

import copy
import os
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent

DEFAULTS: dict = {
    "llm": {
        "ollama_endpoint": "http://localhost:11434",
        "extraction_model": "llama3.1:8b",
        "generation_model": "qwen3:14b",
        "timeout_seconds": 240,
        "num_ctx": 8192,
        "keep_alive": "2m",
        "think": False,
        "pause_seconds": 5,
    },
    "vera": {
        "sow_category": "sow",
        "rfp_category": "rfp",
        "other_category": "other",
        "scoper_agent": "scoper",
    },
    "readiness": {
        # a deliverables table counts as "partly covered" from this share of rows filled in;
        # below it the item is treated as missing
        "partial_min_share": 0.5,
        "min_assumptions": 5,
        "min_section_words": 40,
    },
    "findings": {
        # what a STATED finding of each severity does to the verdict: none, conditions or not_ready.
        # Inferred findings never change the verdict, because nothing in a document backs them.
        "verdict_effect": {"high": "conditions", "medium": "none", "low": "none"},
        # severity of the finding made when a checklist item is partial or missing
        "gap_severity": {
            "change_control": {"missing": "high", "partial": "medium"},
            "assumptions": {"missing": "high", "partial": "medium"},
            "dependencies": {"missing": "medium", "partial": "low"},
            "security_compliance": {"missing": "medium", "partial": "low"},
        },
        "max_per_rule": 3,
        "max_model_findings": 12,
    },
    "paths": {"state_dir": "./state"},
}


def _merge(base: dict, over: dict) -> dict:
    for key, val in over.items():
        if isinstance(val, dict) and isinstance(base.get(key), dict):
            _merge(base[key], val)
        else:
            base[key] = val
    return base


def validate(cfg: dict) -> None:
    llm = cfg["llm"]
    if not str(llm["ollama_endpoint"]).startswith(("http://", "https://")):
        raise ValueError("llm.ollama_endpoint must be an http or https URL")
    for key in ("timeout_seconds", "num_ctx"):
        if not isinstance(llm[key], int | float) or llm[key] < 1:
            raise ValueError(f"llm.{key} must be at least 1")
    r = cfg["readiness"]
    if not 0 < r["partial_min_share"] <= 1:
        raise ValueError("readiness.partial_min_share must be above 0 and at most 1")
    for key in ("min_assumptions", "min_section_words"):
        if not isinstance(r[key], int) or r[key] < 1:
            raise ValueError(f"readiness.{key} must be a whole number of at least 1")
    f = cfg["findings"]
    for sev, effect in f["verdict_effect"].items():
        if sev not in ("high", "medium", "low") or effect not in (
            "none",
            "conditions",
            "not_ready",
        ):
            raise ValueError(
                "findings.verdict_effect maps high, medium, low to none, conditions or not_ready"
            )
    for key in ("max_per_rule", "max_model_findings"):
        if not isinstance(f[key], int) or f[key] < 1:
            raise ValueError(f"findings.{key} must be a whole number of at least 1")
    for item, levels in f["gap_severity"].items():
        if any(v not in ("high", "medium", "low") for v in levels.values()):
            raise ValueError(f"findings.gap_severity.{item} must use high, medium or low")
    if not isinstance(llm["pause_seconds"], int | float) or llm["pause_seconds"] < 0:
        raise ValueError("llm.pause_seconds must be zero or more")


def load_config(path: str | Path | None = None) -> dict:
    cfg = copy.deepcopy(DEFAULTS)
    path = Path(path or os.environ.get("INDY_CONFIG") or ROOT / "config.yaml")
    if path.exists():
        _merge(cfg, yaml.safe_load(path.read_text(encoding="utf-8")) or {})
    if os.environ.get("INDY_OLLAMA_ENDPOINT"):
        cfg["llm"]["ollama_endpoint"] = os.environ["INDY_OLLAMA_ENDPOINT"]
    state = Path(cfg["paths"]["state_dir"])
    cfg["paths"]["state_dir"] = str(state if state.is_absolute() else ROOT / state)
    validate(cfg)
    return cfg
