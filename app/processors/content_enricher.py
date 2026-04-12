"""Fetch article HTML for shortlist company/news items (v3 upgrade)."""

from __future__ import annotations

import logging

import requests
from bs4 import BeautifulSoup

from app.utils.text_utils import normalize_whitespace, strip_html

_DEFAULT_UA = (
    "Mozilla/5.0 (compatible; EmbodiedIntelDigest/1.0; +https://example.invalid)"
)
_MAX_BYTES = 1_500_000
_MAX_CHARS = 50_000


def should_enrich_for_stage2(item) -> bool:
    """Only enterprise news / blog / site articles — not papers or GitHub releases."""
    st = (item.source_type or "").lower()
    cat = (item.category or "").lower()
    if st not in ("rss", "company"):
        return False
    if cat not in ("company", "media"):
        return False
    return True


def _extract_main_text(html: str) -> str:
    soup = BeautifulSoup(html or "", "html.parser")
    for tag in soup(["script", "style", "noscript", "template"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.body or soup
    text = main.get_text(separator="\n") if main else ""
    text = strip_html(text)
    text = normalize_whitespace(text.replace("\n", " "))
    return text


def enrich_item_article(
    item,
    *,
    timeout_sec: float = 18.0,
    log: logging.Logger | None = None,
) -> None:
    """Best-effort: set ``raw_content`` from page HTML; on failure keep ``text`` only."""
    meta = item.meta if isinstance(item.meta, dict) else {}
    url = (item.url or "").strip()
    if not url or not url.lower().startswith(("http://", "https://")):
        meta["content_fetch_status"] = "skipped_bad_url"
        item.meta = meta
        return

    headers = {"User-Agent": _DEFAULT_UA, "Accept": "text/html,application/xhtml+xml"}
    try:
        resp = requests.get(url, headers=headers, timeout=timeout_sec, stream=True)
        resp.raise_for_status()
        raw_bytes = b""
        for chunk in resp.iter_content(chunk_size=65536):
            if not chunk:
                continue
            raw_bytes += chunk
            if len(raw_bytes) >= _MAX_BYTES:
                break
        charset = resp.encoding or "utf-8"
        html = raw_bytes.decode(charset, errors="replace")
    except requests.RequestException as exc:
        meta["content_fetch_status"] = "fetch_failed"
        meta["content_fetch_error"] = str(exc)[:500]
        item.meta = meta
        if log:
            log.warning("content enrich fetch failed %s: %s", url, exc)
        return

    body = _extract_main_text(html)
    if not body or len(body) < 80:
        meta["content_fetch_status"] = "empty_or_short"
        item.meta = meta
        if log:
            log.info("content enrich: little text from %s", url)
        return

    if len(body) > _MAX_CHARS:
        body = body[:_MAX_CHARS]
        meta["raw_content_truncated"] = True
    item.raw_content = body
    meta["content_fetch_status"] = "ok"
    meta["content_source"] = "html_fetch"
    item.meta = meta
