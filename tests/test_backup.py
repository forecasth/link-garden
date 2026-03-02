import zipfile
from pathlib import Path

from link_garden.backup import BackupFormat, create_backup
from link_garden.index import entry_from_bookmark, save_index
from link_garden.model import Bookmark
from link_garden.storage import init_storage, relative_to_root, write_bookmark


def test_backup_zip_contains_expected_files(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    theme_file = tmp_path / "ui" / "theme.yaml"
    theme_file.parent.mkdir(parents=True, exist_ok=True)
    theme_file.write_text("colors:\n  bg: '#fff'\n", encoding="utf-8")

    bookmark = Bookmark(
        id="backup01",
        title="Backup Test",
        url="https://example.com",
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
    bookmark_path = write_bookmark(paths, bookmark)
    save_index(paths, [entry_from_bookmark(bookmark, relative_to_root(paths, bookmark_path))])

    report = create_backup(paths=paths, out_dir=tmp_path / "backups", backup_format=BackupFormat.zip, include_index=True)
    assert report.output_path.exists()

    with zipfile.ZipFile(report.output_path, "r") as archive:
        names = set(archive.namelist())
    assert "data/index.json" in names
    assert "ui/theme.yaml" in names
    assert any(name.startswith("data/bookmarks/") and name.endswith(".md") for name in names)
