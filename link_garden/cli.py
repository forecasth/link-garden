from __future__ import annotations

import http.server
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import threading
import webbrowser
from enum import Enum
from pathlib import Path
from typing import Callable
from urllib.parse import urlsplit

import typer

from link_garden.backup import BackupFormat, create_backup
from link_garden.bookmarks import BookmarkRecord, find_records_by_url, load_record_by_id, persist_record, resolve_record
from link_garden.chrome_import import DedupeMode, import_chrome_bookmarks, watch_import_loop
from link_garden.config import AppConfig, ensure_config_file, load_config
from link_garden.doctor import doctor_fix, run_doctor
from link_garden.enrich import DEFAULT_USER_AGENT, apply_enrichment_to_bookmark, fetch_url_metadata
from link_garden.export import ExportFormat, export_bookmarks
from link_garden.hub import export_hub_directory
from link_garden.index import (
    entry_from_bookmark,
    find_duplicate_entries,
    load_index,
    rebuild_index_with_report,
    save_index,
    save_index_file,
    search_entries,
    upsert_entry,
)
from link_garden.model import Bookmark, IndexEntry
from link_garden.security import ExportScope, Visibility, is_local_host, scope_is_broader_than_public
from link_garden.storage import StoragePaths, init_storage, read_bookmark_file, relative_to_root, write_bookmark
from link_garden.utils import generate_short_id, normalize_folder_path, split_tags, utc_now_iso

logger = logging.getLogger(__name__)
app = typer.Typer(help="Local-first bookmark + notes knowledge garden.")
hub_app = typer.Typer(help="Hub directory tools.")
app.add_typer(hub_app, name="hub")


class ListOutputFormat(str, Enum):
    table = "table"
    tsv = "tsv"
    json = "json"


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s %(message)s")


def _resolve_paths(repo_dir: Path, data_dir: Path | None) -> tuple[Path, Path | None]:
    return repo_dir, data_dir


def _looks_like_url(value: str) -> bool:
    parsed = urlsplit(value.strip())
    return bool(parsed.scheme and parsed.netloc)


def _clip(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    if width <= 3:
        return value[:width]
    return value[: width - 3] + "..."


def _editor_command_for_platform(file_path: Path, editor_override: str | None = None) -> tuple[list[str] | str, bool]:
    editor = (editor_override or os.environ.get("EDITOR", "")).strip()
    if editor:
        return f'{editor} "{file_path}"', True

    if os.name == "nt":
        return ["notepad", str(file_path)], False
    if sys.platform == "darwin":
        return ["open", "-e", str(file_path)], False

    for candidate in ("sensible-editor", "nano", "vi"):
        path = shutil.which(candidate)
        if path:
            return [path, str(file_path)], False
    return ["nano", str(file_path)], False


def _run_editor(file_path: Path, editor_override: str | None = None) -> None:
    command, use_shell = _editor_command_for_platform(file_path, editor_override=editor_override)
    subprocess.run(command, shell=use_shell, check=True)  # noqa: S602


def _merge_tags(existing: list[str], incoming: list[str]) -> list[str]:
    seen = {item.lower() for item in existing}
    merged = existing[:]
    for tag in incoming:
        key = tag.lower()
        if key in seen:
            continue
        seen.add(key)
        merged.append(tag)
    return merged


def _load_app_config(root: Path) -> AppConfig:
    config, warnings = load_config(root.resolve())
    for warning in warnings:
        typer.secho(f"Config warning: {warning}", fg=typer.colors.YELLOW)
    return config


def _warn_if_non_public_scope(scope: ExportScope, *, context: str) -> None:
    if scope_is_broader_than_public(scope):
        typer.secho(
            f"WARNING: {context} includes non-public entries (scope={scope.value}).",
            fg=typer.colors.YELLOW,
            err=True,
        )


def _run_cli_safe(operation: Callable[[], None]) -> None:
    try:
        operation()
    except (ValueError, FileNotFoundError) as exc:
        typer.secho(f"Error: {exc}", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1) from exc


def _serialize_entries(entries: list[IndexEntry]) -> list[dict[str, object]]:
    serialized = [entry.model_dump(mode="json") for entry in entries]
    return sorted(serialized, key=lambda item: str(item.get("id", "")))


def _entries_will_change(existing_entries: list[IndexEntry], rebuilt_entries: list[IndexEntry]) -> bool:
    return _serialize_entries(existing_entries) != _serialize_entries(rebuilt_entries)


def _create_auto_backup(paths: StoragePaths, *, reason: str) -> Path:
    backup_dir = paths.data_dir / "backups"
    report = create_backup(paths=paths, out_dir=backup_dir, backup_format=BackupFormat.zip, include_index=True)
    typer.echo(f"Auto backup ({reason}): {report.output_path}")
    typer.echo(f"Restore hint: extract {report.output_path.name} into the project root and rerun `link-garden doctor`.")
    return report.output_path


def _serve_directory(directory: Path, host: str, port: int, open_browser: bool) -> None:
    class DirectoryHandler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, directory=str(directory), **kwargs)

        def log_message(self, format: str, *args: object) -> None:  # noqa: A003
            logger.info("http_server " + format, *args)

    handler_cls = DirectoryHandler
    server = http.server.ThreadingHTTPServer((host, port), handler_cls)
    url = f"http://{host}:{port}/"
    typer.echo(f"Serving static export at {url} (directory: {directory})")
    if open_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        typer.echo("Server stopped.")
    finally:
        server.server_close()


