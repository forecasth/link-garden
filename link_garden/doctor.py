from __future__ import annotations

import os
import stat
from dataclasses import dataclass, field
from pathlib import Path

from link_garden.config import load_config
from link_garden.index import find_duplicate_entries, load_index, rebuild_index_with_report
from link_garden.security import ExportScope, Visibility, is_local_host
from link_garden.storage import StoragePaths, list_bookmark_files, read_bookmark_file, relative_to_root
from link_garden.utils import normalize_url

EXPORT_SCAN_DIRS = ("exports", "export")


@dataclass
class DoctorIssue:
    code: str
    message: str
    path: str | None = None


@dataclass
class DoctorReport:
    scanned_files: int = 0
    index_entries: int = 0
    issues: list[DoctorIssue] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.issues


def run_doctor(paths: StoragePaths) -> DoctorReport:
    report = DoctorReport()
    _check_configuration(paths, report)
    _check_data_permissions(paths, report)

    try:
        entries = load_index(paths)
    except Exception as exc:  # noqa: BLE001
        report.issues.append(DoctorIssue(code="invalid_index", message=f"Failed to load index: {exc}", path="data/index.json"))
        entries = []
    report.index_entries = len(entries)

    seen_entry_ids: set[str] = set()
    seen_urls: dict[str, str] = {}
    for entry in entries:
        if entry.id in seen_entry_ids:
            report.issues.append(DoctorIssue(code="duplicate_id", message=f"Duplicate id in index: {entry.id}", path=entry.path))
        seen_entry_ids.add(entry.id)

        url_key = normalize_url(entry.url)
        previous = seen_urls.get(url_key)
        if previous and previous != entry.id:
            report.issues.append(DoctorIssue(code="duplicate_url", message=f"Duplicate normalized URL in index: {entry.url}", path=entry.path))
        seen_urls[url_key] = entry.id

        path = (paths.root / entry.path).resolve()
        if not path.exists():
            report.issues.append(DoctorIssue(code="missing_file", message=f"Index entry file missing: {entry.path}", path=entry.path))

    entry_path_set = {(paths.root / entry.path).resolve() for entry in entries}
    bookmark_files = list_bookmark_files(paths)
    report.scanned_files = len(bookmark_files)
    seen_file_ids: set[str] = set()
    for bookmark_file in bookmark_files:
        rel_path = relative_to_root(paths, bookmark_file)
        try:
            bookmark = read_bookmark_file(bookmark_file)
        except Exception as exc:  # noqa: BLE001
            report.issues.append(DoctorIssue(code="invalid_frontmatter", message=f"Invalid YAML/frontmatter: {exc}", path=rel_path))
            continue

        if not bookmark.id:
            report.issues.append(DoctorIssue(code="missing_field", message="Missing required field: id", path=rel_path))
        if not bookmark.url:
            report.issues.append(DoctorIssue(code="missing_field", message="Missing required field: url", path=rel_path))
        if not bookmark.saved_at:
            report.issues.append(DoctorIssue(code="missing_field", message="Missing required field: saved_at", path=rel_path))

        if bookmark.id in seen_file_ids:
            report.issues.append(DoctorIssue(code="duplicate_file_id", message=f"Duplicate id across markdown files: {bookmark.id}", path=rel_path))
        seen_file_ids.add(bookmark.id)

        if bookmark_file.resolve() not in entry_path_set:
            report.issues.append(DoctorIssue(code="orphan_file", message=f"Bookmark file missing from index: {rel_path}", path=rel_path))

    duplicates = find_duplicate_entries(entries)
    for normalized, grouped in sorted(duplicates.items()):
        ids = ", ".join(item.id for item in grouped)
        report.issues.append(DoctorIssue(code="duplicate_url_group", message=f"Duplicate URL group ({normalized}) ids={ids}"))

    _check_export_for_private_entries(paths, report)

    return report


def doctor_fix(paths: StoragePaths) -> tuple[int, int]:
    report = rebuild_index_with_report(paths, dry_run=False)
    return report.indexed, report.skipped


