from __future__ import annotations

import json
from enum import Enum
from html import escape
from pathlib import Path

from link_garden.storage import StoragePaths, load_all_bookmarks, relative_to_root


class ExportFormat(str, Enum):
    markdown = "markdown"
    json = "json"
    html = "html"


def export_bookmarks(paths: StoragePaths, export_format: ExportFormat, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    bookmarks = load_all_bookmarks(paths)
    bookmarks.sort(key=lambda item: item[0].saved_at, reverse=True)

    if export_format == ExportFormat.markdown:
        output_path = out_dir / "bookmarks.md"
        lines = ["# Link Garden Export", ""]
        for bookmark, bookmark_path in bookmarks:
            tags = ", ".join(bookmark.tags) if bookmark.tags else "-"
            rel_path = relative_to_root(paths, bookmark_path)
            lines.append(
                f"- [{bookmark.title}]({bookmark.url}) | saved_at: {bookmark.saved_at} | tags: {tags} | folder: {bookmark.folder_path or '-'} | file: {rel_path}"
            )
            if bookmark.notes:
                lines.append(f"  notes: {bookmark.notes}")
            if bookmark.body:
                body = bookmark.body.replace("\n", " ")
                lines.append(f"  body: {body}")
        output_path.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
        return output_path

    if export_format == ExportFormat.json:
        output_path = out_dir / "bookmarks.json"
        payload = [bookmark.model_dump(mode="json") for bookmark, _ in bookmarks]
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return output_path

    output_path = out_dir / "bookmarks.html"
    lines = [
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\" />",
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />",
        "  <title>Link Garden Export</title>",
        "  <style>",
        "    body { font-family: Georgia, serif; margin: 2rem auto; max-width: 900px; line-height: 1.5; padding: 0 1rem; }",
        "    li { margin-bottom: 1rem; }",
        "    .meta { color: #444; font-size: 0.9rem; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>Link Garden Export</h1>",
        "  <ul>",
    ]
    for bookmark, _ in bookmarks:
        tags = ", ".join(bookmark.tags) if bookmark.tags else "-"
        lines.extend(
            [
                "    <li>",
                f"      <a href=\"{escape(bookmark.url)}\">{escape(bookmark.title)}</a>",
                f"      <div class=\"meta\">saved_at={escape(bookmark.saved_at)} | tags={escape(tags)} | folder={escape(bookmark.folder_path or '-')}</div>",
                f"      <div>{escape(bookmark.notes or bookmark.body or '')}</div>",
                "    </li>",
            ]
        )
    lines.extend(["  </ul>", "</body>", "</html>"])
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_path
