"""Low-level text helpers (v1.4). Do not embed RawItem / ProcessedItem logic here."""

from __future__ import annotations

import re
import unicodedata
from html import unescape

_ws_re = re.compile(r"\s+")


def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFKC", text or "")


def normalize_whitespace(text: str) -> str:
    return _ws_re.sub(" ", (text or "").strip()).strip()


def strip_html(text: str) -> str:
    without_tags = re.sub(r"<[^>]+>", " ", text or "")
    return normalize_whitespace(unescape(without_tags))


def safe_truncate(text: str, max_len: int) -> str:
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3].rstrip() + "..."
