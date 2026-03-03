You are Codex working on the link-garden repository.

We are entering a “Trust Hardening” refinement step.

Do NOT add new features.
Do NOT introduce heavy dependencies.
Do NOT refactor architecture unnecessarily.

The goal of this step is:

Make mutations psychologically safe, recoverable, and friendly for non-developers.

Implement the following in small, incremental commits (grouped logically). Keep code legible and minimal.

---

1. Atomic Writes (CRITICAL)

---

Create a shared utility for atomic writes:

- Write to temporary file in same directory.
- fsync.
- atomic replace (os.replace).
- Ensure cross-platform behavior (Windows compatible).

Apply to:

- Bookmark markdown writes
- index.json writes

Acceptance:

- Interrupting process cannot leave partial JSON or truncated markdown.
- Existing tests pass.
- Add one new test simulating interrupted write behavior (mock failure before replace).

---

2. CLI Error Translation Layer

---

Implement a lightweight wrapper so that:

- ValueError, FileNotFoundError, and expected domain errors
  become clean one-line CLI messages.
- No Python traceback for expected user mistakes.
- Exit code != 0.

Apply to:

- edit
- tag
- move
- set-visibility
- archive
- unarchive

Acceptance:

- Missing ID produces friendly error.
- Add tests verifying no traceback in output.

---

3. Auto Backup Before High-Impact Operations

---

Add --backup-before / --no-backup-before flags.
Default behavior:

- If mutation will occur, create backup automatically.
- Print backup artifact path and restore hint.

Apply to:

- import-chrome
- rebuild-index
- doctor --fix

Backups should go to:
data/backups/

Acceptance:

- Backup created only when mutation count > 0.
- Tests confirm backup artifact exists.
- Clear restore instructions printed.

---

4. Non-Destructive Rebuild Index

---

Change rebuild-index behavior:

If parse errors > 0:

- Write rebuilt index to index.rebuild.json
- Print summary
- Require --yes to overwrite index.json

Acceptance:

- Existing index remains untouched unless confirmed.
- Tests added for this behavior.

---

5. URL Normalization Improvement

---

Fix normalization so:

- "example.com" becomes "https://example.com"
- Not malformed "https:///example.com"

Add tests for:

- bare host
- trailing slash
- uppercase scheme
- query ordering

---

6. Require Confirmation for Broad Mutations

---

For set-visibility --url:

If more than 1 record affected:

- Require --yes flag
- Print count and preview

Add test.

---

7. Narrow Doctor Leak Scan

---

Restrict HTML scan to:

- Explicit export directories
- Not entire repo root

Avoid false positives from site/ or docs/.

---

8. Improve list Output (Low Scope)

---

Default list output:

- Clean human-readable table (id, title, folder, visibility)
  Add:
  --format tsv
  --format json

Keep implementation simple.

---

Constraints:

- Keep diff small and focused.
- Update README where behavior changes.
- Add tests for every new safety behavior.
- Do not break existing test suite.
- Do not add new frameworks.

At the end, produce:

1. Summary of changes
2. Migration notes (if any)
3. Manual test steps
4. Updated trust model description
5. Suggested commit message

Proceed.
