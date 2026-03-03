# link-garden Review + Next-Step Architecture Report

## 1) Repo map (high signal)

### Top-level directories

| Path           | What it does and why it matters                                                                                    |
| -------------- | ------------------------------------------------------------------------------------------------------------------ |
| `link_garden/` | Core application code (CLI, storage, import/export, indexing, doctor, security); this is the product runtime.      |
| `tests/`       | Behavioral safety net for import/index/security/web flows; this defines current contract and prevents regressions. |
| `docs/`        | Short-form design/security/self-host docs for maintainers and deployers.                                           |
| `site/`        | Separate static documentation/marketing microsite; useful for onboarding and philosophy, not runtime-coupled.      |
| `ui/`          | Theme source (`theme.yaml`) consumed by web theme compiler.                                                        |
| `examples/`    | Example bookmark markdown file showing frontmatter/body format.                                                    |
| `.github/`     | CI workflow (ruff, pytest, pip-audit) that keeps baseline quality enforceable.                                     |

### 14 most important files

| File                                                                                                            | Why it matters                                                                                                 |
| --------------------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------- |
| [README.md](/c:/Users/User/Documents/dev/link-garden/README.md)                                                 | Main user-facing contract: quickstart, commands, security model, and expected workflow.                        |
| [pyproject.toml](/c:/Users/User/Documents/dev/link-garden/pyproject.toml)                                       | Package metadata, dependencies, scripts, lint/test config; controls install/runtime footprint.                 |
| [link_garden/cli.py](/c:/Users/User/Documents/dev/link-garden/link_garden/cli.py#L132)                          | Command surface and orchestration for all major workflows (`init`, `import-chrome`, `export`, `doctor`, etc.). |
| [link_garden/storage.py](/c:/Users/User/Documents/dev/link-garden/link_garden/storage.py#L25)                   | Path resolution, markdown+frontmatter parsing, and bookmark file read/write primitives.                        |
| [link_garden/model.py](/c:/Users/User/Documents/dev/link-garden/link_garden/model.py#L8)                        | Pydantic schemas for bookmark/index data integrity at runtime.                                                 |
| [link_garden/index.py](/c:/Users/User/Documents/dev/link-garden/link_garden/index.py#L35)                       | Index loading/saving/search/rebuild and duplicate detection; central to performance and UX.                    |
| [link_garden/chrome_import.py](/c:/Users/User/Documents/dev/link-garden/link_garden/chrome_import.py#L115)      | Chrome Bookmarks JSON parsing/import logic with folder lineage + dedupe strategies.                            |
| [link_garden/bookmarks.py](/c:/Users/User/Documents/dev/link-garden/link_garden/bookmarks.py#L24)               | Record-level lookup and persist sync between markdown files and index.                                         |
| [link_garden/export.py](/c:/Users/User/Documents/dev/link-garden/link_garden/export.py#L18)                     | Public/unlisted/all scoped export for markdown/json/html outputs.                                              |
| [link_garden/doctor.py](/c:/Users/User/Documents/dev/link-garden/link_garden/doctor.py#L32)                     | Integrity/security linting for index/files/config/export leaks.                                                |
| [link_garden/security.py](/c:/Users/User/Documents/dev/link-garden/link_garden/security.py#L6)                  | Visibility and export scope policy model used across commands.                                                 |
| [link_garden/utils.py](/c:/Users/User/Documents/dev/link-garden/link_garden/utils.py#L67)                       | Filename/url normalization and shared parsing utilities; affects dedupe and portability.                       |
| [tests/test_chrome_import.py](/c:/Users/User/Documents/dev/link-garden/tests/test_chrome_import.py)             | Verifies folder preservation + dedupe idempotency behavior, core “de-google import” promise.                   |
| [tests/test_security_visibility.py](/c:/Users/User/Documents/dev/link-garden/tests/test_security_visibility.py) | Verifies scope filtering and dangerous-all guardrails, central to privacy posture.                             |

---

## 2) Current behavior summary (truth table)

| Command          | Inputs                                          | Outputs                        | Side effects (files touched)                                                                                                                                                                                                                                                                                                       | Idempotency                                               | Error modes (surface)                                                                                                                    |
| ---------------- | ----------------------------------------------- | ------------------------------ | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `init`           | target dir                                      | prints initialized paths       | creates `data/bookmarks/`, `data/index.json`, optional `config.yaml` ([cli.py#L132](/c:/Users/User/Documents/dev/link-garden/link_garden/cli.py#L132), [storage.py#L39](/c:/Users/User/Documents/dev/link-garden/link_garden/storage.py#L39), [config.py#L29](/c:/Users/User/Documents/dev/link-garden/link_garden/config.py#L29)) | Yes (safe re-run)                                         | filesystem permission/path errors bubble as exceptions                                                                                   |
| `add`            | URL + optional metadata                         | prints created rel path        | writes new markdown file + upserts `data/index.json` ([cli.py#L147](/c:/Users/User/Documents/dev/link-garden/link_garden/cli.py#L147))                                                                                                                                                                                             | No (new ID each run)                                      | bad FS writes/index parse errors bubble                                                                                                  |
| `import-chrome`  | Bookmarks JSON path, dedupe mode, dry-run/watch | prints import stats            | creates/updates markdown files; writes index once per run unless dry-run ([chrome_import.py#L115](/c:/Users/User/Documents/dev/link-garden/link_garden/chrome_import.py#L115))                                                                                                                                                     | Logical yes with `both`; still rewrites “updated” records | JSON/parse/read errors bubble; watch only catches Ctrl+C                                                                                 |
| `list`           | search/tag/folder/visibility/recent/limit       | tab-separated lines            | none (read-only index)                                                                                                                                                                                                                                                                                                             | Yes                                                       | malformed `index.json` raises `ValueError` traceback ([index.py#L42](/c:/Users/User/Documents/dev/link-garden/link_garden/index.py#L42)) |
| `duplicates`     | `--by`, archived filter                         | grouped duplicate URL printout | none                                                                                                                                                                                                                                                                                                                               | Yes                                                       | unsupported `--by` is `BadParameter`; index errors bubble                                                                                |
| `edit`           | bookmark ID or file path + editor               | prints updated summary         | user edits markdown; command re-parses and syncs index ([cli.py#L298](/c:/Users/User/Documents/dev/link-garden/link_garden/cli.py#L298))                                                                                                                                                                                           | Depends on editor changes                                 | missing ID/path/frontmatter issues raise uncaught `ValueError`                                                                           |
| `tag`            | bookmark ID + add/remove/set                    | prints updated tags            | updates markdown + index for one record                                                                                                                                                                                                                                                                                            | Mostly yes for same final set                             | missing bookmark gives traceback (`ValueError`)                                                                                          |
| `set-visibility` | exactly one of ID or URL + visibility           | prints updated count           | updates markdown + index for one or many URL-matched records                                                                                                                                                                                                                                                                       | Yes for same target visibility                            | wrong arg combos are `BadParameter`; missing ID gives traceback                                                                          |
| `archive`        | bookmark ID (+confirm)                          | prints archived message        | sets archived true in markdown + index                                                                                                                                                                                                                                                                                             | Yes                                                       | missing ID gives traceback; user cancel aborts                                                                                           |
| `unarchive`      | bookmark ID                                     | prints unarchived message      | sets archived false in markdown + index                                                                                                                                                                                                                                                                                            | Yes                                                       | missing ID gives traceback                                                                                                               |
| `move`           | bookmark ID + folder (+optional rename-file)    | prints folder/file             | updates folder metadata; optional file rename/delete old path + index update                                                                                                                                                                                                                                                       | Yes if same target                                        | missing ID gives traceback                                                                                                               |
| `enrich`         | ID or URL + network flags                       | per-item status + summary      | fetches metadata; updates markdown+index unless dry-run ([cli.py#L436](/c:/Users/User/Documents/dev/link-garden/link_garden/cli.py#L436))                                                                                                                                                                                          | Not strictly (fetched_at/source_meta can change)          | bad URL-match usage gives `BadParameter`; network failures are printed `FAILED`                                                          |
| `export`         | format + out dir + scope                        | prints output file             | writes `bookmarks.md` or `bookmarks.json` or `index.html` (+`bookmarks.html`) ([export.py#L18](/c:/Users/User/Documents/dev/link-garden/link_garden/export.py#L18))                                                                                                                                                                | Yes for same inputs/data                                  | `scope=all` without confirm becomes `BadParameter`                                                                                       |
| `backup`         | output dir + format                             | prints backup path/count       | writes zip/tar/copy archive with bookmarks (+index optional + `ui/theme.yaml`) ([backup.py#L43](/c:/Users/User/Documents/dev/link-garden/link_garden/backup.py#L43))                                                                                                                                                               | No (timestamped name each run)                            | filesystem/archive errors bubble                                                                                                         |
| `rebuild-index`  | repo/data dir + dry-run                         | summary + per-file errors      | rewrites `data/index.json` from markdown unless dry-run ([index.py#L87](/c:/Users/User/Documents/dev/link-garden/link_garden/index.py#L87))                                                                                                                                                                                        | Yes given same files                                      | invalid files are skipped, reported; command still exits 0                                                                               |
| `serve`          | host/port/scope/static-dir flags                | prints serving URL             | exports HTML to temp dir (unless static-dir), starts HTTP server ([cli.py#L560](/c:/Users/User/Documents/dev/link-garden/link_garden/cli.py#L560))                                                                                                                                                                                 | N/A long-running                                          | non-local bind blocked without `--allow-remote`; bad static-dir is `BadParameter`                                                        |
| `doctor`         | root + optional rebuild/fix                     | summary + issues; exit code    | read-only by default; optional rebuild-index/fix rewrites index ([cli.py#L620](/c:/Users/User/Documents/dev/link-garden/link_garden/cli.py#L620))                                                                                                                                                                                  | Read-only mode yes                                        | exits `1` when issues found; parsing/index failures reported as issues                                                                   |
| `hub export`     | out dir (+root for `hub.yaml`)                  | prints output file             | writes static `index.html` directory page from manifest ([hub.py#L34](/c:/Users/User/Documents/dev/link-garden/link_garden/hub.py#L34))                                                                                                                                                                                            | Yes                                                       | missing/invalid `hub.yaml` raises exception                                                                                              |

---

## 3) Design intent alignment

### Strong alignment with philosophy

- Local-first, legible storage is real: one markdown file per bookmark + YAML frontmatter ([storage.py#L61](/c:/Users/User/Documents/dev/link-garden/link_garden/storage.py#L61)).
- Self-hostable without managed services: static export + built-in simple server ([cli.py#L560](/c:/Users/User/Documents/dev/link-garden/link_garden/cli.py#L560)).
- Privacy defaults are conservative: default private visibility, public export scope, localhost bind ([config.py#L13](/c:/Users/User/Documents/dev/link-garden/link_garden/config.py#L13), [security.py#L12](/c:/Users/User/Documents/dev/link-garden/link_garden/security.py#L12)).
- Recovery path exists: index rebuild from markdown files ([index.py#L87](/c:/Users/User/Documents/dev/link-garden/link_garden/index.py#L87)).
- Code is mostly small-function and readable, with direct flow from CLI command to domain function.

### Drift / hidden complexity

- Two UI surfaces are present: static export/serve from CLI and a separate FastAPI app not exposed by CLI ([cli.py#L560](/c:/Users/User/Documents/dev/link-garden/link_garden/cli.py#L560), [web/app.py#L118](/c:/Users/User/Documents/dev/link-garden/link_garden/web/app.py#L118)); this adds maintenance surface and dependency weight.
- Mutating command errors are inconsistent: many user mistakes show Python traceback instead of friendly guidance (e.g., [bookmarks.py#L29](/c:/Users/User/Documents/dev/link-garden/link_garden/bookmarks.py#L29) called from [cli.py#L338](/c:/Users/User/Documents/dev/link-garden/link_garden/cli.py#L338)).
- `doctor` leak scan is “too broad” by scanning all repo HTML, which can create false positives and scale poorly ([doctor.py#L198](/c:/Users/User/Documents/dev/link-garden/link_garden/doctor.py#L198)).
- `_resolve_paths` in CLI is currently a no-op abstraction ([cli.py#L50](/c:/Users/User/Documents/dev/link-garden/link_garden/cli.py#L50)).

### Accidental coupling to call out

- Index path values couple to root/data layout (`entry.path` plus `paths.root`) and can become absolute when `data_dir` is outside repo ([storage.py#L47](/c:/Users/User/Documents/dev/link-garden/link_garden/storage.py#L47), [bookmarks.py#L30](/c:/Users/User/Documents/dev/link-garden/link_garden/bookmarks.py#L30)).
- Backup/export logic assumes flat `data/bookmarks/*.md` file layout ([storage.py#L58](/c:/Users/User/Documents/dev/link-garden/link_garden/storage.py#L58), [backup.py#L32](/c:/Users/User/Documents/dev/link-garden/link_garden/backup.py#L32)).
- Theme compilation writes generated CSS into package static path at runtime, coupling app startup to writable install path ([web/app.py#L133](/c:/Users/User/Documents/dev/link-garden/link_garden/web/app.py#L133)).

---

## 4) Critical risks (ranked)

Severity: `S1` critical, `S2` high, `S3` medium, `S4` low.  
Likelihood: `L1` rare, `L2` occasional, `L3` likely, `L4` frequent.

| Rank | Risk                                                                                                                                                                                                                                                                                 |                                                                                                                                                 Sev | Likelihood | Impact            | Smallest meaningful mitigation                                                              |
| ---- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------: | ---------: | ----------------- | ------------------------------------------------------------------------------------------- | ------------------------------------------------------------------- |
| 1    | Non-atomic writes for markdown/index can leave partial or corrupted state on interruption ([storage.py#L135](/c:/Users/User/Documents/dev/link-garden/link_garden/storage.py#L135), [index.py#L50](/c:/Users/User/Documents/dev/link-garden/link_garden/index.py#L50))               |                                                                                                                                                  S1 |         L2 | data loss         | Write to temp file + atomic replace for both bookmark and index writes.                     |
| 2    | Markdown in web detail is rendered with `                                                                                                                                                                                                                                            | safe` after unsanitized markdown conversion ([detail.html#L56](/c:/Users/User/Documents/dev/link-garden/link_garden/web/templates/detail.html#L56)) |         S1 | L2                | security                                                                                    | Sanitize HTML output or render markdown as escaped text by default. |
| 3    | Normal user errors show tracebacks (missing ID/path), harming trust and usability ([bookmarks.py#L29](/c:/Users/User/Documents/dev/link-garden/link_garden/bookmarks.py#L29), [cli.py#L338](/c:/Users/User/Documents/dev/link-garden/link_garden/cli.py#L338))                       |                                                                                                                                                  S2 |         L4 | UX                | Add command-level exception translation (`ValueError` -> `typer.BadParameter`).             |
| 4    | Import is not transactional: file updates happen before final index write ([chrome_import.py#L137](/c:/Users/User/Documents/dev/link-garden/link_garden/chrome_import.py#L137), [chrome_import.py#L190](/c:/Users/User/Documents/dev/link-garden/link_garden/chrome_import.py#L190)) |                                                                                                                                                  S2 |         L3 | data integrity    | Save index incrementally or write rollback journal; at minimum auto-backup before import.   |
| 5    | `rebuild-index`/`doctor --fix` can silently drop unreadable files from index ([index.py#L94](/c:/Users/User/Documents/dev/link-garden/link_garden/index.py#L94), [doctor.py#L97](/c:/Users/User/Documents/dev/link-garden/link_garden/doctor.py#L97))                                |                                                                                                                                                  S2 |         L3 | UX/data integrity | Require explicit `--yes` when skipped/errors > 0, print restore hint, auto-backup first.    |
| 6    | URL dedupe map overwrites duplicates by key; update target may be unexpected (often oldest) ([index.py#L111](/c:/Users/User/Documents/dev/link-garden/link_garden/index.py#L111))                                                                                                    |                                                                                                                                                  S3 |         L3 | UX/data quality   | Store `by_url` as list or choose newest deterministically and report ambiguity.             |
| 7    | `normalize_url("example.com")` becomes `https:///example.com`, causing dedupe/search oddities ([utils.py#L116](/c:/Users/User/Documents/dev/link-garden/link_garden/utils.py#L116))                                                                                                  |                                                                                                                                                  S3 |         L2 | UX/data quality   | Detect bare-host inputs and normalize to `https://example.com`; validate URL on add/import. |
| 8    | Theme compile path may fail on read-only installs/site-packages ([web/app.py#L133](/c:/Users/User/Documents/dev/link-garden/link_garden/web/app.py#L133))                                                                                                                            |                                                                                                                                                  S3 |         L3 | portability       | Compile theme to repo-local cache (or temp) not package directory.                          |
| 9    | Doctor private leak scan traverses whole repo HTML and can false-positive ([doctor.py#L198](/c:/Users/User/Documents/dev/link-garden/link_garden/doctor.py#L198))                                                                                                                    |                                                                                                                                                  S3 |         L3 | UX/performance    | Restrict scan to known export dirs or configurable target paths.                            |
| 10   | No default rollback path for high-impact commands despite existing backup utility ([backup.py#L43](/c:/Users/User/Documents/dev/link-garden/link_garden/backup.py#L43))                                                                                                              |                                                                                                                                                  S2 |         L2 | data loss         | Add `--backup-before` default on for `import-chrome` and `rebuild-index`.                   |

---

## 5) Data integrity & safety audit

### Operations that can lose, duplicate, or corrupt data

- `add` always creates new IDs, so repeated adds of same URL create duplicates by design ([cli.py#L162](/c:/Users/User/Documents/dev/link-garden/link_garden/cli.py#L162)).
- `import-chrome` can duplicate under `by_guid` when GUID is missing; `both` is safest default ([chrome_import.py#L97](/c:/Users/User/Documents/dev/link-garden/link_garden/chrome_import.py#L97)).
- `import-chrome` writes many files then writes index at end; interruption creates orphaned markdown vs stale index.
- `move --rename-file` writes new file then unlinks old path; if index write fails after unlink, index can point stale until rebuild ([bookmarks.py#L72](/c:/Users/User/Documents/dev/link-garden/link_garden/bookmarks.py#L72)).
- `edit` lets user save invalid frontmatter, then sync fails; file remains invalid.
- `rebuild-index` excludes invalid markdown files from index; files remain on disk but “disappear” from commands relying on index.
- `doctor --fix` uses rebuild-index only; no pre-fix snapshot.
- `set-visibility --url` updates all normalized matches; broad mutation can be surprising for users expecting one record.

### Filename sanitization, deterministic naming, collisions, folder preservation, dedupe

- Filename generation is deterministic from `saved_at + slug(title) + id` ([utils.py#L67](/c:/Users/User/Documents/dev/link-garden/link_garden/utils.py#L67)).
- Sanitization strips invalid filename chars and normalizes slug, which is good for cross-platform.
- Collision handling appends `-2`, `-3`, etc. ([storage.py#L124](/c:/Users/User/Documents/dev/link-garden/link_garden/storage.py#L124)); safe, but it breaks strict determinism when clashes exist.
- Chrome folder structure is preserved as metadata (`folder_path`) and includes root bucket (`bookmark_bar`, `other`, `synced`) ([chrome_import.py#L57](/c:/Users/User/Documents/dev/link-garden/link_garden/chrome_import.py#L57)).
- Dedupe modes:
  - `by_guid`: strongest when GUID exists, weak when missing.
  - `by_url`: relies on URL normalization quality.
  - `both`: best practical default.

### Backup / rollback strategy recommendation

- Use existing backup primitive before high-impact operations:
  - Auto-run backup on `import-chrome` and `rebuild-index` unless `--no-backup`.
  - Store in `data/backups/` with timestamp and command metadata.
- Add minimal operation journal:
  - Write `data/.ops/<timestamp>.json` with touched files and previous index hash.
  - On failure, print exact rollback command using created backup artifact.
- Keep rollback simple:
  - “Restore backup archive + run `rebuild-index --dry-run` + `doctor`.”

### “No surprises” guardrails for normal users

- Friendly previews (`--dry-run`) on all mutating commands, not just import/enrich/rebuild.
- Clear mutation summaries: “updated N files, created M, skipped K”.
- Consistent user-facing errors (no Python tracebacks for expected mistakes).
- Confirmation for broad mutations (`set-visibility --url`, `doctor --fix` when skips > 0).

---

## 6) Security & privacy posture (pragmatic)

### Threat model (10 bullets)

- Accidental public bind exposing local data.
- Accidental export of non-public bookmarks.
- Publishing stale/private export artifacts.
- Local machine compromise reading plaintext `data/`.
- Shell/environment abuse via editor command override.
- XSS in web UI from stored markdown content.
- URL/query leakage via capture endpoint GET parameters.
- Oversharing through logs containing sensitive URLs.
- Dependency supply-chain vulnerabilities.
- Misconfiguration drift from secure defaults over time.

### Obvious unsafe defaults or sharp edges

- Good defaults exist for visibility/scope/host ([config.py#L13](/c:/Users/User/Documents/dev/link-garden/link_garden/config.py#L13)).
- Sharp edge: markdown rendered as trusted HTML in web detail (`|safe`).
- Sharp edge: capture endpoint uses GET, so notes/URLs can end up in browser history and reverse-proxy logs ([web/app.py#L317](/c:/Users/User/Documents/dev/link-garden/link_garden/web/app.py#L317)).
- Sharp edge: no built-in auth for exposed instances (documented as non-goal, but still operational risk).

### Lightweight improvements (no heavy auth stack)

- Sanitize markdown output in web detail or disable raw HTML rendering.
- Add optional strict security headers in FastAPI responses (CSP, X-Content-Type-Options, Referrer-Policy).
- Add `--redact-urls` logging mode for import/watch logs.
- Prefer POST-based capture endpoint in docs/bookmarklet guidance.
- Add explicit permission check/report for `data/` on startup in CLI mutating commands.

---

## 7) UX / CLI ergonomics review

### Current UX state

- Help text is generally clear and concise.
- Security warnings are present where they matter (`serve`, non-public scope export).
- Biggest UX issue: many expected user mistakes produce tracebacks, not guided CLI messages.

### Defaults and flags

- Security defaults are sensible.
- Flag naming is inconsistent (`--root` vs `--repo-dir`, optional `--data-dir` only on some commands), which increases cognitive load.

### 5 high-impact, low-bloat improvements

1. Normalize path flags across commands (`--repo-dir` + optional `--data-dir` everywhere).
2. Add global graceful error handler for `ValueError`/`FileNotFoundError` in CLI commands.
3. Add `--dry-run` to `tag`, `move`, `set-visibility`, `archive`, `unarchive`.
4. Add `--json` output mode for `list` and `doctor` to help scripts and less technical users.
5. Add mutation confirmation for broad URL-based updates (`set-visibility --url`) unless `--yes`.

---

## 8) Documentation & onboarding review

### What’s missing for a normal person

- “Where is Chrome Bookmarks file?” platform-specific path guide.
- Step-by-step safe import workflow with backup + dry-run first.
- “What is `data/index.json` vs markdown files?” troubleshooting flow.
- Recovery playbook for common issues (invalid frontmatter, orphan files, duplicate URLs).
- Clear distinction between CLI static export flow and optional FastAPI web app (currently implicit).

### Suggested newbie path (“explain like I’m new”)

1. Install and run `link-garden init`.
2. Create one bookmark with `add`.
3. Open and read one markdown bookmark file.
4. Import Chrome bookmarks with `--dry-run`.
5. Run real import, then `doctor`.
6. Export `--scope public`, inspect output, serve locally.

### Suggested expert quickstart path

1. `pip install -e ".[dev]" && link-garden init .`
2. `link-garden import-chrome --bookmarks-file <path> --dedupe both`
3. `link-garden doctor`
4. `link-garden export --format html --scope public --out ./exports`
5. `link-garden serve --repo-dir . --port 8000`

### Docs that should be generated vs hand-written

- Generated:
  - CLI command reference from Typer help.
  - Config key reference from `AppConfig` defaults/enums.
- Hand-written:
  - Philosophy, privacy model, self-hosting threat tradeoffs.
  - Migration/recovery cookbook and beginner onboarding narrative.

---

## 9) Test coverage & quality

### What is currently tested well

- Chrome import parsing, dedupe modes, and idempotency basics.
- Index rebuild behavior and dry-run behavior.
- Doctor detection of duplicate/missing/frontmatter/security leak issues.
- Export scope filtering and dangerous-all guardrails.
- Backup zip contents.
- URL normalization and filename sanitization.
- Enrichment parser + error handling.
- Web write/capture permission and persistence behavior.
- Theme compilation and file-watch snapshot logic.

Current suite status observed: `32 passed`.

### What is not tested (high-value gaps)

- `add`, `list`, `duplicates`, `set-visibility`, `backup tar/copy`, `hub export` CLI behavior.
- Friendly CLI error messaging for missing IDs/paths.
- Atomicity/recovery behavior on interrupted writes.
- URL normalization edge cases like bare host strings.
- `move --rename-file` full path lifecycle and collision behavior.
- `serve` behavior with non-local bind + allow-remote combinations.

### Next 10 tests for maximum confidence

1. `add` writes markdown + index and respects `config.default_visibility`.
2. `list` filter combinations (`search+tag+folder+visibility+recent`).
3. `set-visibility --url` updates all normalized URL matches, including archived.
4. `move --rename-file` updates index path and removes old file.
5. `import-chrome --dry-run` performs zero writes.
6. `import-chrome` no-op update path increments `skipped` after no-change detection.
7. CLI missing bookmark ID returns friendly error (no traceback).
8. Export HTML escapes potentially unsafe title/notes content.
9. `backup --format tar` and `backup --format copy` include expected artifacts.
10. `hub export` validates schema and produces sorted deterministic output.

### Brittle tests and resilience improvements

- Tests asserting exact path prefixes (`data/bookmarks/`) are layout-coupled; prefer asserting that path exists and is under bookmarks dir.
- Tests relying on exact CLI prose can break on wording tweaks; prefer key-token assertions.
- Hardcoded timestamp assumptions should focus on ordering, not exact full strings.

---

## 10) Performance & scaling notes

### Expected behavior by scale

- ~1k bookmarks: current architecture is fine; latency mostly acceptable.
- ~10k bookmarks: index rewrites and full-file export/doctor scans become noticeable.
- ~100k bookmarks: current `load/save full index + per-record upsert` patterns become a bottleneck; export/rebuild are expensive full scans.

### Hotspots

- Full index rewrite on every single-record mutation ([index.py#L46](/c:/Users/User/Documents/dev/link-garden/link_garden/index.py#L46)).
- Import upsert cost is effectively O(n\*m) during batch operations ([chrome_import.py#L156](/c:/Users/User/Documents/dev/link-garden/link_garden/chrome_import.py#L156), [index.py#L81](/c:/Users/User/Documents/dev/link-garden/link_garden/index.py#L81)).
- Export reads/parses every markdown file each run ([export.py#L30](/c:/Users/User/Documents/dev/link-garden/link_garden/export.py#L30)).
- Doctor scans all bookmark files and all HTML under repo root.

### Simple improvements that keep code legible

- In batch flows, use dict-by-id in memory and save index once.
- Skip file/index writes when imported record has no actual field changes.
- Restrict doctor leak scan to explicit export directories.
- Add optional cached “bookmark count + index checksum” to detect no-op export/rebuild quickly.

---

## 11) Suggestions for the next refinement step (deliverable plan)

### North star

Make mutations trustworthy and beginner-safe: no silent surprises, no scary tracebacks, and recoverable workflows by default.

### Tasks with acceptance criteria

1. Add atomic write helper for bookmark and index writes.
   - Acceptance: forced-interruption test never leaves malformed JSON/frontmatter output files.
2. Add CLI error translation layer for expected user mistakes.
   - Acceptance: missing ID/path returns clean one-line error with non-zero exit, no traceback.
3. Add `--backup-before/--no-backup-before` to `import-chrome` and `rebuild-index` (default on).
   - Acceptance: each run prints backup artifact path and restore hint.
4. Implement import no-op detection + accurate `skipped` counter.
   - Acceptance: repeated import of unchanged file reports `skipped>0` and does not rewrite file.
5. Fix/clarify URL normalization for bare-host input.
   - Acceptance: `example.com` normalizes consistently to intended canonical form and tests cover it.
6. Add `--dry-run` to high-impact curation commands.
   - Acceptance: dry-run shows intended mutations and performs zero writes.
7. Narrow doctor HTML leak scan to known export targets.
   - Acceptance: no false positives from unrelated `site/` or docs HTML.
8. Update onboarding docs with “newbie path”, “expert path”, and recovery section.
   - Acceptance: README links to both paths and includes rollback workflow.
9. Expand tests for the above behavior.
   - Acceptance: at least 10 new focused tests; all existing tests still pass.

### Migrations needed (safe path)

- No data schema migration required.
- Optional operational migration: create `data/backups/` and `data/.ops/` on first mutating run.
- Safe rollout: feature flags default to safe behavior, with opt-out for advanced users.

### Recommended order of operations

1. Atomic writes + friendly error handling.
2. Backup-before for batch commands.
3. Import no-op/dedupe accuracy.
4. Doctor scan narrowing.
5. UX flags (`--dry-run`) + docs updates.
6. Test expansion and release notes.

### Definition of done checklist

- All mutating commands fail safely and leave recoverable state.
- Expected user mistakes never show Python traceback.
- Batch operations produce clear summaries and backup references.
- Doctor reports actionable issues with low false-positive rate.
- New onboarding docs validated by a first-time user walkthrough.
- Test suite passes with new coverage for mutation safety and UX.

---

## 12) Questions for ChatGPT (human-in-the-loop)

1. Should `import-chrome` default to creating an automatic backup every run, or only when `created+updated > 0`?
2. Do you want strict URL validation on `add`/`capture` (reject invalid URLs), or permissive storage with warnings?
3. For duplicate URL matches, should updates target newest entry, oldest entry, or prompt the user?
4. Should `rebuild-index` become non-destructive by default when parse errors exist (write to `index.rebuild.json` first)?
5. Should `set-visibility --url` require `--yes` when more than one record will be changed?
6. Do you want to keep the FastAPI web app as a first-class feature, or explicitly mark it experimental/internal?
7. Is the desired long-term storage model still flat `data/bookmarks/*.md`, or should physical subfolders mirror `folder_path`?
8. Do you want a `restore` command now, or is “backup artifact + manual restore instructions” enough for next step?
9. For non-dev friendliness, should `list` default output become a cleaner table and move TSV to `--format tsv`?
10. Which should be prioritized first for next release: mutation safety, CLI ergonomics, or docs/onboarding polish?
