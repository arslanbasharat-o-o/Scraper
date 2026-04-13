#!/bin/bash

# ==============================================================================
# XCellParts Scraper - Server Startup Script with Requirements Check
# ==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

APP_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
export NODE_PATH="$APP_DIR/node_modules${NODE_PATH:+:$NODE_PATH}"

# Fast scrape defaults (can be overridden by pre-set env vars)
: "${IMAGE_DOWNLOAD_CONCURRENCY:=6}"
: "${PRODUCT_DELAY_MIN_MS:=40}"
: "${PRODUCT_DELAY_MAX_MS:=120}"
: "${IMAGE_SELECTOR_TIMEOUT_MS:=7000}"
: "${IMAGE_EXTRACT_RETRIES:=1}"
: "${IMAGE_EMPTY_RETRIES:=0}"
export IMAGE_DOWNLOAD_CONCURRENCY PRODUCT_DELAY_MIN_MS PRODUCT_DELAY_MAX_MS
export IMAGE_SELECTOR_TIMEOUT_MS IMAGE_EXTRACT_RETRIES IMAGE_EMPTY_RETRIES

echo -e "${BLUE}================================================${NC}"
echo -e "${BLUE}   XCellParts Scraper - Requirements Check${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# 1. Check Node.js
echo -e "${YELLOW}[1/5]${NC} Checking Node.js..."
if ! command -v node &> /dev/null; then
    echo -e "${RED}✗ Node.js not found!${NC}"
    echo "  Please install Node.js from https://nodejs.org/"
    exit 1
fi
NODE_VERSION=$(node -v)
echo -e "${GREEN}✓ Node.js installed${NC} ($NODE_VERSION)"

# 2. Check npm
echo -e "${YELLOW}[2/5]${NC} Checking npm..."
if ! command -v npm &> /dev/null; then
    echo -e "${RED}✗ npm not found!${NC}"
    echo "  npm should be bundled with Node.js. Please reinstall Node.js."
    exit 1
fi
NPM_VERSION=$(npm -v)
echo -e "${GREEN}✓ npm installed${NC} (v$NPM_VERSION)"

# 3. Check and install Node packages
echo -e "${YELLOW}[3/5]${NC} Checking Node.js dependencies..."
cd "$APP_DIR"

if [ ! -d "node_modules" ]; then
    echo "  → Installing npm packages..."
    npm install
    echo -e "${GREEN}✓ npm packages installed${NC}"
else
    # Check if all required packages are installed
    REQUIRED_PACKAGES=("express" "selenium-webdriver" "sharp" "webdriver-manager" "chromedriver")
    MISSING_PACKAGES=()
    
    for package in "${REQUIRED_PACKAGES[@]}"; do
        if [ ! -d "node_modules/$package" ]; then
            MISSING_PACKAGES+=("$package")
        fi
    done
    
    if [ ${#MISSING_PACKAGES[@]} -gt 0 ]; then
        echo "  → Missing packages: ${MISSING_PACKAGES[*]}"
        echo "  → Installing npm packages..."
        npm install
        echo -e "${GREEN}✓ npm packages installed${NC}"
    else
        echo -e "${GREEN}✓ All npm packages found${NC}"
    fi
fi

# 4. Check for Chrome/Chromium (optional but recommended)
echo -e "${YELLOW}[4/5]${NC} Checking for Chrome/Chromium browser..."
CHROME_FOUND=false

if command -v google-chrome &> /dev/null; then
    CHROME_VERSION=$(google-chrome --version)
    echo -e "${GREEN}✓ Google Chrome found${NC} ($CHROME_VERSION)"
    CHROME_FOUND=true
elif command -v chromium &> /dev/null; then
    CHROMIUM_VERSION=$(chromium --version)
    echo -e "${GREEN}✓ Chromium found${NC} ($CHROMIUM_VERSION)"
    CHROME_FOUND=true
elif command -v chromium-browser &> /dev/null; then
    CHROMIUM_VERSION=$(chromium-browser --version)
    echo -e "${GREEN}✓ Chromium Browser found${NC} ($CHROMIUM_VERSION)"
    CHROME_FOUND=true
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # Check for Chrome on macOS
    if [ -d "/Applications/Google Chrome.app" ]; then
        echo -e "${GREEN}✓ Google Chrome found${NC} (macOS)"
        CHROME_FOUND=true
    elif [ -d "/Applications/Chromium.app" ]; then
        echo -e "${GREEN}✓ Chromium found${NC} (macOS)"
        CHROME_FOUND=true
    fi
fi

if [ "$CHROME_FOUND" = false ]; then
    echo -e "${YELLOW}⚠ Chrome/Chromium not found${NC}"
    echo "  WebDriver-compatible browser required for scraping"
    echo "  Install Chrome: https://www.google.com/chrome/"
    echo "  Or Chromium: https://www.chromium.org/getting-involved/download-chromium"
fi

# 5. Check downloads directory
echo -e "${YELLOW}[5/5]${NC} Checking project directories..."
if [ ! -d "$APP_DIR/downloads" ]; then
    echo "  → Creating downloads directory..."
    mkdir -p "$APP_DIR/downloads"
    echo -e "${GREEN}✓ downloads directory created${NC}"
else
    echo -e "${GREEN}✓ downloads directory exists${NC}"
fi

if [ ! -d "$APP_DIR/frontend" ]; then
    echo -e "${RED}✗ frontend directory not found!${NC}"
    echo "  Expected: $APP_DIR/frontend"
    exit 1
fi
echo -e "${GREEN}✓ frontend directory found${NC}"

# Summary
echo ""
echo -e "${BLUE}================================================${NC}"
echo -e "${GREEN}✓ All requirements satisfied!${NC}"
echo -e "${BLUE}================================================${NC}"
echo ""

# Start the server
echo -e "${YELLOW}Starting server on port 3001...${NC}"
echo "  Frontend: http://localhost:3001"
echo "  API: http://localhost:3001/api"
echo "  Speed mode defaults enabled"
echo ""
echo -e "${YELLOW}Press Ctrl+C to stop the server${NC}"
echo ""

node server.js
