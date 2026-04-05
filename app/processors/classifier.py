"""Map RawItem → category using constants.CATEGORIES only (v1.4)."""

from __future__ import annotations

from app import constants
from app.models import RawItem

_MEDIA = "media"
_RESEARCH = "research"
_OPEN = "open_source"
_COMPANY = "company"
_EVENT = "event"


def classify_item(item: RawItem) -> str:
    st = (item.source_type or "").lower()
    if st in ("arxiv", "openalex"):
        cat = _RESEARCH
    elif st == "github":
        cat = _OPEN
    elif st == "company":
        cat = _COMPANY
    elif st == "event":
        cat = _EVENT
    elif st == "rss":
        hint = (item.meta or {}).get("feed_category") or (item.tags[0] if item.tags else "")
        c = str(hint).lower()
        if c in ("company", "corp"):
            cat = _COMPANY
        elif c in ("event", "events"):
            cat = _EVENT
        elif c in ("code", "github", "open_source"):
            cat = _OPEN
        else:
            cat = _MEDIA
    else:
        cat = _MEDIA
    if cat not in constants.CATEGORIES:
        return _MEDIA
    return cat
