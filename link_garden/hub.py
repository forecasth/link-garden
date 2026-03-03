from __future__ import annotations

from html import escape
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field


class HubEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    url: str
    description: str
    tags: list[str] = Field(default_factory=list)
    contact: str | None = None


class HubManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entries: list[HubEntry] = Field(default_factory=list)


def load_hub_manifest(root: Path) -> HubManifest:
    hub_file = root / "hub.yaml"
    if not hub_file.exists():
        raise FileNotFoundError(f"hub.yaml not found at {hub_file}")
    payload = yaml.safe_load(hub_file.read_text(encoding="utf-8")) or {}
    return HubManifest.model_validate(payload)


def export_hub_directory(root: Path, out_dir: Path) -> Path:
    manifest = load_hub_manifest(root.resolve())
    out_dir.mkdir(parents=True, exist_ok=True)
    output_file = out_dir / "index.html"

    entries = sorted(manifest.entries, key=lambda item: item.name.lower())
    lines = [
        "<!doctype html>",
        "<html lang=\"en\">",
        "<head>",
        "  <meta charset=\"utf-8\" />",
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />",
        "  <title>Link Garden Hub Directory</title>",
        "  <style>",
        "    body { margin: 2rem auto; max-width: 900px; font-family: Georgia, serif; line-height: 1.6; padding: 0 1rem; }",
        "    .notice { border: 1px solid #bb5225; background: #fff1ea; color: #6f2c11; padding: 0.75rem; margin-bottom: 1rem; }",
        "    .item { border-top: 1px solid #ddd; padding: 1rem 0; }",
        "    .meta { color: #444; font-size: 0.9rem; }",
        "  </style>",
        "</head>",
        "<body>",
        "  <h1>Link Garden Hub</h1>",
        "  <div class=\"notice\">This page is public. Only list gardens and contact details you are comfortable sharing.</div>",
    ]

    if not entries:
        lines.append("  <p>No entries yet. Add entries to hub.yaml and rerun <code>link-garden hub export</code>.</p>")
    else:
        lines.append("  <div>")
        for entry in entries:
            tags = ", ".join(entry.tags) if entry.tags else "-"
            lines.extend(
                [
                    "    <section class=\"item\">",
                    f"      <h2><a href=\"{escape(entry.url)}\">{escape(entry.name)}</a></h2>",
                    f"      <p>{escape(entry.description)}</p>",
                    f"      <div class=\"meta\">tags: {escape(tags)}</div>",
                    f"      <div class=\"meta\">url: {escape(entry.url)}</div>",
                ]
            )
            if entry.contact:
                lines.append(f"      <div class=\"meta\">contact: {escape(entry.contact)}</div>")
            lines.append("    </section>")
        lines.append("  </div>")

    lines.extend(["</body>", "</html>"])
    output_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return output_file