def _check_configuration(paths: StoragePaths, report: DoctorReport) -> None:
    config, warnings = load_config(paths.root)
    for warning in warnings:
        report.issues.append(
            DoctorIssue(
                code="config_warning",
                message=f"{warning} Fix config.yaml and rerun doctor.",
                path="config.yaml",
            )
        )

    if config.default_visibility != Visibility.private:
        report.issues.append(
            DoctorIssue(
                code="insecure_default_visibility",
                message="default_visibility is not private. Set default_visibility: private in config.yaml.",
                path="config.yaml",
            )
        )
    if config.export_default_scope != ExportScope.public:
        report.issues.append(
            DoctorIssue(
                code="insecure_export_scope",
                message="export_default_scope should be public to avoid accidental leaks.",
                path="config.yaml",
            )
        )
    if config.serve_default_scope != ExportScope.public:
        report.issues.append(
            DoctorIssue(
                code="insecure_serve_scope",
                message="serve_default_scope should be public. Use explicit flags for broader scopes.",
                path="config.yaml",
            )
        )
    if not is_local_host(config.server_bind_host):
        report.issues.append(
            DoctorIssue(
                code="public_bind_config",
                message="server_bind_host is not localhost. Use 127.0.0.1 unless you explicitly proxy it behind auth.",
                path="config.yaml",
            )
        )
    if not config.require_allow_remote:
        report.issues.append(
            DoctorIssue(
                code="allow_remote_not_required",
                message="require_allow_remote is false. Set require_allow_remote: true to prevent accidental exposure.",
                path="config.yaml",
            )
        )


def _check_data_permissions(paths: StoragePaths, report: DoctorReport) -> None:
    if not paths.data_dir.exists():
        return

    if os.name == "posix":
        mode = stat.S_IMODE(paths.data_dir.stat().st_mode)
        if mode & stat.S_IRWXO:
            report.issues.append(
                DoctorIssue(
                    code="data_dir_permissions",
                    message=(
                        f"data directory permissions are too open ({oct(mode)}). "
                        "Recommended: chmod 700 data (and chmod 600 on sensitive files)."
                    ),
                    path=relative_to_root(paths, paths.data_dir),
                )
            )
        return

    # Best-effort check on non-posix systems.
    if not os.access(paths.data_dir, os.R_OK | os.W_OK):
        report.issues.append(
            DoctorIssue(
                code="data_dir_access",
                message="Current user cannot read/write the data directory. Check filesystem ACLs.",
                path=relative_to_root(paths, paths.data_dir),
            )
        )


def _check_export_for_private_entries(paths: StoragePaths, report: DoctorReport) -> None:
    private_urls: dict[str, str] = {}
    for bookmark_file in list_bookmark_files(paths):
        try:
            bookmark = read_bookmark_file(bookmark_file)
        except Exception:  # noqa: BLE001
            continue
        if bookmark.visibility == Visibility.private:
            private_urls[bookmark.url] = bookmark.id

    if not private_urls:
        return

    html_files: list[Path] = []
    for folder_name in EXPORT_SCAN_DIRS:
        export_dir = (paths.root / folder_name).resolve()
        if not export_dir.exists() or not export_dir.is_dir():
            continue
        html_files.extend(sorted(export_dir.rglob("*.html")))

    for html_file in sorted(html_files):
        try:
            html = html_file.read_text(encoding="utf-8", errors="ignore")
        except OSError as exc:
            report.issues.append(
                DoctorIssue(
                    code="export_read_error",
                    message=f"Failed to inspect exported HTML: {exc}",
                    path=relative_to_root(paths, html_file),
                )
            )
            continue

        for private_url, bookmark_id in private_urls.items():
            if private_url and private_url in html:
                report.issues.append(
                    DoctorIssue(
                        code="private_export_leak",
                        message=(
                            f"Private bookmark {bookmark_id} appears in exported HTML. "
                            "Re-export with --scope public."
                        ),
                        path=relative_to_root(paths, html_file),
                    )
                )
                break
