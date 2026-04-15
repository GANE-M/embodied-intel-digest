"""HTML digest; mirrors plaintext grouping order (v1.4)."""

from __future__ import annotations

import html
import os

from app.models import ProcessedItem
from app.outputs.digest_builder import digest_rank_key
from app.outputs.render_context import build_digest_render_context


def build_html_digest(
    items: list[ProcessedItem],
    date_str: str,
    top_n: int,
) -> str:
    ranked = sorted(items, key=lambda x: digest_rank_key(x), reverse=True)[:top_n]
    context = build_digest_render_context(ranked, date_str, top_n)
    prefix = (
        os.getenv("EMAIL_SUBJECT_PREFIX")
        or os.getenv("EMAIL_SUBJECT")
        or "Embodied Intel Digest"
    )
    parts: list[str] = [
        "<html><body>",
        f"<h1>{html.escape(prefix)} — {html.escape(date_str)}</h1>",
    ]
    for entry in context.entries:
        title = html.escape(entry.title)
        if entry.is_update:
            title += " [更新]"
        parts.append("<div style='margin:0 0 16px 0'>")
        parts.append(f"<div>Title: {title}</div>")
        parts.append(f"<div>URL: <a href=\"{html.escape(entry.url, quote=True)}\">{html.escape(entry.url)}</a></div>")
        parts.append(f"<div>Tag: {html.escape(entry.tag)}</div>")
        parts.append(f"<div>EN: {html.escape(entry.summary_en)}</div>")
        parts.append(f"<div>ZH: {html.escape(entry.summary_zh)}</div>")
        parts.append("</div>")
    parts.append("</body></html>")
    return "\n".join(parts)
