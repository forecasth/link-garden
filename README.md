# link-garden

Local-first, self-hostable bookmark + notes knowledge garden.

## Design (MVP)

`link-garden` stores every bookmark as a plain Markdown file with YAML frontmatter in `data/bookmarks/`, and maintains a lightweight `data/index.json` for fast listing/filtering.

### Storage model

- One bookmark file per link.
- Frontmatter fields:
  - `id`, `title`, `url`, `tags`, `saved_at`, `source`, `folder_path`, `chrome_guid`, `notes`, `archived`
- Markdown body contains optional freeform notes.
- Deterministic filename:
  - `<saved_at>__<slug>__<shortid>.md`
  - Example: `20260302T074500Z__openapi-spec__a1b2c3d4e5.md`
- Index file (`data/index.json`) contains:
  - `id`, `title`, `url`, `tags`, `path`, `saved_at`, `folder_path`, `chrome_guid`

### Chrome import model

- Input: Chrome local `Bookmarks` JSON (not HTML export).
- Parser traverses `roots.bookmark_bar`, `roots.other`, `roots.synced`.
- Folder hierarchy is preserved in `folder_path` (for example `bookmark_bar/Research/GPCR`).
- URL nodes become bookmark files with:
  - `source="chrome"`
  - `saved_at` from Chrome `date_added` when available, otherwise current UTC time.
- Dedupe modes:
  - `by_guid`: match by `chrome_guid`
  - `by_url`: match by normalized URL (lowercase scheme/host, strip trailing slash, remove `utm_*`)
  - `both`: prefer guid, fallback to URL
- Idempotent import behavior:
  - Running the same import repeatedly does not create duplicates.

## Quickstart

1. Create and activate a virtual environment.
2. Install package in editable mode:

```bash
pip install -e ".[dev]"
```

3. Initialize a data directory:

```bash
link-garden init .
```

4. Add a bookmark:

```bash
link-garden add --url "https://example.com" --title "Example" --tags "reference,docs" --notes "Useful primer"
```

5. List bookmarks:

```bash
link-garden list --search example
```

## CLI commands

```bash
link-garden init <dir>
link-garden add --url <url> [--title <title>] [--tags t1,t2] [--notes "..."] [--folder "path"] [--source manual]
link-garden import-chrome --bookmarks-file <path> [--profile-name Default] [--dedupe by_url|by_guid|both] [--dry-run]
link-garden list [--tag <tag>] [--search <text>] [--folder <path>] [--limit N]
link-garden export --format markdown|json|html --out <dir>
link-garden doctor [--rebuild-index]
```

## Chrome `Bookmarks` file locations

- Windows: `%LOCALAPPDATA%\Google\Chrome\User Data\<Profile>\Bookmarks`
- macOS: `~/Library/Application Support/Google/Chrome/<Profile>/Bookmarks`
- Linux: `~/.config/google-chrome/<Profile>/Bookmarks`

Safety note: close Chrome before copying its `Bookmarks` file to avoid partial writes during import.

## Usage examples

Dry-run Chrome import:

```bash
link-garden import-chrome --bookmarks-file "./Bookmarks" --dedupe both --dry-run
```

Export to JSON:

```bash
link-garden export --format json --out ./exports
```

Run integrity checks:

```bash
link-garden doctor
```

## Minimal UI status

MVP remains CLI-first, and now includes a small local read-only web UI (FastAPI + Jinja) with list/search/filter/detail pages.

## Additional commands

```bash
# Explicit index rebuild (recommended over doctor --rebuild-index)
link-garden rebuild-index [--repo-dir .] [--data-dir ./data] [--dry-run]

# Local web server
link-garden serve [--host 127.0.0.1] [--port 8000] [--repo-dir .] [--data-dir ./data] [--open-browser/--no-open-browser]

# Chrome import watch mode
link-garden import-chrome --bookmarks-file "./Bookmarks" --watch --interval 60
```

`doctor --rebuild-index` is still supported for backward compatibility, but `rebuild-index` is the preferred explicit workflow.

## Web UI

Run locally:

```bash
link-garden serve --repo-dir . --host 127.0.0.1 --port 8000
```

Open `http://127.0.0.1:8000`.

Features:

- Home page with search box, tag filter, folder filter, and pagination (`page`, `per_page` query params).
- Bookmark detail page with frontmatter, rendered markdown body, and an `Open URL` link.
- Capture endpoint for bookmarklet-style saving:
  - `GET /capture?url=...&title=...&tags=t1,t2&notes=...&folder=...`

Security note: default bind is localhost (`127.0.0.1`). Keep it local unless you intentionally expose it.

## Theming

Design tokens and component styles are defined in one file:

- `ui/theme.yaml`

On `link-garden serve`, the theme compiler reads `ui/theme.yaml` and generates:

