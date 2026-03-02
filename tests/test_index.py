from pathlib import Path

from link_garden.index import load_index, rebuild_index_from_files, rebuild_index_with_report
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


def test_rebuild_index_report_skips_invalid_files(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    write_bookmark(paths, _bookmark("ok123", "https://ok.example.com", "OK", "2026-03-02T00:00:00Z"))
    bad_file = paths.bookmarks_dir / "invalid.md"
    bad_file.write_text("not-a-frontmatter-file", encoding="utf-8")

    report = rebuild_index_with_report(paths)
    loaded = load_index(paths)

    assert report.scanned == 2
    assert report.indexed == 1
    assert report.skipped == 1
    assert len(report.errors) == 1
    assert "invalid.md" in report.errors[0].path
    assert len(loaded) == 1


def test_rebuild_index_report_dry_run_does_not_write(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    write_bookmark(paths, _bookmark("dry123", "https://dry.example.com", "Dry", "2026-03-02T00:00:00Z"))
    paths.index_file.write_text("[]\n", encoding="utf-8")

    report = rebuild_index_with_report(paths, dry_run=True)
    raw_index = paths.index_file.read_text(encoding="utf-8").strip()

    assert report.scanned == 1
    assert report.indexed == 1
    assert raw_index == "[]"
