#!/usr/bin/env bash
# ==============================================================================
# Production Server Setup & Chrome Verification Script
# For Ubuntu/Debian and Linux VPS (e.g. Hostinger 40GB)
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "${PROJECT_ROOT}"

echo "================================================================="
echo "  Scraper Production Server Setup & Environment Initializer"
echo "================================================================="

OS_TYPE="$(uname -s)"
ARCH_TYPE="$(uname -m)"

# ------------------------------------------------------------------------------
# 1. System Browser Verification & Automatic Chrome Installation
# ------------------------------------------------------------------------------
echo ""
echo "[Step 1/5] Checking Google Chrome installation..."

CHROME_BIN=""
if [ -f "/opt/google/chrome/google-chrome" ]; then
    CHROME_BIN="/opt/google/chrome/google-chrome"
elif command -v google-chrome-stable >/dev/null 2>&1; then
    CHROME_BIN="$(command -v google-chrome-stable)"
elif command -v google-chrome >/dev/null 2>&1; then
    CHROME_BIN="$(command -v google-chrome)"
elif [ -f "/usr/bin/google-chrome" ]; then
    CHROME_BIN="/usr/bin/google-chrome"
elif [ -f "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]; then
    CHROME_BIN="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
fi

# Detect and reject Snap Chromium or symlinks pointing to snap
CHROME_IS_SNAP=0
if [ -n "${CHROME_BIN}" ]; then
    RESOLVED_TARGET="$(readlink -f "${CHROME_BIN}" 2>/dev/null || echo "${CHROME_BIN}")"
    VERSION_OUTPUT="$("${CHROME_BIN}" --version 2>&1 || true)"
    if echo "${RESOLVED_TARGET}" | grep -q "snap" || echo "${VERSION_OUTPUT}" | grep -qi "snap"; then
        CHROME_IS_SNAP=1
        echo "  [WARNING] Detected Snap Chromium at ${CHROME_BIN} (resolves to ${RESOLVED_TARGET})."
        echo "            Ubuntu Snap sandboxing blocks DevTools sockets used by Botasaurus."
        echo "            Proceeding to replace with official Google Chrome .deb package..."
    fi
fi

if [ -z "${CHROME_BIN}" ] || [ "${CHROME_IS_SNAP}" -eq 1 ] || [ ! -f "/opt/google/chrome/google-chrome" -a "${OS_TYPE}" = "Linux" ]; then
    if [ "${OS_TYPE}" = "Linux" ]; then
        if [ "${ARCH_TYPE}" != "x86_64" ]; then
            echo "  [ERROR] Google Chrome .deb requires x86_64 architecture (found: ${ARCH_TYPE})."
            echo "          Please install a compatible Chromium build manually."
            exit 1
        fi

        echo "  --> Official Google Chrome not found. Installing via apt / dpkg..."
        
        # Check root or sudo
        SUDO_CMD=""
        if [ "$(id -u)" -ne 0 ]; then
            if command -v sudo >/dev/null 2>&1; then
                SUDO_CMD="sudo"
            else
                echo "  [ERROR] Root or sudo access is required to install Google Chrome deb."
                echo "          Please run as root or install sudo."
                exit 1
            fi
        fi

        TEMP_DEB="/tmp/google-chrome-stable_current_amd64.deb"
        echo "  --> Downloading Google Chrome debian package..."
        ${SUDO_CMD} apt-get update -y
        ${SUDO_CMD} apt-get install -y wget curl ca-certificates gnupg libnss3 libatk1.0-0 libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 libgbm1 libasound2 libpangocairo-1.0-0

        wget -q -O "${TEMP_DEB}" https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
        
        echo "  --> Installing Google Chrome package..."
        ${SUDO_CMD} dpkg -i "${TEMP_DEB}" || ${SUDO_CMD} apt-get install -f -y
        rm -f "${TEMP_DEB}"

        CHROME_BIN="$(command -v google-chrome || echo '/usr/bin/google-chrome')"
    elif [ "${OS_TYPE}" = "Darwin" ]; then
        echo "  [ERROR] Google Chrome is missing on macOS. Please install Google Chrome in /Applications."
        exit 1
    fi
fi

if [ -n "${CHROME_BIN}" ] && [ -x "${CHROME_BIN}" ]; then
    CHROME_VER="$("${CHROME_BIN}" --version 2>&1 || true)"
    echo "  [PASS] Google Chrome verified: ${CHROME_VER}"
    echo "         Path: ${CHROME_BIN}"
else
    echo "  [ERROR] Failed to locate or install Google Chrome."
    exit 1
fi

# ------------------------------------------------------------------------------
# 2. Python Runtime Check
# ------------------------------------------------------------------------------
echo ""
echo "[Step 2/5] Checking Python runtime..."

PYTHON_BIN=""
if [ -f "${PROJECT_ROOT}/.venv/bin/python" ]; then
    VENV_PY_VER="$("${PROJECT_ROOT}/.venv/bin/python" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
    VENV_MAJOR="$(echo "${VENV_PY_VER}" | cut -d. -f1)"
    VENV_MINOR="$(echo "${VENV_PY_VER}" | cut -d. -f2)"
    if [ "${VENV_MAJOR}" = "3" ] && [ "${VENV_MINOR}" -ge 10 ] && [ "${VENV_MINOR}" -le 12 ]; then
        PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
        echo "  [PASS] Existing compatible virtualenv found: ${PYTHON_BIN} (v${VENV_PY_VER})"
    fi
fi

if [ -z "${PYTHON_BIN}" ]; then
    for py_candidate in python3.12 python3.11 python3.10 python3 python; do
        if command -v "${py_candidate}" >/dev/null 2>&1; then
            PY_VERSION="$(${py_candidate} -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || true)"
            PY_MAJOR="$(echo "${PY_VERSION}" | cut -d. -f1)"
            PY_MINOR="$(echo "${PY_VERSION}" | cut -d. -f2)"
            if [ "${PY_MAJOR}" = "3" ] && [ "${PY_MINOR}" -ge 10 ] && [ "${PY_MINOR}" -le 12 ]; then
                PYTHON_BIN="$(command -v "${py_candidate}")"
                echo "  [PASS] Compatible Python found: ${PYTHON_BIN} (v${PY_VERSION})"
                break
            elif [ "${PY_MAJOR}" = "3" ] && [ "${PY_MINOR}" -ge 13 ]; then
                echo "  [NOTICE] ${py_candidate} is v${PY_VERSION} (curl_cffi wheels require Python <= 3.12)."
            fi
        fi
    done
fi

if [ -z "${PYTHON_BIN}" ] && command -v uv >/dev/null 2>&1; then
    echo "  --> Found 'uv'. Provisioning Python 3.12 via uv..."
    uv venv --python 3.12 .venv
    PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
    echo "  [PASS] Provisioned Python via uv: ${PYTHON_BIN}"
fi

if [ -z "${PYTHON_BIN}" ]; then
    echo "  [ERROR] Python 3.10, 3.11, or 3.12 is required (Python 3.13+ lacks curl_cffi wheels)."
    echo "          Please install python3.12: sudo apt-get install -y python3.12 python3.12-venv python3-pip"
    exit 1
fi

# ------------------------------------------------------------------------------
# 3. Virtual Environment & Dependencies
# ------------------------------------------------------------------------------
echo ""
echo "[Step 3/5] Setting up Python virtual environment and dependencies..."

if [ ! -d ".venv" ]; then
    echo "  --> Creating .venv virtual environment..."
    "${PYTHON_BIN}" -m venv .venv
fi

VENV_PYTHON="${PROJECT_ROOT}/.venv/bin/python"

if [ ! -f "${VENV_PYTHON}" ]; then
    echo "  [ERROR] Virtual environment python binary not found at ${VENV_PYTHON}"
    exit 1
fi

if command -v uv >/dev/null 2>&1; then
    echo "  --> Installing / verifying requirements.txt with uv..."
    uv pip install -r requirements.txt --python "${VENV_PYTHON}" -q
else
    echo "  --> Upgrading pip..."
    "${VENV_PYTHON}" -m ensurepip --upgrade >/dev/null 2>&1 || true
    "${VENV_PYTHON}" -m pip install --upgrade pip -q
    echo "  --> Installing / verifying requirements.txt..."
    "${VENV_PYTHON}" -m pip install -r requirements.txt -q
fi
echo "  [PASS] Python dependencies installed successfully."

# ------------------------------------------------------------------------------
# 4. Environment Configuration (.env) Verification
# ------------------------------------------------------------------------------
echo ""
echo "[Step 4/5] Checking environment configuration (.env)..."

if [ ! -f ".env" ]; then
    echo "  --> .env file not found. Initializing from .env.server-40gb.example..."
    if [ -f ".env.server-40gb.example" ]; then
        cp .env.server-40gb.example .env
    elif [ -f ".env.example" ]; then
        cp .env.example .env
    fi

    # Generate cryptographically secure SECRET_KEY
    RANDOM_SECRET="$("${VENV_PYTHON}" -c "import secrets; print(secrets.token_hex(32))")"
    if [ "${OS_TYPE}" = "Darwin" ]; then
        sed -i '' "s/dev-insecure-change-me/${RANDOM_SECRET}/g" .env || true
    else
        sed -i "s/dev-insecure-change-me/${RANDOM_SECRET}/g" .env || true
    fi
    echo "  [PASS] Created .env with new random SECRET_KEY."
fi

# Ensure critical variables are configured in .env
if ! grep -q "^SCRAPER_CHROME_PATH=" .env; then
    echo "SCRAPER_CHROME_PATH=${CHROME_BIN}" >> .env
fi

if ! grep -q "^SCRAPER_PROXY_URL=" .env; then
    echo "# SCRAPER_PROXY_URL=http://user:password@gw.dataimpulse.com:823" >> .env
fi

# ------------------------------------------------------------------------------
# 5. Pre-flight Readiness Verification
# ------------------------------------------------------------------------------
echo ""
echo "[Step 5/5] Executing pre-flight health and readiness audit..."
"${VENV_PYTHON}" -m scrapers.system_check

echo ""
echo "================================================================="
echo "  ✓ SETUP COMPLETE! Server is ready to run."
echo "================================================================="
echo ""
echo "Quick Commands:"
echo "  - Start Server:      gunicorn -w 1 --threads 4 -b 0.0.0.0:5000 app:app"
echo "  - Check Readiness:   curl http://localhost:5000/readyz"
echo "  - Configure Proxy:   Edit SCRAPER_PROXY_URL in .env whenever proxy is purchased"
echo ""
