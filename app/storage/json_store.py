"""Minimal JSON persistence for seen ids and run metadata (v1.4)."""

from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.models import ProcessedItem, RunMetadata
from app.storage.base import BaseStore


class JsonStore(BaseStore):
    def __init__(self, state_dir: Path) -> None:
        self._state_dir = state_dir
        self._path = state_dir / "digest_state.json"
        self._max_runs = 30

    def _load(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {"dedupe_ids": [], "first_seen_at": {}, "runs": []}
        with self._path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {"dedupe_ids": [], "first_seen_at": {}, "runs": []}
        data.setdefault("dedupe_ids", [])
        data.setdefault("first_seen_at", {})
        data.setdefault("runs", [])
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self._state_dir.mkdir(parents=True, exist_ok=True)
        with self._path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def load_seen_ids(self) -> set[str]:
        data = self._load()
        ids = data.get("dedupe_ids")
        if isinstance(ids, list):
            return {str(x) for x in ids}
        return set()

    def has_seen(self, dedupe_id: str) -> bool:
        return dedupe_id in self.load_seen_ids()

    def mark_seen(self, items: Iterable[ProcessedItem]) -> None:
        data = self._load()
        ids = set(str(x) for x in data.get("dedupe_ids", []) if x is not None)
        fs = data.get("first_seen_at")
        if not isinstance(fs, dict):
            fs = {}
        now = datetime.now(timezone.utc).isoformat()
        for it in items:
            did = (it.dedupe_id or "").strip()
            if not did:
                continue
            if did not in fs:
                fs[did] = now
            ids.add(did)
        data["dedupe_ids"] = sorted(ids)
        data["first_seen_at"] = fs
        self._save(data)

    def save_run_metadata(self, run_metadata: RunMetadata) -> None:
        data = self._load()
        runs = data.get("runs")
        if not isinstance(runs, list):
            runs = []
        row = {
            "run_id": run_metadata.run_id,
            "started_at": run_metadata.started_at.isoformat(),
            "finished_at": run_metadata.finished_at.isoformat(),
            "status": run_metadata.status,
            "item_count": run_metadata.item_count,
            "error_count": run_metadata.error_count,
        }
        runs.append(row)
        data["runs"] = runs[-self._max_runs :]
        self._save(data)
