@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

set "APP_NAME=Parts Extractor"
set "VENV_DIR=.venv"
set "VENV_PY=%VENV_DIR%\Scripts\python.exe"
set "REQ_MARKER=%VENV_DIR%\.requirements_installed"
set "PORT_START=5000"
set "PORT_END=5050"

if not defined OPEN_BROWSER set "OPEN_BROWSER=1"
if not defined FLASK_DEBUG set "FLASK_DEBUG=0"

echo.
echo ================================================
echo    %APP_NAME% - Automated Startup
echo ================================================
echo.

echo [1/6] Checking Python runtime...
call :ensure_venv
if errorlevel 1 goto :startup_failed
call :show_python_version
if errorlevel 1 goto :startup_failed

echo [2/6] Checking Python dependencies...
call :ensure_dependencies
if errorlevel 1 goto :startup_failed

echo [3/6] Checking project directories...
call :ensure_directories
if errorlevel 1 goto :startup_failed

echo [4/6] Checking for Chrome/Chromium...
call :check_browser
if errorlevel 1 goto :startup_failed

echo [5/6] Resolving startup port...
call :ensure_port
if errorlevel 1 goto :startup_failed

echo [6/6] Starting %APP_NAME%...
echo.
echo Frontend: http://127.0.0.1:%PORT%
echo Network:  http://0.0.0.0:%PORT%
if /I "%OPEN_BROWSER%"=="1" (
    echo Browser: opening automatically...
    start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:%PORT%/'"
) else (
    echo Browser: auto-open disabled ^(OPEN_BROWSER=%OPEN_BROWSER%^)
)
echo Debug:   %FLASK_DEBUG%
echo.
echo Press Ctrl+C to stop the server
echo.

"%VENV_PY%" app.py
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    color 4c
    echo X %APP_NAME% exited with code %EXIT_CODE%.
) else (
    echo + %APP_NAME% stopped.
)

pause
exit /b %EXIT_CODE%

:startup_failed
echo.
pause
exit /b 1

:ensure_venv
if exist "%VENV_PY%" (
    echo + Using existing virtual environment
    goto :eof
)

set "BOOTSTRAP_CMD="
py -3 -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
if not errorlevel 1 set "BOOTSTRAP_CMD=py -3"

if not defined BOOTSTRAP_CMD (
    python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
    if not errorlevel 1 set "BOOTSTRAP_CMD=python"
)

if not defined BOOTSTRAP_CMD (
    py -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 12) else 1)" >nul 2>nul
    if not errorlevel 1 set "BOOTSTRAP_CMD=py"
)

if not defined BOOTSTRAP_CMD (
    color 4c
    echo X Python 3.12 or newer was not found.
    echo   Install Python 3.12+ and make sure `python` or `py` is available.
    exit /b 1
)

echo   - Creating virtual environment...
%BOOTSTRAP_CMD% -m venv "%VENV_DIR%"
if errorlevel 1 (
    color 4c
    echo X Failed to create virtual environment.
    exit /b 1
)

if not exist "%VENV_PY%" (
    color 4c
    echo X Virtual environment was created, but `%VENV_PY%` was not found.
    exit /b 1
)

echo + Virtual environment created
goto :eof

:show_python_version
set "PYTHON_VERSION="
for /f "tokens=2" %%i in ('"%VENV_PY%" --version 2^>^&1') do set "PYTHON_VERSION=%%i"
if defined PYTHON_VERSION (
    echo + Python ready ^(v%PYTHON_VERSION%^)
) else (
    echo + Python ready
)
goto :eof

:ensure_dependencies
set "INSTALL_DEPS=1"

if exist "%REQ_MARKER%" (
    powershell -NoProfile -ExecutionPolicy Bypass -Command "$req=(Get-Item 'requirements.txt').LastWriteTimeUtc; $mark=(Get-Item '.venv/.requirements_installed').LastWriteTimeUtc; if ($mark -ge $req) { exit 0 } else { exit 1 }" >nul 2>nul
    if not errorlevel 1 set "INSTALL_DEPS=0"
)

if "%INSTALL_DEPS%"=="0" (
    echo + Dependencies are up to date
    goto :eof
)

echo   - Bootstrapping pip...
"%VENV_PY%" -m ensurepip --upgrade >nul 2>nul

echo   - Installing package requirements...
"%VENV_PY%" -m pip install --upgrade pip
if errorlevel 1 (
    color 4c
    echo X Failed to upgrade pip.
    exit /b 1
)

"%VENV_PY%" -m pip install -r requirements.txt
if errorlevel 1 (
    color 4c
    echo X Failed to install Python requirements.
    exit /b 1
)

type nul > "%REQ_MARKER%"
echo + Dependencies installed
goto :eof

:ensure_directories
if not exist "data" mkdir data >nul 2>nul
if not exist "data\site_dbs" mkdir "data\site_dbs" >nul 2>nul
echo + Data directories ready
goto :eof

:check_browser
set "CHROME_FOUND=0"

if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set "CHROME_FOUND=1"
if exist "%ProgramFiles%\Microsoft\Edge\Application\msedge.exe" set "CHROME_FOUND=1"
if exist "%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe" set "CHROME_FOUND=1"

if "%CHROME_FOUND%"=="1" (
    echo + Chrome-compatible browser found
) else (
    echo - Chrome-compatible browser not found ^(recommended for Selenium scraping^)
)
goto :eof

:ensure_port
if defined PORT (
    echo + Using preset PORT=%PORT%
    goto :eof
)

for /f "usebackq delims=" %%i in (`powershell -NoProfile -ExecutionPolicy Bypass -Command "$port=$null; foreach($p in %PORT_START%..%PORT_END%){ try { $listener=[System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any,$p); $listener.Start(); $listener.Stop(); $port=$p; break } catch {} }; if ($port) { $port } else { exit 1 }"`) do set "PORT=%%i"

if not defined PORT (
    color 4c
    echo X No free port found in range %PORT_START%-%PORT_END%.
    echo   Set the PORT environment variable to a free port and run again.
    exit /b 1
)

echo + Using PORT=%PORT%
goto :eof
