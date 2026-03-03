from pathlib import Path

from link_garden.doctor import run_doctor
from link_garden.index import entry_from_bookmark, save_index
from link_garden.model import Bookmark, IndexEntry
from link_garden.storage import init_storage, write_bookmark


def _bookmark(bookmark_id: str, url: str) -> Bookmark:
    return Bookmark(
        id=bookmark_id,
        title=bookmark_id,
        url=url,
        tags=[],
        saved_at="2026-03-02T00:00:00Z",
        source="manual",
        folder_path="bookmark_bar/Test",
        chrome_guid=None,
        notes="",
        archived=False,
        description="",
        fetched_at=None,
        source_meta="",
        canonical_url=None,
        body="",
    )


def test_doctor_detects_missing_files_duplicate_ids_and_duplicate_urls(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    b1 = _bookmark("dup-id", "https://example.com/path/")
    b2 = _bookmark("id-2", "https://example.com/path/?utm_source=feed")

    p1 = write_bookmark(paths, b1)
    p2 = write_bookmark(paths, b2)
    entries = [
        entry_from_bookmark(b1, p1.relative_to(tmp_path).as_posix()),
        entry_from_bookmark(b2, p2.relative_to(tmp_path).as_posix()),
    ]
    entries.append(
        IndexEntry(
            id="dup-id",
            title="duplicate-id-entry",
            url="https://duplicate.example.com",
            tags=[],
            path=p2.relative_to(tmp_path).as_posix(),
            saved_at="2026-03-02T00:00:00Z",
        )
    )
    entries.append(
        IndexEntry(
            id="missing-file",
            title="missing-file",
            url="https://missing.example.com",
            tags=[],
            path="data/bookmarks/does-not-exist.md",
            saved_at="2026-03-02T00:00:00Z",
        )
    )
    save_index(paths, entries)

    bad_file = paths.bookmarks_dir / "bad-frontmatter.md"
    bad_file.write_text("---\nthis is not yaml\n---\n", encoding="utf-8")

    report = run_doctor(paths)
    issue_codes = {issue.code for issue in report.issues}
    assert "duplicate_id" in issue_codes
    assert "missing_file" in issue_codes
    assert "duplicate_url_group" in issue_codes
    assert "invalid_frontmatter" in issue_codes
