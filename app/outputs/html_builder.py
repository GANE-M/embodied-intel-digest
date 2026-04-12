"""HTML digest; mirrors plaintext grouping order (v1.4)."""

from __future__ import annotations

import html
import os

from app.models import ProcessedItem
from app.outputs.digest_builder import digest_rank_key, group_items, sorted_category_names


def build_html_digest(
    items: list[ProcessedItem],
    date_str: str,
    top_n: int,
) -> str:
    ranked = sorted(items, key=lambda x: digest_rank_key(x), reverse=True)[:top_n]
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
            note = ""
            if it.llm_judgement and it.llm_judgement.reason:
                note = "<br/><span style=\"font-size:0.85em;opacity:0.85\">" + html.escape(
                    it.llm_judgement.reason[:400],
                ) + "</span>"
            parts.append(
                f'<li><a href="{url}">{title}</a><br/><span style="font-size:0.9em">{summ}</span>{note}</li>',
            )
        parts.append("</ul>")
    parts.append("</body></html>")
    return "\n".join(parts)
