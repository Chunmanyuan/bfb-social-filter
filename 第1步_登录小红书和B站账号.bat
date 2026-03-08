@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ==================================================
echo   第1步 - 登录小红书和B站账号
echo ==================================================
echo.

if not exist "venv\" (
    echo 未检测到虚拟环境，请先运行【第0步_首次运行前安装系统所需依赖环境.bat】
    pause
    exit /b 1
)

set PYTHON_BIN=venv\Scripts\python.exe

echo 此步骤将打开 2 个 Chrome 窗口：
echo   1) 小红书登录窗口（CDP 配置文件目录）
echo   2) B站登录窗口（标准配置文件目录）
echo.
echo 请在两个窗口中分别登录，登录完成后关闭窗口。
echo.

"%PYTHON_BIN%" MediaCrawler\login_browser_helper.py
chcp 65001 >nul 2>&1

if errorlevel 1 (
    echo.
    echo 打开登录窗口失败，请检查 Chrome 是否已正确安装。
    pause
    exit /b 1
)

echo.
echo ==================================================
echo   登录窗口已打开。
echo   登录完成后，请运行【第2步_启动展示检索服务.bat】
echo ==================================================
pause
