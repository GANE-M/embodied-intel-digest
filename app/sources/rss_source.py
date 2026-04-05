"""Unified RSS/Atom ingestion (v1.3)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import feedparser

from app.models import RawItem
from app.sources.base import BaseSource
from app.utils.hash_utils import make_dedupe_id
from app.utils.logger import get_logger


def _entry_published(entry: Any) -> datetime:
    raw = getattr(entry, "published_parsed", None) or getattr(entry, "updated_parsed", None)
    if raw:
        return datetime(*raw[:6], tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def _entry_updated(entry: Any) -> datetime | None:
    raw = getattr(entry, "updated_parsed", None)
    if raw:
        return datetime(*raw[:6], tzinfo=timezone.utc)
    return None


class RSSSource(BaseSource):
    source_type = "rss"
    source_name = "RSS"

    def __init__(self, feeds: list[dict[str, Any]]) -> None:
        self._feeds = feeds

    def _entry_to_raw_item(self, entry: Any, feed: dict[str, Any]) -> RawItem:
        title = (getattr(entry, "title", "") or "").strip()
        summary = (getattr(entry, "summary", "") or getattr(entry, "description", "") or "").strip()
        link = getattr(entry, "link", "") or ""
        if not link and getattr(entry, "links", None):
            link = entry.links[0].get("href", "") if entry.links else ""
        published = _entry_published(entry)
        updated = _entry_updated(entry)
        name = str(feed.get("name", "feed"))
        ext_id = str(getattr(entry, "id", "") or link or title)[:1024]
        dedupe_id = make_dedupe_id("rss", ext_id, link, title)
        return RawItem(
            source_type=self.source_type,
            source_name=name,
            external_id=ext_id,
            dedupe_id=dedupe_id,
            canonical_id=None,
            title=title,
            text=summary,
            raw_content=None,
            url=link,
            published_at=published,
            updated_at=updated,
            authors=[
                str(a.get("name", ""))
                for a in getattr(entry, "authors", []) or []
                if isinstance(a, dict)
            ],
            tags=[str(feed.get("category", ""))] if feed.get("category") else [],
            meta={
                "feed_url": feed.get("url", ""),
                "feed_category": feed.get("category", ""),
            },
        )

    def _parse_feed(self, feed: dict[str, Any], since: datetime) -> list[RawItem]:
        if not feed.get("enabled", True):
            return []
        url = feed.get("url")
        if not url:
            return []
        since_utc = since.astimezone(timezone.utc) if since.tzinfo else since.replace(tzinfo=timezone.utc)
        parsed = feedparser.parse(str(url))
        out: list[RawItem] = []
        for entry in getattr(parsed, "entries", []) or []:
            raw = self._entry_to_raw_item(entry, feed)
            pub = raw.published_at
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
            if pub >= since_utc:
                out.append(raw)
        return out

    def fetch(self, since: datetime) -> list[RawItem]:
        log = get_logger(__name__)
        try:
            items: list[RawItem] = []
            for feed in self._feeds:
                items.extend(self._parse_feed(feed, since))
            return items
        except Exception as exc:  # noqa: BLE001
            log.warning("rss fetch failed: %s", exc)
            return []