@app.command("init")
def init_cmd(
    directory: Path = typer.Argument(..., help="Project directory to initialize."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    paths = init_storage(directory)
    config_file, created = ensure_config_file(paths.root)
    typer.echo(f"Initialized link-garden at {paths.root}")
    typer.echo(f"- bookmarks: {paths.bookmarks_dir}")
    typer.echo(f"- index: {paths.index_file}")
    if created:
        typer.echo(f"- config: {config_file}")


@app.command("add")
def add_cmd(
    url: str = typer.Option(..., "--url", help="Bookmark URL."),
    title: str | None = typer.Option(None, "--title", help="Optional bookmark title."),
    tags: str = typer.Option("", "--tags", help="Comma-separated tags."),
    notes: str = typer.Option("", "--notes", help="Optional note text."),
    folder: str = typer.Option("", "--folder", help='Folder path such as "Research/AI".'),
    source: str = typer.Option("manual", "--source", help="Bookmark source label."),
    root: Path = typer.Option(Path("."), "--root", help="Project root directory."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    paths = init_storage(root)
    config = _load_app_config(paths.root)

    bookmark = Bookmark(
        id=generate_short_id(),
        title=(title or url).strip(),
        url=url.strip(),
        tags=split_tags(tags),
        saved_at=utc_now_iso(),
        source=source.strip() or "manual",
        folder_path=normalize_folder_path(folder),
        chrome_guid=None,
        notes=notes.strip(),
        archived=False,
        description="",
        fetched_at=None,
        source_meta="",
        canonical_url=None,
        body=notes.strip(),
        visibility=config.default_visibility,
    )

    output_path = write_bookmark(paths, bookmark)
    rel_path = relative_to_root(paths, output_path)
    entries = load_index(paths)
    entries = upsert_entry(entries, entry_from_bookmark(bookmark, rel_path))
    save_index(paths, entries)

    typer.echo(f"Created {rel_path}")


@app.command("import-chrome")
def import_chrome_cmd(
    bookmarks_file: Path = typer.Option(..., "--bookmarks-file", exists=True, file_okay=True, dir_okay=False),
    profile_name: str = typer.Option("Default", "--profile-name", help="Chrome profile label (for logs)."),
    dedupe: DedupeMode = typer.Option(DedupeMode.both, "--dedupe", help="Deduplication strategy."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Print changes without writing."),
    backup_before: bool = typer.Option(
        True,
        "--backup-before/--no-backup-before",
        help="Create a backup in data/backups before applying import changes.",
    ),
    watch: bool = typer.Option(False, "--watch", help="Continuously poll the Bookmarks file and import on change."),
    interval: int = typer.Option(60, "--interval", min=1, help="Watch poll interval in seconds."),
    root: Path = typer.Option(Path("."), "--root", help="Project root directory."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    paths = init_storage(root)
    config = _load_app_config(paths.root)
    if watch:
        if backup_before and not dry_run:
            typer.secho("Watch mode skips auto-backups. Use `link-garden backup` periodically.", fg=typer.colors.YELLOW)
        typer.echo(f"Watching {bookmarks_file} every {interval}s (dedupe={dedupe.value}, dry_run={dry_run}). Press Ctrl+C to stop.")
        try:
            watch_import_loop(
                paths=paths,
                bookmarks_file=bookmarks_file,
                dedupe=dedupe,
                interval_seconds=interval,
                dry_run=dry_run,
                profile_name=profile_name,
                default_visibility=config.default_visibility,
            )
        except KeyboardInterrupt:
            typer.echo("Watch stopped.")
        return

    if dry_run:
        stats = import_chrome_bookmarks(
            paths=paths,
            bookmarks_file=bookmarks_file,
            dedupe=dedupe,
            dry_run=True,
            profile_name=profile_name,
            default_visibility=config.default_visibility,
        )
    else:
        preview = import_chrome_bookmarks(
            paths=paths,
            bookmarks_file=bookmarks_file,
            dedupe=dedupe,
            dry_run=True,
            profile_name=profile_name,
            default_visibility=config.default_visibility,
        )
        pending_mutations = preview.created + preview.updated
        if pending_mutations > 0 and backup_before:
            _create_auto_backup(paths, reason="before import-chrome")
        if pending_mutations == 0:
            stats = preview
        else:
            stats = import_chrome_bookmarks(
                paths=paths,
                bookmarks_file=bookmarks_file,
                dedupe=dedupe,
                dry_run=False,
                profile_name=profile_name,
                default_visibility=config.default_visibility,
            )

    mode_label = "DRY RUN " if dry_run else ""
    typer.echo(f"{mode_label}Import complete: total={stats.total} created={stats.created} updated={stats.updated} skipped={stats.skipped}")


@app.command("list")
def list_cmd(
    tag: str | None = typer.Option(None, "--tag", help="Filter by tag."),
    search: str | None = typer.Option(None, "--search", help="Text search across title/url/tags/folder/description/notes."),
    folder: str | None = typer.Option(None, "--folder", help="Filter by folder prefix."),
    visibility: Visibility | None = typer.Option(None, "--visibility", help="Filter by visibility."),
    include_archived: bool = typer.Option(False, "--include-archived", help="Include archived bookmarks."),
    recent: int | None = typer.Option(None, "--recent", min=1, help="Shortcut for most recent N bookmarks."),
    limit: int = typer.Option(50, "--limit", min=1, help="Maximum rows to print."),
    format: ListOutputFormat = typer.Option(ListOutputFormat.table, "--format", help="Output format."),
    root: Path = typer.Option(Path("."), "--root", help="Project root directory."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    paths = init_storage(root)
    entries = load_index(paths)

    filtered = search_entries(
        entries,
        search=search,
        tag=tag,
        folder=folder,
        visibility=visibility,
        include_archived=include_archived,
    )
    effective_limit = recent if recent is not None else limit
    filtered = filtered[:effective_limit]
    if format == ListOutputFormat.json:
        payload = [entry.model_dump(mode="json") for entry in filtered]
        typer.echo(json.dumps(payload, indent=2))
        return
    if not filtered:
        typer.echo("No bookmarks found.")
        return

    if format == ListOutputFormat.tsv:
        typer.echo("id\ttitle\tfolder\tvisibility")
        for entry in filtered:
            typer.echo(f"{entry.id}\t{entry.title}\t{entry.folder_path or '-'}\t{entry.visibility.value}")
        return

    header = f"{'ID':<12} {'TITLE':<48} {'FOLDER':<28} {'VISIBILITY':<10}"
    typer.echo(header)
    typer.echo("-" * len(header))
    for entry in filtered:
        typer.echo(
            f"{_clip(entry.id, 12):<12} {_clip(entry.title, 48):<48} {_clip(entry.folder_path or '-', 28):<28} {entry.visibility.value:<10}"
        )


@app.command("duplicates")
def duplicates_cmd(
    by: str = typer.Option("url", "--by", help="Duplicate strategy. Currently supports: url"),
    include_archived: bool = typer.Option(False, "--include-archived", help="Include archived bookmarks."),
    repo_dir: Path = typer.Option(Path("."), "--repo-dir", help="Project repository root."),
    data_dir: Path | None = typer.Option(None, "--data-dir", help="Optional data directory override."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    if by != "url":
        raise typer.BadParameter("Only --by url is supported in v0.2")

    paths = init_storage(repo_dir, data_dir=data_dir)
    entries = load_index(paths)
    if not include_archived:
        entries = [entry for entry in entries if not entry.archived]
    groups = find_duplicate_entries(entries)
    if not groups:
        typer.echo("No duplicates found.")
        return

    typer.echo(f"Found {len(groups)} duplicate URL group(s):")
    for key, group in sorted(groups.items()):
        typer.echo(f"- {key}")
        for entry in sorted(group, key=lambda item: item.saved_at, reverse=True):
            typer.echo(f"  {entry.id}\t{entry.saved_at}\t{entry.title}\t{entry.path}")


@app.command("edit")
def edit_cmd(
    id_or_path: str = typer.Argument(..., help="Bookmark id (preferred) or markdown file path."),
    editor: str | None = typer.Option(None, "--editor", help="Editor command override."),
    repo_dir: Path = typer.Option(Path("."), "--repo-dir", help="Project repository root."),
    data_dir: Path | None = typer.Option(None, "--data-dir", help="Optional data directory override."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    def _execute() -> None:
        paths = init_storage(repo_dir, data_dir=data_dir)
        record = resolve_record(paths, id_or_path)
        _run_editor(record.path, editor_override=editor)

        bookmark = read_bookmark_file(record.path)
        synced = persist_record(
            paths,
            BookmarkRecord(bookmark=bookmark, path=record.path, rel_path=record.rel_path, entry=record.entry),
            rename_file=False,
        )
        tags_text = ",".join(synced.bookmark.tags) if synced.bookmark.tags else "-"
        typer.echo(
            f"Updated {synced.bookmark.id}: title={synced.bookmark.title!r} tags={tags_text} archived={synced.bookmark.archived}"
        )

    _run_cli_safe(_execute)


@app.command("tag")
def tag_cmd(
    bookmark_id: str = typer.Argument(..., help="Bookmark id."),
    add: str = typer.Option("", "--add", help="Comma-separated tags to add."),
    remove: str = typer.Option("", "--remove", help="Comma-separated tags to remove."),
    set_tags: str = typer.Option("", "--set", help="Replace tags with comma-separated list."),
    repo_dir: Path = typer.Option(Path("."), "--repo-dir", help="Project repository root."),
    data_dir: Path | None = typer.Option(None, "--data-dir", help="Optional data directory override."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    if not (add.strip() or remove.strip() or set_tags.strip()):
        raise typer.BadParameter("Provide at least one of --add, --remove, or --set")

    def _execute() -> None:
        paths = init_storage(repo_dir, data_dir=data_dir)
        record = load_record_by_id(paths, bookmark_id)

        tags = record.bookmark.tags
        if set_tags.strip():
            tags = split_tags(set_tags)
        if add.strip():
            tags = _merge_tags(tags, split_tags(add))
        if remove.strip():
            remove_set = {item.lower() for item in split_tags(remove)}
            tags = [item for item in tags if item.lower() not in remove_set]

        record.bookmark.tags = tags
        synced = persist_record(paths, record, rename_file=False)
        typer.echo(f"Updated tags for {synced.bookmark.id}: {','.join(synced.bookmark.tags) if synced.bookmark.tags else '-'}")

    _run_cli_safe(_execute)


@app.command("set-visibility")
def set_visibility_cmd(
    id: str | None = typer.Option(None, "--id", help="Bookmark id."),
    url: str | None = typer.Option(None, "--url", help="Bookmark URL (updates all normalized URL matches)."),
    visibility: Visibility = typer.Option(..., "--visibility", help="Visibility to apply."),
    yes: bool = typer.Option(False, "--yes", help="Confirm broad URL-based updates."),
    repo_dir: Path = typer.Option(Path("."), "--repo-dir", help="Project repository root."),
    data_dir: Path | None = typer.Option(None, "--data-dir", help="Optional data directory override."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    if bool(id) == bool(url):
        raise typer.BadParameter("Provide exactly one of --id or --url")

    def _execute() -> None:
        paths = init_storage(repo_dir, data_dir=data_dir)
        records: list[BookmarkRecord]
        if id:
            records = [load_record_by_id(paths, id)]
        else:
            assert url is not None
            records = find_records_by_url(paths, url, include_archived=True)
            if not records:
                raise typer.BadParameter(f"No bookmarks matched URL: {url}")
            if len(records) > 1 and not yes:
                typer.secho(f"Matched {len(records)} bookmarks for URL={url}.", fg=typer.colors.YELLOW, err=True)
                typer.echo("Preview:", err=True)
                for record in records[:5]:
                    typer.echo(f"- {record.bookmark.id}\t{record.bookmark.title}\t{record.rel_path}", err=True)
                if len(records) > 5:
                    typer.echo(f"- ... and {len(records) - 5} more", err=True)
                typer.secho("Re-run with --yes to apply changes to all matches.", fg=typer.colors.YELLOW, err=True)
                raise typer.Exit(code=1)

        for record in records:
            record.bookmark.visibility = visibility
            persist_record(paths, record, rename_file=False)

        target_label = f"id={id}" if id else f"url={url}"
        typer.echo(f"Updated visibility for {len(records)} bookmark(s) ({target_label}) -> {visibility.value}")

    _run_cli_safe(_execute)


@app.command("archive")
def archive_cmd(
    bookmark_id: str = typer.Argument(..., help="Bookmark id."),
    yes: bool = typer.Option(False, "--yes", help="Skip confirmation."),
    repo_dir: Path = typer.Option(Path("."), "--repo-dir", help="Project repository root."),
    data_dir: Path | None = typer.Option(None, "--data-dir", help="Optional data directory override."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    if not yes and not typer.confirm(f"Archive bookmark {bookmark_id}?"):
        raise typer.Abort()

    def _execute() -> None:
        paths = init_storage(repo_dir, data_dir=data_dir)
        record = load_record_by_id(paths, bookmark_id)
        record.bookmark.archived = True
        persist_record(paths, record, rename_file=False)
        typer.echo(f"Archived {bookmark_id}")

    _run_cli_safe(_execute)


@app.command("unarchive")
def unarchive_cmd(
    bookmark_id: str = typer.Argument(..., help="Bookmark id."),
    repo_dir: Path = typer.Option(Path("."), "--repo-dir", help="Project repository root."),
    data_dir: Path | None = typer.Option(None, "--data-dir", help="Optional data directory override."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    def _execute() -> None:
        paths = init_storage(repo_dir, data_dir=data_dir)
        record = load_record_by_id(paths, bookmark_id)
        record.bookmark.archived = False
        persist_record(paths, record, rename_file=False)
        typer.echo(f"Unarchived {bookmark_id}")

    _run_cli_safe(_execute)


@app.command("move")
def move_cmd(
    bookmark_id: str = typer.Argument(..., help="Bookmark id."),
    folder: str = typer.Option(..., "--folder", help="Folder path metadata (does not move file)."),
    rename_file: bool = typer.Option(False, "--rename-file", help="Optionally rename file deterministically."),
    repo_dir: Path = typer.Option(Path("."), "--repo-dir", help="Project repository root."),
    data_dir: Path | None = typer.Option(None, "--data-dir", help="Optional data directory override."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    def _execute() -> None:
        paths = init_storage(repo_dir, data_dir=data_dir)
        record = load_record_by_id(paths, bookmark_id)
        record.bookmark.folder_path = normalize_folder_path(folder)
        synced = persist_record(paths, record, rename_file=rename_file)
        typer.echo(f"Moved {bookmark_id} to folder={synced.bookmark.folder_path} file={synced.rel_path}")

    _run_cli_safe(_execute)


@app.command("enrich")
def enrich_cmd(
    id_or_url: str = typer.Argument(..., help="Bookmark id or URL."),
    timeout: float = typer.Option(5.0, "--timeout", min=0.1, help="Network timeout in seconds."),
    user_agent: str = typer.Option(DEFAULT_USER_AGENT, "--user-agent", help="HTTP user-agent."),
    no_network: bool = typer.Option(False, "--no-network", help="Disable network calls."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes only."),
    overwrite_title: bool = typer.Option(False, "--overwrite-title", help="Overwrite title when metadata has title."),
    all_matches: bool = typer.Option(False, "--all", help="When URL matches multiple bookmarks, enrich all."),
    repo_dir: Path = typer.Option(Path("."), "--repo-dir", help="Project repository root."),
    data_dir: Path | None = typer.Option(None, "--data-dir", help="Optional data directory override."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    paths = init_storage(repo_dir, data_dir=data_dir)

    records: list[BookmarkRecord]
    if _looks_like_url(id_or_url):
        records = find_records_by_url(paths, id_or_url, include_archived=True)
        if not records:
            raise typer.BadParameter(f"No bookmarks matched URL: {id_or_url}")
        if len(records) > 1 and not all_matches:
            raise typer.BadParameter(f"URL matched {len(records)} bookmarks. Re-run with --all to enrich all matches.")
    else:
        records = [load_record_by_id(paths, id_or_url)]

    updated = 0
    failed = 0
    for record in records:
        metadata = fetch_url_metadata(
            record.bookmark.url,
            timeout=timeout,
            user_agent=user_agent,
            no_network=no_network,
        )
        if not metadata.ok:
            failed += 1
            typer.echo(f"FAILED {record.bookmark.id}: {metadata.error}")
            continue

        preview_title = metadata.title or record.bookmark.title
        preview_description = metadata.description or record.bookmark.description
        if dry_run:
            preview_description_text = (preview_description[:80] if preview_description else "")
            typer.echo(
                f"DRY RUN {record.bookmark.id}: title={preview_title!r} description={preview_description_text!r}"
            )
            updated += 1
            continue

        apply_enrichment_to_bookmark(record.bookmark, metadata, overwrite_title=overwrite_title)
        persist_record(paths, record, rename_file=False)
        updated += 1
        typer.echo(f"Enriched {record.bookmark.id}: title={record.bookmark.title!r}")

    typer.echo(f"Enrichment complete: matched={len(records)} updated={updated} failed={failed}")


@app.command("export")
def export_cmd(
    format: ExportFormat = typer.Option(..., "--format", help="Export format."),
    out: Path = typer.Option(..., "--out", help="Output directory."),
    scope: ExportScope | None = typer.Option(None, "--scope", help="Export scope."),
    dangerous_all: bool = typer.Option(
        False,
        "--dangerous-all",
        help="Required with --scope all to confirm private data export.",
    ),
    root: Path = typer.Option(Path("."), "--root", help="Project root directory."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    paths = init_storage(root)
    config = _load_app_config(paths.root)
    effective_scope = scope or config.export_default_scope
    _warn_if_non_public_scope(effective_scope, context="Export")
    try:
        output_file = export_bookmarks(
            paths,
            export_format=format,
            out_dir=out,
            scope=effective_scope,
            dangerous_all=dangerous_all,
        )
    except ValueError as exc:
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(f"Exported {format.value} to {output_file} (scope={effective_scope.value})")


@app.command("backup")
def backup_cmd(
    out: Path = typer.Option(..., "--out", help="Backup output directory."),
    format: BackupFormat = typer.Option(BackupFormat.zip, "--format", help="Backup format."),
    include_index: bool = typer.Option(True, "--include-index/--no-include-index", help="Include data/index.json."),
    repo_dir: Path = typer.Option(Path("."), "--repo-dir", help="Project repository root."),
    data_dir: Path | None = typer.Option(None, "--data-dir", help="Optional data directory override."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    paths = init_storage(repo_dir, data_dir=data_dir)
    report = create_backup(paths=paths, out_dir=out, backup_format=format, include_index=include_index)
    typer.echo(f"Backup created: {report.output_path} (files={report.file_count})")


@app.command("rebuild-index")
def rebuild_index_cmd(
    repo_dir: Path = typer.Option(Path("."), "--repo-dir", help="Project repository root."),
    data_dir: Path | None = typer.Option(None, "--data-dir", help="Optional data directory override."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Scan and validate without writing index.json."),
    yes: bool = typer.Option(False, "--yes", help="Confirm overwriting index.json when parse errors are present."),
    backup_before: bool = typer.Option(
        True,
        "--backup-before/--no-backup-before",
        help="Create a backup in data/backups before replacing index.json.",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    resolved_repo_dir, resolved_data_dir = _resolve_paths(repo_dir, data_dir)
    paths = init_storage(resolved_repo_dir, data_dir=resolved_data_dir)
    report = rebuild_index_with_report(paths, dry_run=True)
    try:
        existing_entries = load_index(paths)
    except Exception:
        existing_entries = []
    mutation_pending = _entries_will_change(existing_entries, report.entries)

    mode_prefix = "DRY RUN " if dry_run else ""
    typer.echo(
        f"{mode_prefix}Rebuild complete: scanned={report.scanned} indexed={report.indexed} skipped={report.skipped} errors={len(report.errors)}"
    )
    for issue in report.errors:
        typer.echo(f"- {issue.path}: {issue.error}")
    if dry_run:
        return

    if report.errors:
        rebuild_path = paths.data_dir / "index.rebuild.json"
        save_index_file(rebuild_path, report.entries)
        typer.echo(f"Wrote rebuilt candidate index to {relative_to_root(paths, rebuild_path)}")
        if not yes:
            typer.secho(
                "Index left unchanged due to parse errors. Re-run with --yes to overwrite data/index.json.",
                fg=typer.colors.YELLOW,
                err=True,
            )
            return
    if not mutation_pending:
        typer.echo("Index already up to date. No changes written.")
        return
    if backup_before:
        _create_auto_backup(paths, reason="before rebuild-index")
    save_index(paths, report.entries)
    typer.echo("index.json updated.")


@app.command("serve")
def serve_cmd(
    host: str | None = typer.Option(None, "--host", help="Server host (defaults to config/server secure default)."),
    port: int = typer.Option(8000, "--port", min=1, max=65535, help="Server port."),
    repo_dir: Path = typer.Option(Path("."), "--repo-dir", help="Project repository root."),
    data_dir: Path | None = typer.Option(None, "--data-dir", help="Optional data directory override."),
    export_mode: ExportScope | None = typer.Option(None, "--export-mode", help="Scope to export before serving."),
    dangerous_all: bool = typer.Option(False, "--dangerous-all", help="Required with --export-mode all."),
    static_dir: Path | None = typer.Option(
        None,
        "--static-dir",
        help="Serve an existing exported static directory instead of generating a temp export.",
    ),
    allow_remote: bool = typer.Option(False, "--allow-remote", help="Required when binding to non-localhost."),
    open_browser: bool = typer.Option(False, "--open-browser/--no-open-browser", help="Open browser on startup."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    resolved_repo_dir, resolved_data_dir = _resolve_paths(repo_dir, data_dir)
    paths = init_storage(resolved_repo_dir, data_dir=resolved_data_dir)
    config = _load_app_config(paths.root)
    effective_host = host or config.server_bind_host
    effective_scope = export_mode or config.serve_default_scope

    if not is_local_host(effective_host):
        if config.require_allow_remote and not allow_remote:
            raise typer.BadParameter(
                f"Refusing to bind to {effective_host}. Re-run with --allow-remote for explicit opt-in.",
            )
        typer.secho(
            f"WARNING: Binding to non-localhost address ({effective_host}). Ensure reverse proxy auth/firewall is enabled.",
            fg=typer.colors.YELLOW,
            err=True,
        )

    _warn_if_non_public_scope(effective_scope, context="Serve export")

    if static_dir is not None:
        target_dir = static_dir.resolve()
        if not target_dir.exists() or not target_dir.is_dir():
            raise typer.BadParameter(f"Static directory does not exist: {target_dir}")
        _serve_directory(target_dir, effective_host, port, open_browser)
        return

    with tempfile.TemporaryDirectory(prefix="link-garden-serve-") as temp_dir:
        export_dir = Path(temp_dir)
        try:
            output_file = export_bookmarks(
                paths,
                export_format=ExportFormat.html,
                out_dir=export_dir,
                scope=effective_scope,
                dangerous_all=dangerous_all,
            )
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
        typer.echo(f"Prepared temporary export: {output_file} (scope={effective_scope.value})")
        _serve_directory(export_dir, effective_host, port, open_browser)


@app.command("doctor")
def doctor_cmd(
    root: Path = typer.Option(Path("."), "--root", help="Project root directory."),
    rebuild_index: bool = typer.Option(False, "--rebuild-index", help="Rebuild index from Markdown files first."),
    fix: bool = typer.Option(False, "--fix", help="Apply safe fixes (currently: rebuild index)."),
    backup_before: bool = typer.Option(
        True,
        "--backup-before/--no-backup-before",
        help="Create a backup in data/backups before applying --fix changes.",
    ),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    paths = init_storage(root)

    if rebuild_index:
        report = rebuild_index_with_report(paths)
        typer.echo(
            f"Rebuilt index (prefer `rebuild-index`): scanned={report.scanned} indexed={report.indexed} skipped={report.skipped} errors={len(report.errors)}"
        )
        for issue in report.errors:
            typer.echo(f"- {issue.path}: {issue.error}")

    if fix:
        preview = rebuild_index_with_report(paths, dry_run=True)
        try:
            existing_entries = load_index(paths)
        except Exception:
            existing_entries = []
        mutation_pending = _entries_will_change(existing_entries, preview.entries)
        if mutation_pending:
            if backup_before:
                _create_auto_backup(paths, reason="before doctor --fix")
            fixed_indexed, fixed_skipped = doctor_fix(paths)
            typer.echo(f"Doctor fix applied: rebuilt index (indexed={fixed_indexed}, skipped={fixed_skipped})")
        else:
            typer.echo("Doctor fix skipped: index already consistent.")

    report = run_doctor(paths)
    typer.echo(f"Doctor summary: scanned_files={report.scanned_files} index_entries={report.index_entries} issues={len(report.issues)}")
    if report.issues:
        for issue in report.issues:
            location = f" [{issue.path}]" if issue.path else ""
            typer.echo(f"- {issue.code}{location}: {issue.message}")
        raise typer.Exit(code=1)

    typer.echo("Doctor check passed.")


@hub_app.command("export")
def hub_export_cmd(
    out: Path = typer.Option(..., "--out", help="Output directory for generated hub page."),
    root: Path = typer.Option(Path("."), "--root", help="Project root containing hub.yaml."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    output_file = export_hub_directory(root=root, out_dir=out)
    typer.echo(f"Hub export created at {output_file}")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
