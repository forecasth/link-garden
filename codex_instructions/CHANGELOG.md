# Changelog

## v0.2 (2026-03-03)

Release theme: trust hardening + web guardrails.

### Added

- Atomic file writes for bookmark markdown and `data/index.json`.
- Auto backups before high-impact operations:
  - `import-chrome`
  - `rebuild-index`
  - `doctor --fix`
- Non-destructive `rebuild-index` flow with `data/index.rebuild.json` when parse errors exist.
- Friendly CLI error translation for common user mistakes (no traceback for expected cases).
- Web safety hardening:
  - markdown sanitization before render
  - unsafe URL scheme blocking (`javascript:`, `data:`)
  - CSP + security headers
  - `POST /capture` support (with `GET /capture` compatibility warning)
  - input size limits on capture/write endpoints
  - web list pagination limits and clamp behavior

### Changed

- `list` default output is now a human-readable table.
- `list` supports `--format table|tsv|json`.
- `set-visibility --url` requires `--yes` when multiple records match.
- `rebuild-index` no longer overwrites `data/index.json` when parse errors are present unless `--yes` is provided.

### Breaking-ish behavior changes

- Scripts that parsed old tab-separated `list` output must now use `link-garden list --format tsv`.
- `set-visibility --url` broad updates now require explicit confirmation via `--yes`.
- `rebuild-index` may stop after writing `data/index.rebuild.json` until you explicitly confirm with `--yes`.

### Upgrade notes

- Review automation/scripts that parse CLI output and add explicit format flags where needed.
- Existing data remains compatible; no schema migration is required.
- Default backup location is `data/backups/` (zip artifacts by default for auto-backup flows).
- After upgrading, run:
  - `link-garden doctor --root .`
  - `link-garden list --root .`

