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

## Import behavior

Chrome import parses the local `Bookmarks` JSON recursively and turns URL nodes into bookmark files while preserving folder lineage in `folder_path`.

- `by_guid`: strongest dedupe when Chrome GUID exists.
- `by_url`: fallback for migrated or missing GUIDs.
- `both`: robust default (guid first, normalized URL second).
