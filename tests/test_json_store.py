"""JsonStore: seen ids, run metadata, in-process cache."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from app.models import ProcessedItem, RunMetadata
from app.storage.json_store import JsonStore


def _item(did: str) -> ProcessedItem:
    return ProcessedItem(
        source_type="rss",
        source_name="n",
        external_id="e",
        dedupe_id=did,
        canonical_id=None,
        title="t",
        text="x",
        raw_content=None,
        url="u",
        published_at=datetime.now(timezone.utc),
        updated_at=None,
    )


def test_json_store_has_seen_mark_seen(tmp_path: Path) -> None:
    st = JsonStore(tmp_path)
    assert not st.has_seen("a")
    st.mark_seen([_item("a")])
    assert st.has_seen("a")
    st.mark_seen([_item("b")])
    assert st.has_seen("a") and st.has_seen("b")


def test_json_store_save_run_metadata(tmp_path: Path) -> None:
    st = JsonStore(tmp_path)
    now = datetime.now(timezone.utc)
    st.save_run_metadata(
        RunMetadata(
            run_id="r1",
            started_at=now,
            finished_at=now,
            status="success",
            item_count=3,
            error_count=0,
        ),
    )
    data = (tmp_path / "digest_state.json").read_text(encoding="utf-8")
    assert "r1" in data
    assert "item_count" in data


def test_json_store_has_seen_uses_cache_not_repeated_full_read(tmp_path: Path) -> None:
    st = JsonStore(tmp_path)
    st.mark_seen([_item("x")])
    opens: list[str] = []

    real_open = Path.open

    def counting_open(self: Path, *args: object, **kwargs: object):
        if self.name == "digest_state.json" and "r" in str(args[0] if args else kwargs.get("mode", "")):
            opens.append("read")
        return real_open(self, *args, **kwargs)

    with patch.object(Path, "open", counting_open):
        assert st.has_seen("x")
        assert st.has_seen("x")
        assert st.has_seen("x")

    assert opens == []
