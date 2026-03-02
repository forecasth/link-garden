from __future__ import annotations

import shutil
import tarfile
import zipfile
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import Enum
from pathlib import Path

from link_garden.storage import StoragePaths


class BackupFormat(str, Enum):
    zip = "zip"
    tar = "tar"
    copy = "copy"


@dataclass
class BackupReport:
    output_path: Path
    file_count: int


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _collect_files(paths: StoragePaths, include_index: bool) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for bookmark_file in sorted(paths.bookmarks_dir.glob("*.md")):
        files.append((bookmark_file.resolve(), f"data/bookmarks/{bookmark_file.name}"))
    if include_index and paths.index_file.exists():
        files.append((paths.index_file.resolve(), "data/index.json"))

    theme_file = (paths.root / "ui" / "theme.yaml").resolve()
    if theme_file.exists():
        files.append((theme_file, "ui/theme.yaml"))
    return files


def create_backup(
    *,
    paths: StoragePaths,
    out_dir: Path,
    backup_format: BackupFormat,
    include_index: bool = True,
) -> BackupReport:
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = _timestamp()
    files = _collect_files(paths, include_index=include_index)

    if backup_format == BackupFormat.copy:
        target_dir = out_dir / f"link-garden-backup-{stamp}"
        target_dir.mkdir(parents=True, exist_ok=True)
        for source, arcname in files:
            destination = target_dir / Path(arcname)
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, destination)
        return BackupReport(output_path=target_dir, file_count=len(files))

    if backup_format == BackupFormat.zip:
        target_zip = out_dir / f"link-garden-backup-{stamp}.zip"
        with zipfile.ZipFile(target_zip, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source, arcname in files:
                archive.write(source, arcname=arcname)
        return BackupReport(output_path=target_zip, file_count=len(files))

    target_tar = out_dir / f"link-garden-backup-{stamp}.tar.gz"
    with tarfile.open(target_tar, "w:gz") as archive:
        for source, arcname in files:
            archive.add(source, arcname=arcname)
    return BackupReport(output_path=target_tar, file_count=len(files))
