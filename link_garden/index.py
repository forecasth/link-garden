from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from link_garden.io_utils import atomic_write_text
from link_garden.model import Bookmark, IndexEntry
from link_garden.security import Visibility
from link_garden.storage import (
    StoragePaths,
    ensure_index_file,
    list_bookmark_files,
    read_bookmark_file,
    relative_to_root,
)
from link_garden.utils import normalize_search_text, normalize_url, strip_markdown


@dataclass
class RebuildError:
    path: str
    error: str


@dataclass
class RebuildReport:
    scanned: int = 0
    indexed: int = 0
    skipped: int = 0
    errors: list[RebuildError] = field(default_factory=list)
    entries: list[IndexEntry] = field(default_factory=list)


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
    save_index_file(paths.index_file, entries)


def save_index_file(index_file: Path, entries: list[IndexEntry]) -> None:
    ordered = sorted(entries, key=lambda item: item.saved_at, reverse=True)
    payload = [entry.model_dump(mode="json") for entry in ordered]
    index_file.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(index_file, json.dumps(payload, indent=2) + "\n")


def entry_from_bookmark(bookmark: Bookmark, rel_path: str) -> IndexEntry:
    notes_text = bookmark.body or bookmark.notes
    search_blob = " ".join(
        [
            bookmark.title,
            bookmark.url,
            " ".join(bookmark.tags),
            bookmark.folder_path,
            bookmark.description,
            strip_markdown(notes_text),
        ]
    )
    return IndexEntry(
        id=bookmark.id,
        title=bookmark.title,
        url=bookmark.url,
        tags=bookmark.tags,
        path=rel_path,
        saved_at=bookmark.saved_at,
        folder_path=bookmark.folder_path,
        chrome_guid=bookmark.chrome_guid,
        archived=bookmark.archived,
        description=bookmark.description,
        search_text=normalize_search_text(search_blob),
        visibility=bookmark.visibility,
    )


def upsert_entry(entries: list[IndexEntry], entry: IndexEntry) -> list[IndexEntry]:
    updated = [existing for existing in entries if existing.id != entry.id]
    updated.append(entry)
    return updated


def rebuild_index_with_report(paths: StoragePaths, dry_run: bool = False) -> RebuildReport:
    report = RebuildReport()
    rebuilt: list[IndexEntry] = []
    for bookmark_file in list_bookmark_files(paths):
        report.scanned += 1
        try:
            bookmark = read_bookmark_file(bookmark_file)
        except Exception as exc:  # noqa: BLE001
            report.skipped += 1
            report.errors.append(RebuildError(path=relative_to_root(paths, bookmark_file), error=str(exc)))
            continue
        rel_path = relative_to_root(paths, bookmark_file)
        rebuilt.append(entry_from_bookmark(bookmark, rel_path))
    report.entries = rebuilt
    report.indexed = len(rebuilt)
    if not dry_run:
        save_index(paths, rebuilt)
    return report


def rebuild_index_from_files(paths: StoragePaths) -> list[IndexEntry]:
    return rebuild_index_with_report(paths, dry_run=False).entries


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


def search_entries(
    entries: Iterable[IndexEntry],
    *,
    search: str | None = None,
    tag: str | None = None,
    folder: str | None = None,
    visibility: Visibility | None = None,
    include_archived: bool = False,
) -> list[IndexEntry]:
    result = list(entries)
    if not include_archived:
        result = [entry for entry in result if not entry.archived]

    if tag:
        tag_key = tag.lower().strip()
        result = [entry for entry in result if any(item.lower() == tag_key for item in entry.tags)]

    if folder:
        folder_key = folder.strip().replace("\\", "/").strip("/")
        result = [entry for entry in result if entry.folder_path.replace("\\", "/").strip("/").startswith(folder_key)]

    if visibility is not None:
        result = [entry for entry in result if entry.visibility == visibility]

    if search:
        needle = normalize_search_text(search)
        filtered: list[IndexEntry] = []
        for entry in result:
            haystack = entry.search_text or normalize_search_text(
                " ".join([entry.title, entry.url, " ".join(entry.tags), entry.folder_path, entry.description])
            )
            if needle in haystack:
                filtered.append(entry)
        result = filtered

    return sorted(result, key=lambda item: item.saved_at, reverse=True)


def find_duplicate_entries(entries: Iterable[IndexEntry]) -> dict[str, list[IndexEntry]]:
    groups: dict[str, list[IndexEntry]] = {}
    for entry in entries:
        key = normalize_url(entry.url)
        groups.setdefault(key, []).append(entry)
    return {key: grouped for key, grouped in groups.items() if len(grouped) > 1}
