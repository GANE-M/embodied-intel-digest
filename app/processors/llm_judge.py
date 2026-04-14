"""Stage-2 LLM structured judgement via OpenAI-compatible HTTP (v3 upgrade)."""

from __future__ import annotations

import json
import os
import re
from typing import Any

import requests

from app.models import JudgementResult, ProcessedItem
from app.utils.text_utils import safe_truncate


def _chat_completions_url(base_url: str) -> str:
    return str(base_url).rstrip("/") + "/v1/chat/completions"


def _extract_possible_json_text(text: str) -> str | None:
    s = (text or "").strip()
    if not s:
        return None

    m = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", s, flags=re.IGNORECASE)
    if m:
        body = (m.group(1) or "").strip()
        if body:
            return body

    start = s.find("{")
    if start >= 0:
        depth = 0
        for i in range(start, len(s)):
            ch = s[i]
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return s[start : i + 1]
    return None


def _parse_judgement_payload(text: str) -> JudgementResult | None:
    s = (text or "").strip()
    if not s:
        return None
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        candidate = _extract_possible_json_text(s)
        if not candidate:
            return None
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    try:
        keep = bool(data.get("keep"))
        imp = float(data.get("importance_score", 0.0))
        nov = float(data.get("novelty_score", 0.0))
        br = float(data.get("brand_relevance_score", 0.0))
        reason = str(data.get("reason", "") or "").strip() or "(no reason)"
        ctype = str(data.get("content_type", "") or "").strip() or "unknown"
    except (TypeError, ValueError):
        return None
    return JudgementResult(
        keep=keep,
        importance_score=min(1.0, max(0.0, imp)),
        novelty_score=min(1.0, max(0.0, nov)),
        brand_relevance_score=min(1.0, max(0.0, br)),
        reason=reason,
        content_type=ctype,
    )


def _normalize_base_url(base_url: str) -> str:
    s = str(base_url or "").strip().rstrip("/")
    if s.endswith("/v1"):
        s = s[:-3]
    return s.rstrip("/")


def judge_item(
    item: ProcessedItem,
    *,
    api_key: str,
    base_url: str,
    model: str | None = None,
    timeout_sec: float = 75.0,
    max_tokens: int = 768,
) -> JudgementResult | None:
    """Return structured judgement or None on failure / empty input."""
    body = (item.raw_content or item.text or "").strip()
    if not body:
        return None
    mdl = (model or os.getenv("LLM_MODEL") or "deepseek-chat").strip()
    url = _chat_completions_url(_normalize_base_url(base_url))
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    schema_hint = (
        'Reply with a single JSON object only, keys: keep (boolean), '
        "importance_score (0-1), novelty_score (0-1), brand_relevance_score (0-1), "
        'reason (short English), content_type (one of: official_company_news, '
        "research_paper, open_source_release, media_article, event, other)."
    )
    user = (
        f"Title: {item.title}\nURL: {item.url}\n"
        f"Category: {item.category}\nSource: {item.source_type} / {item.source_name}\n\n"
        f"Text:\n{safe_truncate(body, 12_000)}"
    )
    payload: dict[str, Any] = {
        "model": mdl,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You filter high-signal embodied-AI intelligence for a brand team daily digest. "
                    + schema_hint
                ),
            },
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    payload_json = dict(payload)
    payload_json["response_format"] = {"type": "json_object"}

    def _post(p: dict[str, Any]) -> requests.Response:
        return requests.post(url, headers=headers, json=p, timeout=timeout_sec)

    try:
        resp = _post(payload_json)
        if resp.status_code >= 400:
            resp = _post(payload)
        resp.raise_for_status()
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        msg = (choice.get("message") or {}).get("content") or ""
        return _parse_judgement_payload(str(msg))
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return None


def _parse_summary_payload(text: str) -> tuple[str, str] | None:
    s = (text or "").strip()
    if not s:
        return None
    try:
        data = json.loads(s)
    except json.JSONDecodeError:
        candidate = _extract_possible_json_text(s)
        if not candidate:
            return None
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    en = str(data.get("summary_en", "") or "").strip()
    zh = str(data.get("summary_zh", "") or "").strip()
    if not en and not zh:
        return None
    return en, zh


def build_deepseek_bilingual_summary(
    item: ProcessedItem,
    *,
    api_key: str,
    base_url: str,
    model: str = "deepseek-chat",
    timeout_sec: float = 75.0,
    max_tokens: int = 768,
) -> tuple[str, str]:
    """Best-effort bilingual summary for final to_send items."""
    body = (item.raw_content or item.text or "").strip()
    if not body:
        return "", ""

    url = _chat_completions_url(_normalize_base_url(base_url))
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    source_context = (
        f"Title: {item.title}\nSource: {item.source_name} ({item.source_type})\n"
        f"Category: {item.category}\nURL: {item.url}\n"
    )
    user = (
        source_context
        + "\nWrite an English summary in 150-200 words for a business audience. "
        + "Do not use bullet points. Then provide a faithful Chinese translation. "
        + "Return JSON with keys summary_en and summary_zh only.\n\n"
        + f"Text:\n{safe_truncate(body, 12000)}"
    )
    payload: dict[str, Any] = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a bilingual technology editor for a brand team's digest. "
                    "Summarize accurately and conservatively."
                ),
            },
            {"role": "user", "content": user},
        ],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }
    payload_json = dict(payload)
    payload_json["response_format"] = {"type": "json_object"}

    def _post(p: dict[str, Any]) -> requests.Response:
        return requests.post(url, headers=headers, json=p, timeout=timeout_sec)

    try:
        resp = _post(payload_json)
        if resp.status_code >= 400:
            resp = _post(payload)
        resp.raise_for_status()
        data = resp.json()
        choice = (data.get("choices") or [{}])[0]
        msg = (choice.get("message") or {}).get("content") or ""
        parsed = _parse_summary_payload(str(msg))
        if parsed:
            return parsed
        if payload_json is not payload:
            return "", ""
        return "", ""
    except (requests.RequestException, ValueError, KeyError, TypeError):
        return "", ""


def stage2_sort_score(item: ProcessedItem) -> float:
    """Composite ranking for keep=True items (spec: 0.5·brand + 0.3·imp + 0.2·novel)."""
    j = item.llm_judgement
    if j is None:
        return item.final_score
    return (
        0.5 * j.brand_relevance_score
        + 0.3 * j.importance_score
        + 0.2 * j.novelty_score
    )
