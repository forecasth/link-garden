You are Codex working on the link-garden repo.

We just completed a “Trust Hardening” pass (atomic writes, backups-before, non-destructive rebuild-index, friendlier CLI errors, safer broad mutations).

NEXT STEP THEME:
Web Safety + Experimental Surface Containment

This is still refinement: small diffs, no rewrites, no heavy dependencies.

Primary goal:
If the FastAPI web surface exists, it must not turn stored content into executable content, and it must have safe defaults.

---

1. Fix XSS / Unsafe Rendering (CRITICAL)

---

Identify anywhere the web UI renders bookmark content (notes/markdown/title/url) into HTML.

Requirements:

- Do NOT use unsafe template filters like `|safe` for user content unless output is sanitized.
- Default behavior should be safe: either escape, or sanitize output.

If you sanitize:

- Keep dependencies minimal. Prefer a lightweight approach.
- Strip/neutralize <script>, on\* handlers, javascript: URLs, and raw HTML blocks.

Add tests:

- A bookmark whose notes contain `<script>alert(1)</script>` must not render a script tag.
- A link with `javascript:alert(1)` must not produce a clickable javascript URL.

---

2. Add Security Headers (Low-bloat)

---

Add sensible default headers for web responses:

- Content-Security-Policy (reasonable default for a static-ish app)
- Referrer-Policy
- X-Content-Type-Options
- X-Frame-Options or frame-ancestors in CSP

Add tests validating headers exist in responses.

---

3. Capture Endpoint: Prefer POST

---

If there is a capture/add endpoint that currently uses GET params:

- Add POST support (same functionality).
- Keep GET for backward compatibility, but:
  - Warn in logs and/or docs that GET can leak into browser history/proxy logs.
  - Encourage POST in bookmarklet/docs.

Add tests for POST capture behavior.

---

4. Mark Web App Explicitly Experimental / Opt-in

---

- Update README/docs to clearly frame the web app as optional/experimental.
- Ensure CLI help text does not imply the web UI is the main/only interface.
- If there is a CLI command that launches the web app, ensure defaults remain safe:
  - bind localhost only by default
  - require explicit allow-remote for non-local binds (retain existing guardrails)

---

## Constraints

- Keep changes incremental.
- Keep dependencies minimal.
- Add tests for each security behavior.
- All existing tests must pass.
- Provide a short migration note if behavior changes.

At the end, output:

1. Summary of changes
2. Security notes (what threats this reduces)
3. Manual test steps
4. Suggested commit message

Proceed.
