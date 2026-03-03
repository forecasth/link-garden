You are an expert full-stack engineer and technical writer. Build a new project called “link-garden” — a local-first, self-hostable bookmark + notes knowledge garden.

GOALS

- Provide a minimal, offline-first system for capturing bookmarks with context (notes/tags), storing them as plain files on disk (Markdown with YAML frontmatter), versionable with git.
- Provide a Chrome Bookmarks “digest” import that reads Chrome’s local Bookmarks JSON file and converts bookmarks/folders into the project’s Markdown format.
- Keep the MVP small, reliable, and easy to run locally. Prefer boring tech, strong CLI ergonomics, clear docs.

MVP FEATURES

1. Local file storage (one file per bookmark)

- Store each bookmark as a Markdown file:
  - YAML frontmatter fields: id, title, url, tags, saved_at, source, folder_path, chrome_guid (if available), notes, archived (bool)
  - Body contains optional freeform notes (can start empty)
- Deterministic filenames:
  - <saved_at>**<slug>**<shortid>.md
  - Avoid collisions; sanitize for Windows/macOS/Linux
- Maintain a small index file:
  - data/index.json (or sqlite optional, but JSON index is fine for MVP)
  - Index includes id, title, url, tags, path, saved_at, folder_path

2. CLI commands (Python)
   Use Python 3.11+ and `typer` for CLI.
   Commands:

- `link-garden init <dir>`: create folder structure
- `link-garden add --url <url> [--title <title>] [--tags t1,t2] [--notes "..."] [--folder "path"] [--source manual]`
- `link-garden import-chrome --bookmarks-file <path> [--profile-name Default] [--dedupe by_url|by_guid|both] [--dry-run]`
- `link-garden list [--tag <tag>] [--search <text>] [--folder <path>] [--limit N]`
- `link-garden export --format markdown|json|html --out <dir>`
- `link-garden doctor`: verify index consistency, broken files, duplicates

3. Chrome Bookmarks digest/import

- Input: Chrome “Bookmarks” JSON file (not HTML export).
- Default Windows paths should be documented (but tool must accept any file path):
  - Windows: %LOCALAPPDATA%\Google\Chrome\User Data\<Profile>\Bookmarks
  - macOS: ~/Library/Application Support/Google/Chrome/<Profile>/Bookmarks
  - Linux: ~/.config/google-chrome/<Profile>/Bookmarks
- Parse `roots` tree (bookmark_bar, other, synced).
- Preserve folder hierarchy:
  - folder_path like "bookmark_bar/Research/GPCR"
- For each URL node:
  - Create a bookmark Markdown file (or update existing if dedupe match).
  - Fill: title=name, url=url, saved_at=converted add_date if present else now, source="chrome", folder_path as above, chrome_guid if present.
- Dedupe rules:
  - If `--dedupe by_guid` and guid exists: stable match on chrome_guid
  - If `by_url`: normalize URL (strip trailing slash, remove utm\_\* query params by default, lowercase scheme/host)
  - If `both`: prefer guid then url
- Idempotent imports: running import twice should not create duplicates.

4. Minimal UI (optional but nice)

- If time permits, provide a tiny local web UI using FastAPI + Jinja or a minimal React static page.
- For MVP, CLI-only is acceptable, but include a plan/placeholder for UI.

PROJECT STRUCTURE

- Use a clean repo layout:
  - /link_garden (python package)
    - cli.py
    - storage.py
    - model.py (pydantic dataclasses)
    - chrome_import.py
    - index.py
    - export.py
    - utils.py
  - /data (created at runtime)
  - /docs (usage + design)
  - pyproject.toml with dependencies
  - tests/ with pytest
- Provide robust unit tests:
  - Chrome JSON parsing (folders + urls)
  - Dedupe logic
  - Filename sanitization
  - Index rebuild

QUALITY & DX REQUIREMENTS

- Must run on Windows/macOS/Linux.
- Clear README with:
  - Quickstart
  - Chrome file locations
  - Example commands
  - Safety note: close Chrome before copying Bookmarks file
- Include a `--dry-run` mode that prints what would be created/updated.
- Log actions clearly. Use structured logging if simple, else standard logging.
- Avoid heavy dependencies.

DELIVERABLES

- All code needed for a working MVP.
- README.md
- Example output files in /examples (optional)
- Tests passing.

IMPLEMENTATION DETAILS

- Use UTC timestamps in ISO 8601 for saved_at.
- Use a short stable ID (e.g., base32/uuid4 shortened).
- URL normalization function should be well-tested.
- Provide a “rebuild index from files” fallback.

Start by generating:

1. A short design doc (in README) explaining how storage and import works.
2. The full repository code scaffolding and core implementation.
3. Tests.
4. Usage examples.

Do not assume any external services. Do not require a browser extension.
