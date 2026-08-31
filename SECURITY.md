# Security Guide — Parts Extractor

## Authentication

The application supports optional session-based authentication via Flask-Login.

### Enabling Authentication

By default, authentication is **disabled** for backward compatibility. To enable it:

1. Set credentials in your `.env` file:
   ```env
   AUTH_USERNAME=admin
   AUTH_ROLE=admin
   # Generate hash: python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('yourpassword'))"
   AUTH_PASSWORD_HASH=pbkdf2:sha256:...
   ```

2. Restart the application.

### Authentication Modes

| Configuration | Behavior |
|---|---|
| Neither `AUTH_PASSWORD` nor `AUTH_PASSWORD_HASH` set | No authentication required (open access) |
| `AUTH_PASSWORD` set (plaintext) | Auth enabled with dev-mode warning logged — use in dev only |
| `AUTH_PASSWORD_HASH` set | Auth enabled with proper hashed password (recommended) |
| `AUTH_ENABLED=0` | Auth disabled even if credentials are set |

### Roles

| Role | Permissions |
|---|---|
| `admin` | Full access including destructive operations (delete history, cleanup, purge watchlist) |
| `operator` | Read + trigger scrapes + manage automation jobs — no destructive deletes |
| `viewer` | Read-only access to history and results |

### Session Security

- Sessions use Flask's signed cookies (requires `SECRET_KEY` to be set).
- Session lifetime: 8 hours by default (`AUTH_SESSION_HOURS`).
- Cookies are `HttpOnly` and `SameSite=Lax` by default.
- In production (non-debug), cookies are also `Secure` (HTTPS-only).

## SECRET_KEY

**Always set `SECRET_KEY` in production.** Without it, the app generates a random key at startup — this means sessions are invalidated on every restart.

Generate a strong key:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

## SSRF Protection

The scraper validates all supplier URLs before fetching:
- Only allowed supplier domains are accepted (`validate_supplier_remote_url`).
- Private/loopback IP ranges are blocked.
- The allowlist is defined in `scrapers/SCRAPER_CONFIG`.

## Cloudflare Tunnel

When `cloudflared` is running, the application is publicly accessible. Ensure authentication is configured before exposing the tunnel. See `.env.example` for configuration.

## Destructive Endpoint Protection

The following endpoints require the `admin` role when auth is enabled:

- `DELETE /api/history/<id>` — delete a history record
- `POST /api/history/<id>/delete` — same via POST
- `DELETE /api/automation/jobs/<id>` — delete a scheduled job
- `DELETE /api/automation/runs/<id>` — delete a run record
- `POST /api/automation/runs/<id>/delete` — same via POST
- `POST /api/watchlist/clear` — wipe entire watchlist
- `POST /api/cleanup` — database cleanup
- `POST /api/menu-map/output/clear` — clear menu map output

Additionally, destructive endpoints that require confirmation (`permanently-delete`) provide a second layer of protection for the most dangerous operations.

## Data Security

- Database files are stored in `data/site_dbs/` — protect this directory.
- No credentials, API keys, or secrets are stored in the database.
- Log files (`server.log`) may contain URLs and product data — treat as sensitive.
- The `.env` file must never be committed to version control (add to `.gitignore`).
