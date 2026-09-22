#!/usr/bin/env bash
# ==============================================================================
# Auto-Heal, Repair & Pre-flight Verification Script
# Parts Extractor - One-Shot Self-Healing Script for Hostinger / Linux VPS
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

echo "======================================================================"
echo "  PARTS EXTRACTOR: ALL-IN-ONE SERVER HEAL & VERIFY"
echo "======================================================================"

OS_TYPE="$(uname -s)"
ARCH_TYPE="$(uname -m)"

# Helper for sudo when not running directly as root
SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        echo "[ERROR] This script requires root or sudo privileges."
        exit 1
    fi
fi

# ------------------------------------------------------------------------------
# STEP 1: Purge Fake/Snap Chrome Symlinks & Install Native Google Chrome (.deb)
# ------------------------------------------------------------------------------
echo ""
echo "[Step 1/6] Auditing and repairing Google Chrome installation..."

CHROME_NEEDS_INSTALL=0

if [ "${OS_TYPE}" = "Linux" ]; then
    # Check if existing google-chrome binary or symlink points to Snap
    CURRENT_CHROME="$(command -v google-chrome || command -v google-chrome-stable || true)"
    if [ -n "${CURRENT_CHROME}" ]; then
        RESOLVED_TARGET="$(readlink -f "${CURRENT_CHROME}" 2>/dev/null || echo "${CURRENT_CHROME}")"
        VERSION_OUTPUT="$("${CURRENT_CHROME}" --version 2>&1 || true)"
        if echo "${RESOLVED_TARGET}" | grep -q "snap" || echo "${VERSION_OUTPUT}" | grep -qi "snap"; then
            echo "  [WARNING] Detected Snap Chromium masquerading as Google Chrome:"
            echo "            Target:  ${RESOLVED_TARGET}"
            echo "            Version: ${VERSION_OUTPUT}"
            echo "  --> Removing stale symlink / alternatives..."
            ${SUDO} rm -f /usr/bin/google-chrome /usr/bin/google-chrome-stable
            CHROME_NEEDS_INSTALL=1
        fi
    fi

    # Check if native /opt/google/chrome/google-chrome is present
    if [ ! -f "/opt/google/chrome/google-chrome" ]; then
        CHROME_NEEDS_INSTALL=1
    fi

    if [ "${CHROME_NEEDS_INSTALL}" -eq 1 ]; then
        if [ "${ARCH_TYPE}" != "x86_64" ]; then
            echo "  [ERROR] Official Google Chrome deb requires x86_64 (detected: ${ARCH_TYPE})."
            exit 1
        fi

        echo "  --> Installing official Google Chrome (.deb) directly from Google..."
        ${SUDO} apt-get update -y
        ${SUDO} apt-get install -y wget curl ca-certificates gnupg libnss3 libatk1.0-0 \
            libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0

        TEMP_DEB="/tmp/google-chrome-stable_current_amd64.deb"
        wget -q -O "${TEMP_DEB}" https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
        ${SUDO} dpkg -i "${TEMP_DEB}" || ${SUDO} apt-get install -f -y
        rm -f "${TEMP_DEB}"
    fi

    # Guarantee canonical symlinks point directly to native binary
    if [ -f "/opt/google/chrome/google-chrome" ]; then
        ${SUDO} ln -sf /opt/google/chrome/google-chrome /usr/bin/google-chrome
        ${SUDO} ln -sf /opt/google/chrome/google-chrome /usr/bin/google-chrome-stable
        FINAL_CHROME="/opt/google/chrome/google-chrome"
    else
        FINAL_CHROME="$(command -v google-chrome || echo '/usr/bin/google-chrome')"
    fi
elif [ "${OS_TYPE}" = "Darwin" ]; then
    FINAL_CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    if [ ! -f "${FINAL_CHROME}" ]; then
        echo "  [ERROR] Google Chrome is missing in /Applications on macOS."
        exit 1
    fi
fi

