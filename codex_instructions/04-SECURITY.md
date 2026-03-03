You are working in the existing "link-garden" repo that already has:

- Typer CLI
- Markdown+YAML frontmatter storage (one file per bookmark)
- Chrome Bookmarks JSON import
- JSON index (data/index.json)
- list/export/doctor commands
- docs + tests

Goal: implement a security-focused "next step" that makes link-garden safe-by-default for local-first use, and documents an opinionated self-hosting setup (home lab / local + nginx reverse proxy). Keep everything open-source friendly.

High-level principles:

1. Accidental exposure is the main threat. Default posture must prevent “oops I exposed my whole garden to the internet.”
2. Provide explicit opt-ins for anything public.
3. Add a simple visibility model (global + per-link) that controls what gets exported/published.
4. Prefer using nginx as the reverse proxy in documentation; do not require Docker, but you can document it optionally.
5. Do not over-engineer. Keep the MVP clean, well-tested, and documented.

Deliverables (implement all):

A) Threat model + security docs

- Add SECURITY.md with:
  - Threat model summary (accidental exposure, privacy from Big Tech as a motivation)
  - Security guarantees + non-goals
  - Secure defaults checklist
  - Safe deployment patterns and what NOT to do
  - Reporting vulnerabilities (even if just email placeholder)
- Add docs/self-hosting.md with an opinionated guide:
  - Recommended local/home-lab setup using nginx reverse proxy
  - TLS guidance (Let’s Encrypt via certbot), optional if local-only
  - Basic Auth option using nginx (htpasswd)
  - Rate limiting examples in nginx
  - “Bind to localhost only” guidance
  - Firewall basics (ufw) + “only open 80/443”
  - Optional: fail2ban mention (brief)
  - Warnings that exposing without auth is dangerous

B) Secure-by-default server behavior (even if minimal)
If the project currently includes any HTTP serving (if it doesn’t, add a minimal optional server command):

- Add a new Typer command: `serve`
- It must bind to 127.0.0.1 by default (NOT 0.0.0.0).
- `--host 0.0.0.0` must require an explicit `--allow-remote` flag (or interactive confirmation disabled in CI).
- Serve only the exported static HTML directory (if present), or provide a `serve --export-mode public|unlisted|all` that exports to a temp dir first, then serves it.
- Add clear console warnings whenever serving anything beyond public scope or beyond localhost.

Implementation constraint:

- Use standard library http.server if possible (keep dependencies minimal). If you already have a web stack, keep it lean.

C) Visibility model (global + per-link)

- Extend bookmark frontmatter schema to include: `visibility: private|unlisted|public`
- Default visibility for new imports should be configurable (default: private).
- Add a repo-level config file `config.yaml` (minimal design system; single YAML file) with keys like:
  - `default_visibility`
  - `export_default_scope` (public/unlisted/all)
  - `serve_default_scope`
  - `server_bind_host` default "127.0.0.1"
  - `require_allow_remote` default true
- Ensure config loading is deterministic and safe; missing config uses secure defaults.

CLI changes:

- `export` gains `--scope public|unlisted|all` (default from config, falling back to public)
- `list` can optionally filter by `--visibility` but should show all by default
- Add `set-visibility` command:
  - `link-garden set-visibility --id <id> --visibility public|unlisted|private`
  - Also allow `--url` targeting for convenience
- Update index rebuild to include visibility.

Behavior:

- Public export must never include private items.
- “All” export must require an explicit `--dangerous-all` flag (or similar) to reduce accidents.

D) Hardening checks in `doctor`
Improve `doctor` to detect common footguns:

- If any command is about to serve/bind publicly, warn.
- Check file permissions for data directory (best-effort cross-platform).
- Detect if exported HTML contains private entries (should never happen; fail if it does).
- Check that config defaults are secure if config file missing or misconfigured.
- Provide actionable recommendations.

E) Hub concept groundwork (opt-in directory)
Implement a minimal “hub export” generator without crawling:

- New command: `hub export --out <dir>`
- It generates a static HTML page that lists submitted gardens from a local YAML file `hub.yaml` (create a schema):
  - entries: { name, url, description, tags, contact(optional) }
- Include a prominent “this is public” note on the page.
- Do not auto-submit anywhere; this is purely local generation.
- Document in docs/hub.md how someone could email a maintainer to be added (placeholder email), and that submission is opt-in.

F) Supply-chain + code hygiene (lightweight, open-source friendly)

- Add or update:
  - `pyproject.toml` tool configs (ruff, mypy optional)
  - A minimal GitHub Actions workflow:
    - run tests
    - run ruff
    - run pip-audit (or equivalent) if feasible
  - Keep it minimal; don’t break local dev.

G) Tests

- Add tests for:
  - visibility filtering in export
  - dangerous flags required for scope=all export
  - serve binds to localhost by default
  - doctor catches a deliberately-inserted private item in export (should fail)
  - config defaults are secure when config missing

Documentation updates:

- Update README.md:
  - Add “Security model” section
  - Add quickstart note: “by default this is local-only; to self-host follow docs/self-hosting.md”
  - Add “Visibility” section explaining private/unlisted/public
  - Add “Hub” section with brief explanation + link to docs/hub.md

Constraints:

- Keep dependencies minimal.
- Prefer standard library.
- Maintain cross-platform compatibility.
- Ensure all commands are idempotent where reasonable.
- Update existing docs/tests rather than duplicating concepts.
- Provide clean, readable, well-structured code and docs.

Return:

- A concise summary of changes
- Any new commands and examples
- Notes on secure defaults and how a user opts into riskier behavior intentionally
