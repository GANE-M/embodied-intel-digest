"""HTML digest; mirrors plaintext grouping order (v1.4)."""

from __future__ import annotations

import html
import os

from app import constants
from app.models import ProcessedItem
from app.outputs.digest_builder import digest_rank_key, sorted_category_names
from app.outputs.render_context import build_digest_render_context


def _display_group_name(category: str) -> str:
    if category in ("company", "media"):
        return "News"
    if category == "research":
        return "Research"
    if category == "open_source":
        return "Open Source"
    if category == "event":
        return "Events"
    return category.title() if category else "News"


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
    groups: dict[str, list] = {}
    for entry, item in zip(context.entries, ranked, strict=False):
        groups.setdefault(item.category if item.category in constants.CATEGORIES else "media", []).append(entry)
    parts: list[str] = [
        "<html><body>",
        f"<h1>{html.escape(prefix)} — {html.escape(date_str)}</h1>",
    ]
    for category in sorted_category_names(groups.keys()):
        parts.append(f"<h2>{html.escape(_display_group_name(category))}</h2>")
        for entry in groups[category]:
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
