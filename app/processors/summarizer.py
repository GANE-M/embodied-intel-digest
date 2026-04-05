"""Digest line summaries (v1.4): template default; LLM reserved with safe fallback."""

from __future__ import annotations

import logging
import os
from typing import Any

import requests

from app import constants
from app.models import ProcessedItem
from app.utils.text_utils import safe_truncate

_LOG = logging.getLogger(__name__)


def build_template_summary(item: ProcessedItem) -> str:
    body = (item.raw_content or item.text or "").strip() or item.title
    base = safe_truncate(body, 400)
    tags = ", ".join(item.matched_keywords[:5])
    if tags:
        return f"【要点】涉及：{tags}。{base}"
    return base


def _build_llm_summary_best_effort(item: ProcessedItem) -> str:
    api_key = os.getenv("LLM_API_KEY")
    base_url = os.getenv("LLM_BASE_URL")
    if not api_key or not base_url:
        return build_template_summary(item)
    model = os.getenv("LLM_MODEL", "gpt-4o-mini")
    url = str(base_url).rstrip("/") + "/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    content = (item.raw_content or item.text or "").strip()
    if not content:
        return build_template_summary(item)
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": "你是中文科技编辑。用 2-4 句中文概括以下材料的关键信息，不要编造事实。",
            },
            {"role": "user", "content": safe_truncate(content, 12_000)},
        ],
        "temperature": 0.3,
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        msg = (choice.get("message") or {}).get("content") or ""
        text = str(msg).strip()
        if not text:
            return build_template_summary(item)
        return safe_truncate(text, 800)
    except (requests.RequestException, ValueError, KeyError, TypeError) as exc:
        _LOG.warning("llm summary failed, using template: %s", exc)
        return build_template_summary(item)


def summarize_item_zh(
    item: ProcessedItem,
    summary_mode: str = constants.DEFAULT_SUMMARY_MODE,
) -> str:
    mode = (summary_mode or constants.DEFAULT_SUMMARY_MODE).lower().strip()
    if mode == "llm":
        return _build_llm_summary_best_effort(item)
    return build_template_summary(item)
