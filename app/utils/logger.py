"""Stdout logging setup (supplemental v1.1)."""

from __future__ import annotations

import logging
import os

_FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def setup_logger(level: str = "INFO") -> None:
    """Attach a single StreamHandler to the root logger if none exist; set root level."""
    root = logging.getLogger()
    lvl = getattr(logging, (level or "INFO").upper(), logging.INFO)
    root.setLevel(lvl)
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter(_FORMAT))
    root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Return a named logger; ensures root stdout handler exists exactly once."""
    if not logging.getLogger().handlers:
        setup_logger(os.getenv("LOG_LEVEL", "INFO"))
    log = logging.getLogger(name)
    log.setLevel(getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))
    return log
