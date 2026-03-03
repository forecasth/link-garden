from pathlib import Path

import pytest
from typer.testing import CliRunner

import link_garden.cli as cli_module

runner = CliRunner()


@pytest.mark.parametrize(
    "command",
    [
        ["edit", "missing-id"],
        ["tag", "missing-id", "--add", "tag1"],
        ["move", "missing-id", "--folder", "bookmark_bar/Test"],
        ["set-visibility", "--id", "missing-id", "--visibility", "public"],
        ["archive", "missing-id", "--yes"],
        ["unarchive", "missing-id"],
    ],
)
def test_cli_missing_id_is_friendly_error_without_traceback(tmp_path: Path, command: list[str]) -> None:
    repo_dir = str(tmp_path)
    result = runner.invoke(cli_module.app, [*command, "--repo-dir", repo_dir])
    assert result.exit_code != 0
    assert "Traceback" not in result.output
    assert "Error: Bookmark id not found: missing-id" in result.output

