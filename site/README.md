# Link Garden Website (`site/`)

This is a standalone static website project inside the main repository.

- Purpose: documentation, philosophy, and onboarding
- Scope: static HTML/CSS only (no runtime coupling with the CLI app)
- Hosting target: GitHub Pages or any static host

## Run locally

Single-command option from repository root:

```bash
python -m http.server 4173 --directory site
```

Or, from inside `site/`:

```bash
cd site
python -m http.server 4173
```

Open `http://localhost:4173`.

## Project layout

```text
site/
  index.html
  styles.css
  about/
    index.html
    philosophy/index.html
    privacy/index.html
    architecture/index.html
  docs/
    index.html
    quickstart/index.html
    importing-chrome/index.html
    organizing-and-frontmatter/index.html
    exporting/index.html
    serving/index.html
    self-hosting/index.html
    security/index.html
    troubleshooting/index.html
```

## Notes

- No external CDN dependencies are required for rendering.
- Content is written directly into page files.
- Docs content is based on current repository behavior (`link-garden` command help, code, tests, and existing docs).
