from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from link_garden.index import build_lookup_maps, entry_from_bookmark, load_index, save_index, upsert_entry
from link_garden.model import Bookmark, IndexEntry
from link_garden.security import Visibility
from link_garden.storage import StoragePaths, read_bookmark_file, relative_to_root, write_bookmark
from link_garden.utils import chrome_micros_to_iso, generate_short_id, normalize_folder_path, normalize_url, utc_now_iso

logger = logging.getLogger(__name__)


class DedupeMode(str, Enum):
    by_url = "by_url"
    by_guid = "by_guid"
    both = "both"


class ChromeBookmarkRecord(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    url: str
    folder_path: str
    date_added: str | None = None
    guid: str | None = None


@dataclass
class ImportStats:
    total: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0


@dataclass(frozen=True)
class FileSnapshot:
    mtime_ns: int
    size_bytes: int


def parse_chrome_bookmarks(bookmarks_file: Path) -> list[ChromeBookmarkRecord]:
    payload = json.loads(bookmarks_file.read_text(encoding="utf-8"))
    roots = payload.get("roots", {})
    records: list[ChromeBookmarkRecord] = []

    for root_name in ("bookmark_bar", "other", "synced"):
        root_node = roots.get(root_name)
        if not isinstance(root_node, dict):
            continue
        children = root_node.get("children", [])
        if not isinstance(children, list):
            continue
        for child in children:
            _walk_chrome_node(child, [root_name], records)
    return records


def _walk_chrome_node(node: dict[str, Any], path_parts: list[str], records: list[ChromeBookmarkRecord]) -> None:
    node_type = node.get("type")
    if node_type == "url":
        url = str(node.get("url", "")).strip()
        if not url:
            return
        records.append(
            ChromeBookmarkRecord(
                title=str(node.get("name", "")).strip() or url,
                url=url,
                folder_path=normalize_folder_path("/".join(path_parts)),
                date_added=node.get("date_added"),
                guid=node.get("guid"),
            )
        )
        return

    if node_type == "folder":
        folder_name = str(node.get("name", "")).strip()
        next_path = path_parts + ([folder_name] if folder_name else [])
        children = node.get("children", [])
        if not isinstance(children, list):
            return
        for child in children:
            if isinstance(child, dict):
                _walk_chrome_node(child, next_path, records)


def _find_existing(
    record: ChromeBookmarkRecord,
    dedupe: DedupeMode,
    by_guid: dict[str, IndexEntry],
    by_url: dict[str, IndexEntry],
) -> IndexEntry | None:
    if dedupe == DedupeMode.by_guid:
        if record.guid:
            return by_guid.get(record.guid)
        return None
    if dedupe == DedupeMode.by_url:
        return by_url.get(normalize_url(record.url))

    if record.guid and record.guid in by_guid:
        return by_guid[record.guid]
    return by_url.get(normalize_url(record.url))


def import_chrome_bookmarks(
    paths: StoragePaths,
    bookmarks_file: Path,
    dedupe: DedupeMode = DedupeMode.both,
    dry_run: bool = False,
    profile_name: str = "Default",
    default_visibility: Visibility = Visibility.private,
) -> ImportStats:
    records = parse_chrome_bookmarks(bookmarks_file)
    entries = load_index(paths)
    by_guid, by_url = build_lookup_maps(entries)

    stats = ImportStats(total=len(records))
    logger.info(
        "import_start profile=%s file=%s records=%d dedupe=%s dry_run=%s",
        profile_name,
        bookmarks_file,
        len(records),
        dedupe.value,
        dry_run,
    )

    for record in records:
        existing = _find_existing(record, dedupe=dedupe, by_guid=by_guid, by_url=by_url)
        if existing:
            stats.updated += 1
            logger.info("import_update id=%s url=%s", existing.id, record.url)
            if dry_run:
                continue

            existing_path = (paths.root / existing.path).resolve()
            bookmark = read_bookmark_file(existing_path)
            bookmark.title = record.title or bookmark.title
            bookmark.url = record.url
            bookmark.source = "chrome"
            bookmark.folder_path = record.folder_path
            if record.guid:
                bookmark.chrome_guid = record.guid
            write_bookmark(paths, bookmark, existing_path=existing_path)

            updated_entry = entry_from_bookmark(bookmark, existing.path)
            entries = upsert_entry(entries, updated_entry)
            if updated_entry.chrome_guid:
                by_guid[updated_entry.chrome_guid] = updated_entry
            by_url[normalize_url(updated_entry.url)] = updated_entry
            continue

        stats.created += 1
        saved_at = chrome_micros_to_iso(record.date_added) or utc_now_iso()
        bookmark = Bookmark(
            id=generate_short_id(),
            title=record.title or record.url,
            url=record.url,
            tags=[],
            saved_at=saved_at,
            source="chrome",
            folder_path=record.folder_path,
            chrome_guid=record.guid,
            notes="",
            archived=False,
            body="",
            visibility=default_visibility,
        )
        logger.info("import_create id=%s url=%s", bookmark.id, bookmark.url)
        if dry_run:
            continue

        created_path = write_bookmark(paths, bookmark)
        rel_path = relative_to_root(paths, created_path)
        new_entry = entry_from_bookmark(bookmark, rel_path)
        entries = upsert_entry(entries, new_entry)
        if new_entry.chrome_guid:
            by_guid[new_entry.chrome_guid] = new_entry
        by_url[normalize_url(new_entry.url)] = new_entry

    if not dry_run:
        save_index(paths, entries)

    logger.info(
        "import_done total=%d created=%d updated=%d skipped=%d",
        stats.total,
        stats.created,
        stats.updated,
        stats.skipped,
    )
    return stats


def get_file_snapshot(path: Path) -> FileSnapshot | None:
    try:
        stat = path.stat()
    except FileNotFoundError:
        return None
    return FileSnapshot(mtime_ns=stat.st_mtime_ns, size_bytes=stat.st_size)


def file_has_changed(previous: FileSnapshot | None, current: FileSnapshot | None) -> bool:
    if previous is None and current is None:
        return False
    if previous is None or current is None:
        return True
    return previous != current


def watch_import_loop(
    paths: StoragePaths,
    bookmarks_file: Path,
    dedupe: DedupeMode,
    interval_seconds: int,
    dry_run: bool,
    profile_name: str,
    default_visibility: Visibility = Visibility.private,
) -> None:
    last_snapshot: FileSnapshot | None = None
    logger.info(
        "watch_start file=%s interval=%ss dedupe=%s dry_run=%s",
        bookmarks_file,
        interval_seconds,
        dedupe.value,
        dry_run,
    )
    while True:
        snapshot = get_file_snapshot(bookmarks_file)
        if file_has_changed(last_snapshot, snapshot):
            if snapshot is None:
                logger.warning("watch_cycle status=missing_file file=%s", bookmarks_file)
            else:
                stats = import_chrome_bookmarks(
                    paths=paths,
                    bookmarks_file=bookmarks_file,
                    dedupe=dedupe,
                    dry_run=dry_run,
                    profile_name=profile_name,
                    default_visibility=default_visibility,
                )
                logger.info(
                    "watch_cycle status=imported total=%d created=%d updated=%d skipped=%d",
                    stats.total,
                    stats.created,
                    stats.updated,
                    stats.skipped,
                )
            last_snapshot = snapshot
        else:
            logger.info("watch_cycle status=no_change")
        time.sleep(interval_seconds)
