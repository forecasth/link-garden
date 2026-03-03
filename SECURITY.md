# Security Policy

## Threat Model Summary

link-garden is designed for local-first use. The primary threat is accidental exposure, for example:

- binding a server to a public interface by mistake
- exporting private entries and publishing them
- opening the service to the internet without auth/rate-limits/firewall controls

Privacy from ad-tech/platform lock-in is a core motivation, but this project does not claim to provide anonymity or enterprise-grade hardening.

## Security Guarantees

- Secure defaults when config is missing:
  - new bookmarks default to `private`
  - export default scope is `public`
  - serve default bind host is `127.0.0.1`
  - remote bind requires explicit `--allow-remote`
- `scope=all` requires explicit `--dangerous-all`.
- Public-scope exports never include `private` entries.
- `doctor` checks for common footguns, including private URLs appearing in exported HTML.

## Non-Goals

- Built-in auth gateway for internet-facing deployment
- Zero-trust or multi-tenant isolation
- End-to-end encryption of local files at rest
- Managed cloud hosting

## Secure Defaults Checklist

- Keep `config.yaml` values at secure defaults unless you have a clear reason.
- Use `link-garden export --scope public` for anything that might be shared.
- Use `link-garden serve` without overriding host for local browsing.
- Run `link-garden doctor` before publishing exports.
- Keep `data/` backups private.

## Safe Deployment Patterns

Recommended:

- Bind link-garden to localhost only.
- Put nginx in front if remote access is needed.
- Use TLS + auth (Basic Auth or stronger) at the proxy layer.
- Limit access by firewall and rate limiting.

Avoid:

- Directly exposing a `0.0.0.0` bind without proxy auth.
- Publishing `--scope all` exports to public hosting.
- Opening extra ports beyond what is required.

Detailed guide: [docs/self-hosting.md](docs/self-hosting.md)

## Vulnerability Reporting

Report suspected vulnerabilities to: `security@example.com` (placeholder).

Include:

- affected version/commit
- reproduction steps
- expected vs actual behavior
