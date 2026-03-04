@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ==================================================
echo           社媒内容提取系统 - 环境一键安装
echo ==================================================

REM 1. 检查是不是已经有 venv 了
if exist "venv\" goto :venv_exists

echo 正在为您创建独立的隔离环境...
python -m venv venv
if errorlevel 1 (
    echo 创建失败！请检查您的系统是否已安装 Python3。
    pause
    exit /b 1
)
goto :install_deps

:venv_exists
echo 发现已存在的虚拟环境。

:install_deps
REM 2. 激活环境并安装依赖
echo 正在为您安装系统所需的全部依赖库，这可能需要几分钟时间，请喝杯水稍候...
call venv\Scripts\activate.bat

REM 升级 pip 到最新版
python -m pip install -i https://pypi.tuna.tsinghua.edu.cn/simple --upgrade pip

REM 根据根目录的总清单批量安装
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements_all.txt

echo ==================================================
echo 环境安装完成！以后您无需再运行此脚本。
echo 请双击运行 "第2步_启动展示检索服务.bat" 来启动系统。
echo ==================================================

pause
