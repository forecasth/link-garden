You are Codex working on link-garden.

We have completed:

- Trust hardening (atomic writes, backups, friendly CLI errors, non-destructive rebuild)
- Web safety + guardrails (sanitizer, scheme blocking, CSP headers, POST capture, input caps, pagination clamps)
  Test suite: 62 passed.

NEXT STEP THEME:
Release Polish (v0.2) — documentation, examples, and “recovery calm”

Do NOT add new runtime features unless tiny and necessary for docs accuracy.
Do NOT add heavy dependencies.

Tasks:

1. Add CHANGELOG.md

- Summarize v0.2: Trust Hardening + Web Guardrails.
- Include “Breaking-ish behavior changes” (list format default table, rebuild-index behavior, set-visibility --url requires --yes).
- Include upgrade notes and where backups live.

2. Add RECOVERY.md (or docs/recovery.md) “cookbook”
   Include short, step-by-step sections:

- “Index is broken / list crashes”
- “I imported and something went weird”
- “How to restore from backup”
- “How to rebuild index safely”
- “Doctor found issues — what now?”
  Keep it friendly and non-scary.

3. Add a Beginner Quickstart path
   In README:

- A 10–15 minute walkthrough with commands.
- Include Chrome bookmarks file location hints (macOS/Windows/Linux) if already known; if not, phrase as “how to find it” without hardcoding risky paths.

4. Add an Example dataset + demo script

- Create examples/demo_seed.py (or similar) that generates a small set of bookmarks with varied visibility/tags/folders.
- Add a Makefile target or simple bash snippet in docs to run it.
- Ensure it doesn’t overwrite existing data unless user confirms or uses a temp dir.

5. Tighten docs around experimental web surface

- One short paragraph: what it is, when to use, what risks remain, safe defaults.

6. Final checks

- Run format/lint if present.
- Ensure all docs commands match actual CLI flags (`--repo-dir` vs `--root`, etc.).
- Tests must still pass.

At end output:

1. Summary of changes
2. Manual docs verification steps
3. Suggested commit message

Proceed.
