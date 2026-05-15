"""Almacenamiento de proyectos en disco — JSON por archivo, ordenados por fecha."""
from __future__ import annotations

import json
import os
from pathlib import Path

_STORE_DIR = Path(os.environ.get("PROJECT_STORE_DIR", "/app/storage"))


def _dir() -> Path:
    _STORE_DIR.mkdir(parents=True, exist_ok=True)
    return _STORE_DIR


def save(run_id: str, data: dict) -> None:
    (_dir() / f"{run_id}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def list_all() -> list[dict]:
    store = _dir()
    projects: list[dict] = []
    for path in sorted(store.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            projects.append({
                "run_id":     raw["run_id"],
                "timestamp":  raw["timestamp"],
                "req_preview": raw.get("req_preview", ""),
                "summary":    raw.get("summary", {}),
            })
        except Exception:
            continue
    return projects


def get(run_id: str) -> dict | None:
    path = _dir() / f"{run_id}.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
