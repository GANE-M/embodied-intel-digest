"""In-memory BaseStore for tests and quick runs (supplemental v1.1).

State lives only in process memory: not suitable for persisting dedupe across
GitHub Actions runners without external storage.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timezone

from app.models import ProcessedItem, RunMetadata
from app.storage.base import BaseStore


class MemoryStore(BaseStore):
    def __init__(self) -> None:
        self._ids: set[str] = set()
        self._first_seen: dict[str, datetime] = {}
        self._runs: list[RunMetadata] = []

    def load_seen_ids(self) -> set[str]:
        return set(self._ids)

    def has_seen(self, dedupe_id: str) -> bool:
        return dedupe_id in self._ids

    def get_first_seen_at(self, dedupe_id: str) -> datetime | None:
        """First time this dedupe id was recorded in this in-memory store."""
        return self._first_seen.get(dedupe_id)

    def mark_seen(self, items: Iterable[ProcessedItem]) -> None:
        now = datetime.now(timezone.utc)
        for it in items:
            if not it.dedupe_id:
                continue
            if it.dedupe_id not in self._first_seen:
                self._first_seen[it.dedupe_id] = now
            self._ids.add(it.dedupe_id)

    def save_run_metadata(self, run_metadata: RunMetadata) -> None:
        self._runs.append(run_metadata)
