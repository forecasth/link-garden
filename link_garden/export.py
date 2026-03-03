from __future__ import annotations

import json
from enum import Enum
from html import escape
from pathlib import Path

from link_garden.security import ExportScope, visibility_allowed
from link_garden.storage import StoragePaths, load_all_bookmarks, relative_to_root


class ExportFormat(str, Enum):
    markdown = "markdown"
    json = "json"
    html = "html"


def export_bookmarks(
    paths: StoragePaths,
    export_format: ExportFormat,
    out_dir: Path,
    *,
    scope: ExportScope = ExportScope.public,
    dangerous_all: bool = False,
) -> Path:
    if scope == ExportScope.all and not dangerous_all:
        raise ValueError("scope=all requires dangerous_all=True")

    out_dir.mkdir(parents=True, exist_ok=True)
    bookmarks = load_all_bookmarks(paths)
    bookmarks.sort(key=lambda item: item[0].saved_at, reverse=True)
    filtered = [(bookmark, path) for bookmark, path in bookmarks if visibility_allowed(bookmark.visibility, scope)]

    if export_format == ExportFormat.markdown:
        output_path = out_dir / "bookmarks.md"
        lines = ["# Link Garden Export", "", f"scope: {scope.value}", ""]
        for bookmark, bookmark_path in filtered:
            tags = ", ".join(bookmark.tags) if bookmark.tags else "-"
            rel_path = relative_to_root(paths, bookmark_path)
            lines.append(
                f"- [{bookmark.title}]({bookmark.url}) | visibility: {bookmark.visibility.value} | saved_at: {bookmark.saved_at} | tags: {tags} | folder: {bookmark.folder_path or '-'} | file: {rel_path}"
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
        payload = [bookmark.model_dump(mode="json") for bookmark, _ in filtered]
        output_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return output_path

    output_path = out_dir / "index.html"
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
        "    .warning { border: 1px solid #bb5225; background: #fff1ea; color: #6f2c11; padding: 0.75rem; margin-bottom: 1rem; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>Link Garden Export</h1>",
        f"  <p class=\"meta\">scope={escape(scope.value)}</p>",
    ]
    if scope != ExportScope.public:
        lines.append("  <div class=\"warning\">This export includes non-public entries. Do not publish it openly.</div>")
    lines.append("  <ul>")
    for bookmark, _ in filtered:
        tags = ", ".join(bookmark.tags) if bookmark.tags else "-"
        lines.extend(
            [
                "    <li>",
                f"      <a href=\"{escape(bookmark.url)}\">{escape(bookmark.title)}</a>",
                (
                    "      <div class=\"meta\">"
                    f"visibility={escape(bookmark.visibility.value)} | saved_at={escape(bookmark.saved_at)} | "
                    f"tags={escape(tags)} | folder={escape(bookmark.folder_path or '-')}"
                    "</div>"
                ),
                f"      <div>{escape(bookmark.notes or bookmark.body or '')}</div>",
                "    </li>",
            ]
        )
    lines.extend(["  </ul>", "</body>", "</html>"])
    html_text = "\n".join(lines) + "\n"
    output_path.write_text(html_text, encoding="utf-8")

    # Backward-compatible secondary filename for older docs/scripts.
    (out_dir / "bookmarks.html").write_text(html_text, encoding="utf-8")
    return output_path
