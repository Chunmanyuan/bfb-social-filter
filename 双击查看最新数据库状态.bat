@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

set DB_PATH=MediaCrawler\data\media_items.db

if not exist "%DB_PATH%" (
    echo Database file not found: %DB_PATH%
    echo Please make sure crawler has run at least once.
    echo --------------------------------------------------
    pause
    exit /b 1
)

if not exist "venv\" (
    echo venv not found. Please run Step 0 installer BAT first.
    pause
    exit /b 1
)

set PYTHON_BIN=venv\Scripts\python.exe

echo ==================================================
echo Database viewer (latest 10 rows)
echo ==================================================
echo.

"%PYTHON_BIN%" MediaCrawler\show_latest_db_status.py

echo.
echo ==================================================
pause
