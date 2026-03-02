from pathlib import Path

from typer.testing import CliRunner

import link_garden.cli as cli_module
from link_garden.index import entry_from_bookmark, load_index, save_index
from link_garden.model import Bookmark
from link_garden.storage import init_storage, read_bookmark_file, relative_to_root, write_bookmark

runner = CliRunner()


def _seed_bookmark(tmp_path: Path, *, bookmark_id: str = "curate01", title: str = "Original Title") -> tuple[Bookmark, Path]:
    paths = init_storage(tmp_path)
    bookmark = Bookmark(
        id=bookmark_id,
        title=title,
        url="https://example.com/path",
        tags=["one"],
        saved_at="2026-03-02T00:00:00Z",
        source="manual",
        folder_path="bookmark_bar/Test",
        chrome_guid=None,
        notes="seed note",
        archived=False,
        description="",
        fetched_at=None,
        source_meta="",
        canonical_url=None,
        body="seed note",
    )
    bookmark_path = write_bookmark(paths, bookmark)
    rel_path = relative_to_root(paths, bookmark_path)
    save_index(paths, [entry_from_bookmark(bookmark, rel_path)])
    return bookmark, bookmark_path


def test_cli_tag_archive_move_updates_file_and_index(tmp_path: Path) -> None:
    bookmark, bookmark_path = _seed_bookmark(tmp_path)
    repo_dir = str(tmp_path)

    tag_result = runner.invoke(
        cli_module.app,
        ["tag", bookmark.id, "--add", "two,Three", "--remove", "one", "--repo-dir", repo_dir],
    )
    assert tag_result.exit_code == 0

    archive_result = runner.invoke(cli_module.app, ["archive", bookmark.id, "--yes", "--repo-dir", repo_dir])
    assert archive_result.exit_code == 0

    move_result = runner.invoke(
        cli_module.app,
        ["move", bookmark.id, "--folder", "bookmark_bar/Research/GPCR", "--repo-dir", repo_dir],
    )
    assert move_result.exit_code == 0

    paths = init_storage(tmp_path)
    saved = read_bookmark_file(bookmark_path)
    assert saved.tags == ["two", "Three"]
    assert saved.archived is True
    assert saved.folder_path == "bookmark_bar/Research/GPCR"

    entries = load_index(paths)
    assert len(entries) == 1
    entry = entries[0]
    assert entry.tags == ["two", "Three"]
    assert entry.archived is True
    assert entry.folder_path == "bookmark_bar/Research/GPCR"


def test_cli_edit_refreshes_index_after_editor_changes(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    bookmark, _ = _seed_bookmark(tmp_path, bookmark_id="edit01", title="Before Edit")
    repo_dir = str(tmp_path)

    def fake_editor(file_path: Path, editor_override: str | None = None) -> None:
        text = file_path.read_text(encoding="utf-8")
        text = text.replace("title: Before Edit", "title: After Edit")
        file_path.write_text(text, encoding="utf-8")

    monkeypatch.setattr(cli_module, "_run_editor", fake_editor)

    result = runner.invoke(cli_module.app, ["edit", bookmark.id, "--repo-dir", repo_dir])
    assert result.exit_code == 0

    paths = init_storage(tmp_path)
    entries = load_index(paths)
    assert entries[0].title == "After Edit"
