from __future__ import annotations

import json
from pathlib import Path

from link_garden.model import Bookmark, IndexEntry
from link_garden.storage import StoragePaths, ensure_index_file, list_bookmark_files, read_bookmark_file, relative_to_root
from link_garden.utils import normalize_url


def load_index(paths: StoragePaths) -> list[IndexEntry]:
    ensure_index_file(paths)
    raw = paths.index_file.read_text(encoding="utf-8").strip()
    if not raw:
        return []
    payload = json.loads(raw)
    if not isinstance(payload, list):
        raise ValueError("data/index.json must be a JSON array")
    return [IndexEntry.model_validate(item) for item in payload]


def save_index(paths: StoragePaths, entries: list[IndexEntry]) -> None:
    ordered = sorted(entries, key=lambda item: item.saved_at, reverse=True)
    payload = [entry.model_dump(mode="json") for entry in ordered]
    paths.index_file.parent.mkdir(parents=True, exist_ok=True)
    paths.index_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def entry_from_bookmark(bookmark: Bookmark, rel_path: str) -> IndexEntry:
    return IndexEntry(
        id=bookmark.id,
        title=bookmark.title,
        url=bookmark.url,
        tags=bookmark.tags,
        path=rel_path,
        saved_at=bookmark.saved_at,
        folder_path=bookmark.folder_path,
        chrome_guid=bookmark.chrome_guid,
    )


def upsert_entry(entries: list[IndexEntry], entry: IndexEntry) -> list[IndexEntry]:
    updated = [existing for existing in entries if existing.id != entry.id]
    updated.append(entry)
    return updated


def rebuild_index_from_files(paths: StoragePaths) -> list[IndexEntry]:
    rebuilt: list[IndexEntry] = []
    for bookmark_file in list_bookmark_files(paths):
        bookmark = read_bookmark_file(bookmark_file)
        rel_path = relative_to_root(paths, bookmark_file)
        rebuilt.append(entry_from_bookmark(bookmark, rel_path))
    save_index(paths, rebuilt)
    return rebuilt


def build_lookup_maps(entries: list[IndexEntry]) -> tuple[dict[str, IndexEntry], dict[str, IndexEntry]]:
    by_guid: dict[str, IndexEntry] = {}
    by_url: dict[str, IndexEntry] = {}
    for entry in entries:
        if entry.chrome_guid:
            by_guid[entry.chrome_guid] = entry
        by_url[normalize_url(entry.url)] = entry
    return by_guid, by_url


def index_paths(entries: list[IndexEntry], root: Path) -> set[Path]:
    return {(root / entry.path).resolve() for entry in entries}
