from pathlib import Path

from link_garden.chrome_import import FileSnapshot, file_has_changed, get_file_snapshot


def test_file_has_changed_matrix() -> None:
    snap_a = FileSnapshot(mtime_ns=1, size_bytes=10)
    snap_b = FileSnapshot(mtime_ns=2, size_bytes=10)
    assert not file_has_changed(None, None)
    assert file_has_changed(None, snap_a)
    assert file_has_changed(snap_a, None)
    assert not file_has_changed(snap_a, snap_a)
    assert file_has_changed(snap_a, snap_b)


def test_file_snapshot_detects_content_change(tmp_path: Path) -> None:
    bookmarks_file = tmp_path / "Bookmarks"
    bookmarks_file.write_text("{}", encoding="utf-8")
    snap1 = get_file_snapshot(bookmarks_file)
    assert snap1 is not None

    bookmarks_file.write_text('{"roots":{}}', encoding="utf-8")
    snap2 = get_file_snapshot(bookmarks_file)
    assert snap2 is not None
    assert file_has_changed(snap1, snap2)


def test_file_snapshot_handles_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    assert get_file_snapshot(missing) is None
