from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

from link_garden.io_utils import atomic_write_text
from link_garden.model import Bookmark
from link_garden.security import Visibility
from link_garden.utils import build_bookmark_filename, ensure_utc_iso, split_tags

FRONTMATTER_RE = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n?(.*)$", re.DOTALL)


@dataclass(frozen=True)
class StoragePaths:
    root: Path
    data_dir: Path
    bookmarks_dir: Path
    index_file: Path


def resolve_paths(root: Path | str | None = None, data_dir: Path | str | None = None) -> StoragePaths:
    root_path = Path(root or Path.cwd()).resolve()
    if data_dir is None:
        resolved_data_dir = root_path / "data"
    else:
        candidate = Path(data_dir)
        if not candidate.is_absolute():
            candidate = root_path / candidate
        resolved_data_dir = candidate.resolve()
    bookmarks_dir = resolved_data_dir / "bookmarks"
    index_file = resolved_data_dir / "index.json"
    return StoragePaths(root=root_path, data_dir=resolved_data_dir, bookmarks_dir=bookmarks_dir, index_file=index_file)


def init_storage(root: Path | str | None = None, data_dir: Path | str | None = None) -> StoragePaths:
    paths = resolve_paths(root, data_dir=data_dir)
    paths.bookmarks_dir.mkdir(parents=True, exist_ok=True)
    if not paths.index_file.exists():
        atomic_write_text(paths.index_file, "[]\n")
    return paths


def relative_to_root(paths: StoragePaths, file_path: Path) -> str:
    resolved = file_path.resolve()
    try:
        return resolved.relative_to(paths.root).as_posix()
    except ValueError:
        return resolved.as_posix()


def list_bookmark_files(paths: StoragePaths) -> list[Path]:
    if not paths.bookmarks_dir.exists():
        return []
    return sorted(paths.bookmarks_dir.glob("*.md"))


def _bookmark_to_markdown(bookmark: Bookmark) -> str:
    frontmatter = bookmark.to_frontmatter()
    frontmatter_text = yaml.safe_dump(frontmatter, sort_keys=False, allow_unicode=False).strip()
    body = bookmark.body.rstrip("\n")
    if body:
        return f"---\n{frontmatter_text}\n---\n\n{body}\n"
    return f"---\n{frontmatter_text}\n---\n"


def _markdown_to_bookmark(text: str, source_path: Path) -> Bookmark:
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError(f"Invalid frontmatter format in {source_path}")

    metadata_raw, body = match.groups()
    metadata = yaml.safe_load(metadata_raw) or {}
    if not isinstance(metadata, dict):
        raise ValueError(f"Frontmatter must be a mapping in {source_path}")

    saved_at = metadata.get("saved_at")
    if not isinstance(saved_at, str):
        raise ValueError(f"Missing or invalid saved_at in {source_path}")

    cleaned_body = body
    if cleaned_body.startswith("\r\n"):
        cleaned_body = cleaned_body[2:]
    elif cleaned_body.startswith("\n"):
        cleaned_body = cleaned_body[1:]

    bookmark = Bookmark(
        id=str(metadata.get("id", "")),
        title=str(metadata.get("title", "")),
        url=str(metadata.get("url", "")),
        tags=split_tags(metadata.get("tags", [])),
        saved_at=ensure_utc_iso(saved_at),
        source=str(metadata.get("source", "manual")),
        folder_path=str(metadata.get("folder_path", "")),
        chrome_guid=metadata.get("chrome_guid"),
        notes=str(metadata.get("notes", "")),
        archived=bool(metadata.get("archived", False)),
        description=str(metadata.get("description", "")),
        fetched_at=metadata.get("fetched_at"),
        source_meta=str(metadata.get("source_meta", "")),
        canonical_url=metadata.get("canonical_url"),
        body=cleaned_body.rstrip("\n"),
        visibility=metadata.get("visibility", Visibility.private.value),
    )
    if not bookmark.id:
        raise ValueError(f"Missing id in {source_path}")
    return bookmark


def read_bookmark_file(path: Path) -> Bookmark:
    text = path.read_text(encoding="utf-8")
    return _markdown_to_bookmark(text, source_path=path)


def write_bookmark(paths: StoragePaths, bookmark: Bookmark, existing_path: Path | None = None) -> Path:
    bookmark.saved_at = ensure_utc_iso(bookmark.saved_at)
    target = existing_path
    if target is None:
        filename = build_bookmark_filename(bookmark.saved_at, bookmark.title, bookmark.id)
        target = paths.bookmarks_dir / filename
        if target.exists():
            stem = target.stem
            counter = 2
            while True:
                candidate = paths.bookmarks_dir / f"{stem}-{counter}.md"
                if not candidate.exists():
                    target = candidate
                    break
                counter += 1

    target.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, _bookmark_to_markdown(bookmark))
    return target


def load_all_bookmarks(paths: StoragePaths) -> list[tuple[Bookmark, Path]]:
    bookmarks: list[tuple[Bookmark, Path]] = []
    for path in list_bookmark_files(paths):
        bookmarks.append((read_bookmark_file(path), path))
    return bookmarks


def ensure_index_file(paths: StoragePaths) -> None:
    if not paths.index_file.exists():
        paths.index_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(paths.index_file, json.dumps([], indent=2) + "\n")
