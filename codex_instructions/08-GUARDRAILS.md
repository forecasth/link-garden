You are Codex working on link-garden. We have completed:

- Trust Hardening (atomic writes, backups, friendly CLI errors, safe rebuild)
- Web Safety (sanitize rendered markdown, block unsafe href schemes, security headers, POST /capture)

NEXT STEP THEME:
Guardrails + Limits + Security Regression Tests

Do NOT add heavy dependencies.
Do NOT add authentication systems.
Keep changes incremental and legible.

---

1. Strengthen sanitizer regression tests

---

Expand tests to include common XSS bypass payloads beyond <script>:

- <img src=x onerror=alert(1)>
- <svg onload=alert(1)>
- <a href="data:text/html,<script>alert(1)</script>">x</a>
- Mixed-case schemes: JaVaScRiPt:
- HTML entity encoded variants (at least one)
- Inline style attribute injection attempt

Acceptance:

- Sanitized output contains no event handler attributes (onerror/onload/etc)
- No javascript: or data: hrefs survive unless explicitly allowed
- No <script>, <svg>, <foreignObject> survive (prefer to strip whole tags)
- Tests pass

---

2. Add input size limits (web capture + render)

---

Implement conservative caps (constants) for:

- title length
- url length
- notes length
- tags count and tag length
- folder_path length

Enforce in:

- POST /capture
- GET /capture (apply same caps; if exceeded, reject with friendly error)
- Any other web write endpoint if present

Acceptance:

- Over-limit input returns 400 with clear message (no traceback)
- Tests for at least 3 cap violations

---

3. Add basic request/response safety defaults

---

- Ensure all web responses set a consistent Content-Type with charset.
- Confirm CSP is present and meaningful (default-src 'self', object-src 'none', base-uri 'none', frame-ancestors 'none', etc.).
- If inline scripts/styles exist, either move them to static files or document why CSP includes unsafe-inline.

Acceptance:

- Tests assert key CSP directives exist (don’t hardcode the entire string; assert tokens)

---

4. Add simple pagination/limit defaults for web listing

---

If the web index lists bookmarks:

- Add query params: ?limit=, ?offset= (or page=)
- Apply max limit cap
- Default limit sensible (e.g., 50)

Acceptance:

- Requesting large limit clamps to max
- Tests cover default + clamp behavior

---

5. Documentation: “Web surface safety + limits”

---

Update docs to include:

- What is sanitized and why
- Which schemes are blocked
- Capture GET vs POST note
- Size limits and how to change them (config/env optional)

Keep it short and human-readable.

---

## Constraints

- Minimal dependencies
- Incremental commits
- Add tests for each new behavior
- All existing tests must pass

At end output:

1. Summary of changes
2. Security notes
3. Manual test steps
4. Suggested commit message

Proceed.