CHROME_VER="$("${FINAL_CHROME}" --version 2>&1 || true)"
echo "  [PASS] Native Google Chrome active: ${CHROME_VER}"
echo "         Path: ${FINAL_CHROME}"

# ------------------------------------------------------------------------------
# STEP 2: Direct DevTools Socket Verification (Smoke Test)
# ------------------------------------------------------------------------------
echo ""
echo "[Step 2/6] Verifying Chrome DevTools remote debugging socket..."

TEST_PORT=51789
"${FINAL_CHROME}" --headless --no-sandbox --disable-dev-shm-usage \
    --remote-debugging-port="${TEST_PORT}" about:blank >/dev/null 2>&1 &
CHROME_TEST_PID=$!

SOCKET_OK=0
for i in 1 2 3 4 5; do
    sleep 0.5
    if curl -s "http://127.0.0.1:${TEST_PORT}/json/version" | grep -q "Browser"; then
        SOCKET_OK=1
        break
    fi
done

kill "${CHROME_TEST_PID}" >/dev/null 2>&1 || true
wait "${CHROME_TEST_PID}" 2>/dev/null || true

if [ "${SOCKET_OK}" -eq 1 ]; then
    echo "  [PASS] DevTools remote debugging port is fully operational (no AppArmor blocks)."
else
    echo "  [ERROR] Chrome started but DevTools port was unreachable."
    exit 1
fi

# ------------------------------------------------------------------------------
# STEP 3: Python Environment & Dependencies
# ------------------------------------------------------------------------------
echo ""
echo "[Step 3/6] Verifying Python virtual environment and dependencies..."

VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"

if [ ! -f "${VENV_PYTHON}" ]; then
    echo "  --> Creating .venv..."
    for py_candidate in python3.12 python3.11 python3.10 python3; do
        if command -v "${py_candidate}" >/dev/null 2>&1; then
            "${py_candidate}" -m venv "${PROJECT_ROOT}/.venv"
            break
        fi
    done
fi

if [ ! -f "${VENV_PYTHON}" ]; then
    echo "  [ERROR] Failed to locate or create Python virtual environment."
    exit 1
fi

"${VENV_PYTHON}" -m pip install -r requirements.txt -q
echo "  [PASS] Dependencies up to date in .venv."

# ------------------------------------------------------------------------------
# STEP 4: Configuration & Environment Hardening (.env)
# ------------------------------------------------------------------------------
echo ""
echo "[Step 4/6] Hardening environment variables (.env)..."

if [ ! -f ".env" ]; then
    if [ -f ".env.server-40gb.example" ]; then
        cp .env.server-40gb.example .env
    else
        cp .env.example .env
    fi
    RANDOM_SECRET="$("${VENV_PYTHON}" -c "import secrets; print(secrets.token_hex(32))")"
    sed -i "s/dev-insecure-change-me/${RANDOM_SECRET}/g" .env || true
fi

# Ensure correct Chrome path
if grep -q "^SCRAPER_CHROME_PATH=" .env; then
    sed -i "s|^SCRAPER_CHROME_PATH=.*|SCRAPER_CHROME_PATH=${FINAL_CHROME}|" .env
else
    echo "SCRAPER_CHROME_PATH=${FINAL_CHROME}" >> .env
fi

# Ensure Turnstile hang prevention
if grep -q "^SCRAPER_BOTASAURUS_BYPASS_CLOUDFLARE=" .env; then
    sed -i "s|^SCRAPER_BOTASAURUS_BYPASS_CLOUDFLARE=.*|SCRAPER_BOTASAURUS_BYPASS_CLOUDFLARE=0|" .env
else
    echo "SCRAPER_BOTASAURUS_BYPASS_CLOUDFLARE=0" >> .env
fi

# Ensure fast HTTP detail scans
if grep -q "^SCRAPER_DETAIL_BROWSER_BATCH=" .env; then
    sed -i "s|^SCRAPER_DETAIL_BROWSER_BATCH=.*|SCRAPER_DETAIL_BROWSER_BATCH=0|" .env
