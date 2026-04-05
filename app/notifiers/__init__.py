"""SMTP and future notification backends."""

from app.notifiers.base import BaseNotifier
from app.notifiers.email_sender import EmailNotifier

__all__ = ["BaseNotifier", "EmailNotifier"]
