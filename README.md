# link-garden

Local-first bookmark + notes knowledge garden with Markdown frontmatter storage.

## Beginner Quickstart (10-15 minutes)

1. Create and activate a virtual environment.
2. Install:

```bash
pip install -e ".[dev]"
```

3. Initialize a project:

```bash
link-garden init .
```

4. Add a bookmark:

```bash
link-garden add --url "https://example.com" --title "Example" --tags "reference,docs"
```

5. List what you have:

```bash
link-garden list --root .
```

6. (Optional) Import Chrome bookmarks carefully:

Find your Chrome profile path in `chrome://version` (look for **Profile Path**), then select the `Bookmarks` file in that profile directory.

Common locations:

- Windows: `%LOCALAPPDATA%\\Google\\Chrome\\User Data\\<Profile>\\Bookmarks`
- macOS: `~/Library/Application Support/Google/Chrome/<Profile>/Bookmarks`
- Linux: `~/.config/google-chrome/<Profile>/Bookmarks` (or Chromium equivalent)

Preview first:

```bash
link-garden import-chrome --bookmarks-file "<path-to-Bookmarks>" --root . --dry-run
```

Then run for real:

```bash
link-garden import-chrome --bookmarks-file "<path-to-Bookmarks>" --root .
```

7. Build a public-safe export:

```bash
link-garden export --format html --out ./exports --scope public
```

8. Serve locally (localhost-only by default):

```bash
link-garden serve --repo-dir . --port 8000
```

9. Run a health check before sharing:

```bash
link-garden doctor --root .
```

By default, serving is local-only (`127.0.0.1`) and public-scope. For self-hosting, follow [docs/self-hosting.md](docs/self-hosting.md).

Quick links:

- [Recovery cookbook](docs/recovery.md)
- [Changelog](CHANGELOG.md)

## Security Model

- Primary threat: accidental exposure of private bookmarks.
- Default posture:
  - `default_visibility: private`
  - export scope defaults to `public`
  - serve binds to `127.0.0.1`
  - remote bind requires explicit `--allow-remote`
- `scope=all` requires explicit `--dangerous-all`
- `doctor` checks for common security footguns, including private URLs leaking into exported HTML.
- High-impact mutating workflows auto-create a backup in `data/backups/` by default (`import-chrome`, `rebuild-index`, `doctor --fix`).

See [SECURITY.md](SECURITY.md) for guarantees, non-goals, deployment patterns, and reporting.

## Visibility

Each bookmark has one of:

- `private`: local-only, never included in public/unlisted export.
- `unlisted`: included only in `unlisted` or `all` scope exports.
- `public`: safe for public export.

Set visibility per bookmark:

```bash
link-garden set-visibility --id <bookmark_id> --visibility public
link-garden set-visibility --url "https://example.com/article" --visibility private
```

Export scopes:

- `public`: only `public`
- `unlisted`: `public + unlisted`
- `all`: `public + unlisted + private` (requires `--dangerous-all`)

## Config

Repo-level config is `config.yaml`:

```yaml
default_visibility: private
export_default_scope: public
serve_default_scope: public
server_bind_host: 127.0.0.1
require_allow_remote: true
```

Missing config falls back to secure defaults.

## Commands

```bash
link-garden init <dir>
link-garden add --url <url> [--title <title>] [--tags t1,t2] [--notes "..."] [--folder "path"]
link-garden import-chrome --bookmarks-file <path> [--profile-name Default] [--dedupe by_url|by_guid|both] [--dry-run] [--backup-before] [--watch]
link-garden list [--search <text>] [--tag <tag>] [--folder <path>] [--visibility private|unlisted|public] [--limit N] [--format table|tsv|json]
link-garden set-visibility --id <id> --visibility private|unlisted|public
link-garden set-visibility --url <url> --visibility private|unlisted|public [--yes]
link-garden export --format markdown|json|html --out <dir> [--scope public|unlisted|all] [--dangerous-all]
link-garden serve [--host 127.0.0.1] [--port 8000] [--export-mode public|unlisted|all] [--dangerous-all] [--allow-remote]
link-garden doctor [--rebuild-index] [--fix] [--backup-before]
link-garden rebuild-index [--dry-run] [--yes] [--backup-before]
link-garden duplicates [--include-archived]
link-garden backup --out <dir> [--format zip|tar|copy]
link-garden hub export --out <dir>
```

`rebuild-index` is now non-destructive when parse errors are found: it writes `data/index.rebuild.json` and leaves `data/index.json` unchanged unless `--yes` is provided.

## Demo Dataset

Generate a small, varied dataset for testing and screenshots:

```bash
# Safe default: writes to a new temp directory
python examples/demo_seed.py

# Explicit root (prompts before appending if data already exists)
python examples/demo_seed.py --root ./demo-garden
```

Then inspect it:

```bash
link-garden list --root ./demo-garden
```

## Hub

`hub export` builds a static, opt-in directory page from local `hub.yaml`.

- No auto-submit or external network calls.
- Public warning is embedded in generated HTML.
- Submission is manual and opt-in.

Details: [docs/hub.md](docs/hub.md)

## Website

This repository includes a standalone static website project in [`site/`](site/).

- Purpose: documentation, philosophy, and onboarding content.
- Separation: the site is independent from the CLI runtime code.
- Deployment: suitable for GitHub Pages or any static host.

Run locally (single command from repo root):

```bash
python -m http.server 4173 --directory site
```

Or:

```bash
cd site
python -m http.server 4173
```

Then open `http://localhost:4173`.

## Experimental Web App (Opt-in)

The FastAPI web interface under `link_garden.web` is optional and currently experimental. Use it for local curation convenience; treat CLI + static export as the primary stable path for publishing and long-term workflows. Remaining risk is the usual one for local web surfaces: browser history/log leakage when using query-string capture (`GET /capture`), so prefer `POST /capture` and keep default local-only exposure.

- Primary interface remains the CLI + static export flow.
- Web defaults are read-only (`enable_write=False`, `enable_capture=False`).
- If you enable capture, prefer `POST /capture` because query-string `GET /capture` requests can leak URLs/notes into browser history and proxy logs.

### Web Safety + Limits

- Rendered markdown is sanitized before display; raw script/svg/foreignObject content is stripped.
- Web links only allow `http://` and `https://` schemes. `javascript:` and `data:` links are blocked.
- Web responses include CSP and baseline security headers. CSP currently allows inline styles because templates still contain inline `style=""` attributes.
- Capture/write inputs are capped (title/url/notes/folder/tags) and over-limit requests return `400`.
- Index listing defaults to `limit=50` and clamps to a max of `100` (`offset` supported).

Tune these defaults by editing constants in [link_garden/web/app.py](link_garden/web/app.py).
