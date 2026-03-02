from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from link_garden.index import find_duplicate_entries, load_index, rebuild_index_with_report
from link_garden.storage import StoragePaths, list_bookmark_files, read_bookmark_file, relative_to_root
from link_garden.utils import normalize_url


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

    return report


def doctor_fix(paths: StoragePaths) -> tuple[int, int]:
    report = rebuild_index_with_report(paths, dry_run=False)
    return report.indexed, report.skipped
