"""Select storage backend from AppConfig (v1.4)."""

from __future__ import annotations

from app import constants
from app.config import AppConfig
from app.storage.base import BaseStore
from app.storage.json_store import JsonStore


def build_store(config: AppConfig) -> BaseStore:
    st = (config.store_type or "").lower().strip()
    if st == constants.STORE_TYPES_JSON:
        if config.state_dir is None:
            raise ValueError("state_dir required for json store")
        return JsonStore(config.state_dir)
    if st in constants.STORE_TYPES_UNSUPPORTED:
        raise ValueError(
            f"store_type={st!r} is reserved for a future DB backend; use 'json' for now.",
        )
    raise ValueError(f"Unsupported store_type: {config.store_type!r}")
