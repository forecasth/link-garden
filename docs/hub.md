# Hub Directory (Opt-In)

`link-garden hub export` generates a static HTML directory from local `hub.yaml`.

- No crawling
- No network submission
- No background sync

It is purely local generation.

## Schema (`hub.yaml`)

```yaml
entries:
  - name: Example Garden
    url: https://example.com
    description: Public notes and links on bioinformatics.
    tags: [biology, notes]
    contact: hello@example.com # optional
```

Fields:

- `name` (required)
- `url` (required)
- `description` (required)
- `tags` (optional list of strings)
- `contact` (optional)

## Generate

```bash
link-garden hub export --out ./hub-site
```

Output:

- `./hub-site/index.html`

The generated page includes a prominent warning that it is public content.

## Submission Model

Hub listing is opt-in. If you run a shared hub, accept entries manually.

Suggested workflow:

1. Contributor emails a maintainer with proposed entry data.
2. Maintainer reviews and adds entry to `hub.yaml`.
3. Maintainer regenerates static hub page.

Contact placeholder for submissions: `hub-maintainer@example.com`
