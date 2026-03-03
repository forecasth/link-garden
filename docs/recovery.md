# Recovery Cookbook

If something feels off, pause first. Your markdown files are still your source of truth.

## 1) Index is broken or `list` crashes

1. Run a health check:

```bash
link-garden doctor --root .
```

2. Preview index rebuild without changing files:

```bash
link-garden rebuild-index --repo-dir . --dry-run
```

3. Rebuild safely:

```bash
link-garden rebuild-index --repo-dir .
```

If parse errors exist, this writes `data/index.rebuild.json` and keeps `data/index.json` unchanged.

4. After fixing bad markdown files, confirm overwrite:

```bash
link-garden rebuild-index --repo-dir . --yes
```

## 2) I imported and something went weird

1. Check duplicates and health:

```bash
link-garden duplicates --repo-dir .
link-garden doctor --root .
```

2. Remember: high-impact commands auto-create backups in `data/backups/`.
3. If needed, restore the latest backup (see next section), then rerun import in dry-run mode first:

```bash
link-garden import-chrome --bookmarks-file <Bookmarks> --root . --dry-run
```

## 3) How to restore from backup

1. Create a fresh backup of current state first (safety net):

```bash
link-garden backup --repo-dir . --out ./data/backups --format zip
```

2. Pick a backup artifact from `data/backups/`.
3. Extract it at project root so `data/bookmarks/` and `data/index.json` are restored.

Zip example:

```bash
python -m zipfile -e data/backups/link-garden-backup-<stamp>.zip .
```

Tar example:

```bash
tar -xzf data/backups/link-garden-backup-<stamp>.tar.gz -C .
```

4. Re-check:

```bash
link-garden doctor --root .
link-garden list --root .
```

## 4) How to rebuild index safely

Use this sequence:

```bash
link-garden rebuild-index --repo-dir . --dry-run
link-garden rebuild-index --repo-dir .
```

If you see parse errors:

- fix the reported files first, or
- inspect `data/index.rebuild.json`, then confirm overwrite:

```bash
link-garden rebuild-index --repo-dir . --yes
```

## 5) Doctor found issues - what now?

- `invalid_index`: rebuild index (dry-run first).
- `invalid_frontmatter`: open and fix YAML/frontmatter in the reported file.
- `orphan_file`: run rebuild-index to re-link file into index.
- `duplicate_url_group`: review with `duplicates` and archive/merge as needed.
- `private_export_leak`: regenerate exports with `--scope public`.

When in doubt: backup first, then make one fix at a time.



