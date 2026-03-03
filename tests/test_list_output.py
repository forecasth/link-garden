import json
from pathlib import Path

from typer.testing import CliRunner

import link_garden.cli as cli_module
from link_garden.index import entry_from_bookmark, save_index
from link_garden.model import Bookmark
from link_garden.security import Visibility
from link_garden.storage import init_storage, relative_to_root, write_bookmark

runner = CliRunner()


def _seed(tmp_path: Path) -> Bookmark:
    paths = init_storage(tmp_path)
    bookmark = Bookmark(
        id="list01",
        title="List Output Test",
        url="https://example.com/list",
        tags=["one"],
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
        visibility=Visibility.public,
    )
    path = write_bookmark(paths, bookmark)
    save_index(paths, [entry_from_bookmark(bookmark, relative_to_root(paths, path))])
    return bookmark


def test_list_default_format_is_human_readable_table(tmp_path: Path) -> None:
    bookmark = _seed(tmp_path)
    result = runner.invoke(cli_module.app, ["list", "--root", str(tmp_path)])
    assert result.exit_code == 0
    assert "ID" in result.output
    assert "TITLE" in result.output
    assert "FOLDER" in result.output
    assert "VISIBILITY" in result.output
    assert bookmark.id in result.output
    assert "\t" not in result.output


def test_list_tsv_output(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = runner.invoke(cli_module.app, ["list", "--root", str(tmp_path), "--format", "tsv"])
    assert result.exit_code == 0
    lines = [line for line in result.output.strip().splitlines() if line.strip()]
    assert lines[0] == "id\ttitle\tfolder\tvisibility"
    assert lines[1].startswith("list01\tList Output Test\tbookmark_bar/Test\tpublic")


def test_list_json_output(tmp_path: Path) -> None:
    _seed(tmp_path)
    result = runner.invoke(cli_module.app, ["list", "--root", str(tmp_path), "--format", "json"])
    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert isinstance(payload, list)
    assert payload[0]["id"] == "list01"
    assert payload[0]["visibility"] == "public"