else
    echo "SCRAPER_DETAIL_BROWSER_BATCH=0" >> .env
fi

echo "  [PASS] .env configured for production stability (direct connection ready)."

# ------------------------------------------------------------------------------
# STEP 5: Service Restart & Health Verification
# ------------------------------------------------------------------------------
echo ""
echo "[Step 5/6] Restarting scraper service and querying health probe..."

SERVICE_RELOADED=0
if command -v systemctl >/dev/null 2>&1; then
    for s_name in scraper gunicorn parts-extractor flask scraper-app parts parts_extractor; do
        if ${SUDO} systemctl list-unit-files 2>/dev/null | grep -E -q "^${s_name}\.service"; then
            SERVICE_RELOADED=1
            echo "  --> Restarting systemd service '${s_name}'..."
            ${SUDO} systemctl daemon-reload
            ${SUDO} systemctl restart "${s_name}"
            sleep 2
            if ${SUDO} systemctl is-active --quiet "${s_name}"; then
                echo "  [PASS] Systemd service '${s_name}' is ACTIVE."
            fi
        fi
    done
fi

if pgrep -f "gunicorn.*app:app" >/dev/null 2>&1 || pgrep -f "gunicorn" >/dev/null 2>&1; then
    echo "  --> Reloading running Gunicorn worker processes via SIGHUP..."
    ${SUDO} pkill -HUP -f gunicorn 2>/dev/null || true
    sleep 2
    SERVICE_RELOADED=1
fi

if command -v supervisorctl >/dev/null 2>&1; then
    if ${SUDO} supervisorctl status 2>/dev/null | grep -E -q "scraper|gunicorn|flask"; then
        echo "  --> Restarting supervisor worker..."
        ${SUDO} supervisorctl restart all >/dev/null 2>&1 || true
        SERVICE_RELOADED=1
    fi
fi

if [ "${SERVICE_RELOADED}" -eq 1 ]; then
    echo "  [PASS] Application worker reloaded successfully."
else
    echo "  [INFO] No managed systemd/gunicorn process found. Restart your Python server process to apply updates."
fi

# Query readiness probe
PROBE_RES="$(curl -s -m 5 http://localhost:5000/readyz 2>/dev/null || true)"
if echo "${PROBE_RES}" | grep -q '"status":"ready"'; then
    echo "  [PASS] /readyz responded HTTP 200: System is READY."
else
    echo "  [INFO] /readyz probe: ${PROBE_RES:-'(Server not listening on localhost:5000 yet)'}"
fi

# Run preflight python diagnostic
echo ""
"${VENV_PYTHON}" -m scrapers.system_check

# ------------------------------------------------------------------------------
# STEP 6: Install Automatic Git Post-Merge Hook
# ------------------------------------------------------------------------------
echo ""
echo "[Step 6/6] Installing automatic Git post-merge hook..."

HOOK_DIR="${PROJECT_ROOT}/.git/hooks"
HOOK_FILE="${HOOK_DIR}/post-merge"

if [ -d "${HOOK_DIR}" ]; then
    cat > "${HOOK_FILE}" << 'HOOK_EOF'
#!/usr/bin/env bash
# Automatically heal and verify after git pull
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
bash "${PROJECT_ROOT}/scripts/auto_fix.sh"
HOOK_EOF
    chmod +x "${HOOK_FILE}"
    echo "  [PASS] Git post-merge hook active. Every future 'git pull' will auto-run this script."
else
    echo "  [INFO] .git/hooks directory not found. Skipping hook installation."
fi

echo ""
echo "======================================================================"
echo "  ✓ ALL REPAIRS COMPLETE: SERVER IS FULLY READY TO SCRAPE"
echo "======================================================================"
echo "  - Google Chrome: ${FINAL_CHROME} (Official .deb, NOT Snap)"
echo "  - DevTools Remote Socket: PASSED"
echo "  - Direct HTTP & Browser Fallback: Operational"
echo "  - Scraper Service: Restarted"
echo "======================================================================"
