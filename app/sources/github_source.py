"""GitHub releases only (v3: no commits / issues noise)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

from app.models import RawItem
from app.sources.base import BaseSource
from app.utils.hash_utils import make_dedupe_id
from app.utils.logger import get_logger


def _normalize_repo_configs(repos: list[str | dict[str, Any]]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for r in repos:
        if isinstance(r, str):
            s = r.strip()
            if s:
                out.append({"repo": s, "enabled": True})
        elif isinstance(r, dict) and r.get("enabled", True):
            s = str(r.get("repo", "")).strip()
            if s:
                cfg = dict(r)
                cfg["repo"] = s
                out.append(cfg)
    return out


class GitHubSource(BaseSource):
    source_type = "github"
    source_name = "GitHub"

    def __init__(
        self,
        repos: list[str] | list[dict[str, Any]],
        orgs: list[str] | None = None,
    ) -> None:
        self._repo_cfgs = _normalize_repo_configs(list(repos))
        self._orgs = orgs or []

    def _headers(self) -> dict[str, str]:
        headers = {"Accept": "application/vnd.github+json"}
        token = os.environ.get("GITHUB_TOKEN")
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return headers

    def _fetch_repo_releases(self, repo: str) -> list[dict[str, Any]]:
        owner, _, name = repo.partition("/")
        if not name:
            return []
        api = f"https://api.github.com/repos/{owner}/{name}/releases"
        try:
            r = requests.get(api, headers=self._headers(), params={"per_page": 15}, timeout=30)
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError, TypeError):
            return []
        if not isinstance(data, list):
            return []
        return [x for x in data if isinstance(x, dict)]

    def _repo_meta(self, repo_cfg: dict[str, Any]) -> dict[str, Any]:
        repo = str(repo_cfg["repo"])
        m: dict[str, Any] = {"repo": repo, "repo_name": repo}
        sp = repo_cfg.get("priority")
        if sp is not None:
            try:
                m["source_priority"] = float(sp)
            except (TypeError, ValueError):
                pass
        cat = repo_cfg.get("category")
        if cat is not None and str(cat).strip():
            m["source_category"] = str(cat).strip()
        return m

    def _release_to_raw_item(
        self,
        release: dict[str, Any],
        repo_cfg: dict[str, Any],
    ) -> RawItem:
        repo = str(repo_cfg["repo"])
        tag = str(release.get("tag_name", ""))
        title = str(release.get("name", "") or tag)
        body = str(release.get("body", "") or "")
        url = str(release.get("html_url", ""))
        published = release.get("published_at")
        try:
            published_at = datetime.fromisoformat(str(published).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            published_at = datetime.now(timezone.utc)
        rid = str(release.get("id", url))
        external_id = f"{repo}:release:{rid}"
        dedupe_id = make_dedupe_id("github", external_id, url, title)
        meta = self._repo_meta(repo_cfg)
        meta.update({"tag": tag, "github_kind": "release"})
        return RawItem(
            source_type=self.source_type,
            source_name=self.source_name,
            external_id=external_id,
            dedupe_id=dedupe_id,
            canonical_id=None,
            title=f"[{repo}] {title}",
            text=body,
            raw_content=body or None,
            url=url,
            published_at=published_at,
            updated_at=None,
            authors=[],
            tags=["release"],
            meta=meta,
        )

    def fetch(self, since: datetime) -> list[RawItem]:
        log = get_logger(__name__)
        try:
            since_utc = since.astimezone(timezone.utc) if since.tzinfo else since.replace(tzinfo=timezone.utc)
            out: list[RawItem] = []
            for repo_cfg in self._repo_cfgs:
                repo = str(repo_cfg["repo"])
                for rel in self._fetch_repo_releases(repo):
                    item = self._release_to_raw_item(rel, repo_cfg)
                    pub = item.published_at
                    if pub.tzinfo is None:
                        pub = pub.replace(tzinfo=timezone.utc)
                    if pub >= since_utc:
                        out.append(item)
            return out
        except Exception as exc:  # noqa: BLE001
            log.warning("github fetch failed: %s", exc)
            return []
