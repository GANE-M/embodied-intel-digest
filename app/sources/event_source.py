"""Conference / event sources (v1.4)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import RawItem
from app.sources.base import BaseSource
from app.utils.hash_utils import make_dedupe_id
from app.utils.logger import get_logger
from app.utils.time_utils import parse_iso_datetime


class EventSource(BaseSource):
    source_type = "event"
    source_name = "Event"

    def __init__(self, feeds: list[dict[str, Any]]) -> None:
        self._feeds = feeds

    def _event_to_raw_item(self, event: dict[str, Any], source: dict[str, Any]) -> RawItem:
        title = str(event.get("title", source.get("name", "event")))
        url = str(event.get("url", source.get("url", "")))
        text = str(event.get("description", ""))
        published_at = datetime.now(timezone.utc)
        if event.get("published_at"):
            try:
                published_at = parse_iso_datetime(str(event["published_at"]))
            except (TypeError, ValueError, OverflowError):
                pass
        ext = f"{url}:{title}"[:1024]
        dedupe_id = make_dedupe_id(
            str(source.get("source_type", self.source_type)),
            ext,
            url,
            title,
        )
        return RawItem(
            source_type=str(source.get("source_type", self.source_type)),
            source_name=str(source.get("name", self.source_name)),
            external_id=ext,
            dedupe_id=dedupe_id,
            canonical_id=None,
            title=title,
            text=text,
            raw_content=text or None,
            url=url,
            published_at=published_at,
            updated_at=None,
            authors=[],
            tags=["event"],
            meta=dict(source),
        )

    def fetch(self, since: datetime) -> list[RawItem]:
        log = get_logger(__name__)
        try:
            _ = since
            out: list[RawItem] = []
            for src in self._feeds:
                if not src.get("enabled", True):
                    continue
                evt = {
                    "title": src.get("name", ""),
                    "url": src.get("url", ""),
                    "description": src.get("description", ""),
                    "published_at": src.get("published_at"),
                }
                out.append(self._event_to_raw_item(evt, src))
            return out
        except Exception as exc:  # noqa: BLE001
            log.warning("event fetch failed: %s", exc)
            return []
