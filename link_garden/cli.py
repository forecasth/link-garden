from __future__ import annotations

import logging
from pathlib import Path

import typer

from link_garden.chrome_import import DedupeMode, import_chrome_bookmarks
from link_garden.export import ExportFormat, export_bookmarks
from link_garden.index import (
    build_lookup_maps,
    entry_from_bookmark,
    index_paths,
    load_index,
    rebuild_index_from_files,
    save_index,
    upsert_entry,
)
from link_garden.model import Bookmark
from link_garden.storage import init_storage, list_bookmark_files, read_bookmark_file, relative_to_root, write_bookmark
from link_garden.utils import generate_short_id, normalize_folder_path, normalize_url, split_tags, utc_now_iso

logger = logging.getLogger(__name__)
app = typer.Typer(help="Local-first bookmark + notes knowledge garden.")


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s %(message)s")


@app.command("init")
def init_cmd(
    directory: Path = typer.Argument(..., help="Project directory to initialize."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    paths = init_storage(directory)
    typer.echo(f"Initialized link-garden at {paths.root}")
    typer.echo(f"- bookmarks: {paths.bookmarks_dir}")
    typer.echo(f"- index: {paths.index_file}")


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
        body=notes.strip(),
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
    root: Path = typer.Option(Path("."), "--root", help="Project root directory."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    paths = init_storage(root)
    stats = import_chrome_bookmarks(
        paths=paths,
        bookmarks_file=bookmarks_file,
        dedupe=dedupe,
        dry_run=dry_run,
        profile_name=profile_name,
    )

    mode_label = "DRY RUN " if dry_run else ""
    typer.echo(f"{mode_label}Import complete: total={stats.total} created={stats.created} updated={stats.updated} skipped={stats.skipped}")


@app.command("list")
def list_cmd(
    tag: str | None = typer.Option(None, "--tag", help="Filter by tag."),
    search: str | None = typer.Option(None, "--search", help="Text search in title/url/tags/folder."),
    folder: str | None = typer.Option(None, "--folder", help="Filter by folder prefix."),
    limit: int = typer.Option(50, "--limit", min=1, help="Maximum rows to print."),
    root: Path = typer.Option(Path("."), "--root", help="Project root directory."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    paths = init_storage(root)
    entries = load_index(paths)

    filtered = entries
    if tag:
        tag_l = tag.lower()
        filtered = [entry for entry in filtered if any(existing.lower() == tag_l for existing in entry.tags)]

    if folder:
        folder_prefix = normalize_folder_path(folder)
        filtered = [entry for entry in filtered if normalize_folder_path(entry.folder_path).startswith(folder_prefix)]

    if search:
        needle = search.lower().strip()
        filtered_search: list = []
        for entry in filtered:
            haystack = " ".join([entry.title, entry.url, " ".join(entry.tags), entry.folder_path]).lower()
            if needle in haystack:
                filtered_search.append(entry)
        filtered = filtered_search

    filtered = sorted(filtered, key=lambda item: item.saved_at, reverse=True)[:limit]
    if not filtered:
        typer.echo("No bookmarks found.")
        return

    for entry in filtered:
        tag_text = ",".join(entry.tags) if entry.tags else "-"
        folder_text = entry.folder_path or "-"
        typer.echo(f"{entry.saved_at}\t{entry.title}\t{entry.url}\t{tag_text}\t{folder_text}")


@app.command("export")
def export_cmd(
    format: ExportFormat = typer.Option(..., "--format", help="Export format."),
    out: Path = typer.Option(..., "--out", help="Output directory."),
    root: Path = typer.Option(Path("."), "--root", help="Project root directory."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    paths = init_storage(root)
    output_file = export_bookmarks(paths, export_format=format, out_dir=out)
    typer.echo(f"Exported {format.value} to {output_file}")


@app.command("doctor")
def doctor_cmd(
    root: Path = typer.Option(Path("."), "--root", help="Project root directory."),
    rebuild_index: bool = typer.Option(False, "--rebuild-index", help="Rebuild index from Markdown files first."),
    verbose: bool = typer.Option(False, "--verbose", help="Enable verbose logging."),
) -> None:
    _configure_logging(verbose)
    paths = init_storage(root)

    if rebuild_index:
        rebuilt = rebuild_index_from_files(paths)
        typer.echo(f"Rebuilt index with {len(rebuilt)} entries.")

    entries = load_index(paths)
    issues: list[str] = []

    seen_ids: set[str] = set()
    seen_urls: dict[str, str] = {}
    by_guid, _ = build_lookup_maps(entries)
    if len(by_guid) < len([entry for entry in entries if entry.chrome_guid]):
        issues.append("Duplicate chrome_guid values found in index.")

    for entry in entries:
        if entry.id in seen_ids:
            issues.append(f"Duplicate id in index: {entry.id}")
        seen_ids.add(entry.id)

        url_key = normalize_url(entry.url)
        if url_key in seen_urls and seen_urls[url_key] != entry.id:
            issues.append(f"Duplicate normalized URL in index: {entry.url}")
        seen_urls[url_key] = entry.id

        path = (paths.root / entry.path).resolve()
        if not path.exists():
            issues.append(f"Missing bookmark file: {entry.path}")
            continue
        try:
            bookmark = read_bookmark_file(path)
        except Exception as exc:  # noqa: BLE001
            issues.append(f"Unreadable bookmark file ({entry.path}): {exc}")
            continue
        if bookmark.id != entry.id:
            issues.append(f"ID mismatch for {entry.path}: index={entry.id} file={bookmark.id}")

    indexed_paths = index_paths(entries, paths.root)
    file_paths = {path.resolve() for path in list_bookmark_files(paths)}
    orphan_files = sorted(file_paths - indexed_paths)
    for orphan in orphan_files:
        issues.append(f"Bookmark file not present in index: {relative_to_root(paths, orphan)}")

    if issues:
        typer.echo("Doctor found issues:")
        for issue in issues:
            typer.echo(f"- {issue}")
        raise typer.Exit(code=1)

    typer.echo("Doctor check passed. Index and files are consistent.")


def main() -> None:
    app()


if __name__ == "__main__":
    main()
