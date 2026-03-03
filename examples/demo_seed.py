from __future__ import annotations

import argparse
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

from link_garden.index import entry_from_bookmark, load_index, save_index, upsert_entry
from link_garden.model import Bookmark
from link_garden.security import Visibility
from link_garden.storage import init_storage, relative_to_root, write_bookmark
from link_garden.utils import generate_short_id

DEMO_BOOKMARKS = [
    {
        "title": "Python Packaging Guide",
        "url": "https://packaging.python.org/en/latest/",
        "tags": ["python", "docs", "learning"],
        "folder_path": "bookmark_bar/Dev/Python",
        "visibility": Visibility.public,
        "notes": "Solid reference for publishing and versioning packages.",
    },
    {
        "title": "Self-hosting Notes",
        "url": "https://example.com/self-hosting",
        "tags": ["ops", "self-host", "notes"],
        "folder_path": "bookmark_bar/Infra",
        "visibility": Visibility.unlisted,
        "notes": "Draft checklist for reverse proxy and firewall setup.",
    },
    {
        "title": "Personal Journal Prompt",
        "url": "https://example.com/journal-prompt",
        "tags": ["personal", "writing"],
        "folder_path": "bookmark_bar/Personal",
        "visibility": Visibility.private,
        "notes": "Private reflection link; keep out of public exports.",
    },
    {
        "title": "Link Garden Inspiration",
        "url": "https://example.net/garden",
        "tags": ["design", "web", "ideas"],
        "folder_path": "bookmark_bar/Design",
        "visibility": Visibility.public,
        "notes": "Interesting layout patterns for personal knowledge sites.",
    },
    {
        "title": "Archive Candidate",
        "url": "https://example.org/old-article",
        "tags": ["archive", "old"],
        "folder_path": "bookmark_bar/Misc",
        "visibility": Visibility.private,
        "notes": "Could archive after migration notes are copied.",
        "archived": True,
    },
    {
        "title": "Research Paper Queue",
        "url": "https://example.edu/papers",
        "tags": ["research", "reading"],
        "folder_path": "bookmark_bar/Research/Queue",
        "visibility": Visibility.unlisted,
        "notes": "Papers to skim this week.",
    },
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed a small demo dataset for link-garden.")
    parser.add_argument(
        "--root",
        type=Path,
        default=None,
        help="Project root to seed. Defaults to a new temporary directory.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Skip confirmation when adding to a root that already has bookmark files.",
    )
    return parser.parse_args()


def _confirm_existing(path: Path) -> bool:
    if not sys.stdin.isatty():
        return False
    try:
        answer = input(f"Existing bookmarks detected in {path}. Append demo data? [y/N]: ").strip().lower()
    except EOFError:
        return False
    return answer in {"y", "yes"}


def _timestamp(base: datetime, offset_minutes: int) -> str:
    return (base + timedelta(minutes=offset_minutes)).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    args = parse_args()
    if args.root is None:
        root = Path(tempfile.mkdtemp(prefix="link-garden-demo-")).resolve()
        print(f"Using temporary demo root: {root}")
    else:
        root = args.root.resolve()
        root.mkdir(parents=True, exist_ok=True)

    paths = init_storage(root)
    existing_files = sorted(paths.bookmarks_dir.glob("*.md"))
    if existing_files and not args.yes:
        if not _confirm_existing(root):
            print("Cancelled. Re-run with --yes to append demo data to an existing project.")
            return 1

    base = datetime(2026, 3, 3, 9, 0, 0, tzinfo=UTC)
    entries = load_index(paths)
    created = 0
    for index, seed in enumerate(DEMO_BOOKMARKS):
        notes = seed["notes"]
        bookmark = Bookmark(
            id=generate_short_id(),
            title=seed["title"],
            url=seed["url"],
            tags=list(seed["tags"]),
            saved_at=_timestamp(base, index),
            source="demo",
            folder_path=seed["folder_path"],
            chrome_guid=None,
            notes=notes,
            archived=bool(seed.get("archived", False)),
            description="",
            fetched_at=None,
            source_meta="",
            canonical_url=None,
            body=notes,
            visibility=seed["visibility"],
        )
        output_path = write_bookmark(paths, bookmark)
        rel_path = relative_to_root(paths, output_path)
        entries = upsert_entry(entries, entry_from_bookmark(bookmark, rel_path))
        created += 1

    save_index(paths, entries)
    print(f"Seeded {created} demo bookmarks.")
    print(f"Project root: {paths.root}")
    print("Try:")
    print(f"  link-garden list --root {paths.root}")
    print(f"  link-garden export --format html --out {paths.root / 'exports'} --scope public --root {paths.root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
