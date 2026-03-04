@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ==================================================
echo       展示检索服务 - 启动中 (DashboardQuerying)
echo ==================================================

if not exist "venv\" (
    echo 错误：找不到 venv 虚拟环境！
    echo 请先运行 "第1步_首次运行前安装系统所需依赖环境.bat"
    pause
    exit /b 1
)

set PYTHON_BIN=venv\Scripts\python.exe
set SERVICE_URL=http://127.0.0.1:8090/

echo 正在启动 DashboardQuerying 服务...
echo 启动后将自动打开浏览器访问: %SERVICE_URL%
echo.

REM 延迟几秒后打开浏览器
start "" cmd /c "timeout /t 5 /nobreak >nul & start %SERVICE_URL%"

REM 启动服务（前台运行，关闭窗口即停止服务）
"%PYTHON_BIN%" DashboardQuerying\app.py

echo ==================================================
echo 服务已停止。
echo ==================================================
pause
