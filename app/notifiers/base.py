"""Abstract notification channel."""

from __future__ import annotations

from abc import ABC, abstractmethod


class BaseNotifier(ABC):
    @abstractmethod
    def send(self, subject: str, body_text: str, body_html: str | None = None) -> None:
        """Deliver a notification payload."""
