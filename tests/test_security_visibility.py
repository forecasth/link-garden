import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import link_garden.cli as cli_module
from link_garden.config import load_config
from link_garden.doctor import run_doctor
from link_garden.export import ExportFormat, export_bookmarks
from link_garden.model import Bookmark
from link_garden.security import ExportScope, Visibility
from link_garden.storage import init_storage, write_bookmark

runner = CliRunner()


def _bookmark(bookmark_id: str, visibility: Visibility, url: str) -> Bookmark:
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
        body="",
        visibility=visibility,
    )


def test_export_visibility_scope_filters_private_and_unlisted(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    write_bookmark(paths, _bookmark("public01", Visibility.public, "https://public.example.com"))
    write_bookmark(paths, _bookmark("unlisted01", Visibility.unlisted, "https://unlisted.example.com"))
    write_bookmark(paths, _bookmark("private01", Visibility.private, "https://private.example.com"))

    public_out = tmp_path / "out-public"
    unlisted_out = tmp_path / "out-unlisted"

    export_bookmarks(paths, export_format=ExportFormat.json, out_dir=public_out, scope=ExportScope.public)
    export_bookmarks(paths, export_format=ExportFormat.json, out_dir=unlisted_out, scope=ExportScope.unlisted)

    public_payload = json.loads((public_out / "bookmarks.json").read_text(encoding="utf-8"))
    unlisted_payload = json.loads((unlisted_out / "bookmarks.json").read_text(encoding="utf-8"))

    assert {item["id"] for item in public_payload} == {"public01"}
    assert {item["id"] for item in unlisted_payload} == {"public01", "unlisted01"}


def test_export_scope_all_requires_dangerous_flag(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    write_bookmark(paths, _bookmark("private01", Visibility.private, "https://private.example.com"))

    with pytest.raises(ValueError, match="dangerous_all"):
        export_bookmarks(
            paths,
            export_format=ExportFormat.json,
            out_dir=tmp_path / "out-all",
            scope=ExportScope.all,
            dangerous_all=False,
        )


def test_cli_export_scope_all_requires_dangerous_flag(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    write_bookmark(paths, _bookmark("private01", Visibility.private, "https://private.example.com"))

    out_dir = tmp_path / "exports"
    result = runner.invoke(
        cli_module.app,
        [
            "export",
            "--format",
            "html",
            "--out",
            str(out_dir),
            "--scope",
            "all",
            "--root",
            str(tmp_path),
        ],
    )
    assert result.exit_code != 0
    assert "dangerous_all" in result.output


def test_doctor_flags_private_export_leak(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    private_url = "https://private.example.com/secret"
    write_bookmark(paths, _bookmark("private01", Visibility.private, private_url))

    exports_dir = tmp_path / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    (exports_dir / "index.html").write_text(f"<html><body>{private_url}</body></html>", encoding="utf-8")

    report = run_doctor(paths)
    issue_codes = {issue.code for issue in report.issues}
    assert "private_export_leak" in issue_codes


def test_doctor_ignores_private_url_in_non_export_html(tmp_path: Path) -> None:
    paths = init_storage(tmp_path)
    private_url = "https://private.example.com/secret"
    write_bookmark(paths, _bookmark("private01", Visibility.private, private_url))

    site_dir = tmp_path / "site"
    site_dir.mkdir(parents=True, exist_ok=True)
    (site_dir / "index.html").write_text(f"<html><body>{private_url}</body></html>", encoding="utf-8")

    report = run_doctor(paths)
    issue_codes = {issue.code for issue in report.issues}
    assert "private_export_leak" not in issue_codes


def test_config_secure_defaults_when_missing(tmp_path: Path) -> None:
    root = tmp_path / "project-root"
    root.mkdir()
    config, warnings = load_config(root)
    assert warnings == []
    assert config.default_visibility == Visibility.private
    assert config.export_default_scope == ExportScope.public
    assert config.serve_default_scope == ExportScope.public
    assert config.server_bind_host == "127.0.0.1"
    assert config.require_allow_remote is True
