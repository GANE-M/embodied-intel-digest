"""Fetch papers from the arXiv Atom API (v1.3)."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import feedparser

from app.models import RawItem
from app.sources.base import BaseSource
from app.utils.hash_utils import make_dedupe_id
from app.utils.logger import get_logger


def _parse_time(struct_time: Any) -> datetime | None:
    if not struct_time:
        return None
    return datetime(*struct_time[:6], tzinfo=timezone.utc)


def _arxiv_canonical(link: str, aid: str) -> str | None:
    for s in (link or "", aid or ""):
        m = re.search(r"arxiv\.org/abs/([^?#]+)", s, flags=re.IGNORECASE)
        if m:
            return re.sub(r"v\d+$", "", m.group(1).strip())
    if aid:
        tail = aid.rstrip("/").split("/")[-1]
        return re.sub(r"v\d+$", "", tail)
    return None


class ArxivSource(BaseSource):
    source_type = "arxiv"
    source_name = "arXiv"

    def __init__(self, categories: list[str], keywords: list[str]) -> None:
        self._categories = categories
        self._keywords = keywords

    def _build_query_url(self) -> str:
        parts: list[str] = []
        for cat in self._categories:
            parts.append(f"cat:{cat}")
        for kw in self._keywords:
            parts.append(f"all:{quote(kw)}")
        q = "+AND+".join(parts) if parts else "all:robotics"
        return f"http://export.arxiv.org/api/query?search_query={q}&sortBy=submittedDate&max_results=50"

    def _query_arxiv(self) -> list[Any]:
        url = self._build_query_url()
        parsed = feedparser.parse(url)
        return list(getattr(parsed, "entries", []) or [])

    def _entry_to_raw_item(self, entry: Any) -> RawItem:
        title = (getattr(entry, "title", "") or "").strip()
        summary = (getattr(entry, "summary", "") or "").strip()
        link = ""
        if getattr(entry, "link", None):
            link = entry.link
        elif getattr(entry, "links", None):
            link = entry.links[0].get("href", "") if entry.links else ""
        published = _parse_time(getattr(entry, "published_parsed", None)) or _parse_time(
            getattr(entry, "updated_parsed", None),
        ) or datetime.now(timezone.utc)
        updated = _parse_time(getattr(entry, "updated_parsed", None))
        aid = str(getattr(entry, "id", "") or link or title)
        canonical = _arxiv_canonical(link, aid)
        external_id = aid[:1024]
        dedupe_id = make_dedupe_id("arxiv", canonical or external_id, link, title)
        authors: list[str] = []
        for a in getattr(entry, "authors", []) or []:
            if isinstance(a, dict) and a.get("name"):
                authors.append(str(a["name"]))
        tags = [t.get("term", "") for t in getattr(entry, "tags", []) or [] if isinstance(t, dict)]
        arxiv_version: int | None = None
        vm = re.search(r"v(\d+)(?:\b|/|$)", f"{link} {aid}")
        if vm:
            arxiv_version = int(vm.group(1))
        return RawItem(
            source_type=self.source_type,
            source_name=self.source_name,
            external_id=external_id,
            dedupe_id=dedupe_id,
            canonical_id=canonical,
            title=title,
            text=summary,
            raw_content=summary or None,
            url=link,
            published_at=published,
            updated_at=updated,
            authors=authors,
            tags=tags,
            meta={"arxiv_id": aid, "arxiv_version": arxiv_version},
        )

    def fetch(self, since: datetime) -> list[RawItem]:
        log = get_logger(__name__)
        try:
            since_utc = since.astimezone(timezone.utc) if since.tzinfo else since.replace(tzinfo=timezone.utc)
            items: list[RawItem] = []
            for entry in self._query_arxiv():
                raw = self._entry_to_raw_item(entry)
                pub = raw.published_at
                if pub.tzinfo is None:
                    pub = pub.replace(tzinfo=timezone.utc)
                if pub >= since_utc:
                    items.append(raw)
            return items
        except Exception as exc:  # noqa: BLE001
            log.warning("arxiv fetch failed: %s", exc)
            return []
