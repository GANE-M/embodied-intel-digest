"""Company sites without stable RSS (v1.4). Config-driven hook; default scrape returns []."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.models import RawItem
from app.sources.base import BaseSource
from app.utils.hash_utils import make_dedupe_id
from app.utils.logger import get_logger


class CompanySiteSource(BaseSource):
    source_type = "company"
    source_name = "CompanySite"

    def __init__(self, sites: list[dict[str, Any]]) -> None:
        self._sites = sites

    def _page_to_raw_item(self, page: dict[str, Any], site: dict[str, Any]) -> RawItem:
        title = str(page.get("title", ""))
        url = str(page.get("url", site.get("url", "")))
        text = str(page.get("text", ""))
        published_at = datetime.now(timezone.utc)
        if page.get("published_at"):
            try:
                published_at = datetime.fromisoformat(str(page["published_at"]).replace("Z", "+00:00"))
            except (TypeError, ValueError):
                pass
        site_name = str(site.get("name", self.source_name))
        ext = f"{url}:{title}"[:1024]
        dedupe_id = make_dedupe_id("company", ext, url, title)
        return RawItem(
            source_type=self.source_type,
            source_name=site_name,
            external_id=ext,
            dedupe_id=dedupe_id,
            canonical_id=None,
            title=title,
            text=text,
            raw_content=text or None,
            url=url,
            published_at=published_at,
            updated_at=None,
            authors=list(page.get("authors") or []),
            tags=list(page.get("tags") or []),
            meta={"site": site_name, **(page.get("meta") or {})},
        )

    def _scrape_site(self, site: dict[str, Any], since: datetime) -> list[RawItem]:
        _ = site, since
        return []

    def fetch(self, since: datetime) -> list[RawItem]:
        log = get_logger(__name__)
        try:
            out: list[RawItem] = []
            for site in self._sites:
                if not site.get("enabled", True):
                    continue
                out.extend(self._scrape_site(site, since))
            return out
        except Exception as exc:  # noqa: BLE001
            log.warning("company site fetch failed: %s", exc)
            return []