- `link_garden/web/static/theme.css`

You can customize colors, typography, spacing, radius, shadows, and component style values in `ui/theme.yaml`. Restart `serve` to regenerate CSS.

## Bookmarklet capture

Create a browser bookmark with this URL as its target:

```javascript
javascript:(function(){var u=encodeURIComponent(location.href);var t=encodeURIComponent(document.title||'');window.open('http://127.0.0.1:8000/capture?url='+u+'&title='+t,'_blank');})();
```

This opens the local capture endpoint and redirects to the saved bookmark detail page.

## Import watch workflow

Non-daemon poll mode is available on Chrome import:

```bash
link-garden import-chrome --bookmarks-file "./Bookmarks" --dedupe both --watch --interval 60
```

It checks bookmark file metadata (`mtime` + size) and imports only when the file changes.

## Roadmap

- [x] Explicit `rebuild-index` command with dry-run summary reporting.
- [x] Minimal local read-only web UI (`serve`) with search/filter/detail/pagination.
- [x] Theme system from a single YAML file compiled to CSS.
- [x] Bookmarklet-friendly capture endpoint (`/capture`).
- [x] Chrome import watch mode (`import-chrome --watch`).
- [ ] Optional write UI (form editing in browser).
- [ ] Optional link health checker.

## v0.2 Editing & Curation

New CLI curation commands:

```bash
link-garden edit <id_or_path> [--editor "code --wait"] [--repo-dir .] [--data-dir ./data]
link-garden tag <id> [--add t1,t2] [--remove t3] [--set t1,t2] [--repo-dir .]
link-garden archive <id> [--yes] [--repo-dir .]
link-garden unarchive <id> [--repo-dir .]
link-garden move <id> --folder "bookmark_bar/Research/GPCR" [--rename-file] [--repo-dir .]
link-garden enrich <id|url> [--timeout 5] [--user-agent "..."] [--no-network] [--dry-run] [--overwrite-title] [--all]
```

Tag normalization rule:

- tags are trimmed
- duplicate tags are removed case-insensitively
- first-seen spelling/casing is preserved

Archive behavior:

- archived bookmarks stay on disk
- `list` and web list/search exclude archived by default
- use `--include-archived` to include them

## Web UI (Read-only vs Write-enabled)

Default web mode is read-only and localhost-only.

```bash
link-garden serve --host 127.0.0.1 --port 8000
```

Write mode is opt-in:

```bash
link-garden serve --enable-write
```

Capture can also be enabled without full write mode:

```bash
link-garden serve --enable-capture
```

Optional capture enrichment on server:

```bash
link-garden serve --enable-write --capture-enrich
```

Write endpoints:

- `POST /api/bookmarks/{id}/tags`
- `POST /api/bookmarks/{id}/archive`
- `POST /api/bookmarks/{id}/notes`

Security warning:

- keep `--host 127.0.0.1` unless you explicitly understand the exposure risks
- do not expose write-enabled mode to the public internet

## Search (includes notes)

Index entries now include `search_text`, built from:

- title
- url
- tags
- folder_path
- description
- markdown body/notes (light markdown stripping)

Search is index-backed for both CLI and web:

```bash
link-garden list --search "gpcr pathway"
link-garden list --search "legacy" --include-archived
```

Recent shortcut:

```bash
link-garden list --recent 25
```

## Capture Bookmarklet (optional enrich)

Capture endpoint:

- `GET /capture?url=...&title=...&tags=...&notes=...&folder=...`
- optional one-shot enrichment: `&enrich=1`

Bookmarklet example:

```javascript
javascript:(function(){var u=encodeURIComponent(location.href);var t=encodeURIComponent(document.title||'');window.open('http://127.0.0.1:8000/capture?url='+u+'&title='+t+'&enrich=1','_blank');})();
```

## Backups & Doctor

Create backups of canonical files:

```bash
link-garden backup --out ./backups --format zip --include-index
link-garden backup --out ./backups --format tar
link-garden backup --out ./backups --format copy
```

Backup includes:

- `data/bookmarks/*.md`
- `data/index.json` (if `--include-index`)
- `ui/theme.yaml` (if present)

Doctor improvements:

```bash
link-garden doctor
link-garden doctor --rebuild-index
link-garden doctor --fix
```

Checks include:

- missing files referenced by index
- invalid YAML/frontmatter
- missing required fields (`id`, `url`, `saved_at`)
- duplicate ids
- duplicate normalized URLs
- markdown files missing from index

`--fix` currently applies safe rebuild behavior (rebuild index from files).

## Duplicates & Maintenance

CLI duplicates view:

```bash
link-garden duplicates
link-garden duplicates --include-archived
```

Web duplicates view:

- `GET /duplicates`

Both use the shared URL normalizer used by import dedupe and doctor checks.
