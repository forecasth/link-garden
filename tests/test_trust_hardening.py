import json
from pathlib import Path

from typer.testing import CliRunner

import link_garden.cli as cli_module
from link_garden.index import entry_from_bookmark, load_index, save_index
from link_garden.model import Bookmark
from link_garden.security import Visibility
from link_garden.storage import init_storage, relative_to_root, write_bookmark

runner = CliRunner()


def _bookmark(bookmark_id: str, url: str, *, visibility: Visibility = Visibility.private) -> Bookmark:
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
        visibility=visibility,
    )


def test_import_chrome_auto_backup_only_when_mutation_occurs(tmp_path: Path) -> None:
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
    bookmarks_file.write_text(json.dumps(payload), encoding="utf-8")

    first = runner.invoke(
        cli_module.app,
        ["import-chrome", "--bookmarks-file", str(bookmarks_file), "--root", str(tmp_path)],
    )
    assert first.exit_code == 0
    assert "Auto backup (before import-chrome):" in first.output
    assert "Restore hint:" in first.output
    backups_dir = tmp_path / "data" / "backups"
    first_backups = sorted(backups_dir.glob("*.zip"))
    assert len(first_backups) == 1

    second = runner.invoke(
        cli_module.app,
        ["import-chrome", "--bookmarks-file", str(bookmarks_file), "--root", str(tmp_path)],
    )
    assert second.exit_code == 0
    assert "created=0 updated=0 skipped=1" in second.output
    second_backups = sorted(backups_dir.glob("*.zip"))
    assert len(second_backups) == 1


def test_rebuild_index_requires_yes_when_parse_errors_exist(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    bookmark = _bookmark("rebuild01", "https://example.com/rebuild")
    write_bookmark(paths, bookmark)
    bad_file = paths.bookmarks_dir / "bad.md"
    bad_file.write_text("not-frontmatter", encoding="utf-8")
    paths.index_file.write_text("[]\n", encoding="utf-8")

    no_yes = runner.invoke(cli_module.app, ["rebuild-index", "--repo-dir", str(tmp_path)])
    assert no_yes.exit_code == 0
    assert "Index left unchanged due to parse errors." in no_yes.output
    assert paths.index_file.read_text(encoding="utf-8") == "[]\n"
    rebuild_file = paths.data_dir / "index.rebuild.json"
    assert rebuild_file.exists()

    with_yes = runner.invoke(cli_module.app, ["rebuild-index", "--repo-dir", str(tmp_path), "--yes"])
    assert with_yes.exit_code == 0
    assert "Auto backup (before rebuild-index):" in with_yes.output
    assert "index.json updated." in with_yes.output
    assert "rebuild01" in paths.index_file.read_text(encoding="utf-8")
    backups = sorted((paths.data_dir / "backups").glob("*.zip"))
    assert len(backups) == 1


def test_doctor_fix_auto_backup_only_when_mutation_pending(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    bookmark = _bookmark("doctor01", "https://example.com/doctor")
    path = write_bookmark(paths, bookmark)
    save_index(paths, [])

    first = runner.invoke(cli_module.app, ["doctor", "--root", str(tmp_path), "--fix"])
    assert first.exit_code == 0
    assert "Auto backup (before doctor --fix):" in first.output
    assert len(load_index(paths)) == 1
    backups_dir = paths.data_dir / "backups"
    first_backups = sorted(backups_dir.glob("*.zip"))
    assert len(first_backups) == 1

    # Ensure index is already in sync for the next run.
    save_index(paths, [entry_from_bookmark(bookmark, relative_to_root(paths, path))])
    second = runner.invoke(cli_module.app, ["doctor", "--root", str(tmp_path), "--fix"])
    assert second.exit_code == 0
    assert "Doctor fix skipped: index already consistent." in second.output
    second_backups = sorted(backups_dir.glob("*.zip"))
    assert len(second_backups) == 1


def test_set_visibility_url_requires_yes_for_broad_mutation(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    first = _bookmark("vis01", "https://example.com/path/")
    second = _bookmark("vis02", "https://example.com/path/?utm_source=feed")
    first_path = write_bookmark(paths, first)
    second_path = write_bookmark(paths, second)
    save_index(
        paths,
        [
            entry_from_bookmark(first, relative_to_root(paths, first_path)),
            entry_from_bookmark(second, relative_to_root(paths, second_path)),
        ],
    )

    blocked = runner.invoke(
        cli_module.app,
        [
            "set-visibility",
            "--url",
            "https://example.com/path",
            "--visibility",
            "public",
            "--repo-dir",
            str(tmp_path),
        ],
    )
    assert blocked.exit_code == 1
    assert "Matched 2 bookmarks" in blocked.output
    assert "Re-run with --yes" in blocked.output
    assert all(entry.visibility == Visibility.private for entry in load_index(paths))

    confirmed = runner.invoke(
        cli_module.app,
        [
            "set-visibility",
            "--url",
            "https://example.com/path",
            "--visibility",
            "public",
            "--yes",
            "--repo-dir",
            str(tmp_path),
        ],
    )
    assert confirmed.exit_code == 0
    assert all(entry.visibility == Visibility.public for entry in load_index(paths))

