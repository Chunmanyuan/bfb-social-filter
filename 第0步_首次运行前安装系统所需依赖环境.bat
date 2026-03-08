@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ==================================================
echo   社交媒体爬虫 - 第0步 环境安装
echo ==================================================
echo.

set CHECK_PASS=1

echo --------------------------------------------------
echo   [检测] 正在检查 Python 是否已安装...
echo --------------------------------------------------
python --version >nul 2>&1
chcp 65001 >nul 2>&1
if errorlevel 1 (
    echo   [X] 未检测到 Python！
    echo       请先安装 Python 3.12 或 3.13 版本。
    echo       下载地址: https://www.python.org/downloads/
    set CHECK_PASS=0
    goto :check_chrome
)

for /f "tokens=2" %%v in ('python --version 2^>^&1') do set PY_FULL_VER=%%v
chcp 65001 >nul 2>&1
for /f "tokens=1,2 delims=." %%a in ("%PY_FULL_VER%") do (
    set PY_MAJOR=%%a
    set PY_MINOR=%%b
)

if not "%PY_MAJOR%"=="3" (
    echo   [X] Python 版本不符合要求！当前版本: %PY_FULL_VER%
    echo       需要 Python 3.12.x 或 3.13.x，请安装对应版本。
    echo       下载地址: https://www.python.org/downloads/
    set CHECK_PASS=0
    goto :check_chrome
)
if "%PY_MINOR%"=="12" goto :python_ok
if "%PY_MINOR%"=="13" goto :python_ok

echo   [X] Python 版本不符合要求！当前版本: %PY_FULL_VER%
echo       需要 Python 3.12.x 或 3.13.x，请安装对应版本。
echo       下载地址: https://www.python.org/downloads/
set CHECK_PASS=0
goto :check_chrome

:python_ok
echo   [OK] Python 版本检测通过: %PY_FULL_VER%

:check_chrome
echo.
echo --------------------------------------------------
echo   [检测] 正在检查 Chrome 浏览器是否已安装...
echo --------------------------------------------------
set CHROME_FOUND=0
if exist "%ProgramFiles%\Google\Chrome\Application\chrome.exe" set CHROME_FOUND=1
if exist "%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe" set CHROME_FOUND=1
if exist "%LocalAppData%\Google\Chrome\Application\chrome.exe" set CHROME_FOUND=1

if "%CHROME_FOUND%"=="0" (
    echo   [X] 未检测到 Chrome 浏览器！
    echo       请先安装 Google Chrome 浏览器。
    echo       下载地址: https://www.google.com/chrome/
    set CHECK_PASS=0
    goto :check_result
)
echo   [OK] Chrome 浏览器检测通过。

:check_result
echo.
if "%CHECK_PASS%"=="0" (
    echo ==================================================
    echo   环境检查未通过，请根据以上提示安装所需软件后重新运行本脚本。
    echo ==================================================
    pause
    exit /b 1
)

echo ==================================================
echo   环境检查全部通过，开始安装依赖...
echo ==================================================
echo.

if exist "venv\" goto :venv_exists

echo 正在创建虚拟环境...
python -m venv venv
chcp 65001 >nul 2>&1
if errorlevel 1 (
    echo 创建虚拟环境失败。请确保 Python 已正确安装后重试。
    pause
    exit /b 1
)
goto :install_deps

:venv_exists
echo 检测到已有虚拟环境。

:install_deps
echo 正在安装依赖，这可能需要几分钟，请耐心等待...
call venv\Scripts\activate.bat
chcp 65001 >nul 2>&1

python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip
chcp 65001 >nul 2>&1
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements_all.txt
chcp 65001 >nul 2>&1

echo.
echo ==================================================
echo   第0步 完成！
echo   接下来请运行【第1步_登录小红书和B站账号.bat】
echo   然后运行【第2步_启动展示检索服务.bat】
echo ==================================================
pause
