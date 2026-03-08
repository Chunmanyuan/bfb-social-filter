@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set "PROJECT_ROOT=%~dp0.."
set "PYTHON_BIN=%PROJECT_ROOT%\venv\Scripts\python.exe"
set "PYINSTALLER_BIN=%PROJECT_ROOT%\venv\Scripts\pyinstaller.exe"
set "ENTRY_SCRIPT=%~dp0dashboard_tray_launcher.py"
set "ICON_FILE=%~dp0heart_icon.ico"
set "DIST_DIR=%PROJECT_ROOT%\Launcher\dist"
set "BUILD_DIR=%PROJECT_ROOT%\Launcher\build\dashboard_launcher"
set "SPEC_DIR=%PROJECT_ROOT%\Launcher"

echo ==================================================
echo Build DashboardLauncher.exe
echo ==================================================

if not exist "%PYTHON_BIN%" (
    echo venv python not found: %PYTHON_BIN%
    echo Please run step-0 environment setup first.
    pause
    exit /b 1
)

echo Installing build dependencies...
"%PYTHON_BIN%" -m pip install -U pystray pyinstaller
if errorlevel 1 (
    echo Failed to install pystray/pyinstaller.
    pause
    exit /b 1
)

if exist "%DIST_DIR%\DashboardLauncher.exe" del /f /q "%DIST_DIR%\DashboardLauncher.exe" >nul 2>&1

echo Packaging executable...
"%PYINSTALLER_BIN%" ^
  --noconfirm ^
  --clean ^
  --onefile ^
  --windowed ^
  --name DashboardLauncher ^
  --icon "%ICON_FILE%" ^
  --distpath "%DIST_DIR%" ^
  --workpath "%BUILD_DIR%" ^
  --specpath "%SPEC_DIR%" ^
  "%ENTRY_SCRIPT%"

if errorlevel 1 (
    echo Build failed.
    pause
    exit /b 1
)

echo Cleaning temporary build files...
if exist "%BUILD_DIR%" rd /s /q "%BUILD_DIR%"
if exist "%SPEC_DIR%\DashboardLauncher.spec" del /f /q "%SPEC_DIR%\DashboardLauncher.spec"
if exist "%SPEC_DIR%\__pycache__" rd /s /q "%SPEC_DIR%\__pycache__"

echo.
echo Build complete:
echo %DIST_DIR%\DashboardLauncher.exe
echo.
pause
