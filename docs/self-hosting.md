# Self-Hosting (Opinionated, nginx-first)

This guide is intentionally conservative. The default recommendation is:

- keep link-garden local-only
- use nginx as the public entrypoint if you need remote access
- require authentication

Exposing link-garden without auth is dangerous.

## 1) Run link-garden on localhost only

Use secure defaults from `config.yaml`:

```yaml
server_bind_host: 127.0.0.1
require_allow_remote: true
serve_default_scope: public
```

Start the local server:

```bash
link-garden serve --repo-dir /srv/link-garden --port 8000
```

Do not bind link-garden directly to `0.0.0.0` unless you intentionally accept the risk.

## 2) nginx reverse proxy (home lab)

Example `/etc/nginx/sites-available/link-garden.conf`:

```nginx
server {
    listen 80;
    server_name links.example.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/link-garden.conf /etc/nginx/sites-enabled/link-garden.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 3) Add Basic Auth at nginx

Install tools and create a password file:

```bash
sudo apt-get install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd your-user
```

Protect the server block:

```nginx
location / {
    auth_basic "Restricted";
    auth_basic_user_file /etc/nginx/.htpasswd;

    proxy_pass http://127.0.0.1:8000;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## 4) TLS with Let's Encrypt (recommended for internet access)

If your instance is reachable publicly:

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d links.example.com
```

For local-only/LAN-only usage, TLS is optional (but still preferred where possible).

## 5) Rate limiting example

Add in nginx `http {}` or included config:

```nginx
limit_req_zone $binary_remote_addr zone=linkgarden_limit:10m rate=10r/m;
```

Then in your server/location:

```nginx
limit_req zone=linkgarden_limit burst=20 nodelay;
```

## 6) Firewall basics (ufw)

Only open ports needed for nginx:

```bash
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw enable
sudo ufw status
```

Do not expose the internal link-garden port (`8000`) directly.

## 7) Optional hardening

- Add `fail2ban` for repeated auth failures on nginx.
- Restrict source IP ranges if your use case allows it (VPN/subnet only).
- Keep OS packages and Python dependencies updated.

## 8) What not to do

- Don't publish `--export-mode all` output on public hosting.
- Don't bind publicly without `--allow-remote`, proxy auth, and firewall rules.
- Don't skip `link-garden doctor` before publishing exports.

## Optional Docker note

Docker is optional. If you containerize, keep the same security posture:

- app bound internally only
- nginx (or equivalent) as auth/TLS edge
- explicit visibility/export scope controls
