"""Abstract content source (v1.3)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime

from app.models import RawItem


class BaseSource(ABC):
    source_type: str
    source_name: str

    @abstractmethod
    def fetch(self, since: datetime) -> list[RawItem]:
        """Return standardized RawItems with ``since`` as the lower bound.

        Implementations should swallow internal errors and return partial/empty lists.
        """
