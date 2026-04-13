"""Best-effort review export utilities (non-blocking)."""

from __future__ import annotations

import json
from pathlib import Path

from app.models import ProcessedItem


def _build_review_record(item: ProcessedItem) -> dict:
    llm = item.llm_judgement
    return {
        "title": item.title,
        "url": item.url,
        "source_name": item.source_name,
        "source_type": item.source_type,
        "category": item.category,
        "published_at": item.published_at.isoformat() if item.published_at else "",
        "final_score": item.final_score,
        "matched_keywords": item.matched_keywords,
        "matched_entities": item.matched_entities,
        "llm_judgement": {
            "keep": llm.keep if llm is not None else None,
            "reason": llm.reason if llm is not None else None,
        },
    }


def _write_jsonl(path: Path, items: list[ProcessedItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(_build_review_record(item), ensure_ascii=False) + "\n")


def export_review_runs(
    state_dir: Path | None,
    run_id: str,
    stage1_input_items: list[ProcessedItem],
    stage2_shortlist: list[ProcessedItem],
    final_to_send: list[ProcessedItem],
    log,
) -> None:
    """Export review JSONLs. Never raise (best effort)."""
    try:
        base = (state_dir or Path(".state")) / "review_runs" / run_id
        _write_jsonl(base / "stage1_input.jsonl", stage1_input_items)
        _write_jsonl(base / "stage2_shortlist.jsonl", stage2_shortlist)
        _write_jsonl(base / "final_to_send.jsonl", final_to_send)
    except Exception as exc:  # noqa: BLE001
        log.warning("review export failed (non-blocking): %s", exc)
