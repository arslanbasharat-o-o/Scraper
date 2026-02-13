@echo off
REM ==============================================================================
REM XCellParts Scraper - Server Startup Script with Requirements Check (Windows)
REM ==============================================================================

setlocal enabledelayedexpansion
set NODE_PATH=%~dp0node_modules;%NODE_PATH%

REM Fast scrape defaults (can be overridden by pre-set env vars)
if not defined IMAGE_DOWNLOAD_CONCURRENCY set IMAGE_DOWNLOAD_CONCURRENCY=6
if not defined PRODUCT_DELAY_MIN_MS set PRODUCT_DELAY_MIN_MS=40
if not defined PRODUCT_DELAY_MAX_MS set PRODUCT_DELAY_MAX_MS=120
if not defined IMAGE_SELECTOR_TIMEOUT_MS set IMAGE_SELECTOR_TIMEOUT_MS=7000
if not defined IMAGE_EXTRACT_RETRIES set IMAGE_EXTRACT_RETRIES=1
if not defined IMAGE_EMPTY_RETRIES set IMAGE_EMPTY_RETRIES=0

REM Colors are limited on Windows, so we'll use simpler output
echo.
echo ================================================
echo    XCellParts Scraper - Requirements Check
echo ================================================
echo.

REM 1. Check Node.js
echo [1/5] Checking Node.js...
where node >nul 2>nul
if %errorlevel% neq 0 (
    color 4c
    echo X Node.js not found!
    echo   Please install Node.js from https://nodejs.org/
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('node -v') do set NODE_VERSION=%%i
echo + Node.js installed (%NODE_VERSION%)

REM 2. Check npm
echo [2/5] Checking npm...
where npm >nul 2>nul
if %errorlevel% neq 0 (
    color 4c
    echo X npm not found!
    echo   npm should be bundled with Node.js. Please reinstall Node.js.
    pause
    exit /b 1
)
for /f "tokens=*" %%i in ('npm -v') do set NPM_VERSION=%%i
echo + npm installed (v%NPM_VERSION%)

REM 3. Check and install Node packages
echo [3/5] Checking Node.js dependencies...
cd /d "%~dp0"

if not exist "node_modules" (
    echo   - Installing npm packages...
    call npm install
    echo + npm packages installed
) else (
    REM Check if required packages exist
    set MISSING=0
    for %%P in (express selenium-webdriver sharp webdriver-manager chromedriver) do (
        if not exist "node_modules\%%P" (
            set MISSING=1
        )
    )
    
    if !MISSING! equ 1 (
        echo   - Missing packages found
        echo   - Installing npm packages...
        call npm install
        echo + npm packages installed
    ) else (
        echo + All npm packages found
    )
)

REM 4. Check for Chrome (optional)
echo [4/5] Checking for Chrome/Chromium browser...
set CHROME_FOUND=0

where chrome >nul 2>nul
if %errorlevel% equ 0 (
    echo + Google Chrome found
    set CHROME_FOUND=1
)

if !CHROME_FOUND! equ 0 (
    if exist "C:\Program Files\Google\Chrome\Application\chrome.exe" (
        echo + Google Chrome found
        set CHROME_FOUND=1
    )
)

if !CHROME_FOUND! equ 0 (
    if exist "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe" (
        echo + Google Chrome found
        set CHROME_FOUND=1
    )
)

if !CHROME_FOUND! equ 0 (
    echo - Chrome/Chromium not found (optional but recommended)
    echo   WebDriver needs a Chrome-compatible browser for scraping
)

REM 5. Check directories
echo [5/5] Checking project directories...

if not exist "downloads\" (
    echo   - Creating downloads directory...
    mkdir downloads
    echo + downloads directory created
) else (
    echo + downloads directory exists
)

if not exist "frontend\" (
    color 4c
    echo X frontend directory not found!
    pause
    exit /b 1
)
echo + frontend directory found

REM Summary
echo.
echo ================================================
echo + All requirements satisfied!
echo ================================================
echo.

REM Start the server
echo Starting server on port 3001...
echo   Frontend: http://localhost:3001
echo   API: http://localhost:3001/api
echo   Speed mode defaults enabled
echo.
echo Press Ctrl+C to stop the server
echo.

node server.js

pause
