You are Codex. You have already generated an MVP for a project named “link-garden” with:

- Typer CLI
- Markdown + YAML frontmatter storage (one file per bookmark)
- Chrome Bookmarks JSON import with dedupe + idempotency + dry-run
- JSON index with rebuild fallback
- export/list/doctor commands
- README + docs/design.md + tests

TASK: Implement the NATURAL NEXT STEPS and the NEXT LEAP, while keeping the project minimal and coherent.

HARD REQUIREMENTS

- Do NOT rewrite the whole project. Make targeted changes.
- Append to README.md when possible; amend only where necessary.
- Keep the CLI backward-compatible.
- Add tests for any new logic.
- Keep the “boring tech” philosophy.

SCOPE
A) CLI improvement: explicit rebuild-index command

1. Add a new CLI command:
   - `link-garden rebuild-index [--data-dir <dir>] [--repo-dir <dir>] [--dry-run]`
2. This should call the existing index rebuild logic (currently reachable via `doctor --rebuild-index`), but now as a first-class command.
3. The command should:
   - Rebuild `data/index.json` from Markdown files on disk
   - Validate each file’s frontmatter and skip/record errors
   - Print a summary: total files scanned, indexed, skipped, errors
4. Keep `doctor --rebuild-index` working, but update README to recommend `rebuild-index`.

B) Minimal UI: FastAPI + Jinja “read-only” UI (MVP UI)
Goal: a simple local web view that works with the existing file + index layer, without adding a database.

1. Add a web server command:
   - `link-garden serve [--host 127.0.0.1] [--port 8000] [--repo-dir <dir>] [--data-dir <dir>] [--open-browser/--no-open-browser]`
2. Implement a minimal FastAPI app that provides:
   - Home page: search box + tag filter + folder filter + list of bookmarks (title, domain, saved_at, tags)
   - Bookmark detail page: shows full frontmatter + rendered Markdown body, with a “Open URL” link
   - Basic pagination (e.g., page & per_page query params)
3. Use Jinja templates (no React). Keep templates minimal and readable.
4. The UI should read from the JSON index for list/search, and load Markdown files for detail view.
5. Add a small static CSS file (or inline minimal CSS), BUT:
   - The design tokens and design system must come from a SINGLE YAML file (see section C)
   - UI styling should be generated from that YAML file (compile at runtime or on start) into a CSS file placed in a static directory.

C) Minimal UI design system based on one YAML file
Create ONE file, e.g. `ui/theme.yaml`, defining:

- colors (bg, surface, text, muted, accent, border)
- typography (font family, base size, scale)
- spacing scale (xs, sm, md, lg, xl)
- radius values
- shadows (subtle, medium)
- components (button, input, card) with references to tokens

1. Implement a tiny “theme compiler” in Python:
   - reads ui/theme.yaml
   - generates `link_garden/web/static/theme.css`
2. The generated CSS should define:
   - :root CSS variables for tokens
   - minimal base styles (body, a, code, headings)
   - component classes used by templates: `.card`, `.btn`, `.input`, `.tag`, `.badge`, `.toolbar`, `.layout`, etc.
3. Provide a default `ui/theme.yaml` that looks clean, neutral, and readable (no loud colors).
4. Document in README:
   - how to customize theme.yaml
   - how CSS is generated and where it goes

D) Next leap additions (small, high leverage)
Implement TWO of the following (choose the best two for MVP momentum), in a minimal way:

Option 1: Import “watch” workflow (non-daemon)

- Add `link-garden import-chrome --watch --interval 60`
- Poll the Bookmarks file every N seconds, and import if the file changed (mtime/size hash)
- Must be safe and not corrupt anything; still idempotent.
- Log each cycle succinctly.

Option 2: “Capture” endpoint for bookmarklet

- Add an HTTP endpoint in the FastAPI app:
  - GET /capture?url=...&title=...&tags=...&notes=...
- It creates a bookmark file + updates index, then redirects to the bookmark detail page.
- Include a README section with a sample bookmarklet JS snippet the user can paste into browser bookmarks.
- Security note: only bind to localhost by default.

Option 3: “Link rot” checker

- Add `link-garden check-links [--timeout 5] [--limit N]` using httpx (optional dep)
- Checks status codes and writes results to data/linkcheck.json
- Show summary

Pick two options that pair well with the new UI and local-first philosophy. Prefer (2) capture endpoint and (1) watch, unless you have a strong reason otherwise.

TESTS

- Add tests for:
  - rebuild-index command logic (or underlying function)
  - theme compiler: YAML -> CSS variables exist
  - any new endpoint logic if adding capture
  - any watch logic if added (unit-test file change detection functions)
- Keep tests fast and offline (don’t make real network calls; mock where needed).

DOCS

- Update README.md:
  - Append a “Web UI” section with quickstart and usage
  - Append a “Theming” section explaining ui/theme.yaml
  - Update “Natural next steps” into “Roadmap” with completed items checked
  - Mention new commands: rebuild-index, serve, and whichever two options you implemented
- Only amend existing README sections if needed; prefer appending.

DEPENDENCIES

- Keep dependencies minimal:
  - fastapi, uvicorn, jinja2, pyyaml (already likely), markdown renderer (python-markdown or mistune)
- Do not add heavy UI frameworks.

OUTPUT

- Provide the exact code changes required:
  - new/modified files
  - updated README.md content
  - updated pyproject.toml dependencies
  - tests
- Ensure `pytest` passes.

Proceed with implementing now.
