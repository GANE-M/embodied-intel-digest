"""GitHub releases + recent commits (minimal v1.4)."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

from app.models import RawItem
from app.sources.base import BaseSource
from app.utils.hash_utils import make_dedupe_id
from app.utils.logger import get_logger


class GitHubSource(BaseSource):
    source_type = "github"
    source_name = "GitHub"

    def __init__(self, repos: list[str], orgs: list[str] | None = None) -> None:
        self._repos = repos
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

    def _fetch_recent_commits(self, repo: str, since: datetime) -> list[dict[str, Any]]:
        owner, _, name = repo.partition("/")
        if not name:
            return []
        api = f"https://api.github.com/repos/{owner}/{name}/commits"
        since_utc = since.astimezone(timezone.utc) if since.tzinfo else since.replace(tzinfo=timezone.utc)
        since_s = since_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            r = requests.get(
                api,
                headers=self._headers(),
                params={"since": since_s, "per_page": 15},
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
        except (requests.RequestException, ValueError, TypeError):
            return []
        if not isinstance(data, list):
            return []
        return [x for x in data if isinstance(x, dict)]

    def _release_to_raw_item(self, release: dict[str, Any], repo: str) -> RawItem:
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
            meta={"repo": repo, "tag": tag, "github_kind": "release"},
        )

    def _commit_to_raw_item(self, commit: dict[str, Any], repo: str) -> RawItem:
        sha = str(commit.get("sha", ""))[:40]
        cmt = commit.get("commit") if isinstance(commit.get("commit"), dict) else {}
        msg = str((cmt.get("message") or "")).split("\n")[0].strip() or sha[:7]
        url = str(commit.get("html_url", ""))
        date_s = (cmt.get("author") or {}).get("date") if isinstance(cmt.get("author"), dict) else None
        try:
            published_at = datetime.fromisoformat(str(date_s).replace("Z", "+00:00"))
        except (TypeError, ValueError):
            published_at = datetime.now(timezone.utc)
        external_id = f"{repo}:commit:{sha[:7]}"
        dedupe_id = make_dedupe_id("github", external_id, url, msg)
        return RawItem(
            source_type=self.source_type,
            source_name=self.source_name,
            external_id=external_id,
            dedupe_id=dedupe_id,
            canonical_id=None,
            title=f"[{repo}] commit {sha[:7]} — {msg}",
            text=msg,
            raw_content=msg or None,
            url=url or f"https://github.com/{repo}/commit/{sha}",
            published_at=published_at,
            updated_at=None,
            authors=[],
            tags=["commit"],
            meta={"repo": repo, "sha": sha, "github_kind": "commit"},
        )

    def fetch(self, since: datetime) -> list[RawItem]:
        log = get_logger(__name__)
        try:
            since_utc = since.astimezone(timezone.utc) if since.tzinfo else since.replace(tzinfo=timezone.utc)
            out: list[RawItem] = []
            for repo in self._repos:
                for rel in self._fetch_repo_releases(repo):
                    item = self._release_to_raw_item(rel, repo)
                    pub = item.published_at
                    if pub.tzinfo is None:
                        pub = pub.replace(tzinfo=timezone.utc)
                    if pub >= since_utc:
                        out.append(item)
                for c in self._fetch_recent_commits(repo, since):
                    item = self._commit_to_raw_item(c, repo)
                    pub = item.published_at
                    if pub.tzinfo is None:
                        pub = pub.replace(tzinfo=timezone.utc)
                    if pub >= since_utc:
                        out.append(item)
            return out
        except Exception as exc:  # noqa: BLE001
            log.warning("github fetch failed: %s", exc)
            return []
