#!/usr/bin/env bash
# Update and prepare the Ubuntu/Linux production deployment.
set -Eeuo pipefail

ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if [[ "$(uname -s)" != Linux ]]; then
  echo "ERROR: deploy.sh is for Linux/Ubuntu servers." >&2
  exit 1
fi
if [[ ! -f requirements.txt || ! -f app.py ]]; then
  echo "ERROR: Run deploy.sh from a complete project checkout." >&2
  exit 1
fi

PYTHON_BIN=""
for candidate in python3.12 python3.11 python3.10 python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)' 2>/dev/null; then
    PYTHON_BIN="$(command -v "$candidate")"
    break
  fi
done
if [[ -z "$PYTHON_BIN" ]] && command -v uv >/dev/null 2>&1; then
  uv python install 3.12
  PYTHON_BIN="$(uv python find 3.12)"
fi
if [[ -z "$PYTHON_BIN" ]]; then
  echo "ERROR: Python 3.10–3.12 is required. Install Python 3.12 or uv." >&2
  exit 1
fi

if [[ ! -x .venv/bin/python ]] || ! .venv/bin/python -c 'import sys; raise SystemExit(0 if (3,10) <= sys.version_info[:2] <= (3,12) else 1)' 2>/dev/null; then
  "$PYTHON_BIN" -m venv .venv
fi
if command -v uv >/dev/null 2>&1; then
  uv pip install --python .venv/bin/python -r requirements.txt
else
  .venv/bin/python -m pip install --upgrade pip
  .venv/bin/python -m pip install -r requirements.txt
fi

if [[ ! -f .env ]]; then
  cp .env.server-40gb.example .env
  SECRET_KEY="$(.venv/bin/python -c 'import secrets; print(secrets.token_hex(32))')"
  SECRET_KEY="$SECRET_KEY" .venv/bin/python - <<'PY'
import os
from pathlib import Path

path = Path(".env")
contents = path.read_text(encoding="utf-8")
contents = contents.replace("SECRET_KEY=dev-insecure-change-me", f"SECRET_KEY={os.environ['SECRET_KEY']}", 1)
path.write_text(contents, encoding="utf-8")
PY
  chmod 600 .env
  echo "Created .env from the 40 GB server template with a unique SECRET_KEY. Configure credentials and proxy settings before production use."
fi
chmod 600 .env
APP_PORT="$(.venv/bin/python - <<'PY'
from dotenv import dotenv_values
import sys

values = dotenv_values(".env")
secret = str(values.get("SECRET_KEY") or "")
if len(secret) < 32 or secret in {"dev-insecure-change-me", "change-me", "your-secret-key"}:
    raise SystemExit("ERROR: .env must contain a unique SECRET_KEY with at least 32 characters.")
port = str(values.get("PORT") or "5000")
if not port.isdigit() or not 1 <= int(port) <= 65535:
    raise SystemExit("ERROR: .env PORT must be an integer between 1 and 65535.")
print(port)
PY
)"

mkdir -p data/site_dbs data/browser_profiles logs storage/temp storage/exports
if command -v google-chrome >/dev/null 2>&1; then
  export SCRAPER_CHROME_PATH="${SCRAPER_CHROME_PATH:-$(command -v google-chrome)}"
elif [[ -x /opt/google/chrome/google-chrome ]]; then
  export SCRAPER_CHROME_PATH="${SCRAPER_CHROME_PATH:-/opt/google/chrome/google-chrome}"
fi

.venv/bin/python - <<'PY'
from scrapers.system_check import run_preflight_check

raise SystemExit(0 if run_preflight_check(fail_fast=False)["overall_ok"] else 1)
PY

if command -v systemctl >/dev/null 2>&1; then
  SERVICE_USER="${SUDO_USER:-$(id -un)}"
  SERVICE_GROUP="$(id -gn "$SERVICE_USER")"
  UNIT_PATH="/etc/systemd/system/scraper.service"
  UNIT_TMP="$(mktemp)"
  cat > "$UNIT_TMP" <<EOF
[Unit]
Description=Parts Extractor scraper dashboard
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_GROUP}
WorkingDirectory=${ROOT_DIR}
EnvironmentFile=${ROOT_DIR}/.env
ExecStart=${ROOT_DIR}/.venv/bin/gunicorn --workers 1 --threads 4 --bind 0.0.0.0:${APP_PORT} app:app
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
  if [[ -e "$UNIT_PATH" ]]; then
    rm -f "$UNIT_TMP"
  elif [[ $EUID -eq 0 ]]; then
    install -m 644 "$UNIT_TMP" "$UNIT_PATH"
    rm -f "$UNIT_TMP"
  elif command -v sudo >/dev/null 2>&1; then
    sudo install -m 644 "$UNIT_TMP" "$UNIT_PATH"
    rm -f "$UNIT_TMP"
  else
    rm -f "$UNIT_TMP"
    echo "ERROR: systemd is available, but sudo is required to install scraper.service." >&2
    exit 1
  fi

  if [[ $EUID -eq 0 ]]; then
    systemctl daemon-reload
    systemctl enable scraper
    systemctl restart scraper
  elif command -v sudo >/dev/null 2>&1; then
    sudo systemctl daemon-reload
    sudo systemctl enable scraper
    sudo systemctl restart scraper
  else
    echo "ERROR: scraper.service needs root or sudo to enable and start." >&2
    exit 1
  fi

  if [[ -e "$UNIT_PATH" ]]; then
    for attempt in {1..30}; do
      if curl --fail --silent --show-error "http://127.0.0.1:${APP_PORT}/readyz" >/dev/null 2>&1; then
        echo "Deployment ready: http://127.0.0.1:${APP_PORT}/readyz"
        exit 0
      fi
      sleep 2
    done
    echo "ERROR: scraper.service did not become ready within 60 seconds." >&2
    if [[ $EUID -eq 0 ]]; then
      systemctl --no-pager --full status scraper || true
    else
      sudo systemctl --no-pager --full status scraper || true
    fi
    exit 1
  fi
fi

if [[ ! $(command -v systemctl || true) ]]; then
  echo "Systemd not detected. Start one Gunicorn process with:"
  echo "  .venv/bin/gunicorn --workers 1 --threads 4 --bind 0.0.0.0:${APP_PORT} app:app"
fi
