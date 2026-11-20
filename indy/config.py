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
