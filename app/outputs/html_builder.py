"""HTML digest; mirrors plaintext grouping order (v1.4)."""

from __future__ import annotations

import html
import os

from app.models import ProcessedItem
from app.outputs.digest_builder import group_items, sorted_category_names


def build_html_digest(
    items: list[ProcessedItem],
    date_str: str,
    top_n: int,
) -> str:
    ranked = sorted(items, key=lambda x: x.final_score, reverse=True)[:top_n]
    grouped = group_items(ranked)
    prefix = (
        os.getenv("EMAIL_SUBJECT_PREFIX")
        or os.getenv("EMAIL_SUBJECT")
        or "Embodied Intel Digest"
    )
    parts: list[str] = [
        "<html><body>",
        f"<h1>{html.escape(prefix)} — {html.escape(date_str)}</h1>",
        f"<p>Top {len(ranked)} items.</p>",
    ]
    for cat in sorted_category_names(grouped.keys()):
        parts.append(f"<h2>{html.escape(cat)}</h2><ul>")
        for it in grouped[cat]:
            title = html.escape(it.title)
            if it.is_update:
                title += " [更新]"
            url = html.escape(it.url, quote=True)
            summ = html.escape(it.summary_zh[:500])
            parts.append(
                f'<li><a href="{url}">{title}</a><br/><span style="font-size:0.9em">{summ}</span></li>',
            )
        parts.append("</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)
