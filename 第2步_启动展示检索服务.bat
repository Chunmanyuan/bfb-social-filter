@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ==================================================
echo   第2步 - 启动展示检索服务
echo ==================================================
echo.

if not exist "venv\" (
    echo 未检测到虚拟环境，请先运行【第0步_首次运行前安装系统所需依赖环境.bat】
    pause
    exit /b 1
)

set PYTHON_BIN=venv\Scripts\python.exe
set SERVICE_URL=http://127.0.0.1:8090/

echo 正在启动展示检索服务...
echo 浏览器将自动打开：%SERVICE_URL%
echo.
echo 如果尚未登录，请先运行【第1步_登录小红书和B站账号.bat】
echo.

start "" cmd /c "timeout /t 5 /nobreak >nul & start %SERVICE_URL%"
"%PYTHON_BIN%" DashboardQuerying\app.py
chcp 65001 >nul 2>&1

echo ==================================================
echo   服务已停止。
echo ==================================================
pause
