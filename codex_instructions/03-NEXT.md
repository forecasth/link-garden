You are Codex. You previously implemented “link-garden” (local-first bookmarks as Markdown + YAML frontmatter) with:

- Typer CLI (init/add/list/import-chrome/export/doctor/rebuild-index/serve)
- Chrome Bookmarks JSON digest import + idempotent dedupe + watch mode
- Minimal FastAPI + Jinja UI (read-only by default)
- /capture endpoint for bookmarklet capture
- YAML-driven theming (ui/theme.yaml -> generated CSS)
- Tests passing

TASK: Implement the NEXT SIX STEPS as a cohesive “v0.2” leap, using targeted changes only. Do not rewrite the project. Keep canonical storage as files on disk.

HARD REQUIREMENTS

- Keep CLI backwards-compatible.
- Prefer appending to README.md; amend only where necessary.
- Add tests for new logic (fast, offline, deterministic).
- Keep dependencies minimal and optional where possible.
- Default security posture: localhost-only, read-only by default for web UI unless explicitly enabled.

OVERVIEW OF WHAT TO BUILD
Implement ALL SIX next steps:

1. Edit/enrich workflow (CLI)
2. Minimal web UI becomes optionally write-capable (still local-only + opt-in)
3. Full-text search over notes (and title/url/tags) (index-backed)
4. Capture enrichment: fetch page metadata optionally (title/description) + store
5. Sync safety + backup ergonomics + stronger doctor checks
6. Quality-of-life UI and CLI polish (folders tree, recent, duplicates view)

DETAIL SPEC

(1) EDIT / ENRICH WORKFLOW (CLI)
Add CLI commands to link_garden/cli.py:

A. `link-garden edit <id_or_path> [--editor <cmd>]`

- Resolve bookmark by id (preferred) or allow direct path to md file.
- Open the file in an editor:
  - Use --editor if provided
  - Else use $EDITOR
  - Else fallback platform-appropriate (Windows: notepad, macOS: open -e, Linux: sensible-editor or nano)
- After editor exits, re-parse frontmatter/body and update the JSON index.
- Print a short summary: updated title/tags/archived state.

B. `link-garden tag <id> --add t1,t2 --remove t3 --set t1,t2`

- Mutate frontmatter tags in-place.
- Normalize tags (trim, lower? pick a consistent rule; document it; preserve user intent where reasonable).
- Update index accordingly.

C. `link-garden archive <id> [--yes]` and `link-garden unarchive <id>`

- Set frontmatter archived boolean.
- Ensure archived items can be excluded by default in list/search/UI, with an explicit include option.

D. `link-garden move <id> --folder "bookmark_bar/Research/GPCR"`

- Update folder_path in frontmatter + index.
- Do NOT physically move files on disk for now; folder_path is metadata.
- (Optional) provide `--rename-file` to rename deterministically based on updated title if desired, but keep default conservative (no rename).

E. `link-garden enrich <id|url> [--timeout 5] [--user-agent "..."] [--no-network] [--dry-run]`

- If id is provided, enrich that bookmark.
- If url is provided, find by normalized URL; if multiple, enrich all or require --all; keep simple.
- Enrichment: fetch page HTML, extract:
  - <title>
  - meta description (name="description" or property="og:description")
  - canonical URL if present (optional)
- Store into frontmatter fields:
  - title (only if missing or if --overwrite-title)
  - description (new)
  - fetched_at (UTC ISO)
  - source_meta (e.g., "enrich")
- Must be safe: timeouts; small max bytes; handle errors gracefully.
- Network calls must be mockable in tests.

(2) WEB UI WRITE CAPABILITY (OPT-IN)
Currently UI is read-only. Add optional write features:

- Add `--enable-write` flag to `link-garden serve` (default false).
- When enable-write is false:
  - Hide write controls and reject write endpoints (HTTP 403).
- When enable-write is true:
  - Allow minimal edits:
    - Add/remove tags
    - Archive/unarchive
    - Edit notes body (optional but preferred)
- Implement write endpoints:
  - POST /api/bookmarks/{id}/tags (add/remove/set)
  - POST /api/bookmarks/{id}/archive (toggle)
  - POST /api/bookmarks/{id}/notes (replace body notes)
- After any write, update the file and index, then redirect back to detail view or return JSON.
- UI changes:
  - Detail page includes tag editor + archive toggle + “Edit notes” (textarea) when enable-write is true.
  - Add a small “Read-only” badge when enable-write is false.
