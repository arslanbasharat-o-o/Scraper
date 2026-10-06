@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0.."

set "APP_NAME=Parts Extractor Windows Laptop Setup"
set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "ENV_TEMPLATE=.env.windows-laptop.example"
set "REQ_MARKER=%VENV_DIR%\.requirements_installed"

echo.
echo ================================================================
echo   %APP_NAME%
echo ================================================================
echo.

echo [1/7] Checking Python 3.10-3.12...
call :find_python
if errorlevel 1 goto :failed

echo [2/7] Preparing virtual environment...
if not exist "%VENV_PY%" (
    %BOOTSTRAP_PY% -m venv "%VENV_DIR%"
    if errorlevel 1 (
        echo X Could not create the virtual environment.
        goto :failed
    )
)
if not exist "%VENV_PY%" (
    echo X Virtual environment Python was not created: %VENV_PY%
    goto :failed
)
"%VENV_PY%" -c "import sys; raise SystemExit(0 if 10 <= sys.version_info.minor <= 12 else 1)"
if errorlevel 1 (
    echo X The existing .venv is not using Python 3.10-3.12.
    echo   Delete .venv manually, then run this setup command again.
    goto :failed
)
echo + Virtual environment ready

echo [3/7] Installing Python dependencies...
"%VENV_PY%" -m ensurepip --upgrade >nul 2>nul
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 goto :dependency_failed
"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 goto :dependency_failed
type nul > "%REQ_MARKER%"
echo + Python dependencies installed

echo [4/7] Creating Windows 10 GB environment configuration...
if not exist ".env" (
    copy /Y "%ENV_TEMPLATE%" ".env" >nul
    if errorlevel 1 (
        echo X Could not create .env from %ENV_TEMPLATE%.
        goto :failed
    )
    "%VENV_PY%" -c "from pathlib import Path; import re,secrets; p=Path('.env'); s=p.read_text(encoding='utf-8'); s,n=re.subn(r'(?m)^SECRET_KEY=.*$', 'SECRET_KEY=' + secrets.token_hex(32), s, count=1); raise SystemExit('SECRET_KEY setting not found' if n != 1 else (p.write_text(s,encoding='utf-8') and 0))"
    if errorlevel 1 (
        echo X Could not generate SECRET_KEY in .env.
        goto :failed
    )
    echo + Created .env with a new SECRET_KEY
) else (
    echo + Existing .env preserved
)

if not exist "data" mkdir data >nul 2>nul
if not exist "data\site_dbs" mkdir "data\site_dbs" >nul 2>nul
echo + Data directories ready

echo [5/7] Checking Chrome-compatible browser...
set "CHROME_FOUND=0"
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "CHROME_FOUND=1"
if "%CHROME_FOUND%"=="0" (
    where winget >nul 2>nul
    if not errorlevel 1 (
        echo   - Chrome not found; installing Google Chrome with winget...
        winget install --id Google.Chrome -e --accept-source-agreements --accept-package-agreements
        if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
        if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
    )
)
if "%CHROME_FOUND%"=="0" (
    echo - Chrome/Edge was not found. Botasaurus may download its own browser runtime.
    echo   Install Google Chrome before scraping if browser fallback reports an error.
) else (
    echo + Chrome-compatible browser found
)

echo [6/7] Running project readiness checks...
"%VENV_PY%" -c "from dotenv import dotenv_values; import sys; v=dotenv_values('.env').get('SECRET_KEY'); raise SystemExit(0 if v and len(v) >= 32 and v not in ('change-me','dev-secret','your-secret-key','dev-insecure-change-me') else 1)"
if errorlevel 1 (
    echo X .env does not contain a usable SECRET_KEY.
    goto :failed
)
"%VENV_PY%" -c "from scrapers.system_check import run_preflight_check; import sys; raise SystemExit(0 if run_preflight_check(fail_fast=False).get('overall_ok') else 1)"
if errorlevel 1 (
    echo X Readiness checks failed.
    goto :failed
)
"%VENV_PY%" -m py_compile app.py database.py
if errorlevel 1 (
    echo X Python source compilation check failed.
    goto :failed
)
echo + Readiness and syntax checks passed

echo [7/7] Verifying application import and health helpers...
"%VENV_PY%" -c "import app; print('Application import: OK')"
if errorlevel 1 goto :failed

echo.
echo ================================================================
echo   + SETUP COMPLETE - LAPTOP READY
echo ================================================================
echo.
echo Start the application with:
echo   start.bat
echo.
echo The setup does not start scraping automatically.
echo.
exit /b 0

:find_python
set "BOOTSTRAP_PY="
py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
if not errorlevel 1 set "BOOTSTRAP_PY=py -3.12"
if not defined BOOTSTRAP_PY (
    py -3.11 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 11) else 1)" >nul 2>nul
    if not errorlevel 1 set "BOOTSTRAP_PY=py -3.11"
)
if not defined BOOTSTRAP_PY (
    py -3.10 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 10) else 1)" >nul 2>nul
    if not errorlevel 1 set "BOOTSTRAP_PY=py -3.10"
)
if not defined BOOTSTRAP_PY (
    python -c "import sys; raise SystemExit(0 if sys.version_info[:2] in ((3, 10), (3, 11), (3, 12)) else 1)" >nul 2>nul
    if not errorlevel 1 set "BOOTSTRAP_PY=python"
)
if not defined BOOTSTRAP_PY (
    where winget >nul 2>nul
    if not errorlevel 1 (
        echo   - Python not found; installing Python 3.12 with winget...
        winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
        py -3.12 -c "import sys; raise SystemExit(0 if sys.version_info[:2] == (3, 12) else 1)" >nul 2>nul
        if not errorlevel 1 set "BOOTSTRAP_PY=py -3.12"
    )
)
if not defined BOOTSTRAP_PY (
    echo X Python 3.10, 3.11, or 3.12 was not found.
    echo   Install Python 3.12 from https://www.python.org/downloads/windows/
    exit /b 1
)
for /f "tokens=2" %%V in ('%BOOTSTRAP_PY% --version 2^>^&1') do echo + Found Python %%V
goto :eof

:dependency_failed
echo X Dependency installation failed. Check the network connection and rerun setup.
goto :failed

:failed
echo.
echo ================================================================
echo   X SETUP FAILED - SEE THE MESSAGE ABOVE
echo ================================================================
exit /b 1
