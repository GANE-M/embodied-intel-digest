"""OpenAlex metadata graph (v1.4). Complements arXiv; does not duplicate arXiv version semantics."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

from app.models import RawItem
from app.sources.base import BaseSource
from app.utils.hash_utils import make_dedupe_id
from app.utils.logger import get_logger


class OpenAlexSource(BaseSource):
    source_type = "openalex"
    source_name = "OpenAlex"

    def __init__(
        self,
        keywords: list[str],
        institutions: list[str] | None = None,
    ) -> None:
        self._keywords = keywords
        self._institutions = institutions or []

    def _work_to_raw_item(self, work: dict[str, Any]) -> RawItem:
        wid = str(work.get("id", ""))
        title = (work.get("title") or work.get("display_name") or "").strip()
        abstract = work.get("abstract_inverted_index")
        text = ""
        if isinstance(abstract, dict):
            text = " ".join(abstract.keys())
        elif isinstance(work.get("abstract"), str):
            text = work["abstract"]
        url = wid
        if work.get("doi"):
            url = f"https://doi.org/{work['doi']}"
        pub_date = work.get("publication_date") or ""
        try:
            published_at = datetime.fromisoformat(pub_date).replace(tzinfo=timezone.utc)
        except (TypeError, ValueError):
            published_at = datetime.now(timezone.utc)
        authors: list[str] = []
        authorships = work.get("authorships") or []
        for a in authorships[:20]:
            inst = a.get("author", {}) if isinstance(a, dict) else {}
            name = inst.get("display_name") if isinstance(inst, dict) else None
            if name:
                authors.append(str(name))
        dedupe_id = make_dedupe_id("openalex", wid, url, title or wid)
        return RawItem(
            source_type=self.source_type,
            source_name=self.source_name,
            external_id=wid[:1024],
            dedupe_id=dedupe_id,
            canonical_id=wid or None,
            title=title or "(untitled)",
            text=text,
            raw_content=text or None,
            url=url,
            published_at=published_at,
            updated_at=None,
            authors=authors,
            tags=[
                str(t.get("display_name", ""))
                for t in (work.get("concepts") or [])[:5]
                if isinstance(t, dict) and t.get("display_name")
            ],
            meta={"openalex_id": wid, "doi": work.get("doi")},
        )

    def fetch(self, since: datetime) -> list[RawItem]:
        log = get_logger(__name__)
        if not self._keywords:
            return []
        try:
            since_utc = since.astimezone(timezone.utc) if since.tzinfo else since.replace(tzinfo=timezone.utc)
            since_day = since_utc.date().isoformat()
            q = " ".join(self._keywords)
            url = "https://api.openalex.org/works"
            filter_parts = [f"from_publication_date:{since_day}"]
            for inst in self._institutions:
                filter_parts.append(f"institutions.id:{inst}")
            params: dict[str, str | int] = {
                "search": q,
                "per_page": 25,
                "filter": ",".join(filter_parts),
            }
            resp = requests.get(url, params=params, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            results: list[RawItem] = []
            for w in data.get("results") or []:
                if not isinstance(w, dict):
                    continue
                item = self._work_to_raw_item(w)
                if item.published_at >= since_utc:
                    results.append(item)
            return results
        except Exception as exc:  # noqa: BLE001
            log.warning("openalex fetch failed: %s", exc)
            return []
