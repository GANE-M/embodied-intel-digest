"""Abstract store (v1.4 minimal contract for DB-ready backends)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from app.models import ProcessedItem, RunMetadata


class BaseStore(ABC):
    @abstractmethod
    def load_seen_ids(self) -> set[str]:
        """Return persisted dedupe ids."""

    @abstractmethod
    def has_seen(self, dedupe_id: str) -> bool:
        """Whether ``dedupe_id`` was already marked seen."""

    @abstractmethod
    def mark_seen(self, items: Iterable[ProcessedItem]) -> None:
        """Persist new seen ids from processed items."""

    @abstractmethod
    def save_run_metadata(self, run_metadata: RunMetadata) -> None:
        """Append or store a run record (pass the full ``RunMetadata`` object)."""
