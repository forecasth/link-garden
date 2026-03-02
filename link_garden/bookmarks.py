from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from link_garden.index import entry_from_bookmark, load_index, save_index, upsert_entry
from link_garden.model import Bookmark, IndexEntry
from link_garden.storage import StoragePaths, read_bookmark_file, relative_to_root, write_bookmark
from link_garden.utils import normalize_url


@dataclass
class BookmarkRecord:
    bookmark: Bookmark
    path: Path
    rel_path: str
    entry: IndexEntry


def _entry_by_id(entries: list[IndexEntry]) -> dict[str, IndexEntry]:
    return {entry.id: entry for entry in entries}


def load_record_by_id(paths: StoragePaths, bookmark_id: str) -> BookmarkRecord:
    entries = load_index(paths)
    mapping = _entry_by_id(entries)
    entry = mapping.get(bookmark_id)
    if entry is None:
        raise ValueError(f"Bookmark id not found: {bookmark_id}")
    file_path = (paths.root / entry.path).resolve()
    if not file_path.exists():
        raise ValueError(f"Bookmark file not found for id={bookmark_id}: {entry.path}")
    bookmark = read_bookmark_file(file_path)
    rel_path = relative_to_root(paths, file_path)
    return BookmarkRecord(bookmark=bookmark, path=file_path, rel_path=rel_path, entry=entry)


def load_record_by_path(paths: StoragePaths, path_value: str | Path) -> BookmarkRecord:
    input_path = Path(path_value)
    if not input_path.is_absolute():
        candidate = (paths.root / input_path).resolve()
        if candidate.exists():
            input_path = candidate
        else:
            input_path = (paths.bookmarks_dir / input_path).resolve()
    if not input_path.exists():
        raise ValueError(f"Bookmark file not found: {path_value}")
    bookmark = read_bookmark_file(input_path)
    rel_path = relative_to_root(paths, input_path)
    entries = load_index(paths)
    entry = next((item for item in entries if item.id == bookmark.id), entry_from_bookmark(bookmark, rel_path))
    return BookmarkRecord(bookmark=bookmark, path=input_path, rel_path=rel_path, entry=entry)


def resolve_record(paths: StoragePaths, id_or_path: str) -> BookmarkRecord:
    candidate = Path(id_or_path)
    looks_like_path = (
        "/" in id_or_path
        or "\\" in id_or_path
        or id_or_path.lower().endswith(".md")
        or candidate.is_absolute()
        or (paths.root / candidate).exists()
    )
    if looks_like_path:
        return load_record_by_path(paths, id_or_path)
    return load_record_by_id(paths, id_or_path)


def persist_record(paths: StoragePaths, record: BookmarkRecord, *, rename_file: bool = False) -> BookmarkRecord:
    existing_path = None if rename_file else record.path
    target_path = write_bookmark(paths, record.bookmark, existing_path=existing_path)
    if rename_file and target_path.resolve() != record.path.resolve() and record.path.exists():
        record.path.unlink()

    rel_path = relative_to_root(paths, target_path)
    entry = entry_from_bookmark(record.bookmark, rel_path)
    entries = load_index(paths)
    updated_entries = upsert_entry(entries, entry)
    save_index(paths, updated_entries)
    return BookmarkRecord(bookmark=record.bookmark, path=target_path, rel_path=rel_path, entry=entry)


def find_records_by_url(paths: StoragePaths, url: str, include_archived: bool = True) -> list[BookmarkRecord]:
    target = normalize_url(url)
    entries = load_index(paths)
    matching = [entry for entry in entries if normalize_url(entry.url) == target]
    if not include_archived:
        matching = [entry for entry in matching if not entry.archived]

    output: list[BookmarkRecord] = []
    for entry in matching:
        path = (paths.root / entry.path).resolve()
        if not path.exists():
            continue
        bookmark = read_bookmark_file(path)
        output.append(BookmarkRecord(bookmark=bookmark, path=path, rel_path=relative_to_root(paths, path), entry=entry))
    return output