- Security:
  - Default host remains 127.0.0.1.
  - Document explicitly: do not expose to internet unless you know what you’re doing.

(3) FULL-TEXT SEARCH OVER NOTES (INDEX-BACKED)
Improve search so it includes notes text and description.

Implementation approach (minimal):

- On add/import/edit/rebuild-index, compute a “search_text” field in the index entry:
  - normalized concatenation of: title, url, tags, folder_path, description, and a notes excerpt/body (strip markdown formatting minimally if easy).
- `link-garden list --search` should search over this field.
- Web UI search should use the same index search.
- Add flags:
  - `link-garden list --include-archived`
  - Web UI toggle “Include archived”.

(4) CAPTURE ENRICHMENT (OPTIONAL)
Enhance /capture:

- Add query param `enrich=1` or `--capture-enrich` option in server config.
- When enabled (and write enabled or at least capture enabled):
  - After creating the bookmark, optionally run enrich step to fill title/description.
- Preserve existing behavior if enrich not requested.
- Still redirect to detail page.

(5) SYNC SAFETY + BACKUP ERGONOMICS + STRONGER DOCTOR
Add:
A. `link-garden backup --out <dir> [--format zip|tar|copy] [--include-index]`

- Minimal recommended: zip repo’s bookmark files + ui/theme.yaml + data/index.json into a timestamped archive.
- Ensure cross-platform paths.

B. Improve `doctor`:

- Add checks:
  - index entries missing corresponding file
  - files missing required frontmatter fields (id, url, saved_at)
  - duplicate ids
  - duplicate normalized URLs (report)
  - invalid YAML frontmatter parse
- Add `doctor --fix` (optional) to:
  - rebuild index
  - optionally add missing id fields (ONLY if safe and user opts in; otherwise just report)
- Add clear summary output.

(6) QUALITY-OF-LIFE POLISH (UI + CLI)
A. Folder tree in UI:

- Build a folder tree from folder_path values in index and render in sidebar with counts.
- Clicking folder filters list.
- Keep it minimal; no JS framework. Light JS is okay but avoid complexity.

B. “Recently added” view:

- UI: a link/tab that sorts by saved_at desc, limited to e.g. last 100.
- CLI: `link-garden list --recent N` (shortcut for sort desc + limit)

C. Duplicates view:

- UI route `/duplicates` (or a filter) that groups bookmarks by normalized URL and shows groups with >1.
- CLI: `link-garden duplicates [--by url]` prints grouped duplicates.

D. URL normalization improvements:

- Ensure the same normalizer is used across import, dedupe detection, duplicates view, and search.
- Keep existing behavior, but add tests for any adjustments.

PROJECT / FILE EXPECTATIONS

- Keep existing structure.
- Add or modify only necessary files in link_garden/.
- Add templates/routes as needed (e.g., duplicates.html, sidebar partial).
- Update pyproject.toml with minimal dependencies:
  - Prefer `httpx` for enrich network calls (already dev dep; consider moving to runtime dep if used at runtime).
  - Avoid heavy HTML parsers; if using BeautifulSoup, justify. Prefer stdlib html.parser or a tiny dependency. (You may use `selectolax` only if absolutely necessary; prefer no.)
- Ensure package data includes new templates/static.

TESTS (must add)

- CLI-level unit tests for tag/archive/move operations (mock editor; test file mutations).
- Index search_text includes notes/description and search matches.
- Web write endpoints:
  - when enable_write=false => 403
  - when enable_write=true => tags/archive/notes updates persist to file + index
- Enrich:
  - mock HTTP responses; validate title/description extraction; ensure timeouts and errors handled.
- Doctor checks:
  - detect missing files, duplicate ids, duplicate urls
- Backup:
  - creates archive/copy in temp dir with expected contents (no huge fixtures).

README UPDATES

- Append sections:
  - “Editing & Curation” (edit/tag/archive/move)
  - “Web UI (Read-only vs Write-enabled)” including the --enable-write flag and localhost warning
  - “Search (includes notes)” explanation
  - “Capture bookmarklet (with optional enrich)”
  - “Backups & Doctor”
  - “Duplicates & Maintenance”
- Only amend existing sections when needed for accuracy.

OUTPUT

- Provide exact changes: new/modified files and their full contents or patches (whichever you normally do).
- Ensure `python -m pytest` passes.

Proceed with implementation now.
