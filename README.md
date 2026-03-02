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

## Minimal UI plan (placeholder)

MVP is CLI-first. A future local UI can be added with FastAPI + Jinja templates:

- Read-only list + search
- Bookmark detail view (render Markdown)
- Local form for adding bookmarks
