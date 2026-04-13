"""Within-run dedupe + cross-run unseen filter (no store writes here) (v1.4)."""

from __future__ import annotations

from app.models import ProcessedItem, RawItem
from app.storage.base import BaseStore
from app.utils.hash_utils import make_dedupe_id, stable_hash


def build_dedupe_key(item: RawItem | ProcessedItem) -> str:
    did = (item.dedupe_id or "").strip()
    if did:
        return did
    url = (item.url or "").strip()
    title = (item.title or "").strip()
    if url or title:
        return stable_hash(url, title)
    return make_dedupe_id(
        item.source_type,
        item.external_id,
        item.url,
        item.title,
    )


def dedupe_items(items: list[ProcessedItem]) -> list[ProcessedItem]:
    groups: dict[str, list[ProcessedItem]] = {}
    for it in items:
        key = build_dedupe_key(it)
        groups.setdefault(key, []).append(it)

    out: list[ProcessedItem] = []
    for key in sorted(groups.keys()):
        grp = groups[key]
        grp_sorted = sorted(
            grp,
            key=lambda x: (x.final_score, x.published_at, x.external_id, x.url, x.title),
            reverse=True,
        )
        winner = grp_sorted[0]
        winner.is_update = len(grp_sorted) > 1
        out.append(winner)
    return out


def filter_unseen_items(items: list[ProcessedItem], store: BaseStore) -> list[ProcessedItem]:
    return [it for it in items if it.dedupe_id and not store.has_seen(it.dedupe_id)]


def filter_new_items(items: list[ProcessedItem], store: BaseStore) -> list[ProcessedItem]:
    return filter_unseen_items(items, store)
