from pathlib import Path

from link_garden.index import load_index, rebuild_index_from_files
from link_garden.model import Bookmark
from link_garden.storage import init_storage, write_bookmark


def _bookmark(bookmark_id: str, url: str, title: str, saved_at: str) -> Bookmark:
    return Bookmark(
        id=bookmark_id,
        title=title,
        url=url,
        tags=["tag1"],
        saved_at=saved_at,
        source="manual",
        folder_path="bookmark_bar/Test",
        chrome_guid=None,
        notes="",
        archived=False,
        body="",
    )


def test_rebuild_index_from_files(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)

    write_bookmark(paths, _bookmark("id1abc", "https://a.example.com", "A", "2026-03-01T00:00:00Z"))
    write_bookmark(paths, _bookmark("id2abc", "https://b.example.com", "B", "2026-03-02T00:00:00Z"))

    rebuilt = rebuild_index_from_files(paths)
    loaded = load_index(paths)

    assert len(rebuilt) == 2
    assert len(loaded) == 2
    assert {entry.id for entry in loaded} == {"id1abc", "id2abc"}
    assert all(entry.path.startswith("data/bookmarks/") for entry in loaded)
