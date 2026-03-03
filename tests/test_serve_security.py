from pathlib import Path

from typer.testing import CliRunner

import link_garden.cli as cli_module

runner = CliRunner()


def test_serve_binds_to_localhost_by_default(tmp_path: Path, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    captured: dict[str, object] = {}

    def fake_serve(directory: Path, host: str, port: int, open_browser: bool) -> None:
        captured["directory"] = directory
        captured["host"] = host
        captured["port"] = port
        captured["open_browser"] = open_browser

    monkeypatch.setattr(cli_module, "_serve_directory", fake_serve)

    result = runner.invoke(cli_module.app, ["serve", "--repo-dir", str(tmp_path), "--port", "8123"])
    assert result.exit_code == 0
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 8123
