import json
from pathlib import Path

from link_garden.chrome_import import DedupeMode, import_chrome_bookmarks, parse_chrome_bookmarks
from link_garden.index import entry_from_bookmark, load_index, save_index
from link_garden.model import Bookmark
from link_garden.storage import init_storage, list_bookmark_files, relative_to_root, write_bookmark


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_parse_chrome_bookmarks_preserves_folder_path(tmp_path: Path) -> None:
    bookmarks_file = tmp_path / "Bookmarks"
    payload = {
        "roots": {
            "bookmark_bar": {
                "children": [
                    {
                        "type": "folder",
                        "name": "Research",
                        "children": [
                            {
                                "type": "folder",
                                "name": "GPCR",
                                "children": [
                                    {
                                        "type": "url",
                                        "name": "Paper",
                                        "url": "https://example.com/paper",
                                        "guid": "guid-1",
                                        "date_added": "13345000000000000",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
            "other": {
                "children": [
                    {
                        "type": "url",
                        "name": "Misc",
                        "url": "https://misc.example.com/",
                        "date_added": "13345000000000001",
                    }
                ]
            },
            "synced": {"children": []},
        }
    }
    _write_json(bookmarks_file, payload)

    parsed = parse_chrome_bookmarks(bookmarks_file)
    assert len(parsed) == 2
    assert parsed[0].folder_path == "bookmark_bar/Research/GPCR"
    assert parsed[0].guid == "guid-1"
    assert parsed[1].folder_path == "other"


def test_import_chrome_is_idempotent_with_both_dedupe(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    bookmarks_file = tmp_path / "Bookmarks"
    payload = {
        "roots": {
            "bookmark_bar": {
                "children": [
                    {
                        "type": "url",
                        "name": "Example",
                        "url": "https://example.com/path/",
                        "guid": "guid-1",
                        "date_added": "13345000000000000",
                    }
                ]
            },
            "other": {"children": []},
            "synced": {"children": []},
        }
    }
    _write_json(bookmarks_file, payload)

    first = import_chrome_bookmarks(paths=paths, bookmarks_file=bookmarks_file, dedupe=DedupeMode.both)
    second = import_chrome_bookmarks(paths=paths, bookmarks_file=bookmarks_file, dedupe=DedupeMode.both)

    assert first.created == 1
    assert first.updated == 0
    assert second.created == 0
    assert second.updated == 1
    assert len(load_index(paths)) == 1
    assert len(list_bookmark_files(paths)) == 1


def test_import_chrome_dedupe_by_url_matches_normalized_url(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)

    existing = Bookmark(
        id="existing123",
        title="Existing",
        url="https://example.com/path/",
        tags=[],
        saved_at="2026-03-02T00:00:00Z",
        source="manual",
        folder_path="bookmark_bar",
        chrome_guid=None,
        notes="",
        archived=False,
        body="",
    )
    existing_path = write_bookmark(paths, existing)
    existing_rel = relative_to_root(paths, existing_path)
    save_index(paths, [entry_from_bookmark(existing, existing_rel)])

    bookmarks_file = tmp_path / "Bookmarks"
    payload = {
        "roots": {
            "bookmark_bar": {
                "children": [
                    {
                        "type": "url",
                        "name": "Updated Example",
                        "url": "https://example.com/path/?utm_source=feed",
                        "date_added": "13345000000000000",
                    }
                ]
            },
            "other": {"children": []},
            "synced": {"children": []},
        }
    }
    _write_json(bookmarks_file, payload)

    stats = import_chrome_bookmarks(paths=paths, bookmarks_file=bookmarks_file, dedupe=DedupeMode.by_url)

    assert stats.created == 0
    assert stats.updated == 1
    assert len(load_index(paths)) == 1
