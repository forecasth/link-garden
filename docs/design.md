# Link Garden Design Notes

## Why file-based storage

The MVP stores each bookmark as Markdown with YAML frontmatter so data is:

- human-readable
- easy to back up
- easy to version with git
- portable across operating systems

## Data flow

1. CLI command creates or updates bookmark model.
2. Bookmark is persisted as one Markdown file under `data/bookmarks/`.
3. `data/index.json` is updated with a compact row for fast list/filter commands.
4. `doctor --rebuild-index` can reconstruct index from files if the index is stale or corrupted.
5. Export/serve always apply visibility scope filters (`public`, `unlisted`, `all`).

## Visibility model

- `private`: default, local-only.
- `unlisted`: opt-in export scope for semi-private sharing.
- `public`: safe for public export.

Config defaults live in repo-level `config.yaml`.

## Import behavior

Chrome import parses the local `Bookmarks` JSON recursively and turns URL nodes into bookmark files while preserving folder lineage in `folder_path`.

- `by_guid`: strongest dedupe when Chrome GUID exists.
- `by_url`: fallback for migrated or missing GUIDs.
- `both`: robust default (guid first, normalized URL second).
- New imports use `default_visibility` from `config.yaml` (default: `private`).

## Optional web surface

`link_garden.web` (FastAPI) is an optional, experimental surface. The canonical workflow remains CLI-first with static exports.

- Markdown display is sanitized to prevent executable content rendering.
- Unsafe URL schemes (for example `javascript:`/`data:`) are blocked in rendered links.
- Capture/write endpoints enforce conservative input size limits and return `400` on violations.
